"""File trong thu muc lam viec cua phien (panel Workspace): liet ke, xem, sua, xoa, tai len, tai xuong."""
import mimetypes
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import sessions, workfiles

router = APIRouter()
MAX_TEXT = 1_000_000
# HTML do agent sinh ra co the chua script: sandbox CSP bien no thanh origin rieng, khong goi duoc /api
PREVIEW_CSP = "sandbox; default-src 'none'; img-src data: 'self'; style-src 'unsafe-inline'; font-src data:"


def _base(sid: str):
    if not sessions.get(sid):
        raise HTTPException(404, "không có phiên này")
    return workfiles.session_dir(cfgmod.load(), sid)


def _path(sid: str, rel: str):
    try:
        return workfiles.safe_path(_base(sid), rel)
    except workfiles.PathError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/sessions/{sid}/files")
def list_files(sid: str):
    return workfiles.tree(_base(sid))


@router.get("/sessions/{sid}/file")
def read_file(sid: str, path: str, raw: bool = False):
    p = _path(sid, path)
    if not p.is_file():
        raise HTTPException(404, "không có file")
    if raw:
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        return FileResponse(p, media_type=mime, headers={"Content-Security-Policy": PREVIEW_CSP, "X-Content-Type-Options": "nosniff"})
    size = p.stat().st_size
    head = p.read_bytes()[:MAX_TEXT]
    if b"\x00" in head[:4096]:
        return {"binary": True, "size": size, "content": ""}
    return {"binary": False, "size": size, "truncated": size > MAX_TEXT, "content": head.decode("utf8", "replace")}


class FileBody(BaseModel):
    path: str
    content: str


@router.put("/sessions/{sid}/file")
def write_file(sid: str, b: FileBody):
    p = _path(sid, b.path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(b.content)
    return {"ok": True}


@router.delete("/sessions/{sid}/file")
def delete_file(sid: str, path: str):
    p = _path(sid, path)
    if p.is_dir():
        raise HTTPException(400, "chỉ xóa được file")
    p.unlink(missing_ok=True)
    return {"ok": True}


@router.post("/sessions/{sid}/upload")
async def upload(sid: str, name: str, request: Request):
    base = _base(sid)
    if int(request.headers.get("content-length") or 0) > workfiles.MAX_UPLOAD:
        raise HTTPException(413, "file quá lớn (tối đa 25MB)")
    data = await request.body()
    if len(data) > workfiles.MAX_UPLOAD:
        raise HTTPException(413, "file quá lớn (tối đa 25MB)")
    safe = re.sub(r"[^\w.\- ]", "_", name.rsplit("/", 1)[-1]).strip(". ") or "tep"
    dest = base / "uploads" / safe
    n = 1
    while dest.exists():
        dest = base / "uploads" / f"{dest.stem.rsplit('_dup', 1)[0]}_dup{n}{dest.suffix}"
        n += 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"path": dest.relative_to(base).as_posix(), "size": len(data)}
