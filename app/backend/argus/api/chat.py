import json
import shutil
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import chat_runner, sessions, workfiles

router = APIRouter()


@router.get("/sessions")
def list_sessions(q: str = ""):
    return [s for s in sessions.list_all(q=q) if s["source"] != "subagent"]  # phien cua agent con xem o trang Viec nen


class NewSession(BaseModel):
    title: str = "Hội thoại mới"


@router.post("/sessions")
def create_session(b: NewSession):
    return {"id": sessions.create(b.title)}


@router.get("/sessions/{sid}")
def get_session(sid: str):
    s = sessions.get(sid)
    if not s:
        raise HTTPException(404, "không có phiên này")
    return {**s, "messages": sessions.messages(sid)}


class Truncate(BaseModel):
    index: int


@router.post("/sessions/{sid}/truncate")
def truncate(sid: str, b: Truncate):
    """Xoa tu tin nhan thu `index` tro di (dung cho sua tin nhan / tao lai cau tra loi)."""
    if not sessions.get(sid):
        raise HTTPException(404, "không có phiên này")
    sessions.truncate_from(sid, max(0, b.index))
    return {"ok": True}


class Rename(BaseModel):
    title: str


@router.patch("/sessions/{sid}")
def rename_session(sid: str, body: Rename):
    sessions.rename(sid, body.title)
    return {"ok": True}


@router.delete("/sessions/{sid}")
def delete_session(sid: str):
    sessions.delete(sid)
    shutil.rmtree(workfiles.session_dir(cfgmod.load(), sid), ignore_errors=True)  # thu muc lam viec cua phien
    return {"ok": True}


class ChatBody(BaseModel):
    text: str
    session: str | None = None
    provider: str | None = None
    attachments: list[str] = []
    permission: Literal["default", "readonly", "guarded", "full"] = "default"
    effort: Literal["auto", "low", "medium", "high"] = "auto"


@router.post("/chat")
def chat(body: ChatBody):
    def gen():
        for ev in chat_runner.stream_chat(body.session, body.text, body.provider, attachments=body.attachments, permission=body.permission,
                                            effort=None if body.effort == "auto" else body.effort):
            if ev["type"] == "ping":
                yield ": ping\n\n"
            else:
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class Approval(BaseModel):
    ok: bool


@router.post("/approvals/{aid}")
def approve(aid: str, body: Approval):
    return {"ok": chat_runner.resolve_approval(aid, body.ok)}
