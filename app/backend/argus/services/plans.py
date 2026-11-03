"""Ke hoach (danh sach viec) cua mot hoi thoai: agent lap bang plan_set, cap nhat bang plan_update, nguoi dung thay tien do tren giao dien."""
import json
import time

from ..core.db import db

STATUSES = ("pending", "in_progress", "done", "blocked")
MARK = {"pending": "[ ]", "in_progress": "[~]", "done": "[x]", "blocked": "[!]"}
MAX_STEPS = 25


def get(sid: str) -> list[dict]:
    with db() as c:
        r = c.execute("SELECT items FROM plans WHERE session_id=?", (sid,)).fetchone()
    return json.loads(r["items"]) if r else []


def _save(sid: str, items: list[dict]) -> list[dict]:
    with db() as c:
        c.execute("INSERT OR REPLACE INTO plans(session_id, items, updated) VALUES(?,?,?)", (sid, json.dumps(items, ensure_ascii=False), time.time()))
    return items


def set_items(sid: str, texts: list[str]) -> list[dict]:
    clean = [t.strip() for t in texts if isinstance(t, str) and t.strip()]
    if not clean:
        raise ValueError("kế hoạch cần ít nhất một bước")
    if len(clean) > MAX_STEPS:
        raise ValueError(f"tối đa {MAX_STEPS} bước, hãy gộp bớt")
    return _save(sid, [{"id": i, "text": t[:300], "status": "pending", "note": ""} for i, t in enumerate(clean, 1)])


def update(sid: str, step: int, status: str, note: str = "") -> list[dict]:
    if status not in STATUSES:
        raise ValueError(f"trạng thái phải là một trong: {', '.join(STATUSES)}")
    items = get(sid)
    for it in items:
        if it["id"] == step:
            it["status"], it["note"] = status, note[:300]
            return _save(sid, items)
    raise ValueError(f"không có bước {step} (có {len(items)} bước)")


def render(items: list[dict]) -> str:
    return "\n".join(f"{it['id']}. {MARK[it['status']]} {it['text']}" + (f"  ({it['note']})" if it["note"] else "") for it in items)


def progress(items: list[dict]) -> tuple[int, int]:
    return sum(it["status"] == "done" for it in items), len(items)


def prompt_block(sid: str) -> str:
    items = get(sid)
    if not items:
        return ""
    done, total = progress(items)
    return f"Kế hoạch hiện tại của hội thoại ({done}/{total} xong):\n{render(items)}\nLàm lần lượt các bước, gọi plan_update khi bắt đầu/xong/bị chặn một bước."
