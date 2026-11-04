import json
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core import config as cfgmod
from ..core import secrets
from ..core.paths import CONFIG_PATH
from ..services import limits, mcp_client, providers, tools
from ..services.telegram_channel import channel as telegram

router = APIRouter()
STARTED = time.time()
VERSION = "0.3.0"
EDITABLE_FILES = {"SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"}


@router.get("/health")
def health():
    return {"ok": True, "version": VERSION, "pid": os.getpid(), "started": STARTED, "time": time.time()}


@router.get("/config")
def get_config():
    cfg = cfgmod.load()
    raw = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    return {"config": cfgmod.masked(cfg), "secrets": secrets.status(raw),
            "tools": [{"name": t.name, "description": t.description, "risk": t.risk} for t in tools.TOOLS.values()]}


@router.put("/config")
def put_config(body: dict):
    new = cfgmod.merge_secrets(cfgmod.Config.model_validate(body), cfgmod.load())
    if new.default_provider not in new.providers:
        raise HTTPException(400, "provider mặc định không tồn tại")
    new.fallback = [n for n in new.fallback if n in new.providers and n != new.default_provider]
    bad = [n for n in new.mcp_servers if not re.match(r"^[a-z0-9][a-z0-9_-]{0,30}$", n)]
    if bad:
        raise HTTPException(400, f"tên MCP server chỉ gồm a-z, 0-9, - và _: {bad[0]}")
    cfgmod.save(new)
    mcp_client.manager.apply(new.mcp_servers)
    telegram.apply(new.channels.telegram)
    return {"ok": True}


class TestBody(BaseModel):
    provider: cfgmod.ProviderCfg | None = None


@router.get("/providers/{name}/limits")
def provider_limits(name: str, refresh: bool = False):
    """Hạn mức phiên 5 giờ và theo tuần (nếu nhà cung cấp cho xem) cùng lượng Argus đã dùng."""
    cfg = cfgmod.load()
    if name not in cfg.providers:
        raise HTTPException(404, f"không có provider '{name}'")
    return limits.get(name, cfg.providers[name], refresh)


@router.post("/providers/{name}/test")
def test_provider(name: str, body: TestBody):
    cfg = cfgmod.load()
    pcfg = body.provider or cfg.providers.get(name)
    if not pcfg:
        raise HTTPException(404, "không có provider")
    if pcfg.api_key == cfgmod.MASK and name in cfg.providers:
        pcfg.api_key = cfg.providers[name].api_key
    t0 = time.time()
    try:
        reply = "".join(e["text"] for e in providers.make_provider(pcfg).stream([{"role": "user", "content": "Tra loi dung 1 tu: ok"}], []) if e["type"] == "delta")
        return {"ok": True, "reply": reply[:120], "latency_ms": int((time.time() - t0) * 1000)}
    except providers.ProviderError as e:
        return {"ok": False, "error": str(e)}


@router.post("/providers/models")
def provider_models(body: TestBody, all_models: bool = False):
    pcfg = body.provider
    if not pcfg:
        raise HTTPException(400, "thiếu cấu hình provider")
    saved = next((p for p in cfgmod.load().providers.values() if p.base_url == pcfg.base_url and p.type == pcfg.type), None)
    if pcfg.api_key == cfgmod.MASK:
        pcfg.api_key = saved.api_key if saved else ""
    try:
        return {"ok": True, "models": providers.list_models(pcfg, only_chat=not all_models)}
    except providers.ProviderError as e:
        return {"ok": False, "error": str(e), "models": []}


@router.get("/ollama/models")
def ollama_models(base_url: str = "http://localhost:11434"):
    base = re.sub(r"/v1/?$", "", base_url).rstrip("/")
    try:
        r = httpx.get(base + "/api/tags", timeout=3)
        return {"models": [m["name"] for m in r.json().get("models", [])]}
    except (httpx.HTTPError, ValueError):
        return {"models": []}


# Model chat chạy cục bộ: (tên, dung lượng tải ~GB, mô tả). Xếp từ nhỏ đến lớn.
LOCAL_CHAT_MODELS = [
    ("qwen3:1.7b", 1.4, "Rất nhẹ và nhanh, hợp máy yếu. Trả lời đơn giản, hay sai khi việc phức tạp."),
    ("qwen3:4b", 2.5, "Cân bằng tốt giữa tốc độ và chất lượng, có chế độ suy luận. Hợp phần lớn máy."),
    ("qwen3:8b", 5.2, "Thông minh hơn rõ rệt, gọi công cụ ổn hơn. Cần máy khá."),
    ("qwen3:14b", 9.3, "Chất lượng cao, hợp việc nhiều bước. Cần GPU mạnh hoặc nhiều RAM."),
    ("gemma3:12b", 8.1, "Đa ngôn ngữ tốt, hiểu được ảnh. Cần máy mạnh."),
]


def _hardware() -> dict:
    ram_gb = 0.0
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                ram_gb = int(line.split()[1]) / 1024 / 1024
                break
    except OSError:
        pass
    if not ram_gb:
        try:
            import psutil  # type: ignore

            ram_gb = psutil.virtual_memory().total / 1024**3
        except Exception:
            try:
                ram_gb = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=3)) / 1024**3
            except Exception:
                pass
    gpu, vram_gb = "", 0.0
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], timeout=4, text=True
            ).strip().splitlines()[0]
            name, mem = [x.strip() for x in out.rsplit(",", 1)]
            gpu, vram_gb = name, int(mem) / 1024
        except Exception:
            pass
    apple = platform.system() == "Darwin" and platform.machine() == "arm64"
    if apple:  # bộ nhớ chung CPU/GPU: dùng được khoảng 70% RAM
        gpu, vram_gb = "Apple Silicon", ram_gb * 0.7
    return {"ram_gb": round(ram_gb, 1), "gpu": gpu, "vram_gb": round(vram_gb, 1), "cpus": os.cpu_count() or 1, "os": platform.system()}


@router.get("/ollama/recommend")
def ollama_recommend(base_url: str = "http://localhost:11434"):
    """Gợi ý model chạy trên máy này + trạng thái Ollama, để giao diện hướng dẫn cài."""
    hw = _hardware()
    base = re.sub(r"/v1/?$", "", base_url).rstrip("/")
    installed: list[str] = []
    running = False
    try:
        r = httpx.get(base + "/api/tags", timeout=3)
        installed = [m["name"] for m in r.json().get("models", [])]
        running = True
    except (httpx.HTTPError, ValueError):
        pass
    has_binary = bool(shutil.which("ollama"))
    items = []
    for name, gb, desc in LOCAL_CHAT_MODELS:
        if hw["vram_gb"] and gb * 1.25 <= hw["vram_gb"]:
            fit = "gpu"  # nằm gọn trong VRAM: nhanh
        elif hw["ram_gb"] and gb * 1.5 <= hw["ram_gb"] * 0.7:
            fit = "cpu"  # chạy được nhưng chậm hơn
        else:
            fit = "heavy"  # quá nặng so với máy
        items.append({"name": name, "size_gb": gb, "desc": desc, "fit": fit, "installed": name in installed})
    gpu_fit = [i for i in items if i["fit"] == "gpu"]
    cpu_fit = [i for i in items if i["fit"] == "cpu" and i["size_gb"] <= 5.5]
    pick = (gpu_fit or cpu_fit or items[:1])[-1]
    for i in items:
        i["recommended"] = i is pick
    return {"hardware": hw, "ollama": {"running": running, "installed": has_binary or running}, "installed_models": installed, "models": items}


@router.get("/workspace/{name}")
def get_file(name: str):
    if name not in EDITABLE_FILES:
        raise HTTPException(403, "không được phép")
    p = cfgmod.load().workspace_path() / name
    return {"content": p.read_text() if p.exists() else ""}


class FileBody(BaseModel):
    content: str


@router.put("/workspace/{name}")
def put_file(name: str, body: FileBody):
    if name not in EDITABLE_FILES:
        raise HTTPException(403, "không được phép")
    ws = cfgmod.load().workspace_path()
    ws.mkdir(parents=True, exist_ok=True)
    (ws / name).write_text(body.content)
    return {"ok": True}


def _is_skill_path(rel: str) -> bool:
    return rel.split("/", 1)[0] == "skills"


@router.get("/workspace-files")
def list_workspace_files():
    """Liệt kê toàn bộ các file trong workspace để người dùng duyệt và quản lý."""
    ws = cfgmod.load().workspace_path()
    if not ws.exists():
        return {"files": []}
    files = []
    SYSTEM_FILES = {"SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"}
    for p in sorted(ws.rglob("*")):
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(ws).parts):
            rel = p.relative_to(ws).as_posix()
            try:
                stat = p.stat()
                files.append({
                    "path": rel,
                    "name": p.name,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "is_system": rel in SYSTEM_FILES,
                    "readonly": rel in SYSTEM_FILES or _is_skill_path(rel),
                    "ext": p.suffix.lower(),
                })
            except OSError:
                continue
    return {"files": files}


@router.get("/workspace-files/download")
def download_workspace_file(path: str):
    ws = cfgmod.load().workspace_path()
    target = (ws / path).resolve()
    if not target.is_relative_to(ws.resolve()) or not target.is_file():
        raise HTTPException(404, "không tìm thấy file")
    mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return FileResponse(target, media_type=mime, filename=target.name)


@router.delete("/workspace-files")
def delete_workspace_file(path: str):
    SYSTEM_FILES = {"SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"}
    if path in SYSTEM_FILES:
        raise HTTPException(400, "không được xóa file hệ thống")
    ws = cfgmod.load().workspace_path()
    target = (ws / path).resolve()
    if not target.is_relative_to(ws.resolve()) or not target.is_file():
        raise HTTPException(404, "không tìm thấy file")
    if _is_skill_path(target.relative_to(ws.resolve()).as_posix()):
        raise HTTPException(400, "file của skill chỉ xem, không được xóa")
    target.unlink(missing_ok=True)
    return {"ok": True}


@router.get("/backup/download")
def backup_download():
    """Tải bản sao lưu toàn bộ cấu hình, database và workspace dưới dạng file .tar.gz."""
    from ..services import backup
    home = backup.Home.default()
    archive, _ = backup.create(home, include_key=True)
    return FileResponse(archive, media_type="application/gzip", filename=archive.name)


@router.post("/backup/restore")
async def backup_restore_upload(request: Request):
    """Khôi phục dữ liệu từ file sao lưu .tar.gz được tải lên."""
    import tempfile
    from ..services import backup
    data = await request.body()
    if not data or len(data) < 100:
        raise HTTPException(400, "file sao lưu không hợp lệ")
    home = backup.Home.default()
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        res = backup.restore(home, tmp_path, force=True)
        return {"ok": True, "result": str(res)}
    except backup.BackupError as e:
        raise HTTPException(400, str(e)) from e
    finally:
        tmp_path.unlink(missing_ok=True)

