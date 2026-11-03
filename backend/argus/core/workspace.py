import shutil
from pathlib import Path

from .config import Config
from .env import getenv
from .paths import CODE_ROOT


def template_dir() -> Path:
    """Noi giu SOUL.md va skill mau. Docker dat ARGUS_TEMPLATE vi thu muc workspace thuong bi mount de len."""
    return Path(getenv("TEMPLATE") or CODE_ROOT / "workspace")


def ensure_workspace(cfg: Config) -> None:
    """Tao workspace va chep SOUL.md, MEMORY.md, skill mau neu thieu (khong bao gio ghi de file da co)."""
    ws = cfg.workspace_path()
    ws.mkdir(parents=True, exist_ok=True)
    src = template_dir()
    if src.resolve() != ws.resolve():
        if not (ws / "SOUL.md").exists() and (src / "SOUL.md").exists():
            shutil.copy(src / "SOUL.md", ws / "SOUL.md")
        example = src / "skills" / "example"
        if example.is_dir() and not (ws / "skills" / "example").exists():
            shutil.copytree(example, ws / "skills" / "example")
    if not (ws / "MEMORY.md").exists():
        (ws / "MEMORY.md").write_text("# Memory\n")
