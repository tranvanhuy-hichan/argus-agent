import json
import time
import uuid

from ..core.db import db


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


def list_all(limit: int = 200) -> list[dict]:
    with db() as c:
        rows = c.execute("""SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id AND m.role='user') AS turns
                            FROM sessions s ORDER BY updated DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


def delete(sid: str) -> None:
    with db() as c:
        c.execute("DELETE FROM sessions WHERE id=?", (sid,))


def rename(sid: str, title: str) -> None:
    with db() as c:
        c.execute("UPDATE sessions SET title=? WHERE id=?", (title[:60], sid))


def messages(sid: str) -> list[dict]:
    with db() as c:
        rows = c.execute("SELECT role,content,tool_calls,tool_call_id FROM messages WHERE session_id=? ORDER BY id", (sid,)).fetchall()
    out = []
    for r in rows:
        m = {"role": r["role"], "content": r["content"]}
        if r["tool_calls"]:
            m["tool_calls"] = json.loads(r["tool_calls"])
        if r["tool_call_id"]:
            m["tool_call_id"] = r["tool_call_id"]
        out.append(m)
    return out


def add_message(sid: str, msg: dict) -> None:
    now = time.time()
    with db() as c:
        c.execute("INSERT INTO messages(session_id,role,content,tool_calls,tool_call_id,ts) VALUES(?,?,?,?,?,?)",
                  (sid, msg["role"], msg.get("content", ""), json.dumps(msg["tool_calls"], ensure_ascii=False) if msg.get("tool_calls") else None,
                   msg.get("tool_call_id"), now))
        c.execute("UPDATE sessions SET updated=? WHERE id=?", (now, sid))
