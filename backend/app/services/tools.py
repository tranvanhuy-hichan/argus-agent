"""Registry tool. Ten tool theo OpenClaw (read/write/exec/web_fetch) de skill ClawHub chay duoc."""
import html
import ipaddress
import json
import os
import re
import socket
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx


@dataclass
class ToolContext:
    workspace: Path
    approver: Callable[[str, str], bool] = lambda kind, detail: False
    confirm_exec: bool = True
    env: dict[str, str] = field(default_factory=dict)
    enabled: dict[str, bool] = field(default_factory=dict)
    skills: dict = field(default_factory=dict)  # name -> skills.Skill
    extra: dict = field(default_factory=dict)  # name -> ToolDef (tool dong, vd. tu MCP)

    def approve(self, kind: str, detail: str) -> bool:
        return self.approver(kind, detail)


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict
    fn: Callable
    risk: str  # safe | file | exec | network | mcp


TOOLS: dict[str, ToolDef] = {}


def tool(name: str, description: str, params: dict[str, tuple[str, str]], required: list[str] | None = None, risk: str = "safe"):
    def deco(fn):
        props = {k: {"type": t, "description": d} for k, (t, d) in params.items()}
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
    p = (p if p.is_absolute() else ctx.workspace / p).resolve()
    ws = ctx.workspace.resolve()
    if p != ws and ws not in p.parents and not ctx.approve(f"file_{mode}", str(p)):
        raise PermissionError("nguoi dung tu choi truy cap file ngoai workspace")
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
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"da ghi {len(content)} ky tu vao {p}"


@tool("list_dir", "Liệt kê file trong thư mục.", {"path": ("string", "đường dẫn thư mục")}, risk="file")
def list_dir(ctx, path="."):
    d = _resolve(ctx, path, "read")
    return "\n".join(sorted(x.name + ("/" if x.is_dir() else "") for x in d.iterdir()))[:5000] or "(rong)"


@tool("exec", "Chạy lệnh shell (bash) trong workspace. Người dùng có thể phải xác nhận.",
      {"command": ("string", "lệnh cần chạy"), "timeout": ("integer", "số giây tối đa (mặc định 60)")}, required=["command"], risk="exec")
def exec_tool(ctx, command, timeout=60):
    if ctx.confirm_exec and not ctx.approve("exec", command):
        return "KHÔNG THỰC HIỆN: lệnh bị từ chối nên CHƯA được chạy, không có kết quả nào. Hãy báo cho người dùng biết lệnh bị từ chối."
    try:
        r = subprocess.run(command, shell=True, executable="/bin/bash", capture_output=True, text=True, cwd=ctx.workspace,
                           env={**os.environ, **ctx.env}, timeout=min(int(timeout), 300))
    except subprocess.TimeoutExpired:
        return f"loi: lenh chay qua {timeout}s va bi dung"
    out = (r.stdout + r.stderr)[-6000:] or "(khong co output)"
    return out if r.returncode == 0 else f"{out}\n[exit code {r.returncode}]"


@tool("web_fetch", "Tải một trang web và trả về nội dung dạng text.", {"url": ("string", "URL http/https")}, risk="network")
def web_fetch(ctx, url):
    r = _fetch(url, headers={"User-Agent": "personal-agent/0.2"})
    text = _html_to_text(r.text) if "html" in r.headers.get("content-type", "") else r.text
    return f"HTTP {r.status_code}\n{text[:8000]}"


@tool("http_request", "Gọi một HTTP API (GET/POST/PUT/DELETE) và trả về phản hồi.",
      {"url": ("string", "URL đầy đủ"), "method": ("string", "GET, POST, PUT hoặc DELETE (mặc định GET)"),
       "body": ("string", "nội dung body (JSON) nếu có"), "headers": ("string", "JSON object các header nếu có")},
      required=["url"], risk="network")
def http_request(ctx, url, method="GET", body="", headers=""):
    h = {"Content-Type": "application/json", "User-Agent": "personal-agent/0.2", **(json.loads(headers) if headers else {})}
    r = _fetch(url, method.upper(), body, h)
    return f"HTTP {r.status_code}\n{r.text[:8000]}"


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
               {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) personal-agent/0.2"})
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
