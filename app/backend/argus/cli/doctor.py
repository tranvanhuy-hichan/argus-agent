"""argus doctor: chan doan moi truong, cau hinh va ket noi; --fix tu sua nhung loi an toan."""
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
from dataclasses import asdict, dataclass

import httpx

from ..core import config as cfgmod
from ..core import secrets
from ..core.paths import CODE_ROOT, CONFIG_PATH, DATA, DB_PATH, DIST, ROOT
from ..services import providers
from . import daemon, runtime, service
from .ui import L, bold, dim, green, red, yellow


@dataclass
class Check:
    group: str
    name: str
    status: str  # ok | warn | fail | info
    detail: str = ""
    hint: str = ""


def _is_local(url: str) -> bool:
    return any(h in url for h in ("localhost", "127.0.0.1", "[::1]"))


def check_environment() -> list[Check]:
    g = L("Môi trường", "Environment")
    out = []
    v = sys.version_info
    out.append(Check(g, "Python", "ok" if v >= (3, 11) else "fail", f"{v.major}.{v.minor}.{v.micro}", "" if v >= (3, 11) else L("Cần Python 3.11+", "Python 3.11+ is required")))
    missing = []
    for mod in ("fastapi", "uvicorn", "httpx", "yaml", "croniter", "mcp", "pypdf", "openpyxl"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    out.append(Check(g, L("Thư viện Python", "Python packages"), "fail" if missing else "ok", ", ".join(missing) if missing else L("đủ", "all present"),
                     "pip install -e backend" if missing else ""))
    node = shutil.which("node")
    out.append(Check(g, "Node.js", "ok" if node else "info", node or L("không có (chỉ cần để build giao diện và chạy MCP server qua npx)", "not found (only needed to build the UI and run MCP servers via npx)")))
    out.append(Check(g, L("Giao diện web", "Web UI"), "ok" if (DIST / "index.html").exists() else "warn",
                     L("đã build", "built") if (DIST / "index.html").exists() else L("chưa build", "not built"), "" if (DIST / "index.html").exists() else "cd app/frontend && npm install && npm run build"))
    return out


def check_storage(fix: bool) -> list[Check]:
    g = L("Dữ liệu", "Data")
    out = []
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        probe = DATA / ".write-test"
        probe.write_text("x")
        probe.unlink()
        out.append(Check(g, L("Thư mục dữ liệu", "Data folder"), "ok", str(ROOT)))
    except OSError as e:
        out.append(Check(g, L("Thư mục dữ liệu", "Data folder"), "fail", f"{ROOT}: {e}"))
        return out
    free = shutil.disk_usage(DATA).free // (1024 * 1024)
    out.append(Check(g, L("Dung lượng trống", "Free disk space"), "warn" if free < 500 else "ok", f"{free} MB"))
    cfg_ok = False
    if CONFIG_PATH.exists():
        try:
            cfg = cfgmod.load()
            cfg_ok = True
            out.append(Check(g, "config.json", "ok", L("hợp lệ", "valid")))
            mode = stat.S_IMODE(CONFIG_PATH.stat().st_mode)
            if mode & 0o077:
                if fix:
                    CONFIG_PATH.chmod(0o600)
                    out.append(Check(g, L("Quyền config.json", "config.json permissions"), "ok", L("đã sửa về 600", "fixed to 600")))
                else:
                    has_key = any(p.api_key for p in cfg.providers.values())
                    out.append(Check(g, L("Quyền config.json", "config.json permissions"), "warn" if has_key else "info", oct(mode),
                                     L("File chứa API key nhưng người khác đọc được. Chạy: argus doctor --fix", "The file holds API keys but is readable by others. Run: argus doctor --fix")))
            else:
                out.append(Check(g, L("Quyền config.json", "config.json permissions"), "ok", oct(mode)))
        except Exception as e:  # noqa: BLE001
            out.append(Check(g, "config.json", "fail", str(e)[:150], L("Sửa hoặc xóa file này (sẽ dùng cấu hình mặc định)", "Fix or delete this file (defaults will be used)")))
    else:
        out.append(Check(g, "config.json", "warn", L("chưa có (đang dùng mặc định)", "missing (using defaults)"), "argus onboard"))
    if cfg_ok:
        st = secrets.status(json.loads(CONFIG_PATH.read_text()))
        if st["failed"]:
            out.append(Check(g, L("Khóa bí mật", "Secrets"), "fail", L(f"{len(st['failed'])} khóa không giải mã được", f"{len(st['failed'])} secret(s) cannot be decrypted"),
                             L("Mất hoặc sai khóa chủ: khôi phục khóa (ARGUS_MASTER_KEY / argus restore) hoặc nhập lại trong giao diện", "Master key lost or wrong: restore it (ARGUS_MASTER_KEY / argus restore) or re-enter the secrets in the UI")))
        elif st["plaintext"] and st["enabled"]:
            if fix:
                cfgmod.save(cfgmod.load(), encrypt=True)
                out.append(Check(g, L("Khóa bí mật", "Secrets"), "ok", L("đã mã hóa các khóa còn chữ thường", "encrypted the remaining plaintext secrets")))
            else:
                out.append(Check(g, L("Khóa bí mật", "Secrets"), "warn", L(f"{st['plaintext']} khóa còn ở dạng chữ thường", f"{st['plaintext']} secret(s) still in plaintext"), "argus secrets encrypt"))
        elif st["encrypted"]:
            out.append(Check(g, L("Khóa bí mật", "Secrets"), "ok", L(f"{st['encrypted']} khóa đã mã hóa · khóa chủ: {st['source']}", f"{st['encrypted']} encrypted · master key: {st['source']}")))
        else:
            out.append(Check(g, L("Khóa bí mật", "Secrets"), "info", L("chưa có khóa nào cần mã hóa", "no secrets to encrypt yet")))
        if st["source"] == "file" and secrets.KEY_FILE.exists() and stat.S_IMODE(secrets.KEY_FILE.stat().st_mode) & 0o077:
            if fix:
                secrets.KEY_FILE.chmod(0o600)
            else:
                out.append(Check(g, L("Quyền master.key", "master.key permissions"), "fail", oct(stat.S_IMODE(secrets.KEY_FILE.stat().st_mode)), "argus doctor --fix"))
    if fix:
        runtime.bootstrap()
    from ..services import backup as backupsvc

    last = backupsvc.list_backups(backupsvc.Home(ROOT, CONFIG_PATH, DB_PATH, secrets.KEY_FILE, cfgmod.load().workspace_path() if cfg_ok or not CONFIG_PATH.exists() else ROOT / "workspace")) if DB_PATH.exists() else []
    out.append(Check(g, L("Sao lưu", "Backups"), "ok" if last else "info", last[0].name if last else L("chưa có (argus backup)", "none yet (argus backup)")))
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            res = conn.execute("PRAGMA integrity_check").fetchone()[0]
            try:
                conn.execute("CREATE VIRTUAL TABLE temp._f USING fts5(a)")
                fts = True
            except sqlite3.OperationalError:
                fts = False
            out.append(Check(g, L("Cơ sở dữ liệu", "Database"), "ok" if res == "ok" else "fail", res))
            out.append(Check(g, L("Tìm kiếm toàn văn (FTS5)", "Full-text search (FTS5)"), "ok" if fts else "warn", "" if fts else L("SQLite không có FTS5: memory_search bị tắt", "SQLite has no FTS5: memory_search is disabled")))
        except sqlite3.Error as e:
            out.append(Check(g, L("Cơ sở dữ liệu", "Database"), "fail", str(e)))
    else:
        out.append(Check(g, L("Cơ sở dữ liệu", "Database"), "info", L("chưa tạo (tạo khi chạy lần đầu)", "not created yet (created on first run)")))
    ws = cfgmod.load().workspace_path() if cfg_ok or not CONFIG_PATH.exists() else None
    if ws:
        soul = (ws / "SOUL.md").exists()
        out.append(Check(g, "Workspace", "ok" if ws.is_dir() else "warn", str(ws), "" if ws.is_dir() else "argus doctor --fix"))
        out.append(Check(g, "SOUL.md", "ok" if soul else "warn", L("có", "present") if soul else L("thiếu (agent không có tính cách/quy tắc)", "missing (the agent has no persona/rules)"), "" if soul else "argus doctor --fix"))
    return out


def check_server() -> list[Check]:
    g = L("Server", "Server")
    st = daemon.read_state()
    host, port = st.get("host", daemon.default_host()), st.get("port", daemon.default_port())
    url = daemon.public_url(host, port)
    h = daemon.health(url)
    out = []
    if h:
        out.append(Check(g, L("Đang chạy", "Running"), "ok", f"{url} · v{h.get('version')} · pid {h.get('pid')}"))
        if host not in ("127.0.0.1", "localhost") and not cfgmod.load().auth.password_hash:
            out.append(Check(g, L("Mở ra ngoài localhost", "Exposed beyond localhost"), "fail", host, L("Đặt mật khẩu: argus onboard (hoặc Cài đặt > Bảo mật)", "Set a password: argus onboard (or Settings > Security)")))
    elif daemon.port_in_use(host, port):
        out.append(Check(g, L("Cổng", "Port"), "warn", L(f"{port} đang bị chương trình khác dùng", f"{port} is used by another program"), "argus start --port <port>"))
    else:
        out.append(Check(g, L("Đang chạy", "Running"), "info", L("không (bật bằng: argus start)", "no (start it with: argus start)")))
    unit = service.unit_path() if service._system() == "Linux" else service.plist_path()
    out.append(Check(g, L("Dịch vụ tự khởi động", "Auto-start service"), "ok" if unit.exists() else "info", str(unit) if unit.exists() else L("chưa cài (argus service install)", "not installed (argus service install)")))
    return out


def check_providers(offline: bool) -> list[Check]:
    g = L("Model", "Models")
    cfg = cfgmod.load()
    out = []
    for name, p in cfg.providers.items():
        tag = f"{name}" + (" ★" if name == cfg.default_provider else "")
        if p.type == "cli":  # dung CLI da dang nhap san: chi kiem tra co lenh, khong goi mang (tranh ton luot dung)
            from ..services import cli_provider

            exe = cli_provider.find(p)
            out.append(Check(g, tag, "ok" if exe else "fail", f"CLI: {exe}" if exe else L("không tìm thấy lệnh CLI", "CLI command not found"),
                             "" if exe else L("Cài CLI và đăng nhập một lần trong terminal (vd. chạy `claude`)", "Install the CLI and log in once in a terminal (e.g. run `claude`)")))
            continue
        key = p.api_key or os.environ.get(p.api_key_env or "", "")
        if not _is_local(p.base_url) and p.type == "openai" and not key or (p.type == "anthropic" and not key):
            out.append(Check(g, tag, "fail", L("thiếu API key", "missing API key"), L(f"Đặt key trong Providers hoặc biến môi trường {p.api_key_env or '<TÊN>'}", f"Set the key in Providers or the {p.api_key_env or '<NAME>'} environment variable")))
            continue
        if offline:
            out.append(Check(g, tag, "info", f"{p.model} ({L('bỏ qua kiểm tra mạng', 'network check skipped')})"))
            continue
        try:
            models = providers.list_models(p, only_chat=False)
            if _is_local(p.base_url) and models and p.model not in models:
                out.append(Check(g, tag, "warn", L(f"đã kết nối nhưng chưa có model '{p.model}'", f"connected but model '{p.model}' is not installed"), f"ollama pull {p.model}"))
            else:
                out.append(Check(g, tag, "ok", f"{p.model} · {L(f'{len(models)} model', f'{len(models)} models')}"))
        except providers.ProviderError as e:
            hint = L("Chạy: ollama serve", "Run: ollama serve") if ":11434" in p.base_url else ""
            sev = "fail"
            if e.status in (401, 403):
                hint = L("API key sai hoặc hết hạn", "The API key is wrong or expired")
            out.append(Check(g, tag, sev, str(e)[:130], hint))
    return out


def check_tools(offline: bool) -> list[Check]:
    g = L("Công cụ & tích hợp", "Tools & integrations")
    cfg = cfgmod.load()
    out = []
    docker = shutil.which("docker")
    if cfg.agent.exec_sandbox == "docker":
        if not docker:
            out.append(Check(g, "Docker sandbox", "fail", L("đã bật nhưng không có lệnh docker", "enabled but the docker command is missing")))
        else:
            r = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=15)
            out.append(Check(g, "Docker sandbox", "ok" if r.returncode == 0 else "fail", cfg.agent.sandbox_image if r.returncode == 0 else L("Docker daemon không chạy", "the Docker daemon is not running")))
    else:
        out.append(Check(g, "Docker sandbox", "info", L("tắt", "off") + (L(" (có Docker, có thể bật trong Cài đặt)", " (Docker is available, you can enable it in Settings)") if docker else "")))
    for name, s in cfg.mcp_servers.items():
        if s.enabled and s.transport == "stdio":
            found = shutil.which(s.command) or os.path.exists(s.command)
            out.append(Check(g, f"MCP: {name}", "ok" if found else "fail", s.command if found else L(f"không tìm thấy lệnh '{s.command}'", f"command '{s.command}' not found")))
        elif s.enabled:
            out.append(Check(g, f"MCP: {name}", "info", s.url))
    tg = cfg.channels.telegram
    if tg.enabled:
        if offline:
            out.append(Check(g, "Telegram", "info", L("bỏ qua kiểm tra mạng", "network check skipped")))
        else:
            try:
                r = httpx.post(f"{tg.api_base}/bot{tg.token}/getMe", timeout=10).json()
                out.append(Check(g, "Telegram", "ok" if r.get("ok") else "fail", f"@{r['result']['username']}" if r.get("ok") else r.get("description", "")))
            except httpx.HTTPError as e:
                out.append(Check(g, "Telegram", "fail", str(e)[:100]))
    skills_n = 0
    needs = 0
    try:
        from ..services import skills as skillmod

        found = skillmod.discover(cfg).values()
        skills_n, needs = len(found), sum(1 for s in found if s.enabled and not s.eligible)
    except Exception:  # noqa: BLE001
        pass
    out.append(Check(g, "Skills", "warn" if needs else "ok", L(f"{skills_n} skill, {needs} cần thiết lập", f"{skills_n} skills, {needs} need setup"), "argus skills list" if needs else ""))
    return out


def check_features(offline: bool) -> list[Check]:
    """Tính năng mở rộng: trình duyệt, ảnh, trí nhớ ngữ nghĩa, điều khiển máy tính và các tool nạp lỗi."""
    g = L("Tính năng mở rộng", "Extended features")
    cfg = cfgmod.load()
    out: list[Check] = []
    from ..services import tools

    for mod, err in getattr(tools, "LOAD_ERRORS", {}).items():
        out.append(Check(g, f"tool: {mod}", "fail", str(err)[:120]))
    if not cfg.browser.enabled:
        out.append(Check(g, L("Trình duyệt", "Browser"), "info", L("tắt", "off")))
    elif offline:
        out.append(Check(g, L("Trình duyệt", "Browser"), "info", L("bỏ qua (chế độ offline)", "skipped (offline mode)")))
    else:
        try:
            from ..services.browser import manager

            b = manager.status()
            if b["launchable"]:
                out.append(Check(g, L("Trình duyệt", "Browser"), "ok", b["executable"]))
            else:
                out.append(Check(g, L("Trình duyệt", "Browser"), "warn", b["error"] or "?", "pip install playwright; sudo apt install chromium"))
        except Exception as e:  # noqa: BLE001
            out.append(Check(g, L("Trình duyệt", "Browser"), "warn", f"{type(e).__name__}: {e}"[:120]))
    try:
        from ..services import embeddings

        e = embeddings.status(cfg)
        detail = f"{e['model_id'] or '-'}" + (L(" (chỉ khớp từ gần giống, chưa hiểu nghĩa)", " (fuzzy lexical only, no real semantics)") if e["backend"] == "hash" else "")
        out.append(Check(g, L("Trí nhớ ngữ nghĩa", "Semantic memory"), "ok" if e["reachable"] else ("info" if e["mode"] == "off" else "warn"), detail if e["reachable"] else (e["error"] or L("tắt", "off"))))
    except Exception as e:  # noqa: BLE001
        out.append(Check(g, L("Trí nhớ ngữ nghĩa", "Semantic memory"), "warn", str(e)[:120]))
    try:
        from ..services import tools_media

        m = tools_media.status()
        out.append(Check(g, L("Tạo ảnh", "Image generation"), "ok" if m.get("image_ok") else "info", f"{m.get('image_provider')} / {m['image_model']}" if m.get("image_ok") else m.get("image_hint", "")))
        out.append(Check(g, L("Xem ảnh", "Vision"), "ok" if m.get("vision_ok") else "info", str(m.get("vision_provider")) if m.get("vision_ok") else m.get("vision_hint", "")))
    except Exception as e:  # noqa: BLE001
        out.append(Check(g, L("Ảnh", "Images"), "warn", str(e)[:120]))
    try:
        from ..services import tools_computer

        c = tools_computer.status()
        if not c["enabled"]:
            out.append(Check(g, L("Điều khiển máy tính", "Computer control"), "info", L("tắt (mặc định)", "off (default)")))
        else:
            out.append(Check(g, L("Điều khiển máy tính", "Computer control"), "warn" if c["hint"] else "ok", c["hint"] or f"{c['platform']}: {', '.join(c['input_tools'])}"))
    except Exception as e:  # noqa: BLE001
        out.append(Check(g, L("Điều khiển máy tính", "Computer control"), "warn", str(e)[:120]))
    return out


def run(offline: bool = False, fix: bool = False, as_json: bool = False) -> int:
    checks = check_environment() + check_storage(fix) + check_server() + check_providers(offline) + check_tools(offline) + check_features(offline)
    if fix and not (DIST / "index.html").exists():
        daemon.ensure_frontend(True)
    if as_json:
        print(json.dumps([asdict(c) for c in checks], ensure_ascii=False, indent=2))
        return 1 if any(c.status == "fail" for c in checks) else 0
    icon = {"ok": green("✓"), "warn": yellow("!"), "fail": red("✗"), "info": dim("·")}
    group = None
    for c in checks:
        if c.group != group:
            group = c.group
            print(f"\n{bold(group)}")
        detail = f"  {dim(c.detail)}" if c.detail else ""
        print(f"  {icon[c.status]} {c.name}{detail}")
        if c.hint and c.status in ("warn", "fail"):
            print(f"      {dim('→ ' + c.hint)}")
    fails = sum(c.status == "fail" for c in checks)
    warns = sum(c.status == "warn" for c in checks)
    print()
    if fails:
        print(red(L(f"{fails} lỗi, {warns} cảnh báo.", f"{fails} problem(s), {warns} warning(s).")))
    elif warns:
        print(yellow(L(f"Ổn, nhưng có {warns} cảnh báo.", f"All good, with {warns} warning(s).")))
    else:
        print(green(L("Mọi thứ đều ổn.", "Everything looks good.")))
    return 1 if fails else 0


__all__ = ["run", "CODE_ROOT"]
