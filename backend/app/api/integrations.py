"""Quan ly MCP server va API token (giao dien /api, chi nhan request tu localhost)."""
import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import tokens
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
