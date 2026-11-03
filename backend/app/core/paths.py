from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
DB_PATH = DATA / "agent.db"
CONFIG_PATH = ROOT / "config.json"
DIST = ROOT / "frontend" / "dist"
