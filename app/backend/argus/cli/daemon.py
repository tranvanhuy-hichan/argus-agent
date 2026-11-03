"""Chay server nen: start / stop / restart / status / logs / dev / open (thay cho run.sh)."""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import httpx

from ..core import config as cfgmod
from ..core.env import getenv
from ..core.paths import CODE_ROOT, DATA, DB_PATH, DIST, LOG_FILE, PID_FILE, ROOT
from .ui import L, bad, bold, dim, green, info, ok, red, warn, yellow

STATE_FILE = DATA / "server.json"
BACKEND_DIR = Path(__file__).resolve().parents[2]  # thu muc chua goi `argus` (de chay duoc ca khi chua pip install)


def default_host() -> str:
    return getenv("HOST") or "127.0.0.1"


def default_port() -> int:
    return int(getenv("PORT") or 8787)


def public_url(host: str, port: int) -> str:
    return f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    cmdline = Path(f"/proc/{pid}/cmdline")
    if cmdline.exists():  # tranh nham voi tien trinh khac da lay lai so pid cu
        try:
            return b"uvicorn" in cmdline.read_bytes() or b"argus" in cmdline.read_bytes()
        except OSError:
            return True
    return True


def read_pid() -> int | None:
    try:
        pid = int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if _alive(pid) else None


def read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def health(url: str, timeout: float = 1.5) -> dict | None:
    try:
        r = httpx.get(url + "/api/health", timeout=timeout)
        return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def port_in_use(host: str, port: int) -> bool:
    probe = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((probe, port)) == 0


def _cleanup() -> None:
    PID_FILE.unlink(missing_ok=True)
    STATE_FILE.unlink(missing_ok=True)


def _server_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(BACKEND_DIR), env.get("PYTHONPATH", "")]))
    return env


def _tail(n: int) -> list[str]:
    try:
        return LOG_FILE.read_text(errors="replace").splitlines()[-n:]
    except OSError:
        return []


def ensure_frontend(build: bool = True) -> None:
    if (DIST / "index.html").exists():
        return
    web = CODE_ROOT / "frontend"
    if build and shutil.which("npm") and (web / "package.json").exists():
        info(L("Giao diện web chưa được build, đang build (lần đầu mất khoảng 1 phút)…", "The web UI is not built yet; building it (about a minute the first time)…"))
        for cmd in (["npm", "install", "--no-fund", "--no-audit"], ["npm", "run", "build"]):
            if subprocess.run(cmd, cwd=web, capture_output=True).returncode != 0:
                warn(L(f"Không build được giao diện ({' '.join(cmd)}). Server vẫn chạy, chỉ có API.", f"Could not build the UI ({' '.join(cmd)}). The server still runs, API only."))
                return
        ok(L("Đã build giao diện.", "UI built."))
    else:
        warn(L("Giao diện web chưa được build (cần Node.js: cd app/frontend && npm install && npm run build). Server vẫn chạy, chỉ có API.",
               "The web UI is not built (needs Node.js: cd app/frontend && npm install && npm run build). The server still runs, API only."))


def start(host: str, port: int, foreground: bool = False, build: bool = True) -> int:
    pid = read_pid()
    if pid:
        st = read_state()
        ok(L(f"Argus Agent đang chạy (pid {pid}) tại {public_url(st.get('host', host), st.get('port', port))}", f"Argus Agent is already running (pid {pid}) at {public_url(st.get('host', host), st.get('port', port))}"))
        return 0
    if port_in_use(host, port):
        bad(L(f"Cổng {port} đang được chương trình khác dùng. Dùng --port để chọn cổng khác, hoặc `argus stop` nếu đó là Argus.",
              f"Port {port} is already in use. Use --port to pick another one, or `argus stop` if that is Argus."))
        return 1
    DATA.mkdir(parents=True, exist_ok=True)
    ensure_frontend(build)
    cmd = [sys.executable, "-m", "uvicorn", "argus.main:app", "--host", host, "--port", str(port)]
    if foreground:
        PID_FILE.write_text(str(os.getpid()))
        STATE_FILE.write_text(json.dumps({"host": host, "port": port, "started": time.time(), "pid": os.getpid()}))
        try:
            return subprocess.call(cmd, cwd=ROOT, env=_server_env())
        except KeyboardInterrupt:
            return 0
        finally:
            _cleanup()
    with open(LOG_FILE, "ab") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=ROOT, env=_server_env(), start_new_session=True)
    PID_FILE.write_text(str(proc.pid))
    STATE_FILE.write_text(json.dumps({"host": host, "port": port, "started": time.time(), "pid": proc.pid}))
    url = public_url(host, port)
    for _ in range(100):  # toi da ~25 giay
        if proc.poll() is not None:
            break
        if health(url):
            ok(L(f"Argus Agent đã chạy (pid {proc.pid}): {bold(url)}", f"Argus Agent is running (pid {proc.pid}): {bold(url)}"))
            print(dim(L("  Xem log: argus logs -f   ·   Dừng: argus stop   ·   Mở giao diện: argus open",
                        "  Logs: argus logs -f   ·   Stop: argus stop   ·   Open the UI: argus open")))
            if host not in ("127.0.0.1", "localhost") and not cfgmod.load().auth.password_hash:
                warn(L("Server đang mở ra ngoài localhost mà chưa đặt mật khẩu giao diện. Chạy `argus onboard` hoặc đặt trong Cài đặt > Bảo mật.",
                       "The server is reachable beyond localhost but no interface password is set. Run `argus onboard` or set one in Settings > Security."))
            return 0
        time.sleep(0.25)
    bad(L("Server không khởi động được. Log gần nhất:", "The server failed to start. Recent log:"))
    for line in _tail(15):
        print(dim("  " + line))
    if proc.poll() is None:
        proc.terminate()
    _cleanup()
    return 1


def stop() -> int:
    pid = read_pid()
    if not pid:
        _cleanup()
        st = read_state() or {}
        if health(public_url(st.get("host", default_host()), st.get("port", default_port()))):
            warn(L("Có một server đang chạy nhưng không do `argus start` khởi động (service systemd, Docker?). Dùng `argus service stop` hoặc docker compose down.",
                   "A server is running but was not started by `argus start` (systemd service, Docker?). Use `argus service stop` or docker compose down."))
            return 1
        info(L("Argus Agent không chạy.", "Argus Agent is not running."))
        return 0
    os.kill(pid, signal.SIGTERM)
    for _ in range(100):
        if not _alive(pid):
            break
        time.sleep(0.1)
    else:
        os.kill(pid, signal.SIGKILL)
        warn(L("Server không tắt kịp, đã buộc dừng.", "The server did not exit in time and was killed."))
    _cleanup()
    ok(L("Đã dừng Argus Agent.", "Argus Agent stopped."))
    return 0


def restart(host: str, port: int, build: bool = True) -> int:
    st = read_state()
    stop()
    return start(st.get("host", host), st.get("port", port), build=build)


def status(as_json: bool = False) -> int:
    pid = read_pid()
    st = read_state()
    host, port = st.get("host", default_host()), st.get("port", default_port())
    url = public_url(host, port)
    h = health(url) if pid or port_in_use(host, port) else None
    cfg = cfgmod.load()
    sessions = 0
    try:
        import sqlite3

        sessions = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM sessions").fetchone()[0] if DB_PATH.exists() else 0
    except Exception:  # noqa: BLE001
        pass
    data = {
        "running": bool(h), "pid": (h or {}).get("pid") or pid, "url": url, "version": (h or {}).get("version"),
        "uptime_s": int(time.time() - (h or {}).get("started", time.time())) if h else None,
        "managed_by_cli": bool(pid), "default_provider": cfg.default_provider,
        "model": cfg.providers[cfg.default_provider].model if cfg.default_provider in cfg.providers else None,
        "providers": list(cfg.providers), "sessions": sessions, "mcp_servers": len(cfg.mcp_servers),
        "telegram": cfg.channels.telegram.enabled, "heartbeat": cfg.heartbeat.enabled, "password": bool(cfg.auth.password_hash),
        "sandbox": cfg.agent.exec_sandbox, "home": str(ROOT),
    }
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data["running"] else 1
    if data["running"]:
        up = data["uptime_s"] or 0
        ok(L(f"Đang chạy · pid {data['pid']} · {bold(url)} · v{data['version']} · {up // 3600}h{up % 3600 // 60:02d}m",
             f"Running · pid {data['pid']} · {bold(url)} · v{data['version']} · {up // 3600}h{up % 3600 // 60:02d}m"))
        if not pid:
            warn(L("Không do `argus start` quản lý (service/Docker).", "Not managed by `argus start` (service/Docker)."))
    else:
        bad(L("Không chạy. Bật bằng: argus start", "Not running. Start it with: argus start"))
    rows = [
        (L("Model mặc định", "Default model"), f"{data['default_provider']} · {data['model']}"),
        (L("Provider", "Providers"), ", ".join(data["providers"])),
        (L("Hội thoại", "Conversations"), str(sessions)),
        ("MCP", L(f"{data['mcp_servers']} server", f"{data['mcp_servers']} server(s)")),
        ("Telegram", green("on") if data["telegram"] else dim("off")),
        ("Heartbeat", green("on") if data["heartbeat"] else dim("off")),
        (L("Mật khẩu giao diện", "Interface password"), green(L("đã đặt", "set")) if data["password"] else yellow(L("chưa đặt", "not set"))),
        ("Sandbox", data["sandbox"]),
        (L("Thư mục dữ liệu", "Data folder"), data["home"]),
    ]
    for k, v in rows:
        print(f"  {dim(k.ljust(22))}{v}")
    return 0 if data["running"] else 1


def logs(follow: bool, n: int) -> int:
    if not LOG_FILE.exists():
        info(L("Chưa có log (server chưa từng chạy bằng `argus start`). Nếu chạy bằng systemd: journalctl --user -u argus -f",
               "No log yet (the server has not run via `argus start`). With systemd: journalctl --user -u argus -f"))
        return 0
    for line in _tail(n):
        print(line)
    if follow:
        try:
            with open(LOG_FILE, errors="replace") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if line:
                        print(line, end="", flush=True)
                    else:
                        time.sleep(0.4)
        except KeyboardInterrupt:
            pass
    return 0


def open_ui(host: str, port: int) -> int:
    st = read_state()
    url = public_url(st.get("host", host), st.get("port", port))
    if not health(url):
        bad(L("Server chưa chạy. Bật bằng: argus start", "The server is not running. Start it with: argus start"))
        return 1
    ok(url)
    webbrowser.open(url)
    return 0


def dev(port: int) -> int:
    """Chay che do phat trien: backend tu nap lai + Vite (cong 5173)."""
    web = CODE_ROOT / "frontend"
    if not shutil.which("npm") or not (web / "package.json").exists():
        bad(L("Cần Node.js và thư mục app/frontend/ để chạy chế độ phát triển.", "Node.js and the app/frontend/ folder are required for dev mode."))
        return 1
    env = _server_env()
    env["ARGUS_DEV_ORIGINS"] = "http://localhost:5173,http://127.0.0.1:5173"
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "argus.main:app", "--reload", "--reload-dir", str(BACKEND_DIR / "argus"), "--port", str(port)], cwd=ROOT, env=env)
    ui = subprocess.Popen(["npm", "run", "dev"], cwd=web)
    info(L("Chế độ phát triển: giao diện http://localhost:5173 (Ctrl+C để dừng cả hai)", "Dev mode: UI at http://localhost:5173 (Ctrl+C stops both)"))
    try:
        api.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in (ui, api):
            p.terminate()
    return 0
