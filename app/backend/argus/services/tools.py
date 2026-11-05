"""Registry tool. Ten tool (read/write/exec/web_fetch) trung voi ten ma skill ClawHub thuong goi, de skill chay duoc."""
import fnmatch
import html
import ipaddress
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from . import checkpoints


@dataclass
class ToolContext:
    workspace: Path
    approver: Callable[[str, str], bool] = lambda kind, detail: False
    confirm_exec: bool = True
    env: dict[str, str] = field(default_factory=dict)
    enabled: dict[str, bool] = field(default_factory=dict)
    skills: dict = field(default_factory=dict)  # name -> skills.Skill
    extra: dict = field(default_factory=dict)  # name -> ToolDef (tool dong, vd. tu MCP)
    project: Path | None = None  # du an nguoi dung da mo (che do Code): doc/ghi ben trong khong can hoi them
    cwd: Path | None = None  # thu muc lam viec cua phien; duong dan tuong doi tinh tu day
    session_id: str | None = None
    depth: int = 0  # do sau cua agent con (0 = agent chinh)
    permission: str = "default"
    provider: str | None = None
    emit: Callable[[dict], None] = lambda ev: None  # gui su kien ra giao dien (plan, anh...)
    cancel: object | None = None  # threading.Event; tool chay lau nen kiem tra de dung som
    confirm_writes: bool = False  # che do 'Hoi truoc': hoi ca khi ghi file/goi HTTP thay doi trong phien
    full_access: bool = False  # che do 'Toan quyen': khong hoi xac nhan nao
    asker: Callable[[str, list[str]], str] | None = None  # hoi nguoi dung mot cau (ask_user); None = khong hoi duoc (API/CLI)
    sandbox: dict = field(default_factory=dict)  # {"mode": "none|docker", "image", "network"}

    @property
    def workdir(self) -> Path:
        return self.cwd or self.workspace

    def approve(self, kind: str, detail: str) -> bool:
        return self.approver(kind, detail)


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict
    fn: Callable
    risk: str  # safe | file | exec | network | mcp
    read_only: bool = False  # tool MCP danh dau chi doc


TOOLS: dict[str, ToolDef] = {}
DENIED = "KHÔNG THỰC HIỆN: yêu cầu bị từ chối nên CHƯA được chạy, không có kết quả nào. Hãy báo cho người dùng biết."


def tool(name: str, description: str, params: dict[str, tuple[str, str]], required: list[str] | None = None, risk: str = "safe"):
    def deco(fn):
        props = {k: ({"type": t, "description": d, "items": {"type": "string"}} if t == "array" else {"type": t, "description": d}) for k, (t, d) in params.items()}
        TOOLS[name] = ToolDef(name, description, {"type": "object", "properties": props, "required": list(params) if required is None else required}, fn, risk)
        return fn
    return deco


def schemas(ctx: ToolContext) -> list[dict]:
    return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in [*TOOLS.values(), *ctx.extra.values()] if ctx.enabled.get(t.name, True)]


def call(ctx: ToolContext, name: str, args: dict) -> tuple[str, bool]:
    t = TOOLS.get(name) or ctx.extra.get(name)
    if not t or not ctx.enabled.get(name, True):
        return f"loi: khong co tool {name}", False
    try:
        return str(t.fn(ctx, **args)), True
    except TypeError as e:
        return f"loi: tham so khong hop le ({e})", False
    except Exception as e:  # tool khong duoc lam sap vong lap agent
        return f"loi: {type(e).__name__}: {e}", False


# ---------- helpers
def _resolve(ctx: ToolContext, path: str, mode: str) -> Path:
    p = Path(path).expanduser()
    p = (p if p.is_absolute() else ctx.workdir / p).resolve()
    ws = ctx.workspace.resolve()
    outside = p != ws and ws not in p.parents
    if outside and ctx.project:
        root = ctx.project.resolve()
        outside = p != root and root not in p.parents
    needs_ok = outside or (mode == "write" and ctx.confirm_writes)
    if needs_ok and not ctx.full_access and not ctx.approve(f"file_{mode}", str(p)):
        raise PermissionError("người dùng từ chối truy cập file này")
    return p


def _check_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("chi ho tro URL http/https")
    for info in socket.getaddrinfo(u.hostname, u.port or 443):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise PermissionError(f"chan truy cap dia chi noi bo ({ip})")


def _fetch(url: str, method: str = "GET", body: str = "", headers: dict | None = None) -> httpx.Response:
    for _ in range(5):
        _check_url(url)
        r = httpx.request(method, url, content=body.encode() if body else None, headers=headers or {}, timeout=30, follow_redirects=False)
        if r.is_redirect and r.headers.get("location"):
            url = str(httpx.URL(url).join(r.headers["location"]))
            method, body = "GET", ""
            continue
        return r
    raise RuntimeError("qua nhieu lan chuyen huong")


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n\n", html.unescape(raw))).strip()


# ---------- tools
@tool("read", "Đọc nội dung một file text. Đường dẫn tương đối tính từ workspace.", {"path": ("string", "đường dẫn file")}, risk="file")
def read_file(ctx, path):
    return _resolve(ctx, path, "read").read_text(errors="replace")[:20000]


@tool("write", "Ghi nội dung vào file (ghi đè), tự tạo thư mục cha.", {"path": ("string", "đường dẫn file"), "content": ("string", "nội dung")}, risk="file")
def write_file(ctx, path, content):
    p = _resolve(ctx, path, "write")
    checkpoints.record(ctx.session_id, p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"da ghi {len(content)} ky tu vao {p}"


@tool("list_dir", "Liệt kê file trong thư mục.", {"path": ("string", "đường dẫn thư mục")}, risk="file")
def list_dir(ctx, path="."):
    d = _resolve(ctx, path, "read")
    return "\n".join(sorted(x.name + ("/" if x.is_dir() else "") for x in d.iterdir()))[:5000] or "(rong)"


def _shell() -> tuple[str | None, str]:
    """(executable, tên hiển thị) của shell dùng để chạy lệnh: bash nếu có, nếu không thì shell mặc định của hệ điều hành (cmd.exe trên Windows)."""
    if sys.platform != "win32" and Path("/bin/bash").exists():
        return "/bin/bash", "bash"
    found = shutil.which("bash")
    if found:
        return found, "bash"
    return None, "cmd.exe" if sys.platform == "win32" else "sh"


def shell_note() -> str:
    """Câu báo cho model biết lệnh shell chạy bằng gì (chỉ khi không phải bash)."""
    name = _shell()[1]
    return "" if name == "bash" else f"Lệnh exec chạy bằng {name} trên {platform.system()}: viết lệnh đúng cú pháp của shell này, không dùng cú pháp bash."


def _docker_cmd(ctx: ToolContext, command: str) -> list[str]:
    sb = ctx.sandbox
    cmd = ["docker", "run", "--rm", "--network", "bridge" if sb.get("network") else "none", "--memory", "1g", "--cpus", "2", "--pids-limit", "256",
           *(["--user", f"{os.getuid()}:{os.getgid()}"] if hasattr(os, "getuid") else []), "-e", "HOME=/tmp", "-v", f"{ctx.workdir.resolve()}:/work", "-w", "/work"]
    for k, v in ctx.env.items():
        cmd += ["-e", f"{k}={v}"]
    return cmd + [sb.get("image") or "python:3.12-slim", "bash", "-c", command]


class _Cancelled(Exception):
    pass


def _run_cancellable(ctx, cmd, timeout, **kw):
    """Nhu subprocess.run nhung dung ngay (kill ca nhom tien trinh) khi nguoi dung bam Dung."""
    import time
    posix = os.name == "posix"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                            start_new_session=posix, **kw)
    end = time.time() + timeout
    chunks: list[str] = []
    import threading
    t = threading.Thread(target=lambda: chunks.append(proc.stdout.read()), daemon=True)
    t.start()

    def kill():
        try:
            if posix:
                import signal
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except OSError:
            pass

    while proc.poll() is None:
        if ctx.cancel is not None and ctx.cancel.is_set():
            kill()
            raise _Cancelled()
        if time.time() > end:
            kill()
            raise subprocess.TimeoutExpired(cmd, timeout)
        time.sleep(0.1)
    t.join(2)
    return subprocess.CompletedProcess(cmd, proc.returncode, "".join(chunks), "")


@tool("exec", "Chạy lệnh shell (bash) trong thư mục làm việc của phiên. Người dùng có thể phải xác nhận.",
      {"command": ("string", "lệnh cần chạy"), "timeout": ("integer", "số giây tối đa (mặc định 60)")}, required=["command"], risk="exec")
def exec_tool(ctx, command, timeout=60):
    if ctx.confirm_exec and not ctx.approve("exec", command):
        return DENIED
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    sandboxed = ctx.sandbox.get("mode") == "docker"
    if sandboxed and not shutil.which("docker"):
        return "loi: da bat sandbox Docker nhung may khong co lenh docker"
    try:
        if sandboxed:
            r = _run_cancellable(ctx, _docker_cmd(ctx, command), min(int(timeout), 300) + 30)
        else:
            r = _run_cancellable(ctx, command, min(int(timeout), 300), shell=True, executable=_shell()[0], cwd=ctx.workdir, env={**os.environ, **ctx.env})
    except subprocess.TimeoutExpired:
        return f"loi: lenh chay qua {timeout}s va bi dung"
    except _Cancelled:
        return "loi: da dung lenh theo yeu cau cua nguoi dung"
    out = (r.stdout + r.stderr)[-6000:] or "(khong co output)"
    out = out if r.returncode == 0 else f"{out}\n[exit code {r.returncode}]"
    return f"[sandbox docker]\n{out}" if sandboxed else out


@tool("web_fetch", "Tải một trang web và trả về nội dung dạng text.", {"url": ("string", "URL http/https")}, risk="network")
def web_fetch(ctx, url):
    r = _fetch(url, headers={"User-Agent": "argus-agent/0.3"})
    text = _html_to_text(r.text) if "html" in r.headers.get("content-type", "") else r.text
    return f"HTTP {r.status_code}\n{text[:8000]}"


@tool("http_request", "Gọi một HTTP API (GET/POST/PUT/DELETE) và trả về phản hồi.",
      {"url": ("string", "URL đầy đủ"), "method": ("string", "GET, POST, PUT hoặc DELETE (mặc định GET)"),
       "body": ("string", "nội dung body (JSON) nếu có"), "headers": ("string", "JSON object các header nếu có")},
      required=["url"], risk="network")
def http_request(ctx, url, method="GET", body="", headers=""):
    if ctx.confirm_writes and not ctx.full_access and method.upper() != "GET" and not ctx.approve("http_request", f"{method.upper()} {url}"):
        return DENIED
    h = {"Content-Type": "application/json", "User-Agent": "argus-agent/0.3", **(json.loads(headers) if headers else {})}
    r = _fetch(url, method.upper(), body, h)
    return f"HTTP {r.status_code}\n{r.text[:8000]}"


SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".mypy_cache", ".pytest_cache", "target"}


def _walk(root: Path):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            yield Path(dp) / fn


@tool("glob", "Tìm file theo mẫu tên (vd. **/*.py, src/**/*.tsx) trong thư mục, bỏ qua .git/node_modules.",
      {"pattern": ("string", "mẫu glob"), "path": ("string", "thư mục gốc (mặc định thư mục làm việc)")}, required=["pattern"], risk="file")
def glob_tool(ctx, pattern, path="."):
    root = _resolve(ctx, path, "read")
    out = []
    for p in _walk(root):
        rel = p.relative_to(root).as_posix()
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(rel, pattern.replace("**/", "")) or fnmatch.fnmatch(p.name, pattern):
            out.append(rel)
            if len(out) >= 300:
                break
    return "\n".join(sorted(out)) or "(không có file nào khớp)"


@tool("grep", "Tìm văn bản/regex trong nội dung các file (như ripgrep). Trả về file:dòng: nội dung.",
      {"pattern": ("string", "regex hoặc chuỗi cần tìm"), "path": ("string", "thư mục hoặc file (mặc định thư mục làm việc)"),
       "include": ("string", "chỉ tìm trong file khớp mẫu này, vd. *.py"), "ignore_case": ("boolean", "không phân biệt hoa thường")},
      required=["pattern"], risk="file")
def grep_tool(ctx, pattern, path=".", include="", ignore_case=False):
    root = _resolve(ctx, path, "read")
    rx = re.compile(pattern, re.I if ignore_case else 0)
    files = [root] if root.is_file() else _walk(root)
    out = []
    for p in files:
        if include and not fnmatch.fnmatch(p.name, include):
            continue
        try:
            if p.stat().st_size > 1_000_000:
                continue
            lines = p.read_text(errors="strict").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for n, ln in enumerate(lines, 1):
            if rx.search(ln):
                out.append(f"{p.relative_to(root) if root.is_dir() else p.name}:{n}: {ln.strip()[:200]}")
                if len(out) >= 200:
                    return "\n".join(out) + "\n[đã cắt ở 200 kết quả, hãy thu hẹp mẫu tìm]"
    return "\n".join(out) or "(không có kết quả)"


@tool("ask_user", "Hỏi người dùng MỘT câu khi thiếu thông tin thật sự không thể tự suy ra. Kèm 2-4 lựa chọn ngắn để họ bấm nhanh (có thể để trống nếu cần câu trả lời tự do). Không dùng cho việc bạn tự quyết được.",
      {"question": ("string", "câu hỏi ngắn gọn"), "options": ("array", "các lựa chọn gợi ý (tùy chọn)")}, required=["question"])
def ask_user(ctx, question, options=None):
    if not ctx.asker:
        return "Không hỏi được người dùng ở chế độ này: hãy tự chọn phương án hợp lý nhất, nêu rõ giả định rồi làm tiếp."
    ans = ctx.asker(question, [str(o) for o in (options or [])][:4]).strip()
    return f"Người dùng trả lời: {ans}" if ans else "Người dùng chưa trả lời: hãy tự chọn phương án hợp lý nhất, nêu rõ giả định rồi làm tiếp."


# ---- lenh chay nen (dev server, test watch...): khong chan luot cua agent
_BG: dict[str, dict] = {}
MAX_BG = 5


def _bg_kill(job: dict) -> None:
    proc = job["proc"]
    if proc.poll() is None:
        try:
            if os.name == "posix":
                import signal
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
        except OSError:
            proc.kill()


def _bg_cleanup() -> None:
    for j in _BG.values():
        _bg_kill(j)


import atexit  # noqa: E402

atexit.register(_bg_cleanup)


@tool("exec_bg", "Chạy một lệnh shell NỀN (dev server, watcher, tiến trình dài) và trả về mã job ngay. Dùng exec_read xem output, exec_stop để dừng. Không dùng cho lệnh ngắn (dùng exec).",
      {"command": ("string", "lệnh cần chạy nền")}, risk="exec")
def exec_bg(ctx, command):
    if ctx.confirm_exec and not ctx.approve("exec", command):
        return DENIED
    if ctx.sandbox.get("mode") == "docker":
        return "loi: lenh nen chua ho tro khi bat sandbox Docker"
    if sum(1 for j in _BG.values() if j["proc"].poll() is None) >= MAX_BG:
        return f"loi: da co {MAX_BG} lenh nen dang chay, hay exec_stop bot"
    from ..core import db as dbmod
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    jid = uuid_hex()
    log = Path(dbmod.DATA) / "bg" / f"{jid}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    f = log.open("wb")
    proc = subprocess.Popen(command, shell=True, executable=_shell()[0], stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=ctx.workdir,
                            env={**os.environ, **ctx.env}, start_new_session=(os.name == "posix"))
    _BG[jid] = {"proc": proc, "log": log, "cmd": command, "file": f}
    return f"đã chạy nền job {jid} (pid {proc.pid}). Dùng exec_read job={jid} để xem output."


def _bg_job(job: str) -> dict:
    j = _BG.get(job)
    if not j:
        raise ValueError(f"không có job '{job}'. Đang có: {', '.join(_BG) or '(không có)'}")
    return j


@tool("exec_read", "Xem output mới nhất của một lệnh nền và trạng thái (đang chạy / đã thoát). Có thể chờ vài giây để output kịp xuất hiện.",
      {"job": ("string", "mã job từ exec_bg"), "wait": ("integer", "chờ tối đa bấy nhiêu giây trước khi đọc (mặc định 0, tối đa 30)")}, required=["job"], risk="exec")
def exec_read(ctx, job, wait=0):
    import time
    j = _bg_job(job)
    time.sleep(max(0, min(int(wait or 0), 30)))
    j["file"].flush()
    out = j["log"].read_bytes()[-6000:].decode("utf-8", "replace") or "(chưa có output)"
    rc = j["proc"].poll()
    return f"[{'đang chạy' if rc is None else f'đã thoát, mã {rc}'}] {j['cmd']}\n{out}"


@tool("exec_stop", "Dừng một lệnh nền.", {"job": ("string", "mã job từ exec_bg")}, risk="exec")
def exec_stop(ctx, job):
    j = _bg_job(job)
    _bg_kill(j)
    return f"đã dừng job {job}"


def uuid_hex() -> str:
    import uuid
    return uuid.uuid4().hex[:6]


def project_notes_path(workspace: Path, project) -> Path:
    import hashlib
    return workspace / "project-notes" / f"{hashlib.sha1(str(project).encode()).hexdigest()[:10]}.md"


@tool("project_note", "Ghi nhớ một điều học được về DỰ ÁN đang mở (cách chạy test, quy ước code, cấu trúc, lỗi hay gặp) để lần sau nhớ lại. Chỉ dùng trong chế độ lập trình.",
      {"note": ("string", "một ý ngắn gọn, hữu ích về dự án")})
def project_note(ctx, note):
    if not ctx.project:
        return "loi: chi dung trong che do lap trinh"
    p = project_notes_path(ctx.workspace, ctx.project)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(f"- {note.strip()}\n")
    return "đã ghi nhớ về dự án"


@tool("remember", "Lưu một điều quan trọng vào bộ nhớ dài hạn (MEMORY.md).", {"note": ("string", "nội dung cần nhớ")})
def remember(ctx, note):
    with (ctx.workspace / "MEMORY.md").open("a") as f:
        f.write(f"- {note}\n")
    return "da nho"


@tool("skills_read", "Nạp hướng dẫn đầy đủ của một skill (theo tên trong danh sách available_skills).", {"name": ("string", "tên skill")})
def skills_read(ctx, name):
    s = ctx.skills.get(name)
    if not s:
        return f"khong co skill '{name}'. Hien co: {', '.join(ctx.skills) or '(trong)'}"
    files = sorted(str(p.relative_to(s.path)) for p in s.path.rglob("*") if p.is_file() and ".clawhub" not in p.parts)[:40]
    return f"{s.instructions()}\n\n[Thu muc skill: {s.path}]\n[File di kem: {', '.join(files)}]"


@tool("edit", "Sửa file bằng cách thay đúng một đoạn văn bản bằng đoạn khác. Báo lỗi nếu đoạn cũ không có hoặc xuất hiện nhiều lần.",
      {"path": ("string", "đường dẫn file"), "old": ("string", "đoạn văn bản cũ, phải khớp chính xác"), "new": ("string", "đoạn văn bản mới")}, risk="file")
def edit_file(ctx, path, old, new):
    p = _resolve(ctx, path, "write")
    checkpoints.record(ctx.session_id, p)
    text = p.read_text()
    n = text.count(old)
    if n != 1:
        raise ValueError(f"đoạn cũ xuất hiện {n} lần (cần đúng 1 lần), hãy cung cấp đoạn dài hơn để duy nhất")
    p.write_text(text.replace(old, new))
    return f"đã sửa {p}"


@tool("web_search", "Tìm kiếm trên web (DuckDuckGo), trả về tiêu đề, link và mô tả ngắn.",
      {"query": ("string", "từ khóa tìm kiếm"), "limit": ("integer", "số kết quả tối đa (mặc định 5)")}, required=["query"], risk="network")
def web_search(ctx, query, limit=5):
    r = _fetch("https://html.duckduckgo.com/html/", "POST", "q=" + quote_plus(query),
               {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) argus-agent/0.3"})
    if r.status_code != 200:
        raise RuntimeError(f"DuckDuckGo trả về HTTP {r.status_code}")
    out = []
    for block in re.split(r'(?=<div class="[^"]*\bresult\b[^"]*")', r.text):
        link = re.search(r'(?s)<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block)
        if not link or "result--ad" in block[:200] or "duckduckgo.com/y.js" in link.group(1):
            continue  # bo quang cao
        snip = re.search(r'(?s)class="result__snippet"[^>]*>(.*?)</a>', block)
        href = html.unescape(link.group(1))
        target = parse_qs(urlparse(href).query).get("uddg")
        out.append(f"{len(out) + 1}. {_html_to_text(link.group(2))}\n   {unquote(target[0]) if target else href}\n   {_html_to_text(snip.group(1)) if snip else ''}")
        if len(out) >= min(int(limit), 10):
            break
    if not out:
        raise RuntimeError("không có kết quả (DuckDuckGo có thể đang chặn truy vấn tự động)")
    return "\n".join(out)


@tool("memory_search", "Tìm lại thông tin trong các cuộc hội thoại cũ và bộ nhớ dài hạn (MEMORY.md).",
      {"query": ("string", "từ khóa cần tìm"), "limit": ("integer", "số kết quả tối đa (mặc định 6)")}, required=["query"])
def memory_search(ctx, query, limit=6):
    from . import sessions  # tranh import vong
    hits = sessions.search(query, min(int(limit), 15))
    mem = ctx.workspace / "MEMORY.md"
    from ..core.text import fold
    terms = fold(query).split()
    notes = [ln for ln in (mem.read_text().splitlines() if mem.exists() else []) if any(t in fold(ln) for t in terms)]
    out = [f"[ghi nhớ] {ln}" for ln in notes[:6]] + [f"[phiên {h['session_id']} · {h['title']}] ({h['role']}) {h['snip']}" for h in hits]
    return "\n".join(out) or "không tìm thấy gì liên quan"


@tool("read_document", "Đọc nội dung file tài liệu: PDF, Excel (xlsx), Word (docx), PowerPoint (pptx), CSV hoặc text. Tài liệu dài được đọc từng phần bằng offset.",
      {"path": ("string", "đường dẫn file"), "offset": ("integer", "vị trí ký tự bắt đầu đọc (mặc định 0); dùng giá trị 'offset=' ở cuối kết quả để đọc tiếp")})
def read_document(ctx, path, offset=0):
    p = _resolve(ctx, path, "read")
    ext = p.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        r = PdfReader(str(p))
        text = "\n\n".join(f"--- trang {i + 1} ---\n{pg.extract_text() or ''}" for i, pg in enumerate(r.pages[:300]))
    elif ext in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(p, read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets[:6]:
            out.append(f"--- sheet {ws.title} ---")
            out += ["\t".join("" if c is None else str(c) for c in row) for row in ws.iter_rows(max_row=500, values_only=True)]
        text = "\n".join(out)
    elif ext == ".docx":
        import zipfile
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml").decode("utf8", "replace")
        text = _html_to_text(re.sub(r"</w:p>", "\n", xml))
    elif ext == ".pptx":
        from .knowledge import _read_pptx
        text = "\n\n".join(f"--- {loc} ---\n{body}" for loc, body in _read_pptx(p)[0])
    else:
        text = p.read_text(errors="replace")
    start, size = max(0, int(offset or 0)), 30000
    chunk = text[start:start + size]
    if start + size < len(text):
        chunk += f"\n\n[da doc ky tu {start}-{start + size} tren tong {len(text)}; goi lai read_document voi offset={start + size} de doc tiep]"
    return chunk or "(khong co noi dung)"


@tool("notify", "Gửi thông báo cho người dùng (hiện trong hộp thư của giao diện và gửi qua Telegram nếu đã kết nối). Dùng khi có điều đáng báo.",
      {"title": ("string", "tiêu đề ngắn"), "message": ("string", "nội dung thông báo")})
def notify(ctx, title, message):
    from . import notifications
    notifications.add(title, message, source="agent")
    return "đã gửi thông báo"


# ---- cac module tool bo sung tu dang ky khi import (ke hoach, agent con, trinh duyet, bo nho, anh, may tinh).
# Module chua ton tai thi bo qua; loi ben trong module (thieu thu vien...) duoc ghi lai de `argus doctor` bao.
import importlib  # noqa: E402

OPTIONAL_MODULES = ("tools_plan", "tools_agents", "tools_browser", "tools_memory", "tools_kb", "tools_media", "tools_computer")
LOAD_ERRORS: dict[str, str] = {}
for _m in OPTIONAL_MODULES:
    try:
        importlib.import_module(f"{__package__}.{_m}")
    except ModuleNotFoundError as _e:
        if _e.name != f"{__package__}.{_m}":
            LOAD_ERRORS[_m] = str(_e)
    except Exception as _e:  # noqa: BLE001 - mot module loi khong duoc lam sap ca he thong tool
        LOAD_ERRORS[_m] = f"{type(_e).__name__}: {_e}"
