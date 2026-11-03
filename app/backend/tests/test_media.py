import base64
import json
import struct
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from argus.core import config as cfgmod
from argus.services import tools, tools_media
from argus.services.tools import DENIED, ToolContext


def make_png() -> bytes:
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b"")


PNG = make_png()


@pytest.fixture
def server():
    state = {"reply": None, "reqs": []}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            state["reqs"].append((self.path, dict(self.headers), body))
            out = json.dumps(state["reply"](self.path, body) if callable(state["reply"]) else state["reply"]).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{s.server_port}"
    yield state
    s.shutdown()


def ctx_for(tmp_env, **kw):
    wd = tmp_env / "workspace"
    return ToolContext(workspace=wd, approver=kw.pop("approver", lambda k, d: True), **kw)


def setup_cfg(**kw):
    cfg = cfgmod.load()
    for k, v in kw.get("providers", {}).items():
        cfg.providers[k] = v
    for k, v in kw.get("media", {}).items():
        setattr(cfg.media, k, v)
    cfgmod.save(cfg)


def gem(url=""):
    return cfgmod.ProviderCfg(base_url="https://generativelanguage.googleapis.com/v1beta/openai", api_key="K", model="m")


def test_gemini_ok(tmp_env, server, monkeypatch):
    monkeypatch.setattr(tools_media, "gemini_root", server["url"])
    server["reply"] = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(PNG).decode()}}]}}]}
    setup_cfg(providers={"g": gem()})
    ctx = ctx_for(tmp_env)
    out = tools_media.generate_image(ctx, "một con mèo")
    assert "[image: media/image-" in out and ".png]" in out
    f = ctx.workdir / out.split("[image: ")[1].split("]")[0]
    assert f.read_bytes().startswith(b"\x89PNG")
    path, hdr, body = server["reqs"][0]
    assert path.endswith("/models/gemini-2.5-flash-image:generateContent") and hdr["x-goog-api-key"] == "K"
    assert body["generationConfig"]["responseModalities"] == ["IMAGE"]


def test_gemini_text_only_and_blocked(tmp_env, server, monkeypatch):
    monkeypatch.setattr(tools_media, "gemini_root", server["url"])
    setup_cfg(providers={"g": gem()})
    server["reply"] = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "Xin lỗi tôi không vẽ được"}]}}]}
    with pytest.raises(RuntimeError, match="Xin lỗi tôi không vẽ được"):
        tools_media.generate_image(ctx_for(tmp_env), "x")
    server["reply"] = {"promptFeedback": {"blockReason": "SAFETY"}}
    with pytest.raises(RuntimeError, match="SAFETY"):
        tools_media.generate_image(ctx_for(tmp_env), "x")


def test_not_an_image(tmp_env, server, monkeypatch):
    monkeypatch.setattr(tools_media, "gemini_root", server["url"])
    setup_cfg(providers={"g": gem()})
    server["reply"] = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b"hello").decode()}}]}}]}
    with pytest.raises(ValueError, match="không phải ảnh"):
        tools_media.generate_image(ctx_for(tmp_env), "x")


def test_openai_b64_and_url(tmp_env, server):
    setup_cfg(providers={"o": cfgmod.ProviderCfg(base_url=server["url"], api_key="K")}, media={"image_provider": "o", "image_model": "dall-e-3"})
    server["reply"] = {"data": [{"b64_json": base64.b64encode(PNG).decode()}]}
    out = tools_media.generate_image(ctx_for(tmp_env), "x", size="512x512")
    assert "[image: media/" in out
    path, hdr, body = server["reqs"][0]
    assert path == "/images/generations" and body["size"] == "512x512" and body["response_format"] == "b64_json" and body["model"] == "dall-e-3"
    server["reply"] = {"data": [{"url": server["url"] + "/x.png"}]}
    with pytest.raises(PermissionError):  # dia chi noi bo bi chan
        tools_media.generate_image(ctx_for(tmp_env), "x")


def test_guarded_denied(tmp_env, server, monkeypatch):
    monkeypatch.setattr(tools_media, "gemini_root", server["url"])
    setup_cfg(providers={"g": gem()})
    asked = []
    ctx = ctx_for(tmp_env, confirm_writes=True, approver=lambda k, d: asked.append((k, d)) or False)
    assert tools_media.generate_image(ctx, "mèo") == DENIED
    assert asked == [("image", "mèo")] and not server["reqs"]


def test_no_provider(tmp_env):
    with pytest.raises(ValueError, match="Chưa có provider sinh ảnh"):
        tools_media.generate_image(ctx_for(tmp_env), "x")


def vision_reply(server):
    server["reply"] = {"choices": [{"delta": {"content": "một pixel đỏ"}, "message": {"content": "một pixel đỏ"}, "finish_reason": "stop"}]}


def test_view_image(tmp_env, server, monkeypatch):
    seen = {}

    class Fake:
        def __init__(self, cfg):
            seen["cfg"] = cfg

        def stream(self, messages, tools_):
            seen["messages"] = messages
            yield {"type": "delta", "text": "một "}
            yield {"type": "delta", "text": "pixel đỏ"}
            yield {"type": "final"}

    monkeypatch.setattr(tools_media.providers, "make_provider", Fake)
    p_novis = cfgmod.ProviderCfg(base_url="http://a", model="novis")
    p_vis = cfgmod.ProviderCfg(base_url="http://b", model="vis", vision=True)
    p_vis2 = cfgmod.ProviderCfg(base_url="http://c", model="vis2", vision=True)
    setup_cfg(providers={"n": p_novis, "v": p_vis, "w": p_vis2})
    ctx = ctx_for(tmp_env)
    (ctx.workdir / "a.png").write_bytes(PNG)
    out = tools_media.view_image(ctx, "a.png", "màu gì?")
    assert out == "một pixel đỏ"
    m = seen["messages"][0]
    assert m["content"] == "màu gì?" and m["images"] == [{"mime": "image/png", "b64": base64.b64encode(PNG).decode()}]
    assert seen["cfg"].model == "vis"  # provider vision dau tien
    ctx.provider = "w"
    tools_media.view_image(ctx, "a.png")
    assert seen["cfg"].model == "vis2" and seen["messages"][0]["content"] == "Mô tả chi tiết ảnh này"
    setup_cfg(media={"vision_provider": "v"})
    tools_media.view_image(ctx, "a.png")
    assert seen["cfg"].model == "vis"


def test_view_image_errors(tmp_env):
    setup_cfg(providers={"n": cfgmod.ProviderCfg(base_url="http://a")})
    ctx = ctx_for(tmp_env)
    (ctx.workdir / "a.png").write_bytes(PNG)
    with pytest.raises(ValueError, match="Model hiểu được ảnh"):
        tools_media.view_image(ctx, "a.png")
    (ctx.workdir / "t.png").write_text("not an image")
    setup_cfg(providers={"v": cfgmod.ProviderCfg(base_url="http://a", vision=True)})
    with pytest.raises(ValueError, match="không phải ảnh"):
        tools_media.view_image(ctx, "t.png")
    with pytest.raises(PermissionError):  # ra ngoai workspace -> bi tu choi
        tools_media.view_image(ctx_for(tmp_env, approver=lambda k, d: False), "../../etc/passwd")


def test_registered_and_status(tmp_env):
    assert {"generate_image", "view_image"} <= set(tools.TOOLS)
    st = tools_media.status()
    assert st["image_ok"] is False and st["vision_ok"] is False
