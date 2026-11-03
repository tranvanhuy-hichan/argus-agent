"""MCP server (stdio) bieu dien agent nay nhu mot tool cho ung dung khac (Claude Code, Cursor, ...).

Chay doc lap, chi goi HTTP toi agent dang chay nen khong phu thuoc code con lai:
  ARGUS_TOKEN=agt_... python mcp_server.py        (ARGUS_URL mac dinh http://127.0.0.1:8787)
"""
import json
import os
import sys

import httpx
from mcp.server.mcpserver import MCPServer

URL = (os.environ.get("ARGUS_URL") or os.environ.get("AGENT_URL") or "http://127.0.0.1:8787").rstrip("/")
TOKEN = os.environ.get("ARGUS_TOKEN") or os.environ.get("AGENT_TOKEN") or ""

mcp = MCPServer("argus", instructions="Giao việc cho trợ lý AI cá nhân chạy trên máy người dùng (có skill, tool và bộ nhớ riêng).")


def _call(method: str, path: str, body: dict | None = None, timeout: float = 330) -> dict:
    if not TOKEN:
        raise RuntimeError("thiếu biến môi trường ARGUS_TOKEN (tạo token ở trang Tích hợp)")
    r = httpx.request(method, URL + path, json=body, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"agent trả về HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


@mcp.tool()
def agent_run(prompt: str, session_id: str = "", exec_policy: str = "deny", exec_allow: list[str] | None = None,
              provider: str = "", timeout_seconds: int = 300) -> str:
    """Giao một việc cho agent và chờ kết quả cuối.

    exec_policy: "deny" (mặc định, không cho chạy lệnh shell), "allowlist" (chỉ lệnh bắt đầu bằng một mục trong exec_allow)
    hoặc "allow" (cho phép mọi lệnh, token phải được cấp quyền). session_id để tiếp tục một hội thoại cũ.
    """
    res = _call("POST", "/v1/run", {"prompt": prompt, "session": session_id or None, "provider": provider or None,
                                    "exec_policy": exec_policy, "exec_allow": exec_allow or [], "timeout": timeout_seconds},
                timeout=timeout_seconds + 30)
    head = f"[session {res['session']}]"
    if res["error"]:
        return f"{head} LỖI: {res['error']}\n{res['output']}".strip()
    used = ", ".join(c["name"] for c in res["tool_calls"])
    return f"{head}{' (tool: ' + used + ')' if used else ''}\n{res['output']}"


@mcp.tool()
def agent_list_skills() -> str:
    """Liệt kê các skill agent đang có."""
    return json.dumps(_call("GET", "/v1/skills", timeout=30), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(f"agent MCP server -> {URL}", file=sys.stderr)
    mcp.run()
