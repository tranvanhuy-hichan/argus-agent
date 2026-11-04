"""Chay agent cho ung dung ben ngoai: khong co nguoi duyet nen quyen chay lenh do chinh sach (policy) quyet dinh."""
import fnmatch
import re
import time
from collections.abc import Callable, Iterator

from . import chat_runner

SHELL_META = re.compile(r"[;&|<>$`\n]")


class PolicyError(ValueError):
    pass


def make_approver(policy: str, allow: list[str], token_allow_exec: bool) -> Callable[[str, str], bool]:
    """deny: tu choi moi thu can xin phep. allow: cho phep exec va tool MCP (token phai co allow_exec).
    allowlist: exec chi khi lenh bat dau bang mot muc trong allow (va khong chua ky tu noi lenh);
    tool MCP khi ten khop mau 'mcp:<glob>'. File ngoai workspace luon bi tu choi."""
    if policy not in ("deny", "allow", "allowlist"):
        raise PolicyError("exec_policy phải là deny, allow hoặc allowlist")
    if policy != "deny" and not token_allow_exec:
        raise PolicyError("token này không được cấp quyền chạy lệnh (allow_exec)")

    def approver(kind: str, detail: str) -> bool:
        if kind not in ("exec", "mcp") or policy == "deny":
            return False
        if policy == "allow":
            return True
        if kind == "exec":
            if SHELL_META.search(detail):
                return False
            return any(detail == a or detail.startswith(a + " ") for a in allow if not a.startswith("mcp:"))
        name = detail.split(" ", 1)[0]
        return any(fnmatch.fnmatch(name, a[4:]) for a in allow if a.startswith("mcp:"))

    return approver


def run_once(prompt: str, *, session: str | None, provider: str | None, approver, only_tools: list[str] | None, timeout: float,
             permission: str = "default", effort: str | None = None, source: str = "api", docs: bool = False) -> dict:
    out = {"session": session, "output": "", "provider": None, "usage": {"prompt": 0, "completion": 0},
           "tool_calls": [], "error": None, "timed_out": False}
    calls: dict[str, dict] = {}
    deadline = time.time() + timeout
    events: Iterator[dict] = chat_runner.stream_chat(session, prompt, provider, approver_override=approver, source=source, only_tools=only_tools,
                                                      permission=permission, effort=effort, docs=docs)
    try:
        for ev in events:
            t = ev["type"]
            if t == "session":
                out["session"] = ev["id"]
            elif t == "assistant":
                out["output"], out["provider"] = ev["content"], ev["provider"]
                out["usage"] = {k: out["usage"][k] + ev["usage"][k] for k in out["usage"]}
            elif t == "tool":
                calls[ev["id"]] = {"name": ev["name"], "args": ev["args"], "ok": None, "result": None}
                out["tool_calls"].append(calls[ev["id"]])
            elif t == "tool_result" and ev["id"] in calls:
                calls[ev["id"]].update(ok=ev["ok"], result=ev["result"])
            elif t == "error":
                out["error"] = ev["message"]
            if time.time() > deadline:
                out["timed_out"], out["error"] = True, out["error"] or f"het thoi gian cho ({int(timeout)}s)"
                break
    finally:
        events.close()  # kich hoat cancel o chat_runner
    return out
