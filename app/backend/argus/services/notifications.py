"""Hop thu thong bao (ket qua automation/heartbeat, ...). Co the day ra kenh chat qua hook `listeners`."""
import time
from collections.abc import Callable

from ..core.db import db

listeners: list[Callable[[dict], None]] = []


def add(title: str, body: str, source: str = "system", session_id: str | None = None) -> dict:
    with db() as c:
        cur = c.execute("INSERT INTO notifications(ts,title,body,source,session_id) VALUES(?,?,?,?,?)", (time.time(), title[:120], body[:4000], source, session_id))
        n = {"id": cur.lastrowid, "ts": time.time(), "title": title, "body": body, "source": source, "session_id": session_id, "read": False}
    for fn in listeners:
        try:
            fn(n)
        except Exception:  # noqa: BLE001 - kenh loi khong duoc lam hong viec ghi thong bao
            pass
    return n


def list_all(limit: int = 100) -> list[dict]:
    with db() as c:
        return [dict(r) | {"read": bool(r["read"])} for r in c.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,))]


def unread_count() -> int:
    with db() as c:
        return c.execute("SELECT COUNT(*) n FROM notifications WHERE read=0").fetchone()["n"]


def mark_read(ids: list[int] | None = None) -> None:
    with db() as c:
        if ids:
            c.executemany("UPDATE notifications SET read=1 WHERE id=?", [(i,) for i in ids])
        else:
            c.execute("UPDATE notifications SET read=1")


def delete_all() -> None:
    with db() as c:
        c.execute("DELETE FROM notifications")
