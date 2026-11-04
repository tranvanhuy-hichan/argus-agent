"""Hạn mức sử dụng của các model: giới hạn theo phiên 5 giờ và theo tuần của gói thuê bao (Claude Code), cùng lượng Argus đã dùng.

Chỉ dùng thứ nhà cung cấp công bố: lệnh `claude -p /usage` (lệnh cục bộ, không tốn lượt gọi model, không đọc khóa đăng nhập).
Antigravity và Codex chưa có lệnh xem hạn mức nên chỉ hiện phần Argus đã dùng."""
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from ..core import db as dbmod
from ..core.config import ProviderCfg
from ..core.db import db
from . import cli_provider

TTL = 60.0
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()
LINE = re.compile(r"^\s*(Current (?:session|week)[^:\n]*):\s*(\d{1,3})%\s+used(?:\s*[·•-]\s*resets?\s+(.+?))?\s*$", re.I | re.M)


def parse_claude_usage(text: str) -> list[dict]:
    """'Current session: 14% used · resets Nov 4, 10:29pm' -> {kind, label, used, resets}."""
    out = []
    for m in LINE.finditer(text):
        label = m.group(1).strip()
        kind = "session" if label.lower().startswith("current session") else "week"
        detail = re.search(r"\((.+)\)", label)
        out.append({"kind": kind, "model": detail.group(1) if detail and kind == "week" else "", "used": min(100, int(m.group(2))), "resets": (m.group(3) or "").strip()})
    return out


def argus_usage(provider: str) -> dict:
    """Token và số lượt gọi mà Argus đã dùng với provider này trong 5 giờ, 24 giờ và 7 ngày qua."""
    now = time.time()
    res = {}
    with db() as c:
        for key, secs in (("h5", 5 * 3600), ("d1", 86400), ("d7", 7 * 86400)):
            r = c.execute("SELECT COUNT(*) calls, COALESCE(SUM(prompt_tokens),0) p, COALESCE(SUM(completion_tokens),0) c FROM usage WHERE provider=? AND ts>=?", (provider, now - secs)).fetchone()
            tot = c.execute("SELECT COALESCE(SUM(prompt_tokens+completion_tokens),0) n FROM usage WHERE ts>=?", (now - secs,)).fetchone()["n"]
            tokens = r["p"] + r["c"]
            res[key] = {"calls": r["calls"], "tokens": tokens, "share": round(tokens / tot, 3) if tot else 0.0}  # phần của model này trong tổng token Argus đã dùng
    return res


def _claude_limits(cfg: ProviderCfg) -> dict:
    if not cli_provider.find(cfg):
        return {"error": "không tìm thấy lệnh claude"}
    workdir = Path(dbmod.DATA) / "cli-run"
    workdir.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}  # luôn xem gói thuê bao, không phải khóa API
    try:
        r = subprocess.run(cli_provider.executable(cfg) + ["-p", "/usage"], capture_output=True, text=True, timeout=40, cwd=workdir, env=env, encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": f"không chạy được lệnh /usage ({type(e).__name__})"}
    windows = parse_claude_usage(r.stdout)
    if not windows:
        first = next((ln.strip() for ln in (r.stdout + r.stderr).splitlines() if ln.strip()), "")
        return {"windows": [], "note": first[:200] or "không đọc được hạn mức"}
    return {"windows": windows}


def get(name: str, cfg: ProviderCfg, refresh: bool = False) -> dict:
    """Hạn mức của một provider (có bộ nhớ đệm 60 giây vì lệnh /usage mất vài giây)."""
    live: dict | None = None
    if cfg.type == "cli" and cfg.cli == "claude":
        with _lock:
            hit = _cache.get(name)
            if hit and not refresh and time.time() - hit[0] < TTL:
                live = hit[1]
        if live is None:
            live = _claude_limits(cfg)
            with _lock:
                _cache[name] = (time.time(), live)
    return {"provider": name, "official": live is not None, "limits": live, "argus": argus_usage(name), "fetched": time.time()}
