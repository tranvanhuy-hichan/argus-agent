"""Checkpoint theo luot: truoc khi agent ghi/sua file, luu ban goc de co the hoan tac ca luot. Chi giu luot gan nhat cua moi phien.
(Chi bat duoc file do tool write/edit thay doi; file bi doi boi lenh shell thi khong hoan tac duoc.)"""
import difflib
import json
import shutil
import threading
from pathlib import Path

from ..core import db as dbmod

MAX_BYTES = 5 * 1024 * 1024
_active: dict[str, dict[str, bytes | None]] = {}
_lock = threading.Lock()


def _dir(sid: str) -> Path:
    return Path(dbmod.DATA) / "checkpoints" / sid


def begin(sid: str) -> None:
    with _lock:
        _active[sid] = {}


def record(sid: str | None, path: Path) -> None:
    """Goi truoc khi ghi `path`: nho noi dung goc (None = file chua ton tai)."""
    if not sid:
        return
    with _lock:
        snap = _active.get(sid)
        if snap is None or str(path) in snap:
            return
        try:
            snap[str(path)] = path.read_bytes() if path.is_file() and path.stat().st_size <= MAX_BYTES else (None if not path.exists() else b"__SKIP__")
        except OSError:
            snap[str(path)] = b"__SKIP__"


def _count(old: bytes | None, new: bytes | None) -> tuple[int, int]:
    a = (old or b"").decode("utf-8", "replace").splitlines()
    b = (new or b"").decode("utf-8", "replace").splitlines()
    added = removed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return added, removed


def finish(sid: str) -> dict | None:
    """Ket thuc luot: luu checkpoint neu co file doi. Tra ve tom tat {"files": [{path, status, added, removed}]} hoac None."""
    with _lock:
        snap = _active.pop(sid, None)
    if not snap:
        return None
    files, manifest = [], {}
    d = _dir(sid)
    changes = []
    for p, old in snap.items():
        if old == b"__SKIP__":
            continue
        path = Path(p)
        new = path.read_bytes() if path.is_file() else None
        if new == old:
            continue
        changes.append((p, old, new))
    if not changes:
        return None
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    for i, (p, old, new) in enumerate(changes):
        if old is not None:
            (d / f"{i}.bak").write_bytes(old)
        manifest[p] = {"existed": old is not None, "blob": f"{i}.bak"}
        a, r = _count(old, new)
        files.append({"path": p, "status": "new" if old is None else "modified", "added": a, "removed": r})
    (d / "manifest.json").write_text(json.dumps(manifest))
    return {"files": files}


def last(sid: str) -> list[str]:
    m = _dir(sid) / "manifest.json"
    try:
        return list(json.loads(m.read_text()))
    except (OSError, ValueError):
        return []


def undo(sid: str) -> list[str]:
    """Khoi phuc cac file ve trang thai truoc luot gan nhat (file moi tao thi xoa). Xong thi bo checkpoint."""
    d = _dir(sid)
    try:
        manifest = json.loads((d / "manifest.json").read_text())
    except (OSError, ValueError):
        return []
    restored = []
    for p, info in manifest.items():
        path = Path(p)
        try:
            if info["existed"]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((d / info["blob"]).read_bytes())
            else:
                path.unlink(missing_ok=True)
            restored.append(p)
        except OSError:
            pass
    shutil.rmtree(d, ignore_errors=True)
    return restored
