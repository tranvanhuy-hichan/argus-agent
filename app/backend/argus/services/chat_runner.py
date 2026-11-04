"""Chay mot luot chat trong thread rieng va day su kien ra queue (cho SSE). Quan ly xin phep (approval)."""
import queue
import re
import threading
import uuid
from collections.abc import Iterator

from . import agent, sessions

APPROVAL_TIMEOUT = 300
_approvals: dict[str, dict] = {}


def _auto_name_session(sid: str, user_text: str, provider: str | None) -> None:
    try:
        sess = sessions.get(sid)
        if not sess:
            return
        msgs = sessions.messages(sid)
        if len(msgs) <= 2:
            from ..core import config as cfgmod
            from .providers import make_provider
            cfg = cfgmod.load()
            pname = provider or cfg.default_provider
            pcfg = cfg.providers.get(pname)
            if not pcfg:
                return
            prompt_name = (
                f"Hãy tóm tắt yêu cầu sau thành một tiêu đề ngắn gọn từ 3 đến 6 từ tiếng Việt, "
                f"viết hoa chữ cái đầu câu, không dùng dấu ngoặc kép, không giải thích gì thêm:\n\"{user_text[:200]}\""
            )
            prov = make_provider(pcfg)
            res = ""
            for ev in prov.stream([{"role": "user", "content": prompt_name}], tools=[]):
                if ev.get("type") == "delta":
                    res += ev.get("text", "")
            clean = re.sub(r'["\'\n\r.]', '', res).strip()
            if clean and len(clean) <= 50 and not clean.lower().startswith("hãy"):
                sessions.rename(sid, clean)
    except Exception:
        pass


def resolve_approval(aid: str, ok: bool) -> bool:
    a = _approvals.get(aid)
    if not a:
        return False
    a["ok"] = ok
    a["event"].set()
    return True


def stream_chat(sid: str | None, text: str, provider: str | None, *, approver_override=None, source: str = "chat",
                only_tools: list[str] | None = None, attachments: list[str] | None = None, permission: str = "default",
                effort: str | None = None, docs: bool = False, temperature: float | None = None,
                max_tokens: int | None = None) -> Iterator[dict]:
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
            agent.run_turn(sid, text, provider, approver_override or approver, q.put, cancel, only_tools, source, attachments, permission, effort, use_docs=docs, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:  # loi bat ngo khong duoc lam treo luong SSE
            q.put({"type": "error", "message": f"{type(e).__name__}: {e}"})
        try:
            from . import habits
            habits.observe(sid, text, source)
        except Exception:  # noqa: BLE001 - gợi ý thói quen không được làm hỏng chat
            pass
        try:
            threading.Thread(target=_auto_name_session, args=(sid, text, provider), daemon=True).start()
        except Exception:
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
