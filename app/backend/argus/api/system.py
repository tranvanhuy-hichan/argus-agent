import json
import os
import re
import time

import httpx
from fastapi import APIRouter, HTTPException
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
