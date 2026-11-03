"""Computer use (THU NGHIEM, rui ro cao): chup man hinh, di chuot, click, go phim.

Linux Wayland can ydotool (can ydotoold chay + quyen /dev/uinput) hoac wtype de go chu; X11 dung xdotool.
Moi hanh dong deu hoi phe duyet tru khi o che do Toan quyen.
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

from ..core import config as cfgmod
from .tools import DENIED, tool

def _which(name: str):
    """Boc shutil.which de tra cuu luc goi (khong co dinh luc import)."""
    return shutil.which(name)


MAX_TEXT = 2000
_SCREEN: dict = {"size": None}  # kich thuoc man hinh lan chup gan nhat (w, h)

KEYS = {"ctrl", "control", "alt", "shift", "super", "meta", "cmd", "return", "enter", "tab", "escape", "esc", "space", "backspace", "delete",
        "up", "down", "left", "right", "home", "end", "pageup", "pagedown", *[f"f{i}" for i in range(1, 13)], *"abcdefghijklmnopqrstuvwxyz0123456789"}
MODS = {"ctrl", "control", "alt", "shift", "super", "meta", "cmd"}
# ten xdotool
_XKEY = {"control": "ctrl", "ctrl": "ctrl", "enter": "Return", "return": "Return", "esc": "Escape", "escape": "Escape", "tab": "Tab", "space": "space",
         "backspace": "BackSpace", "delete": "Delete", "up": "Up", "down": "Down", "left": "Left", "right": "Right", "home": "Home", "end": "End",
         "pageup": "Prior", "pagedown": "Next", "super": "super", "meta": "super", "cmd": "super", "alt": "alt", "shift": "shift"}
# linux input event codes cho ydotool
_YCODE = {"ctrl": 29, "control": 29, "shift": 42, "alt": 56, "super": 125, "meta": 125, "cmd": 125, "return": 28, "enter": 28, "tab": 15, "escape": 1, "esc": 1,
          "space": 57, "backspace": 14, "delete": 111, "up": 103, "down": 108, "left": 105, "right": 106, "home": 102, "end": 107, "pageup": 104, "pagedown": 109,
          **{f"f{i}": 58 + i for i in range(1, 11)}, "f11": 87, "f12": 88}
for _i, _c in enumerate("qwertyuiop"):
    _YCODE[_c] = 16 + _i
for _i, _c in enumerate("asdfghjkl"):
    _YCODE[_c] = 30 + _i
for _i, _c in enumerate("zxcvbnm"):
    _YCODE[_c] = 44 + _i
for _i, _c in enumerate("1234567890"):
    _YCODE[_c] = 2 + _i
_MAC = {"return": 36, "enter": 36, "tab": 48, "space": 49, "backspace": 51, "delete": 117, "escape": 53, "esc": 53, "left": 123, "right": 124, "down": 125, "up": 126}
_CLIKEY = {"return": "return", "enter": "return", "tab": "tab", "space": "space", "backspace": "delete", "delete": "fwd-delete", "escape": "esc", "esc": "esc",
           "left": "arrow-left", "right": "arrow-right", "up": "arrow-up", "down": "arrow-down", "home": "home", "end": "end", "pageup": "page-up", "pagedown": "page-down"}


# ---------- thuan tuy: kiem tra / phan tich
def png_size(data: bytes) -> tuple[int, int]:
    """Doc rong/cao tu IHDR cua PNG."""
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
        raise ValueError("Không phải file PNG hợp lệ.")
    return struct.unpack(">II", data[16:24])


def validate_xy(x, y, size: tuple[int, int] | None = None) -> tuple[int, int]:
    """Toa do phai la so nguyen; co kich thuoc thi bat buoc nam trong man hinh, khong thi chi chan gia tri vo ly."""
    for v in (x, y):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or (isinstance(v, float) and v != int(v)):
            raise ValueError("Toạ độ phải là số nguyên (pixel).")
    x, y = int(x), int(y)
    if size:
        w, h = size
        if not (0 <= x < w and 0 <= y < h):
            raise ValueError(f"Toạ độ ({x}, {y}) nằm ngoài màn hình {w}x{h}.")
        return x, y
    return max(0, min(x, 20000)), max(0, min(y, 20000))


def parse_keys(keys: str) -> list[str]:
    """'ctrl+shift+t' -> ['ctrl','shift','t'] (chu thuong, chi ten phim trong whitelist)."""
    parts = [k.strip().lower() for k in (keys or "").split("+") if k.strip()]
    if not parts or len(parts) > 5:
        raise ValueError("Tổ hợp phím không hợp lệ (ví dụ: ctrl+l, Return).")
    bad = [k for k in parts if k not in KEYS]
    if bad:
        raise ValueError(f"Phím không được hỗ trợ: {', '.join(bad)}.")
    if parts[-1] in MODS:
        raise ValueError("Tổ hợp phím phải kết thúc bằng phím thường.")
    return parts


def detect_platform() -> str:
    """'macos' | 'wayland' | 'x11' | 'windows' | 'other'."""
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        st = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if st == "wayland" or (not st and os.environ.get("WAYLAND_DISPLAY")):
            return "wayland"
        return "x11"
    return "other"


def _unsupported(platform: str):
    raise RuntimeError(f"Điều khiển máy tính chưa hỗ trợ hệ điều hành này ({platform}).")


# ---------- dung argv
def build_screenshot(platform: str, path: str, which=_which) -> list[list[str]]:
    if platform == "macos":
        return [["screencapture", "-x", path]]
    if platform == "wayland":
        if which("grim"):
            return [["grim", path]]
        if which("gnome-screenshot"):
            return [["gnome-screenshot", "-f", path]]
        raise RuntimeError(_missing("wayland", "chụp màn hình", "grim"))
    if platform == "x11":
        if which("scrot"):
            return [["scrot", "-o", path]]
        if which("import"):
            return [["import", "-window", "root", path]]
        if which("gnome-screenshot"):
            return [["gnome-screenshot", "-f", path]]
        raise RuntimeError(_missing("x11", "chụp màn hình", "scrot"))
    _unsupported(platform)


def build_move(platform: str, x: int, y: int, which=_which) -> list[list[str]]:
    if platform == "x11":
        return [["xdotool", "mousemove", str(x), str(y)]]
    if platform == "wayland":
        return [["ydotool", "mousemove", "--absolute", "-x", str(x), "-y", str(y)]]
    if platform == "macos":
        return [["cliclick", f"m:{x},{y}"]] if which("cliclick") else [["osascript", "-e", f'tell application "System Events" to set the position of the mouse to {{{x}, {y}}}']]
    _unsupported(platform)


def build_click(platform: str, x: int, y: int, button: str = "left", double: bool = False, which=_which) -> list[list[str]]:
    if button not in ("left", "right", "middle"):
        raise ValueError("Nút chuột phải là left, right hoặc middle.")
    n = 2 if double else 1
    if platform == "x11":
        b = {"left": "1", "middle": "2", "right": "3"}[button]
        return [["xdotool", "mousemove", str(x), str(y), "click", "--repeat", str(n), b]]
    if platform == "wayland":
        code = {"left": "0xC0", "right": "0xC1", "middle": "0xC2"}[button]
        return [*build_move(platform, x, y), ["ydotool", "click", "--repeat", str(n), code]]
    if platform == "macos":
        if which("cliclick"):
            op = {"left": "dc" if double else "c", "right": "rc", "middle": "c"}[button]
            return [["cliclick", f"{op}:{x},{y}"]]
        if button != "left":
            raise RuntimeError("Click phải/giữa trên macOS cần cliclick (brew install cliclick).")
        return [["osascript", "-e", f'tell application "System Events" to click at {{{x}, {y}}}'] * 1] * 1 if not double else [["osascript", "-e", f'tell application "System Events" to click at {{{x}, {y}}}']] * 2
    _unsupported(platform)


def build_type(platform: str, text: str, which=_which) -> list[list[str]]:
    if platform == "x11":
        return [["xdotool", "type", "--delay", "20", "--", text]]
    if platform == "wayland":
        return [["wtype", "--", text]] if which("wtype") else [["ydotool", "type", "--", text]]
    if platform == "macos":
        if which("cliclick"):
            return [["cliclick", f"t:{text}"]]
        return [["osascript", "-e", "on run argv\ntell application \"System Events\" to keystroke (item 1 of argv)\nend run", text]]
    _unsupported(platform)


def build_key(platform: str, keys: str, which=_which) -> list[list[str]]:
    parts = parse_keys(keys)
    if platform == "x11":
        return [["xdotool", "key", "+".join(_XKEY.get(k, k) for k in parts)]]
    if platform == "wayland":
        down = [f"{_YCODE[k]}:1" for k in parts]
        up = [f"{_YCODE[k]}:0" for k in reversed(parts)]
        return [["ydotool", "key", *down, *up]]
    if platform == "macos":
        mods, key = parts[:-1], parts[-1]
        if which("cliclick") and not mods and key in _CLIKEY:
            return [["cliclick", f"kp:{_CLIKEY[key]}"]]
        m = {"ctrl": "control", "control": "control", "alt": "option", "shift": "shift", "super": "command", "meta": "command", "cmd": "command"}
        using = ", ".join(f"{m[k]} down" for k in mods)
        tail = f" using {{{using}}}" if mods else ""
        act = f"key code {_MAC[key]}" if key in _MAC else f'keystroke "{key}"'
        return [["osascript", "-e", f'tell application "System Events" to {act}{tail}']]
    _unsupported(platform)


def build_scroll(platform: str, direction: str, amount: int = 5, which=_which) -> list[list[str]]:
    if direction not in ("up", "down", "left", "right"):
        raise ValueError("Hướng cuộn phải là up, down, left hoặc right.")
    amount = max(1, min(int(amount), 50))
    if platform == "x11":
        b = {"up": "4", "down": "5", "left": "6", "right": "7"}[direction]
        return [["xdotool", "click", "--repeat", str(amount), b]]
    if platform == "wayland":
        dx, dy = {"up": (0, amount), "down": (0, -amount), "left": (-amount, 0), "right": (amount, 0)}[direction]
        return [["ydotool", "mousemove", "--wheel", "-x", str(dx), "-y", str(dy)]]
    if platform == "macos":
        if which("cliclick"):
            return [["cliclick", "kp:arrow-" + direction] * 1] * amount
        raise RuntimeError("Cuộn trên macOS cần cliclick (brew install cliclick).")
    _unsupported(platform)


# ---------- thong bao thieu cong cu
def _missing(platform: str, what: str, pkg: str) -> str:
    if platform == "wayland":
        extra = " Lưu ý ydotool cần daemon ydotoold chạy và quyền ghi /dev/uinput (thêm user vào nhóm input hoặc udev rule)." if pkg == "ydotool" else ""
        return f"Thiếu công cụ để {what} trên Wayland. Cài bằng: sudo apt install {pkg}.{extra}"
    if platform == "x11":
        return f"Thiếu công cụ để {what} trên X11. Cài bằng: sudo apt install {pkg}."
    return f"Thiếu công cụ để {what}."


def _need_input(platform: str, which=_which) -> None:
    """Bao loi ro rang neu thieu cong cu nhap lieu."""
    if platform == "x11" and not which("xdotool"):
        raise RuntimeError(_missing("x11", "điều khiển chuột/bàn phím", "xdotool"))
    if platform == "wayland" and not which("ydotool"):
        raise RuntimeError(_missing("wayland", "điều khiển chuột/bàn phím", "ydotool"))


def _run(cmds: list[list[str]]) -> None:
    for argv in cmds:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            raise RuntimeError(f"Lệnh {argv[0]} thất bại: {(r.stderr or r.stdout).strip()[:300]}")


# ---------- tool
def _gate(ctx, detail: str) -> bool:
    """Kiem tra bat tinh nang va xin phe duyet. False = bi tu choi."""
    if not cfgmod.load().computer.enabled:
        raise RuntimeError("Điều khiển máy tính đang tắt. Bật trong Cài đặt > Bảo mật > Điều khiển máy tính (hoặc đặt computer.enabled = true trong config).")
    return bool(ctx.full_access or ctx.approve("computer", detail))


@tool("computer_screenshot", "Chụp toàn bộ màn hình và trả về ảnh cùng kích thước (pixel). Thử nghiệm, luôn hỏi phê duyệt.", {}, risk="exec")
def computer_screenshot(ctx):
    if not _gate(ctx, "Chụp màn hình"):
        return DENIED
    plat = detect_platform()
    out = ctx.workdir / "media"
    out.mkdir(parents=True, exist_ok=True)
    name = f"screen-{int(time.time() * 1000)}.png"
    path = out / name
    _run(build_screenshot(plat, str(path)))
    if not path.is_file():
        raise RuntimeError("Không chụp được màn hình (không có file kết quả).")
    w, h = png_size(path.read_bytes())
    _SCREEN["size"] = (w, h)
    return f"[image: media/{name}]\nKích thước màn hình: {w}x{h} pixel. Toạ độ dùng pixel của ảnh này."


@tool("computer_click", "Click chuột tại toạ độ pixel (x, y) của ảnh chụp màn hình.",
      {"x": ("integer", "toạ độ ngang"), "y": ("integer", "toạ độ dọc"), "button": ("string", "left | right | middle"), "double": ("boolean", "click đúp")}, required=["x", "y"], risk="exec")
def computer_click(ctx, x, y, button="left", double=False):
    x, y = validate_xy(x, y, _SCREEN["size"])
    if not _gate(ctx, f"Click {button}{' đúp' if double else ''} tại ({x}, {y})"):
        return DENIED
    plat = detect_platform()
    cmds = build_click(plat, x, y, button, bool(double))
    _need_input(plat)
    _run(cmds)
    return f"Đã click {button}{' đúp' if double else ''} tại ({x}, {y})."


@tool("computer_move", "Di chuyển con trỏ chuột tới toạ độ pixel (x, y).", {"x": ("integer", "toạ độ ngang"), "y": ("integer", "toạ độ dọc")}, risk="exec")
def computer_move(ctx, x, y):
    x, y = validate_xy(x, y, _SCREEN["size"])
    if not _gate(ctx, f"Di chuột tới ({x}, {y})"):
        return DENIED
    plat = detect_platform()
    cmds = build_move(plat, x, y)
    _need_input(plat)
    _run(cmds)
    return f"Đã di chuột tới ({x}, {y})."


@tool("computer_type", "Gõ một đoạn văn bản (tối đa 2000 ký tự) vào cửa sổ đang focus.", {"text": ("string", "văn bản cần gõ")}, risk="exec")
def computer_type(ctx, text):
    if not isinstance(text, str) or not text:
        raise ValueError("Thiếu văn bản cần gõ.")
    if len(text) > MAX_TEXT:
        raise ValueError(f"Văn bản quá dài ({len(text)} > {MAX_TEXT} ký tự).")
    if not _gate(ctx, f"Gõ văn bản: {text[:200]!r}"):
        return DENIED
    plat = detect_platform()
    cmds = build_type(plat, text)
    _need_input(plat)
    _run(cmds)
    return f"Đã gõ {len(text)} ký tự."


@tool("computer_key", "Nhấn một phím hoặc tổ hợp phím, ví dụ 'ctrl+l', 'Return', 'alt+tab'.", {"keys": ("string", "tổ hợp phím nối bằng +")}, risk="exec")
def computer_key(ctx, keys):
    parse_keys(keys)
    if not _gate(ctx, f"Nhấn phím: {keys}"):
        return DENIED
    plat = detect_platform()
    cmds = build_key(plat, keys)
    _need_input(plat)
    _run(cmds)
    return f"Đã nhấn {keys}."


@tool("computer_scroll", "Cuộn chuột theo hướng up/down/left/right.", {"direction": ("string", "up | down | left | right"), "amount": ("integer", "số bước cuộn (mặc định 5)")}, required=["direction"], risk="exec")
def computer_scroll(ctx, direction, amount=5):
    if direction not in ("up", "down", "left", "right"):
        raise ValueError("Hướng cuộn phải là up, down, left hoặc right.")
    if not _gate(ctx, f"Cuộn {direction} {amount} bước"):
        return DENIED
    plat = detect_platform()
    cmds = build_scroll(plat, direction, amount)
    _need_input(plat)
    _run(cmds)
    return f"Đã cuộn {direction} {amount} bước."


def status() -> dict:
    """Trang thai cho `argus doctor` va giao dien."""
    plat = detect_platform()
    w = shutil.which
    shots = [t for t in ("grim", "gnome-screenshot", "scrot", "import", "screencapture") if w(t)]
    inputs = [t for t in ("xdotool", "ydotool", "wtype", "cliclick", "osascript") if w(t)]
    hint = ""
    if plat == "wayland":
        if not w("ydotool"):
            hint = _missing("wayland", "điều khiển chuột/bàn phím", "ydotool")
        elif not shots:
            hint = _missing("wayland", "chụp màn hình", "grim")
    elif plat == "x11":
        if not w("xdotool"):
            hint = _missing("x11", "điều khiển chuột/bàn phím", "xdotool")
        elif not shots:
            hint = _missing("x11", "chụp màn hình", "scrot")
    elif plat == "macos":
        hint = "" if w("cliclick") else "Nên cài cliclick (brew install cliclick) để click/gõ ổn định; cần cấp quyền Accessibility và Screen Recording."
    else:
        hint = "Hệ điều hành này chưa được hỗ trợ."
    return {"enabled": cfgmod.load().computer.enabled, "platform": plat, "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
            "screenshot_tools": shots, "input_tools": inputs, "hint": hint}
