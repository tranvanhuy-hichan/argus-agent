"""API bộ nhớ: trạng thái embedding, reindex, tìm kiếm lai, dọn dẹp MEMORY.md bằng AI."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import config as cfgmod
from ..core import db as dbmod
from ..core.db import db
from ..services import embeddings, memory, memory_index, vectorstore

AUTO = True
router = APIRouter()


class ApplyBody(BaseModel):
    new: str


@router.get("/memory/status")
def status():
    cfg = cfgmod.load()
    with db() as c:
        msgs = c.execute("SELECT COUNT(*) n FROM messages WHERE role IN ('user','assistant') AND content!=''").fetchone()["n"]
    st = vectorstore.stats()
    return {"embedding": embeddings.status(cfg), "vectors": st, "notes": len(memory_index.note_lines(cfg)), "messages": msgs,
            "fts": dbmod.fts_enabled, "reindex": dict(memory_index.progress)}


@router.post("/memory/reindex")
def reindex():
    cfg = cfgmod.load()
    if cfg.memory.embeddings == "off":
        raise HTTPException(400, "Embedding đang tắt (memory.embeddings = off)")
    return {"started": memory_index.start_reindex(cfg), "progress": dict(memory_index.progress)}


@router.get("/memory/reindex")
def reindex_progress():
    return dict(memory_index.progress)


@router.get("/memory/search")
def search(q: str, limit: int = 6):
    from pathlib import Path

    from ..services import tools
    cfg = cfgmod.load()
    ctx = tools.ToolContext(workspace=Path(cfg.workspace_path()))
    return {"results": tools.TOOLS["memory_search"].fn(ctx, q, limit).splitlines()}


@router.post("/memory/curate")
def curate(provider: str | None = None):
    return memory.propose_curation(cfgmod.load(), provider)


@router.post("/memory/curate/apply")
def curate_apply(body: ApplyBody):
    try:
        return memory.apply_curation(cfgmod.load(), body.new)
    except ValueError as e:
        raise HTTPException(400, f"Bản mới không hợp lệ: {e}") from e
