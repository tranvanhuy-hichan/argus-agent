"""Kenh Telegram (long polling, khong can cong mo ra ngoai): nhan tin -> agent -> tra loi, xin phep bang nut bam."""
import logging
import secrets
import threading
import time

import httpx

from ..core import config as cfgmod
from ..core.db import db
from . import chat_runner, notifications, sessions, workfiles

log = logging.getLogger("telegram")
CHUNK = 4000
PAIR_TTL = 600
KIND_LABEL = {"exec": "chạy lệnh shell", "mcp": "gọi tool MCP", "file_read": "đọc file ngoài workspace", "file_write": "ghi file ngoài workspace"}
_pair: dict[str, float] = {}


def new_pair_code() -> str:
    code = f"{secrets.randbelow(10**6):06d}"
    _pair[code] = time.time() + PAIR_TTL
    return code


def _consume_pair(code: str) -> bool:
    exp = _pair.pop(code, 0)
    return exp > time.time()


def _link_get(chat_id: int) -> str | None:
    with db() as c:
        r = c.execute("SELECT session_id FROM channel_links WHERE channel='telegram' AND external_id=?", (str(chat_id),)).fetchone()
    return r["session_id"] if r and sessions.get(r["session_id"]) else None


def _link_set(chat_id: int, sid: str) -> None:
    with db() as c:
        c.execute("INSERT OR REPLACE INTO channel_links(channel,external_id,session_id) VALUES('telegram',?,?)", (str(chat_id), sid))


def _chunks(text: str) -> list[str]:
    return [text[i:i + CHUNK] for i in range(0, len(text), CHUNK)] or ["(không có nội dung)"]


class TelegramChannel:
    def __init__(self) -> None:
        self.cfg = cfgmod.TelegramCfg()
        self.stop_evt = threading.Event()
        self.thread: threading.Thread | None = None
        self.status = {"running": False, "error": "", "bot": ""}
        self._locks: dict[int, threading.Lock] = {}
        self._pending: dict[int, set[str]] = {}  # yeu cau xin phep dang cho, theo chat
        notifications.listeners.append(self._notify)

    # ---- vong doi
    def apply(self, cfg: cfgmod.TelegramCfg) -> None:
        if self.thread and (not cfg.enabled or cfg.token != self.cfg.token or cfg.api_base != self.cfg.api_base):
            self.stop_evt.set()
            self.thread = None
        self.cfg = cfg
        if cfg.enabled and cfg.token and not self.thread:
            self.stop_evt = threading.Event()
            self.thread = threading.Thread(target=self._poll, args=(self.stop_evt,), daemon=True, name="telegram")
            self.thread.start()
        elif not cfg.enabled:
            self.status = {"running": False, "error": "", "bot": ""}

    def api(self, method: str, http_timeout: float = 40, **params) -> dict:
        r = httpx.post(f"{self.cfg.api_base}/bot{self.cfg.token}/{method}", json=params, timeout=http_timeout)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"{method}: {data.get('description', r.status_code)}")
        return data["result"]

    def _poll(self, stop: threading.Event) -> None:
        offset = 0
        try:
            me = self.api("getMe", http_timeout=15)
            self.status = {"running": True, "error": "", "bot": f"@{me.get('username', '')}"}
        except Exception as e:  # noqa: BLE001 - hien loi token len UI
            self.status = {"running": False, "error": str(e)[:200], "bot": ""}
            return
        while not stop.is_set():
            try:
                for u in self.api("getUpdates", http_timeout=40, offset=offset, timeout=20, allowed_updates=["message", "callback_query"]):
                    offset = u["update_id"] + 1
                    threading.Thread(target=self._handle, args=(u,), daemon=True).start()
            except Exception as e:  # noqa: BLE001
                self.status["error"] = str(e)[:200]
                stop.wait(5)
            else:
                self.status["error"] = ""

    # ---- xu ly tin
    def _allowed(self, user_id: int) -> bool:
        return user_id in cfgmod.load().channels.telegram.allowed_users

    def _handle(self, u: dict) -> None:
        try:
            if "callback_query" in u:
                return self._on_callback(u["callback_query"])
            msg = u.get("message") or {}
            if not msg.get("from"):
                return
            uid, chat = msg["from"]["id"], msg["chat"]["id"]
            text = (msg.get("text") or msg.get("caption") or "").strip()
            if text.startswith("/id"):
                return self._say(chat, f"ID Telegram của bạn: {uid}")
            if text.startswith("/pair"):
                code = text.removeprefix("/pair").strip()
                if _consume_pair(code):
                    cfg = cfgmod.load()
                    if uid not in cfg.channels.telegram.allowed_users:
                        cfg.channels.telegram.allowed_users.append(uid)
                        cfgmod.save(cfg)
                    self.cfg = cfg.channels.telegram
                    return self._say(chat, "Đã ghép đôi thành công. Bạn có thể nhắn tin cho agent.")
                return self._say(chat, "Mã ghép đôi sai hoặc đã hết hạn. Tạo mã mới trong giao diện, mục Tích hợp > Kênh chat.")
            if not self._allowed(uid):
                return self._say(chat, "Bạn chưa được phép dùng agent này. Tạo mã ghép đôi trong giao diện web rồi gửi: /pair <mã>")
            denied = self._deny_pending(chat)  # tin moi/ /stop = bo qua yeu cau dang cho, khong de treo hoi thoai
            if text.startswith("/stop"):
                return self._say(chat, "Đã hủy yêu cầu đang chờ." if denied else "Không có gì đang chờ.")
            if text.startswith("/new"):
                with db() as c:
                    c.execute("DELETE FROM channel_links WHERE channel='telegram' AND external_id=?", (str(chat),))
                return self._say(chat, "Đã bắt đầu hội thoại mới.")
            if text.startswith("/help") or text == "/start":
                return self._say(chat, "Cứ nhắn tin để giao việc cho agent. Lệnh: /new (hội thoại mới), /stop (hủy yêu cầu đang chờ), /id, /help.")
            lock = self._locks.setdefault(chat, threading.Lock())
            with lock:
                self._run(chat, msg, text)
        except Exception as e:  # noqa: BLE001 - mot tin loi khong duoc lam chet luong polling
            log.warning("telegram handle: %s", e)

    def _deny_pending(self, chat: int) -> bool:
        pending = self._pending.pop(chat, set())
        for aid in pending:
            chat_runner.resolve_approval(aid, False)
        return bool(pending)

    def _say(self, chat: int, text: str) -> None:
        for part in _chunks(text):
            self.api("sendMessage", chat_id=chat, text=part)

    def _download(self, sid: str, msg: dict) -> list[str]:
        file_id = name = None
        if msg.get("photo"):
            file_id, name = msg["photo"][-1]["file_id"], f"anh_{msg['message_id']}.jpg"
        elif msg.get("document"):
            file_id, name = msg["document"]["file_id"], msg["document"].get("file_name") or f"tep_{msg['message_id']}"
        if not file_id:
            return []
        info = self.api("getFile", file_id=file_id)
        if info.get("file_size", 0) > workfiles.MAX_UPLOAD:
            return []
        data = httpx.get(f"{self.cfg.api_base}/file/bot{self.cfg.token}/{info['file_path']}", timeout=60).content
        dest = workfiles.session_dir(cfgmod.load(), sid) / "uploads" / "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return [dest.relative_to(workfiles.session_dir(cfgmod.load(), sid)).as_posix()]

    def _run(self, chat: int, msg: dict, text: str) -> None:
        sid = _link_get(chat)
        if not sid:
            sid = sessions.create(text[:40] or "Telegram", source="telegram")
            _link_set(chat, sid)
        attachments = self._download(sid, msg)
        text = text or "(người dùng gửi tệp đính kèm)"
        self.api("sendChatAction", chat_id=chat, action="typing")
        before = {t["path"]: t["mtime"] for t in workfiles.tree(workfiles.session_dir(cfgmod.load(), sid)) if not t["dir"]}
        reply, error = "", ""
        for ev in chat_runner.stream_chat(sid, text, None, source="telegram", attachments=attachments):
            if ev["type"] == "approval":
                self._pending.setdefault(chat, set()).add(ev["id"])
                self.api("sendMessage", chat_id=chat, text=f"Agent muốn {KIND_LABEL.get(ev['kind'], ev['kind'])}:\n{ev['detail'][:3000]}",
                         reply_markup={"inline_keyboard": [[{"text": "✅ Cho phép", "callback_data": f"ap:{ev['id']}:1"}, {"text": "❌ Từ chối", "callback_data": f"ap:{ev['id']}:0"}]]})
            elif ev["type"] == "assistant" and ev["content"]:
                reply = ev["content"]
            elif ev["type"] == "error":
                error = ev["message"]
        self._say(chat, reply or (f"⚠ {error}" if error else "(agent không trả lời)"))
        if error and reply:
            self._say(chat, f"⚠ {error}")
        base = workfiles.session_dir(cfgmod.load(), sid)
        fresh = [t for t in workfiles.tree(base) if not t["dir"] and before.get(t["path"]) != t["mtime"]
                 and not t["path"].startswith("uploads/") and 0 < t["size"] <= 10 * 1024 * 1024]
        for t in fresh[:3]:  # gui toi da 3 file agent vua tao/sua
            self._send_file(chat, base / t["path"])

    def _send_file(self, chat: int, path) -> None:
        httpx.post(f"{self.cfg.api_base}/bot{self.cfg.token}/sendDocument", data={"chat_id": chat}, files={"document": (path.name, path.read_bytes())}, timeout=60)

    def _on_callback(self, cq: dict) -> None:
        if not self._allowed(cq["from"]["id"]):
            return self.api("answerCallbackQuery", callback_query_id=cq["id"], text="Bạn không có quyền.")
        _, aid, ok = cq["data"].split(":")
        done = chat_runner.resolve_approval(aid, ok == "1")
        for pend in self._pending.values():
            pend.discard(aid)
        self.api("answerCallbackQuery", callback_query_id=cq["id"], text="Đã ghi nhận" if done else "Yêu cầu đã hết hạn")
        m = cq.get("message") or {}
        if m:
            self.api("editMessageText", chat_id=m["chat"]["id"], message_id=m["message_id"], text=f"{m.get('text', '')}\n\n{'✅ Đã cho phép' if ok == '1' else '❌ Đã từ chối'}")

    # ---- thong bao chu dong (heartbeat, automation)
    def _notify(self, n: dict) -> None:
        if not self.status["running"]:
            return
        for uid in self.cfg.allowed_users:
            self._say(uid, f"🔔 {n['title']}\n{n['body']}")


channel = TelegramChannel()
