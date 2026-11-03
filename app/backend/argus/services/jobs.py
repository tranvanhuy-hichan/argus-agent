"""Viec chay nen (task) va agent con (subagent): moi job la mot phien agent rieng, luu tien do trong bang `jobs`."""
import json
import threading
import time
import uuid
from collections.abc import Callable

from ..core import config as cfgmod
from ..core.db import db
from . import notifications, sessions

ACTIVE = ("queued", "running")
_registry: dict[str, threading.Event] = {}
_lock = threading.Lock()
_slots: threading.BoundedSemaphore | None = None
_slots_n = 0


class JobError(Exception):
    pass


def _semaphore(n: int) -> threading.BoundedSemaphore:
    global _slots, _slots_n
    with _lock:
        if _slots is None or _slots_n != n:
            _slots, _slots_n = threading.BoundedSemaphore(n), n
        return _slots


def _row(r) -> dict:
    return dict(r) | {"cancel_requested": bool(r["cancel_requested"]), "notify": bool(r["notify"])}


def get(job_id: str) -> dict | None:
    with db() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _row(r) if r else None


def list_jobs(status: str = "", kind: str = "", limit: int = 100) -> list[dict]:
    with db() as c:
        rows = c.execute("SELECT * FROM jobs WHERE (?='' OR status=?) AND (?='' OR kind=?) ORDER BY created DESC LIMIT ?", (status, status, kind, kind, limit)).fetchall()
    return [_row(r) for r in rows]


def _update(job_id: str, **fields) -> None:
    keys = ", ".join(f"{k}=?" for k in fields)
    with db() as c:
        c.execute(f"UPDATE jobs SET {keys} WHERE id=?", (*fields.values(), job_id))


def create(goal: str, *, kind: str = "task", title: str = "", role: str = "", parent_session: str | None = None, parent_job: str | None = None, depth: int = 0,
           permission: str = "default", provider: str | None = None, max_steps: int | None = None, notify: bool = True) -> str:
    jid = uuid.uuid4().hex[:8]
    with db() as c:
        c.execute("""INSERT INTO jobs(id,kind,title,goal,role,status,parent_session,parent_job,depth,permission,provider,max_steps,notify,created)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (jid, kind, (title or goal)[:80], goal, role, "queued", parent_session, parent_job, depth, permission, provider, max_steps, int(notify), time.time()))
    return jid


def request_cancel(job_id: str) -> bool:
    job = get(job_id)
    if not job or job["status"] not in ACTIVE:
        return False
    _update(job_id, cancel_requested=1)
    ev = _registry.get(job_id)
    if ev:
        ev.set()
    if job["status"] == "queued":
        _update(job_id, status="cancelled", finished=time.time())
    return True


def delete(job_id: str) -> bool:
    job = get(job_id)
    if not job or job["status"] in ACTIVE:
        return False
    with db() as c:
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    return True


def recover_interrupted() -> int:
    """Khi server khoi dong lai, cac job dang chay do dang bi mat tien trinh nen duoc danh dau 'interrupted'."""
    with db() as c:
        cur = c.execute("UPDATE jobs SET status='interrupted', finished=?, error='bị gián đoạn do server khởi động lại' WHERE status IN ('queued','running')", (time.time(),))
        return cur.rowcount


def _profile_tools(cfg: cfgmod.Config, role: str, depth: int) -> tuple[list[str] | None, str]:
    """Danh sach tool cho phep + doan prompt cua vai tro. None = moi tool (tru tool tao agent con neu da toi do sau toi da)."""
    from . import tools

    prof = cfg.agents.profiles.get(role) if role and role != "general" else None
    if role and role != "general" and not prof:
        raise JobError(f"không có vai trò '{role}'. Có: {', '.join(cfg.agents.profiles) or '(chưa có)'}, general")
    every = [*tools.TOOLS]
    allowed = list(prof.tools) if prof and prof.tools else every
    allowed += [n for n in ("plan_set", "plan_update", "plan_show") if n not in allowed]
    if depth + 1 >= cfg.agents.max_depth:  # agent con o tang cuoi khong duoc tao them agent con
        allowed = [n for n in allowed if n not in ("delegate", "task_start")]
    return allowed, (prof.prompt if prof else "")


def execute(job_id: str, approver: Callable[[str, str], bool] | None = None, cancel: threading.Event | None = None) -> dict:
    """Chay mot job tu dau den cuoi trong thread hien tai va tra ve dong job da cap nhat."""
    from . import agent  # import tre de tranh vong

    job = get(job_id)
    if not job:
        raise JobError("không có job")
    cfg = cfgmod.load()
    cancel = cancel or threading.Event()
    _registry[job_id] = cancel
    try:
        allowed, role_prompt = _profile_tools(cfg, job["role"] or "", job["depth"])
        prof = cfg.agents.profiles.get(job["role"] or "")
        max_steps = job["max_steps"] or (prof.max_steps if prof else cfg.agents.task_max_steps)
        provider = job["provider"] or (prof.provider if prof else None)
        sid = sessions.create(f"{'🤖' if job['kind'] == 'subagent' else '⏳'} {job['title']}", source=job["kind"])
        _update(job_id, status="running", started=time.time(), session_id=sid, max_steps=max_steps)
        extra = (f"{role_prompt}\n\n" if role_prompt else "") + (
            "Bạn đang chạy như một " + ("agent con" if job["kind"] == "subagent" else "việc nền") + " để hoàn thành mục tiêu được giao. "
            "Không hỏi lại người giao việc; tự quyết định hợp lý. Với việc nhiều bước, lập kế hoạch bằng plan_set. "
            "Khi xong, trả lời bằng KẾT QUẢ CUỐI CÙNG đầy đủ, ngắn gọn, đủ để người giao việc dùng ngay.")
        state = {"steps": 0, "last": "", "final": "", "error": None, "t": 0.0}

        def on_event(ev: dict) -> None:
            if db_cancelled(job_id):
                cancel.set()
            t = ev["type"]
            if t == "tool":
                state["steps"] += 1
                a = ev["args"]
                state["last"] = f"{ev['name']}: {str(a.get('command') or a.get('path') or a.get('url') or a.get('query') or a.get('task') or json.dumps(a, ensure_ascii=False))[:100]}"
            elif t == "assistant" and ev["content"]:
                state["final"] = ev["content"]
            elif t == "error":
                state["error"] = ev["message"]
            if t in ("tool", "assistant", "error") and (time.time() - state["t"] > 0.25 or t != "tool"):
                state["t"] = time.time()  # gioi han tan suat ghi DB khi tool chay rat nhanh
                _update(job_id, steps=state["steps"], progress=state["last"][:160])

        agent.run_turn(sid, job["goal"], provider, approver or (lambda kind, detail: False), on_event, cancel, only_tools=allowed, source=job["kind"],
                       permission=job["permission"], system_extra=extra, max_steps=max_steps, depth=job["depth"] + (1 if job["kind"] == "subagent" else 0), job_id=job_id, workdir_sid=job["parent_session"])
        status = "cancelled" if cancel.is_set() or db_cancelled(job_id) else ("failed" if state["error"] else "done")
        _update(job_id, status=status, steps=state["steps"], result=state["final"][:20000], error=state["error"], finished=time.time(), progress=state["last"][:160])
    except Exception as e:  # noqa: BLE001 - mot job loi khong duoc lam sap server
        _update(job_id, status="failed", error=f"{type(e).__name__}: {e}"[:500], finished=time.time())
    finally:
        _registry.pop(job_id, None)
    done = get(job_id)
    if done and done["notify"] and done["kind"] == "task":
        icon = {"done": "✅", "failed": "⚠️", "cancelled": "⏹"}.get(done["status"], "")
        notifications.add(f"{icon} Việc nền: {done['title']}", (done["result"] or done["error"] or "")[:600], source="task", session_id=done["session_id"])
    return done or {}


def db_cancelled(job_id: str) -> bool:
    job = get(job_id)
    return bool(job and job["cancel_requested"])


def start_background(goal: str, **kw) -> str:
    """Tao job va chay o thread nen; toi da `max_parallel` job cung luc (cac job con lai cho trong hang doi)."""
    jid = create(goal, **kw)
    n = cfgmod.load().agents.max_parallel

    def run() -> None:
        sem = _semaphore(n)
        with sem:
            job = get(jid)
            if job and job["status"] == "queued":
                execute(jid)

    threading.Thread(target=run, daemon=True, name=f"job-{jid}").start()
    return jid


def run_subagent(ctx, role: str, task: str) -> dict:
    """Chay agent con DONG BO trong thread hien tai (dung chung bo phe duyet va co huy cua agent cha)."""
    cfg = cfgmod.load()
    if ctx.depth >= cfg.agents.max_depth:
        raise JobError(f"đã đạt độ sâu tối đa của agent con ({cfg.agents.max_depth})")
    if role != "general" and role not in cfg.agents.profiles:  # bao loi ngay, khong tao job vo nghia
        raise JobError(f"không có vai trò '{role}'. Có: {', '.join(cfg.agents.profiles) or '(chưa có)'}, general")
    jid = create(task, kind="subagent", title=f"{role}: {task}", role=role, parent_session=ctx.session_id, depth=ctx.depth, permission=ctx.permission, provider=ctx.provider, notify=False)
    sem = _semaphore(cfg.agents.max_parallel + 4)  # agent con dong bo cua mot luot chat dung han muc rieng, rong hon viec nen
    with sem:
        return execute(jid, approver=ctx.approver, cancel=ctx.cancel if hasattr(ctx.cancel, "is_set") else None)
