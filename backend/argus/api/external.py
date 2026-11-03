"""API cong khai cho ung dung ben ngoai (xac thuc bang Bearer token): POST /v1/run."""
import json
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core import config as cfgmod
from ..services import api_run, chat_runner, skills as skillmod, tokens

router = APIRouter(prefix="/v1")


def auth(authorization: str | None = Header(None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    info = tokens.verify(token) if token.startswith("agt_") else None
    if not info:
        raise HTTPException(401, "thiếu hoặc sai API token", headers={"WWW-Authenticate": "Bearer"})
    return info


class RunBody(BaseModel):
    prompt: str = Field(min_length=1, max_length=50_000)
    session: str | None = None
    provider: str | None = None
    exec_policy: str = "deny"
    exec_allow: list[str] = []
    tools: list[str] | None = Field(None, description="Chỉ cho phép các tool này trong lượt chạy")
    timeout: int = Field(300, ge=5, le=900)
    stream: bool = False


@router.get("/status")
def status(_: dict = Depends(auth)):
    cfg = cfgmod.load()
    return {"ok": True, "time": time.time(), "default_provider": cfg.default_provider, "providers": list(cfg.providers)}


@router.get("/skills")
def list_skills(_: dict = Depends(auth)):
    return [{"name": s.name, "description": s.description, "active": s.active} for s in skillmod.discover(cfgmod.load()).values()]


@router.post("/run")
def run(body: RunBody, token: dict = Depends(auth)):
    try:
        approver = api_run.make_approver(body.exec_policy, body.exec_allow, token["allow_exec"])
    except api_run.PolicyError as e:
        raise HTTPException(403, str(e)) from e
    if body.provider and body.provider not in cfgmod.load().providers:
        raise HTTPException(400, f"provider '{body.provider}' không tồn tại")
    if not body.stream:
        return api_run.run_once(body.prompt, session=body.session, provider=body.provider, approver=approver, only_tools=body.tools, timeout=body.timeout)

    def gen():
        for ev in chat_runner.stream_chat(body.session, body.prompt, body.provider, approver_override=approver, source="api", only_tools=body.tools):
            if ev["type"] == "ping":
                yield ": ping\n\n"
            elif ev["type"] != "approval":
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
