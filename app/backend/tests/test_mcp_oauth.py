"""OAuth cho MCP server tu xa: may chu gia (MCP + may chu cap quyen) di qua toan bo luong cua SDK."""
import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from argus.core import config as cfgmod
from argus.core.db import db
from argus.services import mcp_oauth
from argus.services.mcp_client import manager


class Fake(BaseHTTPRequestHandler):
    base = ""
    registered: list = []
    token_calls: list = []

    def log_message(self, *a):
        pass

    def _send(self, code, obj=None, headers=None):
        body = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        b = Fake.base
        if self.path.startswith("/.well-known/oauth-protected-resource"):
            return self._send(200, {"resource": b + "/mcp", "authorization_servers": [b]})
        if self.path.startswith("/.well-known/oauth-authorization-server"):
            return self._send(200, {"issuer": b, "authorization_endpoint": b + "/authorize", "token_endpoint": b + "/token", "registration_endpoint": b + "/register",
                                    "response_types_supported": ["code"], "grant_types_supported": ["authorization_code", "refresh_token"],
                                    "code_challenge_methods_supported": ["S256"], "token_endpoint_auth_methods_supported": ["none"]})
        self._send(405)

    def do_DELETE(self):
        self._send(200)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode()
        if self.path == "/register":
            info = json.loads(raw)
            Fake.registered.append(info)
            return self._send(201, {**info, "client_id": "cid-123"})
        if self.path == "/token":
            form = parse_qs(raw)
            Fake.token_calls.append({k: v[0] for k, v in form.items()})
            return self._send(200, {"access_token": "tok-abc", "token_type": "Bearer", "expires_in": 3600, "refresh_token": "ref-xyz"})
        if self.path == "/mcp":
            if self.headers.get("Authorization") != "Bearer tok-abc":
                return self._send(401, {"error": "unauthorized"}, {"WWW-Authenticate": f'Bearer resource_metadata="{Fake.base}/.well-known/oauth-protected-resource"'})
            msg = json.loads(raw)
            m, i = msg.get("method"), msg.get("id")
            if m == "initialize":
                return self._send(200, {"jsonrpc": "2.0", "id": i, "result": {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1"}}},
                                  {"Mcp-Session-Id": "s1"})
            if m == "tools/list":
                return self._send(200, {"jsonrpc": "2.0", "id": i, "result": {"tools": [{"name": "echo", "description": "Echo", "inputSchema": {"type": "object", "properties": {}}}]}})
            return self._send(202)
        self._send(404)


@pytest.fixture
def remote(tmp_env):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    Fake.base = f"http://127.0.0.1:{srv.server_port}"
    Fake.registered, Fake.token_calls = [], []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    manager.start()
    yield Fake.base
    manager.stop()
    srv.shutdown()


def wait_for(name, status, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        s = manager.status().get(name, {})
        if s.get("status") == status:
            return s
        time.sleep(0.1)
    raise AssertionError(f"{name}: cho '{status}' nhung dang la {manager.status().get(name)}")


def test_full_login_logout_flow(remote):
    cfg = cfgmod.McpServerCfg(transport="http", url=remote + "/mcp", oauth=True)
    manager.apply({"notion": cfg})
    s = wait_for("notion", "needs_auth")
    assert s["oauth"] and not s["logged_in"] and Fake.registered == []  # chua dang nhap: khong dang ky client vo ich

    res = manager.begin_login("notion", "http://127.0.0.1:8787")
    assert res["ok"] and res["auth_url"].startswith(remote + "/authorize")
    q = parse_qs(urlparse(res["auth_url"]).query)
    assert q["redirect_uri"] == ["http://127.0.0.1:8787/api/mcp/oauth/callback"] and q["code_challenge_method"] == ["S256"] and q["client_id"] == ["cid-123"]
    assert manager.status()["notion"]["auth_url"] == res["auth_url"]  # giao dien doc duoc URL tu trang thai

    assert mcp_oauth.complete(q["state"][0], "the-code")  # nguoi dung bam 'Cho phep' -> callback tra ma ve
    s = wait_for("notion", "connected")
    assert [t["name"] for t in s["tools"]] == ["echo"] and s["logged_in"] and s["auth_url"] == ""
    assert Fake.token_calls[0]["code"] == "the-code" and Fake.token_calls[0]["grant_type"] == "authorization_code" and Fake.token_calls[0]["code_verifier"]

    with db() as c:  # token khong bao gio nam chu thuong trong DB
        raw = c.execute("SELECT value FROM kv WHERE key='mcp_oauth:notion'").fetchone()["value"]
    assert raw.startswith("enc:v1:") and "tok-abc" not in raw and "ref-xyz" not in raw

    manager.logout("notion")
    wait_for("notion", "needs_auth")
    assert not mcp_oauth.Store("notion").logged_in()


def test_restart_reconnects_with_saved_token_without_login(remote):
    cfg = cfgmod.McpServerCfg(transport="http", url=remote + "/mcp", oauth=True)
    manager.apply({"linear": cfg})
    wait_for("linear", "needs_auth")
    url = manager.begin_login("linear", "http://127.0.0.1:8787")["auth_url"]
    mcp_oauth.complete(parse_qs(urlparse(url).query)["state"][0], "c1")
    wait_for("linear", "connected")
    manager.apply({})                      # tat het (nhu khi server dung)
    time.sleep(0.5)
    manager.apply({"linear": cfg})         # khoi dong lai: dung token da luu, khong can dang nhap
    wait_for("linear", "connected")
    assert len(Fake.token_calls) == 1


def test_logged_out_oauth_server_is_not_probed_and_test_endpoint_explains(remote):
    cfg = cfgmod.McpServerCfg(transport="http", url=remote + "/mcp", oauth=True)
    assert "OAuth" in manager.test(cfg)["error"]


def test_flow_not_interactive_needs_auth_and_unknown_state():
    async def go():
        with pytest.raises(mcp_oauth.NeedsAuth):
            await mcp_oauth.Flow(False, lambda u: None).redirect("https://x/authorize?state=s1")
    asyncio.run(go())
    assert mcp_oauth.complete("khong-co-state", "c") is False


def test_flow_error_from_provider_is_reported():
    async def go():
        urls = []
        f = mcp_oauth.Flow(True, urls.append)
        await f.redirect("https://x/authorize?state=sErr")
        loop = asyncio.get_running_loop()
        loop.call_later(0.05, lambda: mcp_oauth.complete("sErr", error="access_denied"))
        with pytest.raises(RuntimeError, match="access_denied"):
            await f.callback()
        assert urls == ["https://x/authorize?state=sErr"]
    asyncio.run(go())


def test_store_changes_redirect_base_drops_old_client(tmp_env):
    async def go():
        s = mcp_oauth.Store("x")
        s.use_redirect_base("http://127.0.0.1:8787")
        from mcp.shared.auth import OAuthToken
        await s.set_tokens(OAuthToken(access_token="a", token_type="Bearer"))
        assert s.logged_in()
        s.use_redirect_base("http://127.0.0.1:8787")
        assert s.logged_in()                       # cung dia chi: giu nguyen
        s.use_redirect_base("http://127.0.0.1:9999")
        assert not s.logged_in()                   # doi cong: client cu khong con hop le
    asyncio.run(go())
