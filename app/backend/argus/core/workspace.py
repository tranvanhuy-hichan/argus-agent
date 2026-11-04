import shutil
from pathlib import Path

from .config import Config
from .env import getenv
from .paths import CODE_ROOT


def template_dir() -> Path:
    """Noi giu SOUL.md va skill mau. Docker dat ARGUS_TEMPLATE vi thu muc workspace thuong bi mount de len."""
    return Path(getenv("TEMPLATE") or CODE_ROOT / "templates" / "workspace")


def seed_skills(src: Path, dst: Path) -> None:
    """Chep skill dung san vao workspace dung mot lan moi skill: skill nguoi dung da xoa se khong tu quay lai,
    con skill moi o ban cap nhat se duoc them vao."""
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    marker = dst / ".seeded"
    done = set(marker.read_text().split()) if marker.exists() else set()
    if not marker.exists():  # workspace cu da co skill example nhung chua co marker
        done |= {p.name for p in dst.iterdir() if p.is_dir()}
    for d in sorted(src.iterdir()):
        if d.is_dir() and d.name not in done:
            if not (dst / d.name).exists():
                shutil.copytree(d, dst / d.name)
            done.add(d.name)
    marker.write_text("\n".join(sorted(done)) + "\n")


def ensure_workspace(cfg: Config) -> None:
    """Tao workspace va chep SOUL.md, MEMORY.md, skill mau neu thieu (khong bao gio ghi de file da co)."""
    ws = cfg.workspace_path()
    ws.mkdir(parents=True, exist_ok=True)
    src = template_dir()
    if src.resolve() != ws.resolve():
        if not (ws / "SOUL.md").exists() and (src / "SOUL.md").exists():
            shutil.copy(src / "SOUL.md", ws / "SOUL.md")
        seed_skills(src / "skills", ws / "skills")
    if not (ws / "MEMORY.md").exists():
        (ws / "MEMORY.md").write_text("# Memory\n")
