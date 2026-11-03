"""Nha cung cap 'CLI': dung mot CLI da dang nhap san (vd. Claude Code) lam bo nao thay cho API key.

CLI chi dong vai mot model sinh van ban (cong cu rieng cua no bi tat). Cong cu cua Argus duoc mo ta trong prompt va model
goi bang khoi <tool_call>{...}</tool_call>; Argus tu chay cong cu (giu nguyen phe duyet, ke hoach, tri nho) roi gui ket qua o luot sau.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path

from ..core import db as dbmod
from ..core.config import ProviderCfg

TIMEOUT = 300
OPEN, CLOSE = "<tool_call>", "</tool_call>"
CLAUDE_MODELS = ["sonnet", "opus", "haiku"]
STRIP_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")  # co thi CLI se dung khoa nay (tinh phi API) thay vi tai khoan dang nhap
CLAUDE_SYSTEM = "You are a plain text completion engine. Follow the instructions in the user message exactly. You have no tools of your own."

PROTOCOL = """You have NO tools of your own, but the host system can run the tools listed below for you.
To use tools, reply with ONLY one or more blocks in exactly this form, then STOP and write nothing else:
<tool_call>{"name": "<tool name>", "arguments": {<json arguments>}}</tool_call>
The host runs them and sends the results in the next turn. When you have enough information, answer the user in plain text instead.
Never describe a tool call in prose; never invent tool results.

Available tools (name: description | JSON schema of arguments):
"""


class CliError(Exception):
    pass


def executable(cfg: ProviderCfg) -> list[str]:
    """Lenh can chay (khong gom tham so cua Argus)."""
    if cfg.cli == "custom":
        parts = shlex.split(cfg.command or "")
        if not parts:
            raise CliError("chưa nhập lệnh cho CLI tùy chỉnh")
        return parts
    return [cfg.command or "claude"]


def find(cfg: ProviderCfg) -> str | None:
    """Duong dan tuyet doi cua CLI neu tim thay (dung cho `argus doctor` va giao dien)."""
    try:
        return shutil.which(executable(cfg)[0])
    except CliError:
        return None


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
    parts.append("Now write the next [Assistant] message: either tool call block(s) or the final plain-text answer. Do not write the '[Assistant]' label.")
    return "\n\n".join(parts)


class CliProvider:
    def __init__(self, cfg: ProviderCfg):
        self.cfg = cfg

    def _cmd(self) -> list[str]:
        exe = executable(self.cfg)
        if self.cfg.cli == "custom":
            return exe
        cmd = exe + ["-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages", "--tools", "",
                     "--no-session-persistence", "--disable-slash-commands", "--strict-mcp-config", "--system-prompt", CLAUDE_SYSTEM]
        if self.cfg.model:
            cmd += ["--model", self.cfg.model]
        return cmd

    def stream(self, messages: list[dict], tools: list[dict], effort: str | None = None) -> Iterator[dict]:
        from .providers import ProviderError

        try:
            cmd = self._cmd()
        except CliError as e:
            raise ProviderError(str(e)) from e
        if not shutil.which(cmd[0]):
            raise ProviderError(f"không tìm thấy lệnh '{cmd[0]}'. Hãy cài CLI và đăng nhập (ví dụ chạy `{cmd[0]}` một lần trong terminal).")
        env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
        workdir = Path(dbmod.DATA) / "cli-run"  # thu muc trong, de CLI khong doc CLAUDE.md/du an nao
        workdir.mkdir(parents=True, exist_ok=True)
        prompt = build_prompt(messages, tools)
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=workdir, env=env, text=True, encoding="utf-8")
        except OSError as e:
            raise ProviderError(f"không chạy được CLI: {e}") from e
        timer = threading.Timer(TIMEOUT, proc.kill)
        timer.start()
        err_lines: list[str] = []
        threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True).start()
        threading.Thread(target=lambda: (proc.stdin.write(prompt), proc.stdin.close()), daemon=True).start()
        flt, full, usage, result_err = _Filter(), "", {"prompt": 0, "completion": 0}, ""
        streamed = False
        try:
            for line in proc.stdout:
                text = ""
                if self.cfg.cli == "custom":
                    text = line
                else:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    t = d.get("type")
                    if t == "stream_event" and d["event"].get("type") == "content_block_delta" and d["event"]["delta"].get("type") == "text_delta":
                        text, streamed = d["event"]["delta"]["text"], True
                    elif t == "assistant" and not streamed:  # CLI khong tra tung manh: lay ca khoi
                        text = "".join(b.get("text", "") for b in d["message"].get("content", []) if b.get("type") == "text")
                    elif t == "result":
                        u = d.get("usage") or {}
                        usage = {"prompt": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0), "completion": u.get("output_tokens", 0)}
                        if d.get("is_error"):
                            result_err = str(d.get("result") or "lỗi không rõ")
                if text:
                    full += text
                    if (out := flt.feed(text)):
                        yield {"type": "delta", "text": out}
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        if result_err:
            raise ProviderError(f"CLI: {result_err[:300]}")
        if proc.returncode not in (0, None) and not full.strip():
            raise ProviderError(f"CLI thoát với mã {proc.returncode}: {''.join(err_lines)[:300].strip() or 'không có thông báo'}")
        if (tail := flt.flush()):
            yield {"type": "delta", "text": tail}
        plain, calls = parse_calls(full)
        yield {"type": "final", "content": plain, "tool_calls": calls, "usage": usage}
