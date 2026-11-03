import os
from pathlib import Path

from .env import getenv

# Bo cuc thu muc:
#   CODE_ROOT = <repo>/app        ma nguon co dinh (backend, frontend, mau workspace) - an toan de cai lai/xoa
#   ROOT      = <repo>/user-data  du lieu ca nhan (config.json, data/, workspace/, backups/) - KHONG xoa, nho sao luu
# Dat ARGUS_HOME de dua du lieu ca nhan sang noi khac.
CODE_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = CODE_ROOT.parent


def _default_root() -> Path:
    new = REPO_ROOT / "user-data"
    # Bo cuc cu (truoc khi tach thu muc): du lieu nam ngay o goc repo. Con dung thi giu nguyen de khong mat du lieu.
    legacy = (REPO_ROOT / "config.json").exists() or (REPO_ROOT / "data" / "agent.db").exists()
    return REPO_ROOT if legacy and not new.exists() else new


ROOT = Path(getenv("HOME")).expanduser().resolve() if getenv("HOME") else _default_root()
DATA = ROOT / "data"
DB_PATH = DATA / "agent.db"
CONFIG_PATH = Path(getenv("CONFIG") or ROOT / "config.json")  # Docker dat o /app/data de luu ben
DIST = CODE_ROOT / "frontend" / "dist"
PID_FILE = DATA / "server.pid"
LOG_FILE = DATA / "server.log"
