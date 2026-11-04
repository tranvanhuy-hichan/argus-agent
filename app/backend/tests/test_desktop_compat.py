"""Tương thích Windows và bản đóng gói desktop (logic chạy được kiểm trên Linux bằng cách giả lập nền tảng)."""
import sys

from argus import desktop_server
from argus.core import paths
from argus.services import browser, tools


def test_shell_is_bash_on_linux_and_note_is_empty():
    exe, name = tools._shell()
    assert name == "bash" and exe and tools.shell_note() == ""


def test_windows_without_bash_uses_cmd_and_tells_the_model(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    assert tools._shell() == (None, "cmd.exe")
    assert "cmd.exe" in tools.shell_note()


def test_windows_with_git_bash_prefers_bash(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(tools.shutil, "which", lambda name: r"C:\Program Files\Git\bin\bash.exe" if name == "bash" else None)
    assert tools._shell()[1] == "bash" and tools.shell_note() == ""


def test_exec_runs_with_resolved_shell(tmp_path):
    ctx = tools.ToolContext(workspace=tmp_path, confirm_exec=False)
    assert tools.exec_tool(ctx, "echo xin-chào").strip() == "xin-chào"


def test_windows_browser_discovery(monkeypatch, tmp_path):
    exe = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setattr(browser.shutil, "which", lambda name: None)
    assert browser.find_chromium() == str(exe)


def test_docker_command_without_getuid(monkeypatch, tmp_path):
    monkeypatch.delattr(tools.os, "getuid", raising=False)
    monkeypatch.delattr(tools.os, "getgid", raising=False)
    ctx = tools.ToolContext(workspace=tmp_path, sandbox={"mode": "docker"})
    assert "--user" not in tools._docker_cmd(ctx, "ls")


def test_frozen_layout_points_to_bundle(monkeypatch, tmp_path):
    """Bản đóng gói: frontend/dist và templates nằm trong thư mục giải nén của PyInstaller."""
    import importlib
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setenv("ARGUS_HOME", str(tmp_path / "data-home"))
    try:
        reloaded = importlib.reload(paths)
        assert reloaded.CODE_ROOT == tmp_path and reloaded.DIST == tmp_path / "frontend" / "dist" and reloaded.ROOT == (tmp_path / "data-home").resolve()
    finally:
        monkeypatch.undo()
        importlib.reload(paths)


def test_server_falls_back_to_free_port_when_preferred_is_busy():
    import socket
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    busy.listen()
    preferred = busy.getsockname()[1]
    s = desktop_server.bind("127.0.0.1", preferred)
    try:
        assert s.getsockname()[1] not in (0, preferred)
    finally:
        s.close(); busy.close()
    free = desktop_server.bind("127.0.0.1", 0)
    assert free.getsockname()[1] > 0
    free.close()
