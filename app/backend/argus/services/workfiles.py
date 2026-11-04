"""Thu muc lam viec rieng cua moi phien: workspace/sessions/<sid>/ (file agent tao ra, file nguoi dung dinh kem)."""
import os
import re
from pathlib import Path

from ..core.config import Config

SID_RE = re.compile(r"^[a-f0-9]{8}$")
MAX_UPLOAD = 25 * 1024 * 1024


class PathError(ValueError):
    pass


def session_dir(cfg: Config, sid: str) -> Path:
    if not SID_RE.match(sid):
        raise PathError("session id không hợp lệ")
    return cfg.workspace_path() / "sessions" / sid


def workdir_for(cfg: Config, sid: str) -> Path:
    """Thư mục làm việc của phiên: dự án người dùng đã mở (chế độ Code) hoặc thư mục riêng của phiên."""
    from . import sessions
    project = (sessions.get(sid) or {}).get("project") or ""
    return Path(project) if project else session_dir(cfg, sid)


def safe_path(base: Path, rel: str) -> Path:
    """Phan giai `rel` ben trong `base`; tu choi '..', duong dan tuyet doi va symlink thoat ra ngoai."""
    if not rel or rel.startswith(("/", "\\")) or "\x00" in rel:
        raise PathError("đường dẫn không hợp lệ")
    root = base.resolve()
    target = (base / rel).resolve()
    if target != root and root not in target.parents:
        raise PathError("đường dẫn nằm ngoài thư mục cho phép")
    return target


IGNORE = {"node_modules", "__pycache__", "venv", "dist", "build", "target", "coverage"}


def tree(base: Path, limit: int = 500) -> list[dict]:
    """Liệt kê file; bỏ thư mục ẩn và thư mục nặng (node_modules, venv...) ngay khi duyệt để dự án lớn không bị chậm."""
    if not base.is_dir():
        return []
    out: list[dict] = []
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in IGNORE and not (Path(root) / d).is_symlink())
        for name in [*dirs, *sorted(f for f in files if not f.startswith("."))]:
            p = Path(root) / name
            try:
                st = p.stat()
            except OSError:
                continue
            out.append({"path": p.relative_to(base).as_posix(), "dir": p.is_dir(), "size": 0 if p.is_dir() else st.st_size, "mtime": st.st_mtime})
            if len(out) >= limit:
                return sorted(out, key=lambda e: e["path"])
    return sorted(out, key=lambda e: e["path"])
