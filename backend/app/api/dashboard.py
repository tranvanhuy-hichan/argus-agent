import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import scheduler, sessions, skills as skillmod, usage

router = APIRouter()


@router.get("/dashboard")
def dashboard(days: int = Query(7, ge=1, le=90)):
    cfg = cfgmod.load()
    skills = skillmod.discover(cfg).values()
    jobs = scheduler.list_jobs()
    return {
        **usage.dashboard(days),
        "skills": {"total": len(skills), "active": sum(s.active for s in skills), "needs_setup": sum(s.enabled and not s.eligible for s in skills)},
        "automations": {"total": len(jobs), "enabled": sum(j["enabled"] for j in jobs),
                        "next": min((j["next_run"] for j in jobs if j["enabled"] and j["next_run"]), default=None)},
        "providers": {"default": cfg.default_provider, "count": len(cfg.providers)},
        "recent_sessions": sessions.list_all(6),
        "now": time.time(),
    }


class JobBody(BaseModel):
    name: str
    schedule: str
    prompt: str
    provider: str | None = None
    enabled: bool = True


@router.get("/automations")
def list_jobs():
    return scheduler.list_jobs()


def _save(job: JobBody, job_id: str | None = None):
    try:
        return {"id": scheduler.save_job(job.model_dump(), job_id)}
    except scheduler.ScheduleError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/automations")
def create_job(job: JobBody):
    return _save(job)


@router.put("/automations/{job_id}")
def update_job(job_id: str, job: JobBody):
    return _save(job, job_id)


@router.delete("/automations/{job_id}")
def delete_job(job_id: str):
    scheduler.delete_job(job_id)
    return {"ok": True}


@router.post("/automations/{job_id}/run")
def run_job(job_id: str):
    import threading
    threading.Thread(target=scheduler.run_job, args=(job_id,), daemon=True).start()
    return {"ok": True}
