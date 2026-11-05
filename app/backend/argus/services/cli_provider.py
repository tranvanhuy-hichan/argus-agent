"""Nha cung cap 'CLI': dung mot CLI da dang nhap san (Claude Code, Antigravity `agy`, Codex...) lam bo nao thay cho API key.

CLI chi dong vai mot model sinh van ban (cong cu rieng cua no bi tat). Cong cu cua Argus duoc mo ta trong prompt va model
goi bang khoi <tool_call>{...}</tool_call>; Argus tu chay cong cu (giu nguyen phe duyet, ke hoach, tri nho) roi gui ket qua o luot sau.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path

from ..core import db as dbmod
from ..core.config import ProviderCfg

TIMEOUT = 300
OPEN, CLOSE = "<tool_call>", "</tool_call>"
CLAUDE_MODELS = ["sonnet", "opus", "haiku"]
MAX_ARG = 120_000  # CLI nhan loi nhac qua tham so dong lenh; Linux gioi han ~128 KB moi tham so
CLAUDE_SYSTEM = "You are a plain text completion engine. Follow the instructions in the user message exactly. You have no tools of your own."

PROTOCOL = """You have NO tools of your own, but the host system can run the tools listed below for you.
To use tools, reply with ONLY one or more blocks in exactly this form, then STOP and write nothing else:
<tool_call>{"name": "<tool name>", "arguments": {<json arguments>}}</tool_call>
The host runs them and sends the results in the next turn. When you have enough information, answer the user in plain text instead.
Never describe a tool call in prose; never invent tool results.
IMPORTANT: your own built-in tools (RunCommand, file edit, browser, etc.) are DISABLED and will be denied, which makes your reply empty. To run a command, read or write a file, or search, you MUST emit a <tool_call> block for the host tool of that name below.

Available tools (name: description | JSON schema of arguments):
"""


class CliError(Exception):
    pass


DEFAULT_EXE = {"claude": "claude", "agy": "agy", "codex": "codex"}


def executable(cfg: ProviderCfg) -> list[str]:
    """Lenh can chay (khong gom tham so cua Argus)."""
    if cfg.cli == "custom":
        parts = shlex.split(cfg.command or "")
        if not parts:
            raise CliError("chưa nhập lệnh cho CLI tùy chỉnh")
        return parts
    return [cfg.command or DEFAULT_EXE[cfg.cli]]


def find(cfg: ProviderCfg) -> str | None:
    """Duong dan tuyet doi cua CLI neu tim thay (dung cho `argus doctor` va giao dien)."""
    try:
        return shutil.which(executable(cfg)[0])
    except CliError:
        return None


class _Run:
    """Trang thai mot lan chay CLI: van ban sinh ra, token, loi, file ket qua (neu CLI ghi ra file)."""

    def __init__(self) -> None:
        self.usage = {"prompt": 0, "completion": 0}
        self.error = ""
        self.streamed = False
        self.out_file = ""


def _claude_cmd(cfg, exe, prompt, run):
    cmd = exe + ["-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages", "--tools", "",
                 "--no-session-persistence", "--disable-slash-commands", "--strict-mcp-config", "--system-prompt", CLAUDE_SYSTEM,
                 "--setting-sources", "user"]
    return cmd + (["--model", cfg.model] if cfg.model else []), prompt


def _claude_feed(d, run):
    t = d.get("type")
    if t == "stream_event" and d["event"].get("type") == "content_block_delta" and d["event"]["delta"].get("type") == "text_delta":
        run.streamed = True
        return d["event"]["delta"]["text"]
    if t == "assistant" and not run.streamed:  # CLI khong tra tung manh: lay ca khoi
        return "".join(b.get("text", "") for b in d["message"].get("content", []) if b.get("type") == "text")
    if t == "result":
        u = d.get("usage") or {}
        run.usage = {"prompt": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0), "completion": u.get("output_tokens", 0)}
        if d.get("is_error"):
            run.error = str(d.get("result") or "lỗi không rõ")
    return ""


def _agy_cmd(cfg, exe, prompt, run):
    # agy coi tham so ngay sau -p la loi nhac: moi co khac phai dung TRUOC -p, -p dung cuoi cung. Loi nhac chi di qua tham so (khong doc stdin)
    cmd = exe + ["--output-format", "stream-json", "--disable-slash-commands"] + (["--model", cfg.model] if cfg.model else []) + ["-p", prompt]
    return cmd, None


def _agy_feed(d, run):
    ev = d.get("event")
    if ev == "step_update":
        su = d["step_update"]
        if su.get("step_type") == "agent_response" and su.get("text_delta"):
            run.streamed = True
            return su["text_delta"]
    elif ev == "result":
        r = d.get("result") or {}
        u = r.get("usage") or {}
        run.usage = {"prompt": u.get("input_tokens", 0) + u.get("cache_read_tokens", 0), "completion": u.get("output_tokens", 0)}
        if r.get("status") not in (None, "SUCCESS"):
            run.error = f"{r.get('status')}: {r.get('error') or r.get('response') or 'lỗi không rõ'}"
        elif not run.streamed:
            return r.get("response", "")
    return ""


def _codex_cmd(cfg, exe, prompt, run):
    # Chua kiem chung voi ban Codex that (may chua cai): flag theo tai lieu `codex exec`; ket qua cuoi con duoc doc tu file -o
    run.out_file = str(Path(dbmod.DATA) / "cli-run" / f"codex-{uuid.uuid4().hex[:8]}.txt")
    cmd = exe + ["exec", "--json", "--skip-git-repo-check", "--sandbox", "read-only", "-o", run.out_file] + (["--model", cfg.model] if cfg.model else []) + [prompt]
    return cmd, None


def _codex_feed(d, run):
    t = d.get("type")
    if t == "item.completed" and (d.get("item") or {}).get("type") == "agent_message":
        run.streamed = True
        return d["item"].get("text", "")
    if t == "turn.completed":
        u = d.get("usage") or {}
        run.usage = {"prompt": u.get("input_tokens", 0), "completion": u.get("output_tokens", 0)}
    elif t in ("turn.failed", "error"):
        run.error = str((d.get("error") or {}).get("message") or d.get("message") or "lỗi không rõ")
    return ""


def _custom_cmd(cfg, exe, prompt, run):
    return exe, prompt


# cli -> (xay lenh, doc mot dong JSON, bien moi truong can go de CLI dung tai khoan dang nhap thay vi khoa API)
ADAPTERS = {
    "claude": (_claude_cmd, _claude_feed, ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")),
    "agy": (_agy_cmd, _agy_feed, ()),
    "codex": (_codex_cmd, _codex_feed, ("CODEX_API_KEY", "OPENAI_API_KEY")),
    "custom": (_custom_cmd, None, ()),
}


def list_cli_models(cfg: ProviderCfg) -> list[str]:
    """Model co the chon: Claude co 3 ten viet tat; `agy models` liet ke that; cac CLI khac de trong."""
    if cfg.cli == "claude":
        return CLAUDE_MODELS
    if cfg.cli != "agy" or not find(cfg):
        return []
    workdir = Path(dbmod.DATA) / "cli-run"
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(executable(cfg) + ["models"], capture_output=True, text=True, timeout=30, cwd=workdir)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [ln.split("\t")[0].strip() for ln in r.stdout.splitlines() if "\t" in ln and ln.split("\t")[0].strip()]


class _Filter:
    """Chi cho van ban nam TRUOC khoi <tool_call> hien ra cho nguoi dung."""

    def __init__(self) -> None:
        self.pending, self.hidden = "", False

    def feed(self, s: str) -> str:
        if self.hidden:
            return ""
        self.pending += s
        i = self.pending.find(OPEN)
        if i >= 0:
            out, self.pending, self.hidden = self.pending[:i], "", True
            return out
        keep = next((k for k in range(min(len(OPEN) - 1, len(self.pending)), 0, -1) if OPEN.startswith(self.pending[-k:])), 0)
        out, self.pending = self.pending[:len(self.pending) - keep], self.pending[len(self.pending) - keep:]
        return out

    def flush(self) -> str:
        out = "" if self.hidden else self.pending
        self.pending = ""
        return out


def parse_calls(text: str) -> tuple[str, list[dict]]:
    """Tach van ban thuong va cac loi goi cong cu khoi <tool_call>."""
    calls = []
    for raw in re.findall(re.escape(OPEN) + r"\s*(\{.*?\})\s*" + re.escape(CLOSE), text, re.S):
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue
        args = d.get("arguments", d.get("args", {}))
        if isinstance(d.get("name"), str) and isinstance(args, dict):
            calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": d["name"], "args": args})
    plain = re.sub(re.escape(OPEN) + r".*?" + re.escape(CLOSE), "", text, flags=re.S).strip()
    return (plain if calls else text.strip()), calls


def build_prompt(messages: list[dict], tools: list[dict]) -> str:
    parts = []
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    if system:
        parts.append(f"# Instructions\n{system}")
    if tools:
        parts.append(PROTOCOL + "\n".join(f"- {t['name']}: {t.get('description', '')} | {json.dumps(t.get('parameters', {}), ensure_ascii=False)}" for t in tools))
    parts.append("# Conversation so far")
    for m in messages:
        role = m["role"]
        if role == "system":
            continue
        if role == "user":
            parts.append(f"[User]\n{m.get('content', '')}")
        elif role == "assistant":
            body = m.get("content", "")
            for c in m.get("tool_calls") or []:
                body += f"\n{OPEN}{json.dumps({'name': c['name'], 'arguments': c['args']}, ensure_ascii=False)}{CLOSE}"
            parts.append(f"[Assistant]\n{body.strip()}")
        elif role == "tool":
            parts.append(f"[Tool result for {m.get('tool_call_id', '')}]\n{m.get('content', '')}")
    parts.append("Now write the next [Assistant] message: either tool call block(s) or the final plain-text answer. Do not write the '[Assistant]' label. Never use your own built-in tools; use <tool_call> blocks only.")
    return "\n\n".join(parts)


class CliProvider:
    def __init__(self, cfg: ProviderCfg):
        self.cfg = cfg

    def stream(self, messages: list[dict], tools: list[dict], effort: str | None = None,
               temperature: float | None = None, max_tokens: int | None = None, **kwargs) -> Iterator[dict]:
        from .providers import ProviderError

        try:
            exe = executable(self.cfg)
        except CliError as e:
            raise ProviderError(str(e)) from e
        if not shutil.which(exe[0]):
            raise ProviderError(f"không tìm thấy lệnh '{exe[0]}'. Hãy cài CLI và đăng nhập (ví dụ chạy `{exe[0]}` một lần trong terminal).")
        make_cmd, feed, strip = ADAPTERS[self.cfg.cli]
        env = {k: v for k, v in os.environ.items() if k not in strip}
        workdir = Path(tempfile.gettempdir()) / "argus-cli-run"  # thu muc trong tach biet khoi moi git repo, de CLI khong doc CLAUDE.md/du an nao
        workdir.mkdir(parents=True, exist_ok=True)
        prompt = build_prompt(messages, tools)
        run = _Run()
        cmd, stdin_text = make_cmd(self.cfg, exe, prompt, run)
        if stdin_text is None and len(prompt) > MAX_ARG:
            raise ProviderError(f"lời nhắc dài {len(prompt):,} ký tự, vượt giới hạn tham số dòng lệnh của CLI ({MAX_ARG:,}). Hãy mở hội thoại mới hoặc giảm \"Số tin nhắn gửi kèm\" trong Cài đặt.")
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=workdir, env=env, text=True, encoding="utf-8")
        except OSError as e:
            raise ProviderError(f"không chạy được CLI: {e}") from e
        timer = threading.Timer(TIMEOUT, proc.kill)
        timer.start()
        cancel = getattr(self, "cancel", None)
        if cancel is not None:  # bam Dung: kill CLI ngay, khong doi no tra loi xong
            def _watch():
                while proc.poll() is None:
                    if cancel.wait(0.3):
                        proc.kill()
                        return
            threading.Thread(target=_watch, daemon=True).start()
        err_lines: list[str] = []
        threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True).start()
        threading.Thread(target=lambda: (proc.stdin.write(stdin_text or ""), proc.stdin.close()), daemon=True).start()
        flt, full = _Filter(), ""
        raw_log = workdir / "last-run.jsonl"  # lan chay gan nhat cua CLI, de chan doan khi CLI tra ve rong
        raw_f = raw_log.open("w", encoding="utf-8")
        try:
            for line in proc.stdout:
                raw_f.write(line)
                if feed is None:
                    text = line
                else:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = feed(d, run)
                if text:
                    full += text
                    if (out := flt.feed(text)):
                        yield {"type": "delta", "text": out}
        finally:
            raw_f.close()
            timer.cancel()
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            if not full.strip() and run.out_file and Path(run.out_file).exists():  # CLI chi ghi cau tra loi cuoi ra file
                full = Path(run.out_file).read_text(errors="replace")
                if full.strip():
                    yield {"type": "delta", "text": flt.feed(full)}
            if run.out_file:
                Path(run.out_file).unlink(missing_ok=True)
        if run.error:
            raise ProviderError(f"CLI: {run.error[:300]}")
        if proc.returncode not in (0, None) and not full.strip():
            raise ProviderError(f"CLI thoát với mã {proc.returncode}: {''.join(err_lines)[:300].strip() or 'không có thông báo'}")
        if (tail := flt.flush()):
            yield {"type": "delta", "text": tail}
        plain, calls = parse_calls(full)
        yield {"type": "final", "content": plain, "tool_calls": calls, "usage": run.usage}
