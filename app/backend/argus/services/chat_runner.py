"""Chay mot luot chat trong thread rieng va day su kien ra queue (cho SSE). Quan ly xin phep (approval)."""
import queue
import re
import threading
import uuid
from collections.abc import Iterator

import time

from . import agent, sessions

APPROVAL_TIMEOUT = 300
_approvals: dict[str, dict] = {}
_questions: dict[str, dict] = {}
QUESTION_TIMEOUT = 900


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


def answer_question(qid: str, text: str) -> bool:
    q = _questions.get(qid)
    if not q:
        return False
    q["answer"] = text
    q["event"].set()
    return True


def resolve_approval(aid: str, ok: bool) -> bool:
    a = _approvals.get(aid)
    if not a:
        return False
    a["ok"] = ok
    a["event"].set()
    return True


class Run:
    """Mot luot chay agent song doc lap voi ket noi HTTP: su kien duoc luu lai de client doi trang roi noi lai (attach) van xem tiep duoc."""

    def __init__(self, sid: str) -> None:
        self.sid, self.events, self.done = sid, [], False
        self.cond = threading.Condition()
        self.cancel = threading.Event()
        self.finished_at = 0.0

    def push(self, ev: dict) -> None:
        with self.cond:
            self.events.append(ev)
            if ev["type"] == "done":
                self.done, self.finished_at = True, time.time()
            self.cond.notify_all()

    def tail(self, start: int = 0) -> Iterator[dict]:
        i = start
        while True:
            with self.cond:
                if i >= len(self.events) and not self.done:
                    self.cond.wait(15)
                batch, i = self.events[i:], len(self.events)
                finished = self.done
            if batch:
                yield from batch
            elif not finished:
                yield {"type": "ping"}
            if finished:
                return


_runs: dict[str, Run] = {}
_runs_lock = threading.Lock()
KEEP_FINISHED = 120  # giu su kien cua luot da xong de client noi lai kip nhan ket qua


def _gc() -> None:
    now = time.time()
    for k, r in list(_runs.items()):
        if r.done and now - r.finished_at > KEEP_FINISHED:
            _runs.pop(k, None)


def state(sid: str) -> dict:
    """Trang thai cho client noi lai: dang chay khong, da co bao nhieu su kien (cursor), xin phep dang cho."""
    r = _runs.get(sid)
    pending = [{"id": k, "kind": a["kind"], "detail": a["detail"]} for k, a in _approvals.items() if a.get("sid") == sid]
    questions = [{"id": k, "question": q["question"], "options": q["options"]} for k, q in _questions.items() if q.get("sid") == sid]
    return {"active": bool(r and not r.done), "cursor": len(r.events) if r else 0, "pending": pending, "questions": questions}


def active(sid: str) -> bool:
    r = _runs.get(sid)
    return bool(r and not r.done)


def stop(sid: str) -> bool:
    """Dung ro rang luot dang chay cua phien (nut Dung); dong tab/doi trang KHONG goi ham nay."""
    r = _runs.get(sid)
    if not r or r.done:
        return False
    r.cancel.set()
    for a in [*_approvals.values(), *_questions.values()]:
        a["event"].set()
    return True


def attach(sid: str, start: int = 0) -> Iterator[dict]:
    """Noi lai vao luot dang chay (hoac vua xong): phat lai tu su kien thu `start`. Khong co luot nao thi tra ve 'done' ngay."""
    r = _runs.get(sid)
    if not r:
        yield {"type": "done"}
        return
    yield from r.tail(start)


def stream_chat(sid: str | None, text: str, provider: str | None, *, approver_override=None, source: str = "chat",
                only_tools: list[str] | None = None, attachments: list[str] | None = None, permission: str = "default",
                effort: str | None = None, docs: bool = False, temperature: float | None = None,
                max_tokens: int | None = None, detach: bool = False) -> Iterator[dict]:
    """detach=True (giao dien web): dong ket noi khong dung agent; client noi lai bang attach(). Mac dinh (CLI/API/Telegram): dong ket noi thi dung."""
    if not sid or not sessions.get(sid):
        sid = sessions.create(text, source=source)
    with _runs_lock:
        _gc()
        if active(sid):
            yield {"type": "session", "id": sid}
            yield {"type": "error", "message": "Phiên này đang có một lượt chạy. Hãy đợi xong hoặc bấm Dừng.", "tpl": "Phiên này đang có một lượt chạy. Hãy đợi xong hoặc bấm Dừng."}
            yield {"type": "done"}
            return
        run = Run(sid)
        _runs[sid] = run
    cancel = run.cancel

    def approver(kind: str, detail: str) -> bool:
        aid = uuid.uuid4().hex
        _approvals[aid] = {"event": threading.Event(), "ok": False, "sid": sid, "kind": kind, "detail": detail}
        run.push({"type": "approval", "id": aid, "kind": kind, "detail": detail})
        _approvals[aid]["event"].wait(APPROVAL_TIMEOUT)
        ok = _approvals.pop(aid)["ok"] and not cancel.is_set()
        run.push({"type": "approval_done", "id": aid, "ok": ok})
        return ok

    def asker(question: str, options: list[str]) -> str:
        qid = uuid.uuid4().hex
        _questions[qid] = {"event": threading.Event(), "answer": "", "sid": sid, "question": question, "options": options}
        run.push({"type": "question", "id": qid, "question": question, "options": options})
        _questions[qid]["event"].wait(QUESTION_TIMEOUT)
        ans = _questions.pop(qid)["answer"] if not cancel.is_set() else ""
        run.push({"type": "question_done", "id": qid, "answer": ans})
        return ans

    def worker():
        try:
            agent.run_turn(sid, text, provider, approver_override or approver, run.push, cancel, only_tools, source, attachments, permission, effort, use_docs=docs, temperature=temperature, max_tokens=max_tokens,
                           asker=None if approver_override else asker)
        except Exception as e:  # loi bat ngo khong duoc lam treo luong SSE
            run.push({"type": "error", "message": f"{type(e).__name__}: {e}"})
        try:
            from . import checkpoints
            if (summary := checkpoints.finish(sid)):
                run.push({"type": "turn_summary", **summary})
        except Exception:  # noqa: BLE001 - tom tat thay doi khong duoc lam hong chat
            pass
        try:
            from . import habits
            habits.observe(sid, text, source)
        except Exception:  # noqa: BLE001 - gợi ý thói quen không được làm hỏng chat
            pass
        try:
            threading.Thread(target=_auto_name_session, args=(sid, text, provider), daemon=True).start()
        except Exception:
            pass
        run.push({"type": "done"})

    threading.Thread(target=worker, daemon=True).start()
    yield {"type": "session", "id": sid}
    try:
        yield from run.tail(0)
    finally:
        if not detach:
            cancel.set()  # client ngat ket noi -> dung agent, tu choi cac xin phep dang cho
            for a in [*_approvals.values(), *_questions.values()]:
                a["event"].set()
