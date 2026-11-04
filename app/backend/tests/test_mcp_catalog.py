"""Danh muc dich vu MCP, tim trong thu vien chinh thuc va tham do loai dang nhap."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from argus.services import mcp_catalog, mcp_probe, mcp_registry

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,30}$")


def test_catalog_entries_are_well_formed():
    ids = [s["id"] for s in mcp_catalog.SERVICES]
    assert len(ids) == len(set(ids)) and len(ids) >= 40
    groups = {g["id"] for g in mcp_catalog.GROUPS}
    for s in mcp_catalog.SERVICES:
        assert NAME_RE.match(s["id"]), s["id"]  # dung lam ten server MCP
        assert s["url"].startswith("https://") and s["group"] in groups and s["auth"] in ("oauth", "open", "token")
        assert s["desc"]["vi"] and s["desc"]["en"] and re.fullmatch(r"[0-9A-Fa-f]{6}", s["color"])
        assert s["transport"] == ("sse" if s["url"].endswith("/sse") else "http")
        assert (s["auth"] == "token") == ("token" in s)
    for g in mcp_catalog.GROUPS:
        assert any(s["group"] == g["id"] for s in mcp_catalog.SERVICES), g  # khong co nhom rong
    assert {"github", "vercel", "notion", "stripe"} <= set(ids)
    assert next(s for s in mcp_catalog.SERVICES if s["id"] == "github")["auth"] == "token"


def test_registry_keeps_only_remote_servers_and_flags_community(monkeypatch):
    payload = {"servers": [
        {"server": {"name": "com.stripe/mcp", "title": "Stripe", "description": "x", "remotes": [{"type": "streamable-http", "url": "https://mcp.stripe.com"}]}},
        {"server": {"name": "io.github.someone/tool", "description": "y", "remotes": [{"type": "sse", "url": "https://x.example/sse", "headers": [{"name": "Authorization", "isSecret": True}]}]}},
        {"server": {"name": "com.local/only-stdio", "packages": [{"registryType": "npm"}]}},
        {"server": {"name": "eu.templ/pay", "remotes": [{"type": "streamable-http", "url": "https://n.eu/mcp/{token}"}]}},
        {"server": {"name": "com.stripe/mcp", "remotes": [{"type": "streamable-http", "url": "https://mcp.stripe.com"}]}},  # ban cu cung ten: bo trung
    ], "metadata": {"nextCursor": "abc"}}

    class R:
        def raise_for_status(self): pass
        def json(self): return payload

    seen = {}
    monkeypatch.setattr(mcp_registry.httpx, "get", lambda url, params=None, timeout=None: (seen.update(params=params), R())[1])
    out = mcp_registry.search("stripe", "cur1")
    assert seen["params"] == {"search": "stripe", "limit": 30, "cursor": "cur1"} and out["next"] == "abc"
    names = [i["id"] for i in out["items"]]
    assert names == ["com.stripe/mcp", "io.github.someone/tool"]  # bo muc chi co goi cai dat, muc URL co {bien}, va ban trung
    stripe, gh = out["items"]
    assert stripe["transport"] == "http" and not stripe["community"] and stripe["publisher"] == "com.stripe"
    assert gh["transport"] == "sse" and gh["community"] and gh["needs_header"] == ["Authorization"]


def test_registry_error_is_reported(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("no network")
    monkeypatch.setattr(mcp_registry.httpx, "get", boom)
    with pytest.raises(mcp_registry.RegistryError, match="ConnectError"):
        mcp_registry.search("x")


class Fake(BaseHTTPRequestHandler):
    base = ""

    def log_message(self, *a): pass

    def _j(self, code, obj=None, headers=None):
        b = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        b, p = Fake.base, self.path
        if p == "/open":
            return self._j(200, {"jsonrpc": "2.0", "id": 1, "result": {}})
        if p in ("/oauth", "/nodcr"):
            return self._j(401, {}, {"WWW-Authenticate": f'Bearer resource_metadata="{b}/prm{p}"'})
        if p == "/token":
            return self._j(401, {})
        self._j(500, {})

    def do_GET(self):
        b, p = Fake.base, self.path
        if p.startswith("/prm/"):
            return self._j(200, {"resource": b + p[4:], "authorization_servers": [f"{b}/as{p[4:]}"]})
        if p.startswith("/.well-known/oauth-authorization-server/as/"):
            meta = {"issuer": f"{b}/as/{p.rsplit('/', 1)[-1]}", "authorization_endpoint": b + "/authorize", "token_endpoint": b + "/tokenx"}
            if p.endswith("/oauth"):
                meta["registration_endpoint"] = b + "/register"
            return self._j(200, meta)
        self._j(404, {})


@pytest.fixture
def fake_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    Fake.base = f"http://127.0.0.1:{srv.server_port}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield Fake.base
    srv.shutdown()


@pytest.mark.parametrize("path,kind", [("/open", "open"), ("/oauth", "oauth"), ("/nodcr", "oauth-manual"), ("/token", "token"), ("/boom", "down")])
def test_probe_classifies_auth_kind(fake_server, path, kind):
    assert mcp_probe.probe(fake_server + path)["kind"] == kind


def test_probe_unreachable_host_is_down():
    assert mcp_probe.probe("http://127.0.0.1:1/mcp")["kind"] == "down"


@pytest.fixture
def client(tmp_env):
    from fastapi.testclient import TestClient

    from argus.main import app
    return TestClient(app)


def test_api_catalog_and_short_registry_query(client):
    d = client.get("/api/mcp/catalog").json()
    assert len(d["services"]) >= 40 and d["groups"][0]["label"]["en"]
    assert client.get("/api/mcp/registry?q=a").json() == {"items": [], "next": ""}  # truy van qua ngan: khong goi mang


def test_api_probe_rejects_internal_addresses(client):
    assert client.post("/api/mcp/probe", json={"url": "http://127.0.0.1:9/mcp"}).status_code == 400
    assert client.post("/api/mcp/probe", json={"url": "http://192.168.1.10/mcp"}).status_code == 400
    assert client.post("/api/mcp/probe", json={"url": "ftp://example.com/x"}).status_code == 400


def test_new_plugins_are_in_catalog_with_valid_shape():
    by_id = {s["id"]: s for s in mcp_catalog.SERVICES}
    assert len(by_id) == len(mcp_catalog.SERVICES)  # id không trùng
    groups = {g["id"] for g in mcp_catalog.GROUPS}
    for sid in ("buildkite", "betterstack", "grafana", "globalping", "aws-knowledge", "alltrails", "amplitude", "cloudinary", "clay", "close", "shopify", "godaddy"):
        s = by_id[sid]
        assert s["url"].startswith("https://") and s["group"] in groups and s["auth"] in ("oauth", "open", "token") and s["desc"]["vi"] and s["desc"]["en"]
    assert by_id["godaddy"]["auth"] == "open" and by_id["buildkite"]["auth"] == "oauth"
