"""Chế độ Code: mở một dự án trên máy làm thư mục làm việc của phiên, xem thay đổi (git) và hoàn tác từng file."""
import json
import os
import re
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.db import db
from ..services import sessions, workfiles

AUTO = True
PROTECTED = ("main", "master")
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


class ProjectBody(BaseModel):
    path: str | None = None  # None/rong = tat che do lap trinh cho phien nay


@router.post("/sessions/{sid}/project")
def set_session_project(sid: str, b: ProjectBody):
    """Bật/tắt chế độ lập trình ngay trong một hội thoại: gắn thư mục dự án làm thư mục làm việc (hoặc bỏ đi)."""
    if not sessions.get(sid):
        raise HTTPException(404, "không có phiên này")
    if not b.path:
        sessions.set_project(sid, "")
        return {"project": ""}
    p = _dir(b.path)
    _remember(str(p))
    sessions.set_project(sid, str(p))
    return {"project": str(p)}


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


def _git(p: Path, *args: str, ok: tuple[int, ...] = (0,), timeout: int = 20) -> str:
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=p, capture_output=True, text=True, timeout=timeout, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"})
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
    branch, files, upstream, ahead = "", [], "", 0
    for line in out.splitlines():
        if line.startswith("## "):
            head = line[3:]
            branch = head.split("...")[0].removeprefix("No commits yet on ")
            if "..." in head:
                upstream = head.split("...")[1].split(" ")[0]
            if "[ahead " in head:
                ahead = int(head.split("[ahead ")[1].split("]")[0].split(",")[0])
            continue
        code, path = line[:2], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append({"path": path.strip('"'), "status": "new" if code == "??" or "A" in code else "deleted" if "D" in code else "modified"})
    return {"repo": True, "branch": branch, "files": files[:500], "upstream": upstream, "ahead": ahead, "protected": branch in PROTECTED}


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


# ---------- thao tac git co rao chan (giao dien nut Git trong chat)
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,80}$")


def _need_repo(sid: str) -> Path:
    p = _project(sid)
    if not _is_repo(p):
        raise HTTPException(400, "dự án này chưa phải kho git")
    return p


def _current(p: Path) -> str:
    return _git(p, "rev-parse", "--abbrev-ref", "HEAD").strip()


class BranchBody(BaseModel):
    name: str


@router.post("/sessions/{sid}/git/branch")
def git_branch(sid: str, b: BranchBody):
    """Tạo và chuyển sang nhánh mới (thay đổi chưa commit được giữ nguyên)."""
    p = _need_repo(sid)
    if not BRANCH_RE.match(b.name) or ".." in b.name or b.name.endswith((".lock", "/", ".")):
        raise HTTPException(400, "tên nhánh không hợp lệ (chỉ chữ, số, . _ - /)")
    _git(p, "switch", "-c", b.name)
    return {"branch": b.name}


class CommitBody(BaseModel):
    message: str
    files: list[str]
    allow_protected: bool = False
    new_branch: str = ""  # co ten: tao va chuyen sang nhanh nay roi moi commit (mot buoc, dung khi dang o main)


@router.post("/sessions/{sid}/git/commit")
def git_commit(sid: str, b: CommitBody):
    """Commit đúng các file được chọn (không bao giờ `git add -A`). Từ chối trên main/master trừ khi người dùng xác nhận."""
    p = _need_repo(sid)
    msg = b.message.strip()
    if not msg:
        raise HTTPException(400, "chưa nhập nội dung commit")
    if not b.files:
        raise HTTPException(400, "chưa chọn file nào")
    nb = b.new_branch.strip()
    if nb and (not BRANCH_RE.match(nb) or ".." in nb or nb.endswith((".lock", "/", "."))):
        raise HTTPException(400, "tên nhánh không hợp lệ (chỉ chữ, số, . _ - /)")
    if not nb and _current(p) in PROTECTED and not b.allow_protected:
        raise HTTPException(409, f"đang ở nhánh {_current(p)}: hãy tạo nhánh mới hoặc xác nhận commit thẳng")
    for f in b.files:
        try:
            workfiles.safe_path(p, f)
        except workfiles.PathError as e:
            raise HTTPException(400, str(e)) from e
    if nb:
        _git(p, "switch", "-c", nb)
    _git(p, "add", "-A", "--", *b.files)  # -A chi trong pham vi cac file da chon (de ghi nhan ca file bi xoa)
    _git(p, "commit", "-m", msg, "--", *b.files)
    return {"commit": _git(p, "rev-parse", "--short", "HEAD").strip(), "branch": _current(p)}


class PushBody(BaseModel):
    confirm: bool = False
    allow_protected: bool = False


@router.post("/sessions/{sid}/git/push")
def git_push(sid: str, b: PushBody):
    """Đẩy nhánh hiện tại lên origin. Luôn cần confirm=true; không bao giờ force; main/master cần xác nhận riêng."""
    p = _need_repo(sid)
    if not b.confirm:
        raise HTTPException(400, "cần xác nhận trước khi push")
    branch = _current(p)
    if branch in PROTECTED and not b.allow_protected:
        raise HTTPException(409, f"đang ở nhánh {branch}: hãy xác nhận riêng để push thẳng")
    if branch == "HEAD":
        raise HTTPException(400, "đang ở trạng thái detached HEAD")
    out = _git(p, "push", "-u", "origin", branch, timeout=90)
    return {"branch": branch, "output": out.strip()[-500:]}


def _branches(p: Path) -> list[str]:
    return [x for x in _git(p, "for-each-ref", "--format=%(refname:short)", "--sort=-committerdate", "refs/heads").splitlines() if x]


@router.get("/sessions/{sid}/git/branches")
def git_branches(sid: str):
    p = _need_repo(sid)
    return {"current": _current(p), "branches": _branches(p)}


@router.post("/sessions/{sid}/git/switch")
def git_switch(sid: str, b: BranchBody):
    """Chuyển sang một nhánh có sẵn. Git từ chối nếu thay đổi chưa commit bị xung đột (thông báo lỗi được trả về nguyên văn)."""
    p = _need_repo(sid)
    if b.name not in _branches(p):
        raise HTTPException(400, "không có nhánh này")
    _git(p, "switch", b.name)
    return {"branch": b.name}


class SuggestBody(BaseModel):
    files: list[str]


def _fallback_message(files: list[str]) -> str:
    names = [Path(f).name for f in files[:3]]
    return "update " + ", ".join(names) + (f" and {len(files) - 3} more" if len(files) > 3 else "")


@router.post("/sessions/{sid}/git/suggest")
def git_suggest(sid: str, b: SuggestBody):
    """Gợi ý nội dung commit (Conventional Commits, tiếng Anh) từ diff của các file chọn; lỗi model thì dùng tên file."""
    p = _need_repo(sid)
    files = [f for f in b.files if f][:50]
    if not files:
        raise HTTPException(400, "chưa chọn file nào")
    for f in files:
        try:
            workfiles.safe_path(p, f)
        except workfiles.PathError as e:
            raise HTTPException(400, str(e)) from e
    diff = _git(p, "diff", "HEAD", "--no-color", "--stat", "-p", "--", *files)[:6000]
    new = [f for f in files if f not in diff]
    try:
        from ..core import config as cfgmod
        from ..services.providers import make_provider
        cfg = cfgmod.load()
        name = cfg.agent.fast_provider if cfg.agent.fast_provider in cfg.providers else cfg.default_provider
        prompt = ("Write ONE git commit message in Conventional Commits style (type: short summary, max 72 chars, English, no quotes, no explanation) "
                  f"for this change.\nNew files: {', '.join(new) or '(none)'}\n\n{diff}")
        text = ""
        for ev in make_provider(cfg.providers[name]).stream([{"role": "user", "content": prompt}], tools=[]):
            if ev.get("type") == "delta":
                text += ev.get("text", "")
        msg = text.strip().splitlines()[0].strip("`\"' ") if text.strip() else ""
        return {"message": msg[:100] or _fallback_message(files)}
    except Exception:  # noqa: BLE001 - goi y khong duoc lam hong viec commit
        return {"message": _fallback_message(files)}
