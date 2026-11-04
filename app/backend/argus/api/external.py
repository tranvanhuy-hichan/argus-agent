"""API cong khai cho ung dung ben ngoai (xac thuc bang Bearer token): POST /v1/run."""
import json
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core import config as cfgmod
from ..services import api_run, chat_runner, knowledge, skills as skillmod, tokens

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


# ---------- tài liệu: thêm, xem, tìm, hỏi đáp
def _docs_write(token: dict) -> None:
    if not token.get("allow_docs"):
        raise HTTPException(403, "token này không được cấp quyền thêm/xóa tài liệu (allow_docs)")


def _doc(d: dict) -> dict:
    return {k: d.get(k) for k in ("id", "name", "ext", "size", "pages", "chunks", "status", "note", "added")}


@router.get("/documents")
def list_documents(_: dict = Depends(auth)):
    return [_doc(d) for d in knowledge.list_docs()]


@router.post("/documents")
async def upload_document(name: str, request: Request, token: dict = Depends(auth)):
    """Gửi nội dung file thô trong thân yêu cầu, tên file ở tham số `name`. Việc đọc và lập chỉ mục chạy nền (xem `status`)."""
    _docs_write(token)
    if int(request.headers.get("content-length") or 0) > knowledge.MAX_UPLOAD:
        raise HTTPException(413, "file quá lớn (tối đa 60MB)")
    try:
        return _doc(knowledge.add_bytes(name, await request.body(), "api"))
    except knowledge.KnowledgeError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/documents/{did}")
def delete_document(did: str, token: dict = Depends(auth)):
    _docs_write(token)
    if not knowledge.delete(did):
        raise HTTPException(404, "không có tài liệu này")
    return {"ok": True}


class DocSearchBody(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(6, ge=1, le=15)


@router.post("/documents/search")
def search_documents(body: DocSearchBody, _: dict = Depends(auth)):
    """Chỉ tìm kiếm, không gọi model: trả các đoạn khớp nhất kèm tên file và vị trí."""
    return [{k: h[k] for k in ("doc_id", "name", "loc", "text", "score")} for h in knowledge.search(body.query, body.limit)]


class DocAskBody(BaseModel):
    question: str = Field(min_length=1, max_length=20_000)
    session: str | None = None
    provider: str | None = None
    timeout: int = Field(300, ge=5, le=900)


@router.post("/documents/ask")
def ask_documents(body: DocAskBody, _: dict = Depends(auth)):
    """Hỏi đáp trên kho tài liệu: câu trả lời kèm danh sách nguồn (tên file, vị trí). Dùng lượt gọi model đang cấu hình."""
    if not knowledge.has_docs():
        raise HTTPException(400, "chưa có tài liệu nào sẵn sàng")
    if body.provider and body.provider not in cfgmod.load().providers:
        raise HTTPException(400, f"provider '{body.provider}' không tồn tại")
    r = api_run.run_once(body.question, session=body.session, provider=body.provider, approver=lambda kind, detail: False, only_tools=["kb_search"],
                         timeout=body.timeout, docs=True)
    answer, sources = knowledge.plain_sources(r["output"])
    return {"answer": answer, "sources": sources, "session": r["session"], "provider": r["provider"], "usage": r["usage"], "error": r["error"], "timed_out": r["timed_out"]}
