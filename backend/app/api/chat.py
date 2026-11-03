import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services import chat_runner, sessions

router = APIRouter()


@router.get("/sessions")
def list_sessions():
    return sessions.list_all()


@router.get("/sessions/{sid}")
def get_session(sid: str):
    s = sessions.get(sid)
    if not s:
        raise HTTPException(404, "khong co phien nay")
    return {**s, "messages": [m for m in sessions.messages(sid) if m["role"] != "system"]}


class Rename(BaseModel):
    title: str


@router.patch("/sessions/{sid}")
def rename_session(sid: str, body: Rename):
    sessions.rename(sid, body.title)
    return {"ok": True}


@router.delete("/sessions/{sid}")
def delete_session(sid: str):
    sessions.delete(sid)
    return {"ok": True}


class ChatBody(BaseModel):
    text: str
    session: str | None = None
    provider: str | None = None


@router.post("/chat")
def chat(body: ChatBody):
    def gen():
        for ev in chat_runner.stream_chat(body.session, body.text, body.provider):
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
