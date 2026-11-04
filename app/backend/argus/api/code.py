"""Chế độ Code: mở một dự án trên máy làm thư mục làm việc của phiên, xem thay đổi (git) và hoàn tác từng file."""
import json
import os
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.db import db
from ..services import sessions, workfiles

AUTO = True
router = APIRouter()
MAX_DIFF = 200_000
RECENT_KEY = "code_recent"


def _recent() -> list[dict]:
    with db() as c:
        r = c.execute("SELECT value FROM kv WHERE key=?", (RECENT_KEY,)).fetchone()
    try:
        return json.loads(r["value"]) if r else []
    except ValueError:
        return []


def _remember(path: str) -> None:
    items = [x for x in _recent() if x["path"] != path][:11]
    items.insert(0, {"path": path, "name": Path(path).name or path, "ts": time.time()})
    with db() as c:
        c.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (RECENT_KEY, json.dumps(items)))


def _dir(path: str) -> Path:
    p = Path(path).expanduser()
    try:
        p = p.resolve()
    except OSError as e:
        raise HTTPException(400, "đường dẫn không hợp lệ") from e
    if not p.is_dir():
        raise HTTPException(400, "không phải thư mục")
    return p


@router.get("/code/browse")
def browse(path: str = ""):
    """Liệt kê thư mục con để chọn dự án (chỉ thư mục, bỏ thư mục ẩn)."""
    if os.name == "nt" and path == "::drives":
        drives = [f"{c}:\\" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{c}:\\").exists()]
        return {"path": "", "parent": None, "git": False, "dirs": [{"name": d, "path": d, "git": False} for d in drives]}
    p = _dir(path or str(Path.home()))
    dirs = []
    try:
        for d in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            if d.name.startswith(".") or not d.is_dir():
                continue
            dirs.append({"name": d.name, "path": str(d), "git": (d / ".git").exists()})
    except PermissionError as e:
        raise HTTPException(403, "không có quyền đọc thư mục này") from e
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "git": (p / ".git").exists(), "dirs": dirs}


def _branch(p: Path) -> str:
    """Tên nhánh đọc thẳng từ .git/HEAD (không gọi git cho từng dự án)."""
    try:
        head = (p / ".git" / "HEAD").read_text().strip()
    except OSError:
        return ""
    return head.removeprefix("ref: refs/heads/") if head.startswith("ref: ") else head[:7]


@router.get("/code/projects")
def projects():
    out = []
    for x in _recent():
        p = Path(x["path"])
        if p.is_dir():
            out.append({**x, "git": (p / ".git").exists(), "branch": _branch(p)})
    return out


class OpenBody(BaseModel):
    path: str


@router.post("/code/open")
def open_project(b: OpenBody):
    p = _dir(b.path)
    _remember(str(p))
    return {"id": sessions.create(p.name or str(p), source="code", project=str(p)), "project": str(p)}


# ---------- git cho phien co du an
def _project(sid: str) -> Path:
    s = sessions.get(sid)
    if not s:
        raise HTTPException(404, "không có phiên này")
    if not s.get("project"):
        raise HTTPException(400, "phiên này không mở dự án")
    p = Path(s["project"])
    if not p.is_dir():
        raise HTTPException(404, "thư mục dự án không còn tồn tại")
    return p


def _git(p: Path, *args: str, ok: tuple[int, ...] = (0,)) -> str:
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=p, capture_output=True, text=True, timeout=20, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.TimeoutExpired) as e:
        raise HTTPException(500, f"không chạy được git: {e}") from e
    if r.returncode not in ok:
        raise HTTPException(400, (r.stderr or r.stdout).strip()[:300] or "git báo lỗi")
    return r.stdout


def _is_repo(p: Path) -> bool:
    try:
        r = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=p, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


@router.get("/sessions/{sid}/git")
def git_status(sid: str):
    p = _project(sid)
    if not _is_repo(p):
        return {"repo": False, "branch": "", "files": []}
    out = _git(p, "status", "--porcelain=v1", "-b", "-uall")
    branch, files = "", []
    for line in out.splitlines():
        if line.startswith("## "):
            branch = line[3:].split("...")[0]
            continue
        code, path = line[:2], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append({"path": path.strip('"'), "status": "new" if code == "??" or "A" in code else "deleted" if "D" in code else "modified"})
    return {"repo": True, "branch": branch, "files": files[:500]}


@router.get("/sessions/{sid}/git/diff")
def git_diff(sid: str, path: str):
    p = _project(sid)
    try:
        target = workfiles.safe_path(p, path)
    except workfiles.PathError as e:
        raise HTTPException(400, str(e)) from e
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", path], cwd=p, capture_output=True, timeout=10).returncode == 0
    if tracked:
        diff = _git(p, "diff", "HEAD", "--no-color", "--", path)
    elif target.is_file():
        diff = _git(p, "diff", "--no-index", "--no-color", "--", "/dev/null", path, ok=(0, 1))
    else:
        diff = ""
    return {"diff": diff[:MAX_DIFF], "truncated": len(diff) > MAX_DIFF}


class RevertBody(BaseModel):
    path: str


@router.post("/sessions/{sid}/git/revert")
def git_revert(sid: str, b: RevertBody):
    """Hoàn tác một file về trạng thái HEAD; file mới (chưa có trong git) thì xóa đi."""
    p = _project(sid)
    try:
        target = workfiles.safe_path(p, b.path)
    except workfiles.PathError as e:
        raise HTTPException(400, str(e)) from e
    in_head = subprocess.run(["git", "cat-file", "-e", f"HEAD:{b.path}"], cwd=p, capture_output=True, timeout=10).returncode == 0
    if in_head:
        _git(p, "restore", "--source=HEAD", "--staged", "--worktree", "--", b.path)
    else:
        subprocess.run(["git", "rm", "-f", "--cached", "--ignore-unmatch", "--", b.path], cwd=p, capture_output=True, timeout=10)
        target.unlink(missing_ok=True)
    return {"ok": True}
