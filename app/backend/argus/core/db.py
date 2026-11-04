import sqlite3
from contextlib import contextmanager

from .paths import DATA, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, source TEXT DEFAULT 'chat');
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', tool_calls TEXT, tool_call_id TEXT, ts REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS usage(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, provider TEXT, model TEXT,
  prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0,
  latency_ms INTEGER DEFAULT 0, ok INTEGER DEFAULT 1, session_id TEXT);
CREATE TABLE IF NOT EXISTS tool_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, name TEXT NOT NULL,
  ok INTEGER DEFAULT 1, duration_ms INTEGER DEFAULT 0, session_id TEXT);
CREATE TABLE IF NOT EXISTS cron_jobs(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, schedule TEXT NOT NULL, prompt TEXT NOT NULL, provider TEXT,
  enabled INTEGER DEFAULT 1, last_run REAL, last_status TEXT, last_output TEXT, next_run REAL);
CREATE TABLE IF NOT EXISTS api_tokens(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, hash TEXT NOT NULL UNIQUE, prefix TEXT NOT NULL,
  allow_exec INTEGER DEFAULT 0, created REAL NOT NULL, last_used REAL);
"""


EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, session_id TEXT, source TEXT, tool TEXT NOT NULL,
  args TEXT, decision TEXT, ok INTEGER, duration_ms INTEGER, result TEXT);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
  source TEXT, session_id TEXT, read INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS plans(session_id TEXT PRIMARY KEY, items TEXT NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT, goal TEXT NOT NULL, role TEXT, status TEXT NOT NULL,
  session_id TEXT, parent_session TEXT, parent_job TEXT, depth INTEGER DEFAULT 0,
  permission TEXT DEFAULT 'default', provider TEXT, steps INTEGER DEFAULT 0, max_steps INTEGER,
  progress TEXT, result TEXT, error TEXT, cancel_requested INTEGER DEFAULT 0, notify INTEGER DEFAULT 1,
  created REAL, started REAL, finished REAL);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created);
CREATE TABLE IF NOT EXISTS habit_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, session_id TEXT, text TEXT NOT NULL, tokens TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_habit_ts ON habit_requests(ts);
CREATE TABLE IF NOT EXISTS habit_suggestions(
  id TEXT PRIMARY KEY, status TEXT NOT NULL, tokens TEXT NOT NULL, examples TEXT NOT NULL, count INTEGER NOT NULL,
  draft TEXT, created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS channel_links(
  channel TEXT NOT NULL, external_id TEXT NOT NULL, session_id TEXT NOT NULL, PRIMARY KEY(channel, external_id));
"""

MIGRATIONS = [
    ("sessions", "summary", "TEXT DEFAULT ''"),
    ("sessions", "summary_upto", "INTEGER DEFAULT 0"),
    ("sessions", "project", "TEXT DEFAULT ''"),
    ("messages", "attachments", "TEXT"),
    ("cron_jobs", "notify", "INTEGER DEFAULT 1"),
    ("api_tokens", "allow_docs", "INTEGER DEFAULT 0"),
]

fts_enabled = False


def _ensure_columns(c: sqlite3.Connection) -> None:
    for table, col, decl in MIGRATIONS:
        if col not in {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def _ensure_fts(c: sqlite3.Connection) -> None:
    """Tim kiem toan van lich su hoi thoai (bo nho). Chi muc `folded` la van ban da bo dau; bo qua neu khong co FTS5."""
    global fts_enabled
    from .text import fold
    try:
        cols = [r["name"] for r in c.execute("PRAGMA table_info(messages_fts)")]
        if cols and cols[0] != "folded":  # schema cu (chua bo dau): dung lai tu dau
            c.execute("DROP TABLE messages_fts")
            cols = []
        if not cols:
            c.execute("CREATE VIRTUAL TABLE messages_fts USING fts5(folded, content UNINDEXED, session_id UNINDEXED, role UNINDEXED)")
            rows = c.execute("SELECT content, session_id, role FROM messages WHERE role IN ('user','assistant') AND content!=''").fetchall()
            c.executemany("INSERT INTO messages_fts(folded, content, session_id, role) VALUES(?,?,?,?)", [(fold(r["content"]), r["content"], r["session_id"], r["role"]) for r in rows])
        fts_enabled = True
    except sqlite3.OperationalError:
        fts_enabled = False


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
        c.executescript(EXTRA_SCHEMA)
        _ensure_columns(c)
        _ensure_fts(c)
