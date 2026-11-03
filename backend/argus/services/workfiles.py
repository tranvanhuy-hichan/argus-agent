"""Thu muc lam viec rieng cua moi phien: workspace/sessions/<sid>/ (file agent tao ra, file nguoi dung dinh kem)."""
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


def safe_path(base: Path, rel: str) -> Path:
    """Phan giai `rel` ben trong `base`; tu choi '..', duong dan tuyet doi va symlink thoat ra ngoai."""
    if not rel or rel.startswith(("/", "\\")) or "\x00" in rel:
        raise PathError("đường dẫn không hợp lệ")
    root = base.resolve()
    target = (base / rel).resolve()
    if target != root and root not in target.parents:
        raise PathError("đường dẫn nằm ngoài thư mục cho phép")
    return target


def tree(base: Path, limit: int = 500) -> list[dict]:
    if not base.is_dir():
        return []
    out = []
    for p in sorted(base.rglob("*")):
        if any(part.startswith(".") for part in p.relative_to(base).parts):
            continue
        st = p.stat()
        out.append({"path": p.relative_to(base).as_posix(), "dir": p.is_dir(), "size": 0 if p.is_dir() else st.st_size, "mtime": st.st_mtime})
        if len(out) >= limit:
            break
    return out
