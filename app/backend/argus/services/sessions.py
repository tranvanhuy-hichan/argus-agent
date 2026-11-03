import json
import time
import uuid

from ..core import db as dbmod
from ..core.db import db
from ..core.text import fold


def create(title: str, source: str = "chat") -> str:
    sid = uuid.uuid4().hex[:8]
    now = time.time()
    with db() as c:
        c.execute("INSERT INTO sessions(id,title,created,updated,source) VALUES(?,?,?,?,?)", (sid, title[:60] or "Hội thoại mới", now, now, source))
    return sid


def get(sid: str) -> dict | None:
    with db() as c:
        r = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    return dict(r) if r else None


def list_all(limit: int = 200, q: str = "") -> list[dict]:
    with db() as c:
        rows = c.execute("""SELECT s.id,s.title,s.created,s.updated,s.source,
                            (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id AND m.role='user') AS turns
                            FROM sessions s WHERE (?='' OR s.title LIKE '%'||?||'%') ORDER BY updated DESC LIMIT ?""", (q, q, limit)).fetchall()
    return [dict(r) for r in rows]


def delete(sid: str) -> None:
    with db() as c:
        c.execute("DELETE FROM messages_fts WHERE session_id=?", (sid,)) if dbmod.fts_enabled else None
        c.execute("DELETE FROM sessions WHERE id=?", (sid,))
    try:
        from . import vectorstore
        vectorstore.delete_session(sid)
    except Exception:  # noqa: BLE001 - kho vector khong duoc lam hong viec xoa phien
        pass


def rename(sid: str, title: str) -> None:
    with db() as c:
        c.execute("UPDATE sessions SET title=? WHERE id=?", (title[:60], sid))


def _row_to_msg(r) -> dict:
    m = {"role": r["role"], "content": r["content"]}
    if r["tool_calls"]:
        m["tool_calls"] = json.loads(r["tool_calls"])
    if r["tool_call_id"]:
        m["tool_call_id"] = r["tool_call_id"]
    if r["attachments"]:
        m["attachments"] = json.loads(r["attachments"])
    return m


def messages(sid: str, after_id: int = 0, with_ids: bool = False) -> list[dict]:
    with db() as c:
        rows = c.execute("SELECT id,role,content,tool_calls,tool_call_id,attachments FROM messages WHERE session_id=? AND id>? ORDER BY id", (sid, after_id)).fetchall()
    out = [_row_to_msg(r) for r in rows]
    if with_ids:
        for m, r in zip(out, rows):
            m["_id"] = r["id"]
    return out


def add_message(sid: str, msg: dict) -> None:
    now = time.time()
    with db() as c:
        c.execute("INSERT INTO messages(session_id,role,content,tool_calls,tool_call_id,attachments,ts) VALUES(?,?,?,?,?,?,?)",
                  (sid, msg["role"], msg.get("content", ""), json.dumps(msg["tool_calls"], ensure_ascii=False) if msg.get("tool_calls") else None,
                   msg.get("tool_call_id"), json.dumps(msg["attachments"]) if msg.get("attachments") else None, now))
        c.execute("UPDATE sessions SET updated=? WHERE id=?", (now, sid))
        if dbmod.fts_enabled and msg["role"] in ("user", "assistant") and msg.get("content"):
            c.execute("INSERT INTO messages_fts(folded, content, session_id, role) VALUES(?,?,?,?)", (fold(msg["content"]), msg["content"], sid, msg["role"]))
    if msg["role"] in ("user", "assistant") and msg.get("content"):
        try:
            from . import memory_index
            memory_index.enqueue_message(sid, msg["role"], msg["content"], now)
        except Exception:  # noqa: BLE001 - chi muc vector khong duoc lam hong chat
            pass


def truncate_from(sid: str, index: int) -> None:
    """Xoa tin nhan tu vi tri `index` (tinh theo thu tu trong phien) tro di, de sua/tao lai mot luot."""
    with db() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM messages WHERE session_id=? ORDER BY id", (sid,))]
        if index < len(ids):
            c.execute("DELETE FROM messages WHERE session_id=? AND id>=?", (sid, ids[index]))
            c.execute("UPDATE sessions SET summary='', summary_upto=0 WHERE id=? AND summary_upto>=?", (sid, ids[index]))


def set_summary(sid: str, summary: str, upto: int) -> None:
    with db() as c:
        c.execute("UPDATE sessions SET summary=?, summary_upto=? WHERE id=?", (summary, upto, sid))


def _excerpt(text: str, terms: list[str], width: int = 150) -> str:
    """Doan trich quanh tu khoa dau tien, danh dau bang [ ]. Vi tri tinh tren ban da bo dau (cung do dai voi ban goc dang NFC)."""
    import unicodedata
    text = unicodedata.normalize("NFC", text)
    folded = fold(text)
    import re
    found = [m for t in terms if (m := re.search(rf"(?<!\w){re.escape(t)}(?!\w)", folded))]  # khop nguyen tu, khong khop 'da' trong 'dang'
    first = min(found, key=lambda m: m.start(), default=None)
    pos, end = (first.start(), first.end()) if first and len(folded) == len(text) else (first.start() if first else 0, 0)
    start = max(0, pos - width // 2)
    piece = text[start:start + width]
    if len(folded) == len(text) and end > pos:
        a, b = pos - start, end - start
        piece = f"{piece[:a]}[{piece[a:b]}]{piece[b:]}"
    return ("…" if start else "") + piece + ("…" if start + width < len(text) else "")


def search(query: str, limit: int = 8) -> list[dict]:
    """Tim trong toan bo lich su hoi thoai (FTS5, khong phan biet dau/hoa thuong)."""
    terms = [t for t in "".join(ch if ch.isalnum() else " " for ch in fold(query)).split() if t]
    if not terms or not dbmod.fts_enabled:
        return []
    with db() as c:
        rows = c.execute("""SELECT f.session_id, f.role, f.content, s.title, s.updated
                            FROM messages_fts f JOIN sessions s ON s.id=f.session_id WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?""",
                         (" ".join(f'"{t}"' for t in terms), limit)).fetchall()
    return [{"session_id": r["session_id"], "role": r["role"], "snip": _excerpt(r["content"], terms), "title": r["title"], "updated": r["updated"]} for r in rows]
