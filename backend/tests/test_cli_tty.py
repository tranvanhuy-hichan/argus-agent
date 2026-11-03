"""Kiem thu menu chon bang phim tren terminal ao (pty): mui ten, Space, Enter, End, Co/Khong."""
import fcntl
import json
import os
import pty
import re
import select
import socket
import struct
import sys
import termios
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "posix", reason="can terminal POSIX")
BACKEND = Path(__file__).resolve().parents[1]
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
UP, DOWN, RIGHT, LEFT, END = b"\x1b[A", b"\x1b[B", b"\x1b[C", b"\x1b[D", b"\x1b[F"


class Pty:
    def __init__(self, argv: list[str], env: dict[str, str]):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.execvpe(argv[0], argv, env)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 110, 0, 0))
        self.text = ""

    def read_until(self, needle: str, timeout: float = 20) -> None:
        end = time.time() + timeout
        while needle not in ANSI.sub("", self.text):
            if time.time() > end:
                raise AssertionError(f"khong thay {needle!r}. Man hinh cuoi:\n{ANSI.sub('', self.text)[-900:]}")
            if select.select([self.fd], [], [], 0.1)[0]:
                try:
                    self.text += os.read(self.fd, 4096).decode("utf-8", "replace")
                except OSError:
                    break

    def send(self, data: bytes) -> None:
        time.sleep(0.15)  # cho menu ve xong, giong toc do go cua nguoi
        os.write(self.fd, data)

    def mark(self) -> None:
        self.text = ""

    def finish(self, timeout: float = 20) -> int:
        end = time.time() + timeout
        while time.time() < end:
            if select.select([self.fd], [], [], 0.1)[0]:
                try:
                    self.text += os.read(self.fd, 4096).decode("utf-8", "replace")
                except OSError:  # pty dong khi tien trinh thoat; van phai lay ma thoat o duoi
                    pass
            done, status = os.waitpid(self.pid, os.WNOHANG)
            if done:
                return os.waitstatus_to_exitcode(status)
        os.kill(self.pid, 9)
        raise AssertionError("tien trinh khong thoat. Man hinh cuoi:\n" + ANSI.sub("", self.text)[-600:])


def env_for(home: Path, lang: str) -> dict[str, str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return {**os.environ, "ARGUS_HOME": str(home), "ARGUS_PORT": str(port), "ARGUS_LANG": lang, "PYTHONPATH": str(BACKEND), "TERM": "xterm-256color", "NO_COLOR": ""}


def test_onboard_with_arrow_keys_space_and_enter(tmp_path):
    p = Pty([sys.executable, "-m", "argus", "onboard"], env_for(tmp_path, "en"))
    p.read_until("Language / Ngôn ngữ")
    p.send(UP)                      # English (mac dinh) -> Tieng Viet
    p.send(b"\r")
    p.read_until("Bạn tên là gì")   # giao dien da doi sang tieng Viet
    p.send(b"Ann\r")
    p.read_until("Chọn nhà cung cấp")
    p.send(END)                     # nhay xuong muc cuoi: 'Bo qua'
    p.send(b"\r")
    p.read_until("Space để chọn")   # danh sach tick tinh nang
    p.mark()
    p.send(b" ")                    # bo tick 'Hoi xac nhan truoc khi chay lenh shell' (dang tick san)
    p.read_until("◻")               # o vuong rong xuat hien
    p.send(b"\r")
    p.read_until("Chạy Argus Agent ngay bây giờ")
    p.send(RIGHT)                   # Co -> Khong bang mui ten phai
    p.send(b"\r")
    assert p.finish() == 0
    cfg = json.loads((tmp_path / "config.json").read_text())
    assert cfg["language"] == "vi" and cfg["agent"]["confirm_exec"] is False and cfg["heartbeat"]["enabled"] is False
    assert "Ann" in (tmp_path / "workspace" / "USER.md").read_text()
    assert not (tmp_path / "data" / "server.pid").exists()  # da chon Khong, khong chay server


def test_multiselect_all_with_a_key_then_confirm_exits_cleanly(tmp_path):
    """'a' chon het; chi kiem tra menu ve dung va phan hoi phim, roi Ctrl+C thoat gon (khong de terminal o che do la)."""
    p = Pty([sys.executable, "-m", "argus", "onboard", "--language", "en"], env_for(tmp_path, "en"))
    p.read_until("What is your name")
    p.send(b"\r")
    p.read_until("Choose a provider")
    p.send(END)
    p.send(b"\r")
    p.read_until("Space to toggle")
    p.send(b"a")
    p.read_until("◼")
    p.send(b"\x03")                 # Ctrl+C
    assert p.finish() != 0          # bi ngat, khong treo
