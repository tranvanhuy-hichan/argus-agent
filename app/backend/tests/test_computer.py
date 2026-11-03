import struct
import subprocess

import pytest

from argus.core import config as cfgmod
from argus.services import tools, tools_computer as tc
from argus.services.tools import DENIED, ToolContext


@pytest.fixture(autouse=True)
def no_real(monkeypatch):
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(tc.subprocess, "run", fake_run)
    monkeypatch.setattr(tc.shutil, "which", lambda n: None)
    tc._SCREEN["size"] = None
    return calls


def enable(on=True):
    cfg = cfgmod.load()
    cfg.computer.enabled = on
    cfgmod.save(cfg)


def ctx_for(tmp_env, approver=lambda k, d: True, **kw):
    return ToolContext(workspace=tmp_env / "workspace", approver=approver, **kw)


def test_disabled_by_default(tmp_env, no_real):
    with pytest.raises(RuntimeError, match="đang tắt"):
        tc.computer_click(ctx_for(tmp_env), 1, 1)
    with pytest.raises(RuntimeError, match="Bảo mật"):
        tc.computer_screenshot(ctx_for(tmp_env))
    assert not no_real


def test_approval_always_requested(tmp_env, no_real, monkeypatch):
    enable()
    monkeypatch.setattr(tc, "detect_platform", lambda: "x11")
    monkeypatch.setattr(tc.shutil, "which", lambda n: "/usr/bin/" + n)
    asked = []
    deny = ctx_for(tmp_env, approver=lambda k, d: asked.append((k, d)) or False)
    assert tc.computer_click(deny, 5, 6) == DENIED
    assert tc.computer_type(deny, "hi") == DENIED
    assert tc.computer_key(deny, "ctrl+l") == DENIED
    assert tc.computer_move(deny, 1, 2) == DENIED
    assert tc.computer_scroll(deny, "down") == DENIED
    assert tc.computer_screenshot(deny) == DENIED
    assert len(asked) == 6 and all(k == "computer" for k, _ in asked) and "(5, 6)" in asked[0][1]
    assert not no_real
    ok = ctx_for(tmp_env)
    assert "Đã click" in tc.computer_click(ok, 5, 6)
    assert no_real[-1] == ["xdotool", "mousemove", "5", "6", "click", "--repeat", "1", "1"]
    full = ctx_for(tmp_env, approver=lambda k, d: pytest.fail("không được hỏi"), full_access=True)
    tc.computer_key(full, "Return")


def test_builders():
    w = lambda n: None
    assert tc.build_click("x11", 10, 20, "right", True) == [["xdotool", "mousemove", "10", "20", "click", "--repeat", "2", "3"]]
    assert tc.build_click("wayland", 10, 20) == [["ydotool", "mousemove", "--absolute", "-x", "10", "-y", "20"], ["ydotool", "click", "--repeat", "1", "0xC0"]]
    assert tc.build_click("macos", 1, 2, which=lambda n: "x") == [["cliclick", "c:1,2"]]
    assert tc.build_click("macos", 1, 2, double=True, which=lambda n: "x") == [["cliclick", "dc:1,2"]]
    assert tc.build_type("x11", "a b") == [["xdotool", "type", "--delay", "20", "--", "a b"]]
    assert tc.build_type("wayland", "hi", which=lambda n: "x") == [["wtype", "--", "hi"]]
    assert tc.build_type("wayland", "hi", which=w) == [["ydotool", "type", "--", "hi"]]
    assert tc.build_key("x11", "ctrl+shift+t") == [["xdotool", "key", "ctrl+shift+t"]]
    assert tc.build_key("x11", "Return") == [["xdotool", "key", "Return"]]
    assert tc.build_key("wayland", "ctrl+l") == [["ydotool", "key", "29:1", "38:1", "38:0", "29:0"]]
    assert tc.build_move("x11", 3, 4) == [["xdotool", "mousemove", "3", "4"]]
    assert tc.build_scroll("x11", "down", 3) == [["xdotool", "click", "--repeat", "3", "5"]]
    assert tc.build_screenshot("macos", "/p.png") == [["screencapture", "-x", "/p.png"]]
    assert tc.build_screenshot("wayland", "/p.png", which=lambda n: n == "grim") == [["grim", "/p.png"]]
    assert tc.build_screenshot("wayland", "/p.png", which=lambda n: n == "gnome-screenshot") == [["gnome-screenshot", "-f", "/p.png"]]
    assert tc.build_screenshot("x11", "/p.png", which=lambda n: n == "scrot") == [["scrot", "-o", "/p.png"]]
    with pytest.raises(RuntimeError, match="chưa hỗ trợ"):
        tc.build_click("windows", 1, 1)


def test_missing_tool_messages():
    with pytest.raises(RuntimeError, match="sudo apt install ydotool"):
        tc._need_input("wayland", which=lambda n: None)
    with pytest.raises(RuntimeError, match="sudo apt install xdotool"):
        tc._need_input("x11", which=lambda n: None)
    with pytest.raises(RuntimeError, match="sudo apt install grim"):
        tc.build_screenshot("wayland", "/p", which=lambda n: None)


def test_missing_tool_via_tool(tmp_env, no_real, monkeypatch):
    enable()
    monkeypatch.setattr(tc, "detect_platform", lambda: "wayland")
    with pytest.raises(RuntimeError, match="ydotool"):
        tc.computer_click(ctx_for(tmp_env), 1, 1)
    assert not no_real


def test_coordinates():
    assert tc.validate_xy(5, 6, (100, 100)) == (5, 6)
    assert tc.validate_xy(5.0, 6) == (5, 6)
    assert tc.validate_xy(10**9, -5) == (20000, 0)
    with pytest.raises(ValueError, match="ngoài màn hình"):
        tc.validate_xy(100, 0, (100, 100))
    for bad in ("1", 1.5, True, None):
        with pytest.raises(ValueError):
            tc.validate_xy(bad, 1)


def test_text_limit(tmp_env):
    enable()
    with pytest.raises(ValueError, match="quá dài"):
        tc.computer_type(ctx_for(tmp_env), "a" * 2001)


def test_key_parsing():
    assert tc.parse_keys("Ctrl+Shift+T") == ["ctrl", "shift", "t"]
    assert tc.parse_keys("Return") == ["return"]
    for bad in ("", "ctrl+", "ctrl+rm", "ctrl+shift", "a+b+c+d+e+f"):
        with pytest.raises(ValueError):
            tc.parse_keys(bad)


def png(w, h):
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", w, h) + b"\x08\x02\x00\x00\x00"


def test_png_size_and_screenshot(tmp_env, no_real, monkeypatch):
    assert tc.png_size(png(1920, 1080)) == (1920, 1080)
    with pytest.raises(ValueError):
        tc.png_size(b"nope")
    enable()
    monkeypatch.setattr(tc, "detect_platform", lambda: "macos")
    ctx = ctx_for(tmp_env)

    def fake_run(argv, **kw):
        open(argv[-1], "wb").write(png(800, 600))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(tc.subprocess, "run", fake_run)
    out = tc.computer_screenshot(ctx)
    assert "[image: media/screen-" in out and "800x600" in out
    with pytest.raises(ValueError, match="ngoài màn hình"):
        tc.computer_click(ctx, 900, 10)


def test_registered_and_status(monkeypatch):
    assert {"computer_screenshot", "computer_click", "computer_move", "computer_type", "computer_key", "computer_scroll"} <= set(tools.TOOLS)
    assert all(tools.TOOLS[n].risk == "exec" for n in tools.TOOLS if n.startswith("computer_"))
    monkeypatch.setattr(tc, "detect_platform", lambda: "wayland")
    st = tc.status()
    assert st["platform"] == "wayland" and "ydotool" in st["hint"]
