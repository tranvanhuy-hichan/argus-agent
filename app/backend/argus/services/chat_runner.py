"""Chay mot luot chat trong thread rieng va day su kien ra queue (cho SSE). Quan ly xin phep (approval)."""
import queue
import threading
import uuid
from collections.abc import Iterator

from . import agent, sessions

APPROVAL_TIMEOUT = 300
_approvals: dict[str, dict] = {}


def resolve_approval(aid: str, ok: bool) -> bool:
    a = _approvals.get(aid)
    if not a:
        return False
    a["ok"] = ok
    a["event"].set()
    return True


def stream_chat(sid: str | None, text: str, provider: str | None, *, approver_override=None, source: str = "chat",
                only_tools: list[str] | None = None, attachments: list[str] | None = None, permission: str = "default",
                effort: str | None = None) -> Iterator[dict]:
    if not sid or not sessions.get(sid):
        sid = sessions.create(text, source=source)
    q: queue.Queue = queue.Queue()
    cancel = threading.Event()

    def approver(kind: str, detail: str) -> bool:
        aid = uuid.uuid4().hex
        _approvals[aid] = {"event": threading.Event(), "ok": False}
        q.put({"type": "approval", "id": aid, "kind": kind, "detail": detail})
        _approvals[aid]["event"].wait(APPROVAL_TIMEOUT)
        return _approvals.pop(aid)["ok"] and not cancel.is_set()

    def worker():
        try:
            agent.run_turn(sid, text, provider, approver_override or approver, q.put, cancel, only_tools, source, attachments, permission, effort)
        except Exception as e:  # loi bat ngo khong duoc lam treo luong SSE
            q.put({"type": "error", "message": f"{type(e).__name__}: {e}"})
        try:
            from . import habits
            habits.observe(sid, text, source)
        except Exception:  # noqa: BLE001 - gợi ý thói quen không được làm hỏng chat
            pass
        q.put({"type": "done"})

    threading.Thread(target=worker, daemon=True).start()
    yield {"type": "session", "id": sid}
    try:
        while True:
            try:
                ev = q.get(timeout=15)
            except queue.Empty:
                yield {"type": "ping"}
                continue
            yield ev
            if ev["type"] == "done":
                return
    finally:
        cancel.set()  # client ngat ket noi -> dung agent, tu choi cac xin phep dang cho
        for a in list(_approvals.values()):
            a["event"].set()
