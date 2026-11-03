"""MCP server mau (stdio) de thu tich hop: python examples/demo_mcp_server.py
Them vao trang Tich hop > MCP Servers voi lenh: <duong dan .venv>/bin/python, tham so: <duong dan file nay>."""
import datetime
import random

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

mcp = MCPServer("demo")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def current_time() -> str:
    """Trả về ngày giờ hiện tại của máy."""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def add(a: float, b: float) -> float:
    """Cộng hai số."""
    return a + b


@mcp.tool()
def roll_dice(sides: int = 6) -> int:
    """Tung một viên xúc xắc có số mặt cho trước (tool này không đánh dấu read-only nên sẽ hỏi xác nhận)."""
    return random.randint(1, sides)


if __name__ == "__main__":
    mcp.run()
