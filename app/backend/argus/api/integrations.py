"""Quan ly MCP server va API token (giao dien /api, chi nhan request tu localhost)."""
import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import mcp_catalog, mcp_oauth, mcp_probe, mcp_registry, tokens
from ..services import tools as core_tools
from ..services.mcp_client import manager

router = APIRouter()
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,30}$")


@router.get("/mcp")
def mcp_status():
    cfg = cfgmod.load()
    live = manager.status()
    masked = cfgmod.masked(cfg)["mcp_servers"]
    return [{"name": n, "config": masked[n],
             "status": live.get(n, {}).get("status", "disabled" if not c.enabled else "connecting"),
             "error": live.get(n, {}).get("error", ""),
             "oauth": c.oauth, "logged_in": live.get(n, {}).get("logged_in", False), "auth_url": live.get(n, {}).get("auth_url", ""),
             "tools": [{k: t[k] for k in ("name", "full_name", "description", "read_only")} for t in live.get(n, {}).get("tools", [])]}
            for n, c in cfg.mcp_servers.items()]


class McpTest(BaseModel):
    name: str | None = None
    server: cfgmod.McpServerCfg


@router.post("/mcp/test")
def mcp_test(body: McpTest):
    old = cfgmod.load().mcp_servers
    cfgmod.merge_mcp_secrets({"x": body.server}, {"x": old[body.name]} if body.name in old else {})
    return manager.test(body.server)


@router.post("/mcp/{name}/reconnect")
def mcp_reconnect(name: str):
    if name not in cfgmod.load().mcp_servers:
        raise HTTPException(404, "không có server này")
    manager.reconnect(name)
    return {"ok": True}


@router.get("/mcp/catalog")
def mcp_catalog_list():
    return mcp_catalog.catalog()


@router.get("/mcp/registry")
def mcp_registry_search(q: str = "", cursor: str = ""):
    """Tim trong thu vien MCP chinh thuc (chi muc co may chu tu xa). Noi dung do cong dong dang, Argus khong kiem duyet."""
    if len(q.strip()) < 2:
        return {"items": [], "next": ""}
    try:
        return mcp_registry.search(q, cursor)
    except mcp_registry.RegistryError as e:
        raise HTTPException(502, str(e)) from e


class ProbeBody(BaseModel):
    url: str


@router.post("/mcp/probe")
def mcp_probe_url(body: ProbeBody):
    """Cho biet dia chi MCP can dang nhap kieu gi (oauth / token / open) truoc khi them."""
    try:
        core_tools._check_url(body.url)  # khong tham do dia chi noi bo
    except (ValueError, PermissionError, OSError) as e:
        raise HTTPException(400, f"địa chỉ không hợp lệ hoặc là địa chỉ nội bộ: {e}") from e
    return mcp_probe.probe(body.url)


@router.post("/mcp/{name}/oauth/start")
def mcp_oauth_start(name: str, request: Request):
    """Bam 'Dang nhap': tra URL cap quyen cua nha cung cap; giao dien mo no trong tab moi."""
    c = cfgmod.load().mcp_servers.get(name)
    if not c or not c.oauth:
        raise HTTPException(404, "server này không dùng đăng nhập OAuth")
    base = f"{request.url.scheme}://{request.headers.get('host', '127.0.0.1:8787')}"
    return manager.begin_login(name, base)


@router.post("/mcp/{name}/oauth/logout")
def mcp_oauth_logout(name: str):
    if name not in cfgmod.load().mcp_servers:
        raise HTTPException(404, "không có server này")
    manager.logout(name)
    return {"ok": True}


PAGE = """<!doctype html><meta charset="utf-8"><title>Argus Agent</title>
<body style="font-family:system-ui;background:#0b0b0d;color:#e8e8ea;display:grid;place-items:center;height:100vh;margin:0">
<div style="text-align:center;max-width:28rem;padding:1rem"><h2>{title}</h2><p style="color:#9a9aa3">{body}</p></div>"""


@router.get("/mcp/oauth/callback", response_class=HTMLResponse)
def mcp_oauth_callback(state: str = "", code: str = "", error: str = "", error_description: str = "", iss: str = ""):
    """Nha cung cap chuyen huong trinh duyet ve day sau khi nguoi dung cho phep."""
    if mcp_oauth.complete(state, code, error_description or error, iss):
        if not (error or not code):
            return PAGE.format(title="✓ Đã đăng nhập / Signed in", body="Bạn có thể đóng tab này và quay lại Argus. / You can close this tab and return to Argus.")
        return PAGE.format(title="Đăng nhập bị từ chối / Sign-in refused", body=(error_description or error or "")[:200])
    return PAGE.format(title="Phiên đăng nhập đã hết hạn / Sign-in expired", body="Hãy quay lại Argus và bấm “Đăng nhập” lần nữa. / Go back to Argus and press Sign in again.")


# ---------- token
@router.get("/tokens")
def list_tokens():
    return tokens.list_all()


class NewToken(BaseModel):
    name: str
    allow_exec: bool = False


@router.post("/tokens")
def create_token(b: NewToken):
    info, token = tokens.create(b.name, b.allow_exec)
    return {**info, "token": token}


@router.delete("/tokens/{tid}")
def revoke_token(tid: str):
    tokens.revoke(tid)
    return {"ok": True}


@router.get("/integration-info")
def info():
    script = Path(__file__).resolve().parents[1] / "mcp_server.py"
    return {"python": sys.executable, "mcp_server_script": str(script)}
