"""Quản lý trình duyệt Chromium (Playwright sync API) chạy trong MỘT thread riêng."""
from __future__ import annotations

import atexit
import queue
import re
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..core import config as cfgmod
from ..core.paths import DATA

CANDIDATES = ("/snap/bin/chromium", "chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
PROFILE_ROOT = DATA / "browser" / "profile"  # thư mục KHÔNG ẩn: snap chromium không ghi được vào thư mục ẩn hoặc /tmp


def find_chromium(configured: str = "") -> str | None:
    """Tìm file thực thi Chromium/Chrome trong máy."""
    if configured:
        return shutil.which(configured) or (configured if Path(configured).exists() else None)
    for c in CANDIDATES:
        p = shutil.which(c)
        if p:
            return p
    return None


class Session:
    """Một context trình duyệt của một cuộc hội thoại."""

    def __init__(self, key: str, context: Any):
        self.key = key
        self.context = context
        self.pages: list[Any] = []
        self.page: Any = None
        self.dialogs: list[str] = []
        self.shots = 0
        self.last_used = time.time()
        context.on("page", self._on_page)
        for p in context.pages:
            self._on_page(p)
        if not self.pages:
            self._on_page(context.new_page())
        self.page = self.pages[-1]

    def _on_page(self, page: Any) -> None:
        self.pages.append(page)
        self.page = page
        page.on("dialog", self._on_dialog)
        page.on("close", lambda *_: self._on_close(page))

    def _on_close(self, page: Any) -> None:
        if page in self.pages:
            self.pages.remove(page)
        if self.page is page and self.pages:
            self.page = self.pages[-1]

    def _on_dialog(self, d: Any) -> None:
        self.dialogs.append(f"{d.type}: {d.message}")
        try:
            d.dismiss()
        except Exception:  # noqa: BLE001
            pass

    def current(self) -> Any:
        if self.page is None or self.page.is_closed():
            self.page = self.pages[-1] if self.pages else self.context.new_page()
        return self.page


class BrowserManager:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pw: Any = None
        self._sessions: dict[str, Session] = {}
        self._stop = False

    # ---- thread worker
    def _ensure_thread(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop = False
            self._thread = threading.Thread(target=self._loop, name="argus-browser", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while not self._stop:
            try:
                item = self._q.get(timeout=15)
            except queue.Empty:
                self._reap()
                continue
            if item is None:
                break
            fn, box, done = item
            try:
                box["ok"] = fn()
            except BaseException as e:  # noqa: BLE001 - trả lại cho thread gọi
                box["err"] = e
            done.set()
            self._reap()
        self._close_all()

    def _reap(self) -> None:
        try:
            idle = cfgmod.load().browser.idle_minutes * 60
        except Exception:  # noqa: BLE001
            idle = 600
        for k, s in list(self._sessions.items()):
            if time.time() - s.last_used > idle:
                self._close_session(k)
        if not self._sessions and self._pw is not None:
            self._stop_pw()

    def _close_session(self, key: str) -> None:
        s = self._sessions.pop(key, None)
        if s:
            try:
                s.context.close()
            except Exception:  # noqa: BLE001
                pass

    def _stop_pw(self) -> None:
        try:
            self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._pw = None

    def _close_all(self) -> None:
        for k in list(self._sessions):
            self._close_session(k)
        if self._pw is not None:
            self._stop_pw()

    # ---- gọi từ thread bất kỳ
    def run(self, fn: Callable[[], Any], timeout: float = 60, cancel: Any = None) -> Any:
        """Chạy fn trong thread trình duyệt, trả kết quả hoặc ném lại lỗi."""
        self._ensure_thread()
        box: dict = {}
        done = threading.Event()
        self._q.put((fn, box, done))
        end = time.time() + timeout
        while not done.wait(0.25):
            if cancel is not None and cancel.is_set():
                raise RuntimeError("đã huỷ")
            if time.time() > end:
                raise TimeoutError(f"trình duyệt không phản hồi sau {int(timeout)} giây")
        if "err" in box:
            raise box["err"]
        return box.get("ok")

    def with_session(self, key: str, fn: Callable[[Session], Any], timeout: float = 60, cancel: Any = None) -> Any:
        """Lấy (hoặc tạo) session theo key rồi chạy fn(session) trong thread trình duyệt."""
        def job() -> Any:
            s = self._get(key)
            s.last_used = time.time()
            try:
                return fn(s)
            finally:
                s.last_used = time.time()
        return self.run(job, timeout, cancel)

    def _get(self, key: str) -> Session:
        s = self._sessions.get(key)
        if s is not None:
            try:
                s.context.pages  # noqa: B018 - kiểm tra context còn sống
                return s
            except Exception:  # noqa: BLE001
                self._sessions.pop(key, None)
        cfg = cfgmod.load().browser
        exe = find_chromium(cfg.executable)
        if not exe:
            raise RuntimeError("không tìm thấy Chromium/Chrome trong máy (đặt browser.executable trong cấu hình)")
        if self._pw is None:
            from playwright.sync_api import sync_playwright  # lazy
            self._pw = sync_playwright().start()
        prof = PROFILE_ROOT / (re.sub(r"[^A-Za-z0-9_-]", "_", key)[:60] or "default")
        prof.mkdir(parents=True, exist_ok=True)
        ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(prof), executable_path=exe, headless=cfg.headless,
            viewport={"width": 1280, "height": 800}, accept_downloads=False,
        )
        ctx.set_default_timeout(15000)
        s = Session(key, ctx)
        self._sessions[key] = s
        return s

    def close(self, key: str) -> bool:
        if not (self._thread and self._thread.is_alive()):
            return False
        had = key in self._sessions
        self.run(lambda: self._close_session(key), 20)
        return had

    def shutdown(self) -> None:
        t = self._thread
        if t and t.is_alive():
            self._stop = True
            self._q.put(None)
            t.join(10)

    def status(self) -> dict:
        """Thông tin cho `argus doctor`."""
        cfg = cfgmod.load().browser
        out: dict = {"enabled": cfg.enabled, "playwright": False, "executable": find_chromium(cfg.executable), "launchable": False, "error": ""}
        try:
            import playwright  # noqa: F401
            out["playwright"] = True
        except Exception as e:  # noqa: BLE001
            out["error"] = f"thiếu playwright: {e}"
            return out
        if not out["executable"]:
            out["error"] = "không tìm thấy Chromium/Chrome"
            return out
        try:
            self.with_session("__doctor__", lambda s: s.current().title(), 45)
            self.close("__doctor__")
            out["launchable"] = True
        except Exception as e:  # noqa: BLE001
            out["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        return out


manager = BrowserManager()
atexit.register(manager.shutdown)
