import re
import time

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import mcp_client, providers, tools

router = APIRouter()
EDITABLE_FILES = {"SOUL.md", "USER.md", "MEMORY.md"}


@router.get("/health")
def health():
    return {"ok": True, "time": time.time()}


@router.get("/config")
def get_config():
    cfg = cfgmod.load()
    return {"config": cfgmod.masked(cfg), "tools": [{"name": t.name, "description": t.description, "risk": t.risk} for t in tools.TOOLS.values()]}


@router.put("/config")
def put_config(body: dict):
    new = cfgmod.merge_secrets(cfgmod.Config.model_validate(body), cfgmod.load())
    if new.default_provider not in new.providers:
        raise HTTPException(400, "provider mac dinh khong ton tai")
    new.fallback = [n for n in new.fallback if n in new.providers and n != new.default_provider]
    bad = [n for n in new.mcp_servers if not re.match(r"^[a-z0-9][a-z0-9_-]{0,30}$", n)]
    if bad:
        raise HTTPException(400, f"tên MCP server chỉ gồm a-z, 0-9, - và _: {bad[0]}")
    cfgmod.save(new)
    mcp_client.manager.apply(new.mcp_servers)
    return {"ok": True}


class TestBody(BaseModel):
    provider: cfgmod.ProviderCfg | None = None


@router.post("/providers/{name}/test")
def test_provider(name: str, body: TestBody):
    cfg = cfgmod.load()
    pcfg = body.provider or cfg.providers.get(name)
    if not pcfg:
        raise HTTPException(404, "khong co provider")
    if pcfg.api_key == cfgmod.MASK and name in cfg.providers:
        pcfg.api_key = cfg.providers[name].api_key
    t0 = time.time()
    try:
        reply = "".join(e["text"] for e in providers.make_provider(pcfg).stream([{"role": "user", "content": "Tra loi dung 1 tu: ok"}], []) if e["type"] == "delta")
        return {"ok": True, "reply": reply[:120], "latency_ms": int((time.time() - t0) * 1000)}
    except providers.ProviderError as e:
        return {"ok": False, "error": str(e)}


@router.post("/providers/models")
def provider_models(body: TestBody):
    pcfg = body.provider
    if not pcfg:
        raise HTTPException(400, "thiếu cấu hình provider")
    saved = next((p for p in cfgmod.load().providers.values() if p.base_url == pcfg.base_url and p.type == pcfg.type), None)
    if pcfg.api_key == cfgmod.MASK:
        pcfg.api_key = saved.api_key if saved else ""
    try:
        return {"ok": True, "models": providers.list_models(pcfg)}
    except providers.ProviderError as e:
        return {"ok": False, "error": str(e), "models": []}


@router.get("/ollama/models")
def ollama_models(base_url: str = "http://localhost:11434"):
    base = re.sub(r"/v1/?$", "", base_url).rstrip("/")
    try:
        r = httpx.get(base + "/api/tags", timeout=3)
        return {"models": [m["name"] for m in r.json().get("models", [])]}
    except (httpx.HTTPError, ValueError):
        return {"models": []}


@router.get("/workspace/{name}")
def get_file(name: str):
    if name not in EDITABLE_FILES:
        raise HTTPException(403, "khong duoc phep")
    p = cfgmod.load().workspace_path() / name
    return {"content": p.read_text() if p.exists() else ""}


class FileBody(BaseModel):
    content: str


@router.put("/workspace/{name}")
def put_file(name: str, body: FileBody):
    if name not in EDITABLE_FILES:
        raise HTTPException(403, "khong duoc phep")
    ws = cfgmod.load().workspace_path()
    ws.mkdir(parents=True, exist_ok=True)
    (ws / name).write_text(body.content)
    return {"ok": True}
