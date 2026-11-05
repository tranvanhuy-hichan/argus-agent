import json
import shutil
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import chat_runner, sessions, usage, workfiles

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


@router.get("/sessions/{sid}/usage")
def session_usage(sid: str):
    """Token đã dùng trong phiên và ngữ cảnh còn lại của model đang dùng."""
    if not sessions.get(sid):
        raise HTTPException(404, "không có phiên này")
    return usage.session_usage(sid, cfgmod.load().providers)


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


class PinBody(BaseModel):
    pinned: bool = True


@router.patch("/sessions/{sid}")
def rename_session(sid: str, body: Rename):
    sessions.rename(sid, body.title)
    return {"ok": True}


@router.post("/sessions/{sid}/pin")
def pin_session(sid: str, body: PinBody):
    sessions.pin(sid, body.pinned)
    return {"ok": True}


@router.delete("/sessions/{sid}")
def delete_session(sid: str):
    sessions.delete(sid)
    shutil.rmtree(workfiles.session_dir(cfgmod.load(), sid), ignore_errors=True)  # thu muc lam viec cua phien
    return {"ok": True}


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse(ev: dict) -> str:
    return ": ping\n\n" if ev["type"] == "ping" else f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"


class ChatBody(BaseModel):
    text: str
    session: str | None = None
    provider: str | None = None
    attachments: list[str] = []
    permission: Literal["default", "readonly", "guarded", "full"] = "default"
    effort: Literal["auto", "low", "medium", "high", "thinking"] = "auto"
    docs: bool = False  # "Hỏi từ tài liệu": chỉ trả lời dựa trên kho tài liệu, có nguồn
    temperature: float | None = None
    max_tokens: int | None = None


@router.post("/chat")
def chat(body: ChatBody):
    def gen():
        for ev in chat_runner.stream_chat(body.session, body.text, body.provider, attachments=body.attachments, permission=body.permission,
                                            effort=None if body.effort == "auto" else body.effort, docs=body.docs,
                                            temperature=body.temperature, max_tokens=body.max_tokens, detach=True):
            yield _sse(ev)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/sessions/{sid}/run")
def run_state(sid: str):
    """Phiên có đang chạy agent không (giao diện dùng để nối lại sau khi đổi trang)."""
    return chat_runner.state(sid)


@router.get("/sessions/{sid}/attach")
def attach(sid: str, start: int = 0):
    """Nối lại luồng sự kiện của lượt đang chạy, phát lại từ sự kiện thứ `start`."""
    def gen():
        for ev in chat_runner.attach(sid, max(0, start)):
            yield _sse(ev)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/sessions/{sid}/stop")
def stop_run(sid: str):
    return {"ok": chat_runner.stop(sid)}


class Approval(BaseModel):
    ok: bool


@router.post("/approvals/{aid}")
def approve(aid: str, body: Approval):
    return {"ok": chat_runner.resolve_approval(aid, body.ok)}


class Answer(BaseModel):
    answer: str


@router.post("/questions/{qid}")
def answer_question(qid: str, body: Answer):
    return {"ok": chat_runner.answer_question(qid, body.answer)}


@router.get("/sessions/{sid}/checkpoint")
def checkpoint_state(sid: str):
    from ..services import checkpoints
    return {"files": checkpoints.last(sid)}


@router.post("/sessions/{sid}/undo")
def undo_last_turn(sid: str):
    """Hoàn tác các file agent đã ghi/sửa trong lượt gần nhất (không gồm thay đổi do lệnh shell)."""
    from ..services import checkpoints
    if chat_runner.active(sid):
        raise HTTPException(409, "agent đang chạy, hãy dừng rồi hoàn tác")
    return {"restored": checkpoints.undo(sid)}
