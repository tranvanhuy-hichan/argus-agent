"""API viec chay nen, agent con va ke hoach."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import jobs, plans, sessions

AUTO = True
router = APIRouter()


@router.get("/tasks")
def list_tasks(status: str = "", kind: str = "", limit: int = 100):
    return jobs.list_jobs(status, kind, limit)


@router.get("/tasks/{job_id}")
def get_task(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "không có việc này")
    return job


class NewTask(BaseModel):
    goal: str
    title: str = ""
    role: str = "general"
    permission: str = "default"
    provider: str | None = None
    max_steps: int | None = None


@router.post("/tasks")
def start_task(b: NewTask):
    if b.permission not in ("default", "readonly", "guarded", "full"):
        raise HTTPException(400, "quyền không hợp lệ")
    cfg = cfgmod.load()
    if b.role not in (*cfg.agents.profiles, "general"):
        raise HTTPException(400, f"không có vai trò '{b.role}'")
    jid = jobs.start_background(b.goal.strip(), kind="task", title=b.title or b.goal[:60], role=b.role, permission=b.permission, provider=b.provider, max_steps=b.max_steps)
    return {"id": jid}


@router.post("/tasks/{job_id}/cancel")
def cancel_task(job_id: str):
    return {"ok": jobs.request_cancel(job_id)}


@router.delete("/tasks/{job_id}")
def delete_task(job_id: str):
    if not jobs.delete(job_id):
        raise HTTPException(400, "chỉ xóa được việc đã kết thúc")
    return {"ok": True}


@router.get("/sessions/{sid}/plan")
def get_plan(sid: str):
    if not sessions.get(sid):
        raise HTTPException(404, "không có phiên này")
    items = plans.get(sid)
    done, total = plans.progress(items)
    return {"items": items, "done": done, "total": total}
