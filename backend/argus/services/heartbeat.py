"""Heartbeat: dinh ky cho agent tu kiem tra danh sach viec trong HEARTBEAT.md va chu dong bao khi co gi dang chu y."""
import threading
import time

from ..core import config as cfgmod
from ..core.db import db
from . import agent, notifications, sessions

OK_TOKEN = "HEARTBEAT_OK"
DEFAULT_FILE = """# Heartbeat
Danh sách việc agent tự kiểm tra mỗi lần heartbeat. Mỗi dòng là một việc. Xóa hết nội dung để tạm dừng.

- Nếu thư mục workspace có file mới đáng chú ý, hãy báo cho tôi.
"""
_stop = threading.Event()
_state = {"next": 0.0, "running": False}


def kv_get(key: str) -> str:
    with db() as c:
        r = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return r["value"] if r else ""


def kv_set(key: str, value: str) -> None:
    with db() as c:
        c.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (key, value))


def status() -> dict:
    cfg = cfgmod.load().heartbeat
    return {"enabled": cfg.enabled, "interval_minutes": cfg.interval_minutes, "running": _state["running"],
            "last_run": float(kv_get("hb_last_run") or 0) or None, "last_status": kv_get("hb_last_status") or None,
            "last_output": kv_get("hb_last_output") or None, "next_run": _state["next"] or None}


def run_once() -> dict:
    if _state["running"]:
        return status()
    _state["running"] = True
    try:
        cfg = cfgmod.load()
        f = cfg.workspace_path() / "HEARTBEAT.md"
        checklist = f.read_text().strip() if f.exists() else ""
        sid = kv_get("hb_session")
        if not sid or not sessions.get(sid):
            sid = sessions.create("💓 Heartbeat", source="heartbeat")
            kv_set("hb_session", sid)
        prompt = (f"Đây là heartbeat định kỳ, không có người dùng đang chờ. Làm theo danh sách việc dưới đây (dùng tool nếu cần). "
                  f"Nếu không có gì đáng báo, trả lời đúng một dòng: {OK_TOKEN}. Nếu có, trả lời ngắn gọn điều cần báo cho người dùng.\n\n{checklist}")
        events: list[dict] = []
        agent.run_turn(sid, prompt, cfg.heartbeat.provider, lambda k, d: False, events.append, source="heartbeat")
        err = next((e["message"] for e in events if e["type"] == "error"), None)
        text = next((e["content"] for e in reversed(events) if e["type"] == "assistant"), "").strip()
        status_ = "error" if err else ("ok" if OK_TOKEN in text or not text else "alert")
        if status_ == "alert":
            notifications.add("Heartbeat", text, source="heartbeat", session_id=sid)
        kv_set("hb_last_run", str(time.time()))
        kv_set("hb_last_status", status_)
        kv_set("hb_last_output", (err or text)[:1000])
    finally:
        _state["running"] = False
        _state["next"] = time.time() + cfgmod.load().heartbeat.interval_minutes * 60
    return status()


def _loop() -> None:
    while not _stop.wait(20):
        cfg = cfgmod.load().heartbeat
        if not cfg.enabled:
            _state["next"] = 0
            continue
        if not _state["next"]:
            _state["next"] = time.time() + cfg.interval_minutes * 60
        if time.time() >= _state["next"]:
            threading.Thread(target=run_once, daemon=True).start()
            _state["next"] = time.time() + cfg.interval_minutes * 60


def start() -> None:
    _stop.clear()
    threading.Thread(target=_loop, daemon=True, name="heartbeat").start()


def stop() -> None:
    _stop.set()
