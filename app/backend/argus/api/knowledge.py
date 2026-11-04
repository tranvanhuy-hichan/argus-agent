"""Kho tài liệu: thêm file hoặc thư mục, xem trạng thái lập chỉ mục, thử tìm, xóa, tải lại bản gốc."""
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import embeddings, jobs, knowledge

AUTO = True
router = APIRouter()


@router.get("/knowledge")
def list_docs():
    cfg = cfgmod.load()
    e = None
    try:
        e = embeddings.get_embedder(cfg)
    except Exception:  # noqa: BLE001
        pass
    return {"docs": knowledge.list_docs(), "stats": knowledge.stats(), "supported": sorted(knowledge.SUPPORTED), "semantic": e.kind if e else None}


@router.post("/knowledge/upload")
async def upload(name: str, request: Request):
    if int(request.headers.get("content-length") or 0) > knowledge.MAX_UPLOAD:
        raise HTTPException(413, "file quá lớn (tối đa 60MB)")
    try:
        return knowledge.add_bytes(name, await request.body())
    except knowledge.KnowledgeError as e:
        raise HTTPException(400, str(e)) from e


class FolderBody(BaseModel):
    path: str


@router.post("/knowledge/folder")
def add_folder(b: FolderBody):
    p = Path(b.path).expanduser()
    try:
        return knowledge.add_folder(p.resolve())
    except (knowledge.KnowledgeError, OSError) as e:
        raise HTTPException(400, str(e)) from e


class SearchBody(BaseModel):
    query: str
    limit: int = 6


@router.post("/knowledge/search")
def search(b: SearchBody):
    if not b.query.strip():
        raise HTTPException(400, "nhập nội dung cần tìm")
    return knowledge.search(b.query, b.limit)


class AnalyzeBody(BaseModel):
    focus: str = ""


@router.post("/knowledge/analyze")
def analyze(b: AnalyzeBody):
    """Phân tích các tài liệu đã thêm và đề xuất phương án: chạy như một việc nền, kết quả xem ở trang Tác vụ."""
    if not knowledge.has_docs():
        raise HTTPException(400, "chưa có tài liệu nào sẵn sàng để phân tích")
    focus = b.focus.strip() or "Phân tích các tài liệu này và đề xuất phương án thực hiện."
    return {"id": jobs.start_background(focus[:2000], kind="analysis", title="Phân tích tài liệu: " + focus[:50], permission="readonly")}


@router.delete("/knowledge/{did}")
def delete(did: str):
    if not knowledge.delete(did):
        raise HTTPException(404, "không có tài liệu này")
    return {"ok": True}


@router.get("/knowledge/{did}/file")
def file(did: str):
    d = knowledge.get(did)
    if not d or not d.get("path") or not Path(d["path"]).is_file():
        raise HTTPException(404, "không còn file gốc")
    return FileResponse(d["path"], media_type=mimetypes.guess_type(d["name"])[0] or "application/octet-stream", filename=Path(d["name"]).name,
                        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})
