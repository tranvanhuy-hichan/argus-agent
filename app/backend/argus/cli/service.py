"""Cai Argus thanh dich vu chay cung may: systemd (Linux, che do user) va launchd (macOS)."""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from ..core.paths import LOG_FILE, ROOT
from . import daemon
from .ui import L, bad, bold, dim, info, ok, warn

NAME = "argus"
LABEL = "com.argus.agent"


def _q(s: str) -> str:
    return f'"{s}"' if " " in s else s


def systemd_unit(host: str, port: int) -> str:
    """Duong dan co dau cach (vd. 'My projects') phai duoc boc nhay kep trong ExecStart."""
    exec_start = " ".join(_q(a) for a in [sys.executable, "-m", "uvicorn", "argus.main:app", "--host", host, "--port", str(port)])
    env_lines = [f'Environment="PYTHONPATH={daemon.BACKEND_DIR}"']  # systemd: boc ca phep gan, khong chi gia tri
    if os.environ.get("ARGUS_HOME"):
        env_lines.append(f'Environment="ARGUS_HOME={os.environ["ARGUS_HOME"]}"')
    return "\n".join(["[Unit]", "Description=Argus Agent", "After=network-online.target", "Wants=network-online.target", "",
                      "[Service]", "Type=simple", f"WorkingDirectory={ROOT}", *env_lines, f"ExecStart={exec_start}",
                      "Restart=on-failure", "RestartSec=3", "", "[Install]", "WantedBy=default.target", ""])


def launchd_plist(host: str, port: int) -> str:
    args = "".join(f"\n    <string>{a}</string>" for a in [sys.executable, "-m", "uvicorn", "argus.main:app", "--host", host, "--port", str(port)])
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array>{args}
  </array>
  <key>WorkingDirectory</key><string>{ROOT}</string>
  <key>EnvironmentVariables</key><dict><key>PYTHONPATH</key><string>{daemon.BACKEND_DIR}</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{LOG_FILE}</string>
  <key>StandardErrorPath</key><string>{LOG_FILE}</string>
</dict></plist>
'''


def unit_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / f"{NAME}.service"


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _system() -> str:
    return platform.system()


def install(host: str, port: int, dry_run: bool = False) -> int:
    system = _system()
    if system == "Linux":
        path, text = unit_path(), systemd_unit(host, port)
    elif system == "Darwin":
        path, text = plist_path(), launchd_plist(host, port)
    else:
        bad(L("Hệ điều hành này chưa hỗ trợ `argus service`. Trên Windows hãy dùng WSL hoặc Docker (docker compose up -d).",
              "`argus service` is not supported on this OS. On Windows use WSL or Docker (docker compose up -d)."))
        return 1
    if dry_run:
        print(dim(f"# {path}"))
        print(text)
        return 0
    if system == "Linux" and not shutil.which("systemctl"):
        bad(L("Không tìm thấy systemctl.", "systemctl was not found."))
        return 1
    if daemon.read_pid():
        info(L("Đang dừng server chạy nền hiện tại để service tiếp quản cổng.", "Stopping the current background server so the service can take over the port."))
        daemon.stop()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    ok(L(f"Đã ghi {path}", f"Wrote {path}"))
    if system == "Linux":
        steps = [["systemctl", "--user", "daemon-reload"], ["systemctl", "--user", "enable", "--now", f"{NAME}.service"]]
    else:
        steps = [["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)]]
    for cmd in steps:
        r = _run(cmd)
        if r.returncode != 0 and "bootout" not in cmd:
            bad(L(f"Lệnh thất bại: {' '.join(cmd)}", f"Command failed: {' '.join(cmd)}"))
            print(dim((r.stderr or r.stdout).strip()))
            return 1
    ok(L(f"Đã bật dịch vụ. Xem log: {'journalctl --user -u argus -f' if system == 'Linux' else f'argus logs -f'}", f"Service enabled. Logs: {'journalctl --user -u argus -f' if system == 'Linux' else 'argus logs -f'}"))
    if system == "Linux":
        print(dim(L("  Muốn chạy cả khi chưa đăng nhập: loginctl enable-linger $USER", "  To run even when you are not logged in: loginctl enable-linger $USER")))
    print(dim(f"  {L('Địa chỉ', 'URL')}: {bold(daemon.public_url(host, port))}"))
    return 0


def uninstall() -> int:
    system = _system()
    path = unit_path() if system == "Linux" else plist_path()
    if not path.exists():
        info(L("Chưa cài dịch vụ.", "The service is not installed."))
        return 0
    if system == "Linux":
        _run(["systemctl", "--user", "disable", "--now", f"{NAME}.service"])
    else:
        _run(["launchctl", "bootout", f"gui/{os.getuid()}", str(path)])
    path.unlink(missing_ok=True)
    if system == "Linux":
        _run(["systemctl", "--user", "daemon-reload"])
    ok(L("Đã gỡ dịch vụ.", "Service removed."))
    return 0


def control(action: str) -> int:
    """start | stop | restart | status cho dich vu da cai."""
    system = _system()
    if system == "Linux":
        r = _run(["systemctl", "--user", action, f"{NAME}.service"])
    elif system == "Darwin":
        label = f"gui/{os.getuid()}/{LABEL}"
        cmd = {"start": ["launchctl", "kickstart", label], "stop": ["launchctl", "kill", "SIGTERM", label], "restart": ["launchctl", "kickstart", "-k", label], "status": ["launchctl", "print", label]}[action]
        r = _run(cmd)
    else:
        bad(L("Hệ điều hành này chưa hỗ trợ.", "Unsupported OS."))
        return 1
    out = (r.stdout or r.stderr).strip()
    if action == "status":
        active = r.returncode == 0 and ("active (running)" in out or "state = running" in out or system == "Darwin")
        (ok if active else warn)(L("Dịch vụ đang chạy.", "Service is running.") if active else L("Dịch vụ không chạy hoặc chưa cài.", "Service is not running or not installed."))
        return 0 if active else 3
    (ok if r.returncode == 0 else bad)(out or action)
    return r.returncode
