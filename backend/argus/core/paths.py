import os
from pathlib import Path

from .env import getenv

# CODE_ROOT: ma nguon (giao dien da build, mau workspace). ROOT: du lieu nguoi dung (data/, config.json, workspace/).
# Mac dinh hai thu nay la mot (chay tu repo); dat ARGUS_HOME de tach du lieu ra noi khac.
CODE_ROOT = Path(__file__).resolve().parents[3]
ROOT = Path(getenv("HOME")).expanduser().resolve() if getenv("HOME") else CODE_ROOT
DATA = ROOT / "data"
DB_PATH = DATA / "agent.db"
CONFIG_PATH = Path(getenv("CONFIG") or ROOT / "config.json")  # Docker dat o /app/data de luu ben
DIST = CODE_ROOT / "frontend" / "dist"
PID_FILE = DATA / "server.pid"
LOG_FILE = DATA / "server.log"
