"""Automations: chay prompt theo lich cron (khong co nguoi duyet -> exec/ngoai workspace bi tu choi)."""
import threading
import time
import uuid

from croniter import croniter

from ..core.db import db
from . import agent, notifications, sessions

TICK = 15
_stop = threading.Event()


class ScheduleError(ValueError):
    pass


def next_run(schedule: str, base: float | None = None) -> float:
    if not croniter.is_valid(schedule):
        raise ScheduleError(f"biểu thức cron không hợp lệ: {schedule}")
    return croniter(schedule, base or time.time()).get_next(float)


def list_jobs() -> list[dict]:
    with db() as c:
        return [dict(r) | {"enabled": bool(r["enabled"]), "notify": bool(r["notify"])} for r in c.execute("SELECT * FROM cron_jobs ORDER BY name")]


def save_job(job: dict, job_id: str | None = None) -> str:
    nxt = next_run(job["schedule"])
    with db() as c:
        if job_id:
            c.execute("UPDATE cron_jobs SET name=?,schedule=?,prompt=?,provider=?,enabled=?,next_run=?,notify=? WHERE id=?",
                      (job["name"], job["schedule"], job["prompt"], job.get("provider"), int(job["enabled"]), nxt, int(job.get("notify", True)), job_id))
        else:
            job_id = uuid.uuid4().hex[:8]
            c.execute("INSERT INTO cron_jobs(id,name,schedule,prompt,provider,enabled,next_run,notify) VALUES(?,?,?,?,?,?,?,?)",
                      (job_id, job["name"], job["schedule"], job["prompt"], job.get("provider"), int(job["enabled"]), nxt, int(job.get("notify", True))))
    return job_id


def delete_job(job_id: str) -> None:
    with db() as c:
        c.execute("DELETE FROM cron_jobs WHERE id=?", (job_id,))


def run_job(job_id: str) -> None:
    with db() as c:
        r = c.execute("SELECT * FROM cron_jobs WHERE id=?", (job_id,)).fetchone()
    if not r:
        return
    sid = sessions.create(f"⏱ {r['name']}", source="cron")
    events: list[dict] = []
    started = time.time()
    try:
        agent.run_turn(sid, r["prompt"], r["provider"], lambda kind, detail: False, events.append, source="cron")
    except Exception as e:
        events.append({"type": "error", "message": f"{type(e).__name__}: {e}"})
    err = next((e["message"] for e in events if e["type"] == "error"), None)
    text = next((e["content"] for e in reversed(events) if e["type"] == "assistant"), "")
    with db() as c:
        c.execute("UPDATE cron_jobs SET last_run=?, last_status=?, last_output=?, next_run=? WHERE id=?",
                  (started, "error" if err else "ok", (err or text)[:2000], next_run(r["schedule"]), job_id))
    if r["notify"] and (err or text):
        notifications.add(f"Automation: {r['name']}" + (" (lỗi)" if err else ""), err or text, source="cron", session_id=sid)


def _loop() -> None:
    while not _stop.wait(TICK):
        with db() as c:
            due = [r["id"] for r in c.execute("SELECT id FROM cron_jobs WHERE enabled=1 AND next_run<=?", (time.time(),))]
        for job_id in due:
            with db() as c:  # dat next_run ngay de tick sau khong chay lai trong luc job dang chay
                c.execute("UPDATE cron_jobs SET next_run=? WHERE id=?", (time.time() + 3600, job_id))
            threading.Thread(target=run_job, args=(job_id,), daemon=True).start()


def start() -> None:
    _stop.clear()
    threading.Thread(target=_loop, daemon=True, name="scheduler").start()


def stop() -> None:
    _stop.set()
