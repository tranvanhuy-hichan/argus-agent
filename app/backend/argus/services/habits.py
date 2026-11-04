"""Nhận ra việc người dùng lặp lại (>= 3 phiên khác nhau) và gợi ý biến nó thành skill hoặc automation.

Phát hiện bằng so khớp từ khóa (không tốn token); bản nháp do model soạn một lần, lỗi thì dùng bản nháp dự phòng."""
import json
import re
import threading
import time
import unicodedata
import uuid

from ..core import config as cfgmod
from ..core.db import db
from . import notifications, scheduler, skills
from .providers import make_provider

THRESHOLD = 3          # số phiên khác nhau cùng yêu cầu thì gợi ý
WINDOW = 90 * 86400    # chỉ xét yêu cầu trong 90 ngày gần đây
SIMILAR = 0.5
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,60}$")
STOP = set("""toi ban hay giup cho la cua va de co khong nhe nha voi cac nhung mot nay do the nao gi thi se da dang
please the a an to of and for me my you can could would is are in on it this that with i do""".split())

DRAFT_PROMPT = """Người dùng đã gửi các yêu cầu tương tự nhau nhiều lần. Hãy soạn bản nháp để họ khỏi phải lặp lại.
Chọn kind:
- "automation" nếu yêu cầu mang tính định kỳ (hằng ngày, mỗi sáng, hằng tuần...): trả thêm "prompt" (lời nhắc tự đủ ý để chạy không cần người) và "schedule" (cron 5 trường).
- "skill" nếu không: trả "body" là hướng dẫn Markdown ngắn gọn các bước agent cần làm.
Chỉ trả một đối tượng JSON: {"kind","name","title","description","body","prompt","schedule"}.
"name" kebab-case a-z0-9 và dấu -, "title" và "description" viết bằng ngôn ngữ của người dùng, mô tả khi nào nên dùng."""


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _fold(text)) if len(w) > 2 and w not in STOP}


def similar(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    inter = len(a & b)
    return inter / len(a | b) >= SIMILAR or (min(len(a), len(b)) >= 4 and inter / min(len(a), len(b)) >= 0.75)


def observe(sid: str, text: str, source: str = "chat") -> str | None:
    """Ghi lại yêu cầu; trả về id gợi ý nếu vừa phát hiện một thói quen mới."""
    text = (text or "").strip()
    if source != "chat" or len(text) < 12 or text.startswith("/") or not cfgmod.load().agent.suggest_habits:
        return None
    tk = tokens(text)
    if len(tk) < 3:
        return None
    now = time.time()
    with db() as c:
        c.execute("INSERT INTO habit_requests(ts,session_id,text,tokens) VALUES(?,?,?,?)", (now, sid, text[:600], json.dumps(sorted(tk))))
        rows = c.execute("SELECT session_id,text,tokens FROM habit_requests WHERE ts>? ORDER BY id DESC LIMIT 500", (now - WINDOW,)).fetchall()
        known = [set(json.loads(r["tokens"])) for r in c.execute("SELECT tokens FROM habit_suggestions")]
    if any(similar(tk, k) for k in known):
        return None
    sessions_seen: set[str] = set()
    examples: list[str] = []
    for r in rows:
        if similar(tk, set(json.loads(r["tokens"]))) and r["session_id"] not in sessions_seen:
            sessions_seen.add(r["session_id"])
            examples.append(r["text"])
    if len(sessions_seen) < THRESHOLD:
        return None
    return _create(tk, examples[:5], len(sessions_seen))


def _spawn(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True).start()


def _create(tk: set[str], examples: list[str], count: int) -> str:
    sid = uuid.uuid4().hex[:8]
    with db() as c:
        c.execute("INSERT INTO habit_suggestions(id,status,tokens,examples,count,created,updated) VALUES(?,?,?,?,?,?,?)",
                  (sid, "drafting", json.dumps(sorted(tk)), json.dumps(examples, ensure_ascii=False), count, time.time(), time.time()))
    _spawn(_draft_and_notify, sid)
    return sid


def fallback_draft(examples: list[str], tk: set[str]) -> dict:
    words = sorted(tk, key=lambda w: (-len(w), w))[:3]
    name = "-".join(words) or "viec-lap-lai"
    ex = "\n".join(f"- {e}" for e in examples)
    return {"kind": "skill", "name": name, "title": examples[0][:60], "description": f"Dùng khi người dùng yêu cầu kiểu: {examples[0][:100]}",
            "body": f"Người dùng thường yêu cầu việc này. Các ví dụ:\n{ex}\n\nLàm theo cách họ mong đợi, hỏi lại nếu thiếu thông tin.", "prompt": "", "schedule": ""}


def parse_draft(raw: str) -> dict | None:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    kind = d.get("kind")
    name = re.sub(r"[^a-z0-9_-]+", "-", _fold(str(d.get("name", ""))).strip()).strip("-")[:60]
    if kind not in ("skill", "automation") or not NAME_RE.match(name):
        return None
    out = {"kind": kind, "name": name, "title": str(d.get("title") or name)[:80], "description": str(d.get("description", ""))[:300],
           "body": str(d.get("body", "")), "prompt": str(d.get("prompt", "")), "schedule": str(d.get("schedule", "")).strip()}
    if kind == "skill" and not out["body"].strip():
        return None
    if kind == "automation":
        try:
            scheduler.next_run(out["schedule"])
        except scheduler.ScheduleError:
            return None
        if not out["prompt"].strip():
            return None
    return out


def _draft_and_notify(sid: str) -> None:
    with db() as c:
        r = c.execute("SELECT * FROM habit_suggestions WHERE id=?", (sid,)).fetchone()
    examples, tk = json.loads(r["examples"]), set(json.loads(r["tokens"]))
    draft = None
    try:
        cfg = cfgmod.load()
        out = "".join(e["text"] for e in make_provider(cfg.providers[cfg.default_provider]).stream(
            [{"role": "system", "content": DRAFT_PROMPT}, {"role": "user", "content": "\n".join(f"- {e}" for e in examples)}], []) if e["type"] == "delta")
        draft = parse_draft(out)
    except Exception:  # noqa: BLE001 - không có model vẫn phải có bản nháp
        draft = None
    draft = draft or fallback_draft(examples, tk)
    with db() as c:
        c.execute("UPDATE habit_suggestions SET status='pending', draft=?, updated=? WHERE id=?", (json.dumps(draft, ensure_ascii=False), time.time(), sid))
    what = "tự động hóa" if draft["kind"] == "automation" else "kỹ năng"
    notifications.add(f"Gợi ý: tạo {what} “{draft['title']}”", f"Bạn đã lặp lại việc này {r['count']} lần. Mở Trang chủ để xem bản nháp và duyệt.", source="habit")


def _row(r) -> dict:
    return {"id": r["id"], "status": r["status"], "count": r["count"], "examples": json.loads(r["examples"]),
            "draft": json.loads(r["draft"]) if r["draft"] else None, "created": r["created"]}


def list_pending() -> list[dict]:
    with db() as c:
        return [_row(r) for r in c.execute("SELECT * FROM habit_suggestions WHERE status='pending' ORDER BY created DESC")]


def dismiss(sid: str) -> bool:
    with db() as c:
        return c.execute("UPDATE habit_suggestions SET status='dismissed', updated=? WHERE id=? AND status IN ('pending','drafting')", (time.time(), sid)).rowcount > 0


def accept(sid: str, draft: dict) -> dict:
    """Tạo skill/automation từ bản nháp (đã được người dùng chỉnh)."""
    with db() as c:
        r = c.execute("SELECT status FROM habit_suggestions WHERE id=?", (sid,)).fetchone()
    if not r or r["status"] != "pending":
        raise ValueError("gợi ý không còn hiệu lực")
    name = draft.get("name", "")
    if not NAME_RE.match(name):
        raise ValueError("tên chỉ gồm a-z, 0-9, - và _")
    cfg = cfgmod.load()
    if draft.get("kind") == "automation":
        job_id = scheduler.save_job({"name": draft.get("title") or name, "schedule": draft.get("schedule", ""), "prompt": draft.get("prompt", ""),
                                     "provider": None, "enabled": True, "notify": True})
        result = {"kind": "automation", "id": job_id}
    else:
        if not draft.get("body", "").strip():
            raise ValueError("kỹ năng cần có nội dung")
        skills.create(cfg, name, draft.get("description", ""), draft["body"])
        result = {"kind": "skill", "name": name}
    with db() as c:
        c.execute("UPDATE habit_suggestions SET status='accepted', updated=? WHERE id=?", (time.time(), sid))
    return result
