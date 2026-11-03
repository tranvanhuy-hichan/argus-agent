"""Lập chỉ mục vector nền cho tin nhắn và MEMORY.md. Lỗi không bao giờ được làm hỏng chat."""
import logging
import queue
import re
import threading
import time
from collections.abc import Callable

from ..core import config as cfgmod
from . import embeddings, vectorstore

log = logging.getLogger("argus.memory_index")
MIN_CHARS = 8
CHUNK = 800
_q: queue.Queue = queue.Queue()
_worker: threading.Thread | None = None
_lock = threading.Lock()
progress: dict = {"running": False, "done": 0, "total": 0, "error": "", "finished": 0.0}


def chunk_text(text: str, size: int = CHUNK) -> list[str]:
    """Cắt theo đoạn/câu thành các mảnh ~size ký tự."""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    pieces: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        for s in re.split(r"(?<=[.!?。])\s+|\n", para):
            while len(s) > size:  # câu quá dài: cắt cứng ở khoảng trắng gần nhất
                cut = s.rfind(" ", 0, size)
                cut = cut if cut > size // 2 else size
                pieces.append(s[:cut])
                s = s[cut:].lstrip()
            if s.strip():
                pieces.append(s.strip())
    out, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) + 1 > size:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        out.append(cur)
    return out


def _enabled(cfg) -> bool:
    return cfg.memory.embeddings != "off" and cfg.memory.auto_index


def _ensure_worker() -> None:
    global _worker
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="memory-index", daemon=True)
            _worker.start()


def enqueue_message(session_id: str, role: str, content: str, ts: float | None = None) -> None:
    """Không chặn: chỉ đưa vào hàng đợi; luồng nền sẽ nhúng và lưu."""
    try:
        if role not in ("user", "assistant") or len((content or "").strip()) < MIN_CHARS:
            return
        _q.put((session_id, role, content, ts or time.time()))
        _ensure_worker()
    except Exception:  # noqa: BLE001
        log.exception("enqueue thất bại")


def _run() -> None:
    while True:
        batch = [_q.get()]
        try:
            while len(batch) < 32:
                batch.append(_q.get_nowait())
        except queue.Empty:
            pass
        try:
            _process(batch)
        except Exception:  # noqa: BLE001
            log.warning("lập chỉ mục thất bại, bỏ qua lô", exc_info=True)
        finally:
            for _ in batch:
                _q.task_done()


def _process(batch: list[tuple]) -> None:
    cfg = cfgmod.load()
    if not _enabled(cfg):
        return
    rows = [(sid, role, ch, ts) for sid, role, content, ts in batch for ch in chunk_text(content) if len(ch) >= MIN_CHARS]
    if not rows:
        return
    vecs, model = embeddings.embed(cfg, [r[2] for r in rows])
    vectorstore.add([{"kind": "message", "ref": r[1], "session_id": r[0], "text": r[2], "model": model, "vec": v, "ts": r[3]} for r, v in zip(rows, vecs)])


def flush(timeout: float = 10.0) -> bool:
    """Chờ hàng đợi rỗng (dùng cho test/CLI). True nếu xong trong thời hạn."""
    end = time.time() + timeout
    while time.time() < end:
        if _q.unfinished_tasks == 0:
            return True
        time.sleep(0.02)
    return _q.unfinished_tasks == 0


def note_lines(cfg) -> list[str]:
    f = cfg.workspace_path() / "MEMORY.md"
    if not f.exists():
        return []
    return [ln.strip()[2:].strip() for ln in f.read_text(errors="replace").splitlines() if ln.strip().startswith("- ") and len(ln.strip()) > 4]


def index_notes(cfg) -> int:
    """Nhúng lại các dòng MEMORY.md (kind='note')."""
    lines = note_lines(cfg)
    vectorstore.delete_kind("note")
    if not lines:
        return 0
    vecs, model = embeddings.embed(cfg, lines)
    return vectorstore.add([{"kind": "note", "ref": "MEMORY.md", "text": t, "model": model, "vec": v} for t, v in zip(lines, vecs)])


def reindex(cfg, on_progress: Callable[[int, int], None] | None = None) -> dict:
    """Nhúng lại toàn bộ: mọi tin nhắn của mọi phiên + ghi chú MEMORY.md."""
    from ..core.db import db
    e = embeddings.get_embedder(cfg)
    if e is None:
        raise embeddings.EmbeddingError("embedding đang tắt")
    with db() as c:
        msgs = c.execute("SELECT session_id, role, content, ts FROM messages WHERE role IN ('user','assistant') AND content!='' ORDER BY id").fetchall()
    rows = [(m["session_id"], m["role"], ch, m["ts"]) for m in msgs for ch in chunk_text(m["content"]) if len(ch) >= MIN_CHARS]
    notes = note_lines(cfg)
    total = len(rows) + len(notes)
    vectorstore.clear()
    done = 0
    for i in range(0, len(rows), 32):
        part = rows[i:i + 32]
        vecs, model = e.embed([r[2] for r in part])
        vectorstore.add([{"kind": "message", "ref": r[1], "session_id": r[0], "text": r[2], "model": model, "vec": v, "ts": r[3]} for r, v in zip(part, vecs)])
        done += len(part)
        if on_progress:
            on_progress(done, total)
    n = index_notes(cfg)
    if on_progress:
        on_progress(total, total)
    return {"messages": len(rows), "notes": n, "model": e.model_id}


def start_reindex(cfg) -> bool:
    """Chạy reindex ở luồng nền; False nếu đang chạy."""
    with _lock:
        if progress["running"]:
            return False
        progress.update(running=True, done=0, total=0, error="")

    def cb(d: int, t: int) -> None:
        progress.update(done=d, total=t)

    def job() -> None:
        try:
            reindex(cfg, cb)
        except Exception as ex:  # noqa: BLE001
            progress["error"] = str(ex)[:200]
        finally:
            progress.update(running=False, finished=time.time())

    threading.Thread(target=job, name="memory-reindex", daemon=True).start()
    return True
