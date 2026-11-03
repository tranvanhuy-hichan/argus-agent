import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from argus.core import config as cfgmod
from argus.services import tools
from argus.services.browser import find_chromium, manager
from argus.services.tools_browser import validate_url

PAGE1 = b"""<!doctype html><html><head><title>Trang thu</title></head><body>
<h1>Dang nhap</h1>
<label for=u>Email</label><input id=u type=text>
<label for=p>Mat khau</label><input id=p type=password>
<label><input type=checkbox id=c> Nho toi</label>
<button id=go onclick="document.getElementById('out').textContent='Xin chao '+document.getElementById('u').value">Gui</button>
<button onclick="alert('canh bao!')">Bao</button>
<a href="/two">Trang hai</a><div id=out></div></body></html>"""
PAGE2 = b"<html><head><title>Hai</title></head><body><p>Day la trang hai</p></body></html>"


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGE2 if self.path.startswith("/two") else PAGE1
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _can_launch() -> bool:
    if not find_chromium():
        return False
    try:
        import playwright  # noqa: F401
    except Exception:
        return False
    return True


def test_validate_url():
    validate_url("https://example.com/x", False, resolve=False)
    validate_url("about:blank", False)
    for bad in ("file:///etc/passwd", "chrome://settings", "about:config", "javascript:alert(1)", "ftp://x.com", "http://localhost:8000", "http://127.0.0.1/", "http://10.0.0.5/", "http://169.254.169.254/"):
        with pytest.raises((ValueError, PermissionError)):
            validate_url(bad, False, resolve=False)
    validate_url("http://127.0.0.1:80/", True)
    with pytest.raises(ValueError):
        validate_url("file:///etc/passwd", True)


pytestmark_browser = pytest.mark.skipif(not _can_launch(), reason="khong co Chromium/Playwright")


@pytest.fixture
def web(tmp_env):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cfg = cfgmod.load()
    cfg.browser.allow_private = True
    cfgmod.save(cfg)
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    manager.shutdown()


def _ctx(tmp_env, sid="t1", **kw):
    ws = tmp_env / "workspace"
    return tools.ToolContext(workspace=ws, session_id=sid, **kw)


def _ref(text: str, needle: str) -> str:
    m = re.search(r"\[(e\d+)\][^\n]*" + needle, text)
    assert m, f"khong thay {needle} trong:\n{text}"
    return m.group(1)


@pytestmark_browser
def test_flow(tmp_env, web):
    ctx = _ctx(tmp_env)
    out, ok = tools.call(ctx, "browser_open", {"url": web + "/"})
    assert ok, out
    assert "Trang thu" in out and "Dang nhap" in out
    u, p = _ref(out, 'textbox "Email"'), _ref(out, 'textbox "Mat khau"')
    go, link = _ref(out, 'button "Gui"'), _ref(out, 'link "Trang hai" -> /two')
    assert "checkbox" in out and "unchecked" in out
    out, ok = tools.call(ctx, "browser_type", {"ref": u, "text": "an@x.vn"})
    assert ok and 'value="an@x.vn"' in out
    out, ok = tools.call(ctx, "browser_type", {"ref": p, "text": "bimat123"})
    assert ok and "bimat123" not in out and "••••" in out
    out, ok = tools.call(ctx, "browser_click", {"ref": go})
    assert ok and "Xin chao an@x.vn" in out
    out, ok = tools.call(ctx, "browser_click", {"ref": _ref(out, 'button "Bao"')})
    assert ok and "canh bao!" in out
    out, ok = tools.call(ctx, "browser_snapshot", {})
    out, ok = tools.call(ctx, "browser_click", {"ref": _ref(out, "link")})
    assert ok and "Day la trang hai" in out
    out, ok = tools.call(ctx, "browser_back", {})
    assert ok and "Dang nhap" in out
    out, ok = tools.call(ctx, "browser_text", {})
    assert ok and "Dang nhap" in out
    out, ok = tools.call(ctx, "browser_scroll", {"direction": "down"})
    assert ok
    out, ok = tools.call(ctx, "browser_screenshot", {})
    assert ok and "[image: media/browser-1.png]" in out
    assert (ctx.workdir / "media" / "browser-1.png").read_bytes().startswith(b"\x89PNG")
    out, ok = tools.call(ctx, "browser_click", {"ref": "e999"})
    assert not ok and "browser_snapshot" in out
    out, ok = tools.call(ctx, "browser_close", {})
    assert ok


@pytestmark_browser
def test_guarded(tmp_env, web):
    asked = []
    ctx = _ctx(tmp_env, "t2", confirm_writes=True, approver=lambda k, d: asked.append((k, d)) or False)
    out, ok = tools.call(ctx, "browser_open", {"url": web + "/"})
    assert ok and not asked
    out, ok = tools.call(ctx, "browser_click", {"ref": _ref(out, 'button "Gui"')})
    assert ok and out.startswith("KHÔNG THỰC HIỆN")
    assert asked and asked[0][0] == "browser" and web in asked[0][1]
    out, ok = tools.call(ctx, "browser_press", {"key": "Tab"})
    assert out.startswith("KHÔNG THỰC HIỆN")


def test_private_blocked(tmp_env):
    cfg = cfgmod.load()
    cfg.browser.allow_private = False
    cfgmod.save(cfg)
    out, ok = tools.call(_ctx(tmp_env), "browser_open", {"url": "http://127.0.0.1:9/"})
    assert not ok and "nội bộ" in out


def test_disabled(tmp_env):
    cfg = cfgmod.load()
    cfg.browser.enabled = False
    cfgmod.save(cfg)
    out, ok = tools.call(_ctx(tmp_env), "browser_snapshot", {})
    assert not ok and "tắt" in out
