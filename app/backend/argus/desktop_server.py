"""Điểm vào của bản đóng gói (ứng dụng desktop): chạy server Argus cho cửa sổ Electron.

  argus-server --port 8787 [--host 127.0.0.1]     chạy server (dữ liệu ở ARGUS_HOME, Electron đặt vào thư mục dữ liệu người dùng)
  argus-server --mcp                              chế độ MCP stdio cho ứng dụng khác (xem mcp_server.py)
Ghi một dòng `ARGUS_READY <port>` ra stdout khi server đã nhận kết nối để Electron biết lúc nào mở cửa sổ.
"""
import argparse
import os
import runpy
import sys


def bind(host: str, port: int):
    """Mở socket ở cổng ưa thích; bận (hoặc port=0) thì lấy cổng trống bất kỳ để app vẫn mở được."""
    import socket

    sock = socket.socket()
    if os.name != "nt":  # trên Windows SO_REUSEADDR cho phép chiếm cổng đang dùng nên không đặt
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError:
        sock.bind((host, 0))
    return sock


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="argus-server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0, help="cổng ưa thích (cố định để đăng nhập OAuth của MCP còn hiệu lực lần sau); bận hoặc 0 thì tự chọn")
    ap.add_argument("--mcp", action="store_true")
    a = ap.parse_args(argv)
    if a.mcp:
        runpy.run_module("argus.mcp_server", run_name="__main__")
        return 0

    import uvicorn

    from .main import app

    sock = bind(a.host, a.port)
    port = sock.getsockname()[1]
    os.environ["ARGUS_PORT"] = str(port)

    class Server(uvicorn.Server):
        async def startup(self, sockets=None):  # noqa: ANN001
            await super().startup(sockets)
            if self.started:
                print(f"ARGUS_READY {port}", flush=True)

    server = Server(uvicorn.Config(app, log_level="warning", access_log=False))
    server.run(sockets=[sock])
    return 0


if __name__ == "__main__":
    sys.exit(main())
