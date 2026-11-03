"""Kho vector trong SQLite (float32 BLOB), cosine similarity; chỉ so sánh vector cùng model_id."""
import struct
import time
from array import array

from ..core.db import db


def ensure_schema() -> None:
    """Idempotent va re: DB co the bi thay the (khoi phuc ban sao luu) nen khong nho trang thai."""
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS memory_vectors(
            id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, ref TEXT, session_id TEXT, text TEXT,
            model TEXT, dim INTEGER, vec BLOB, ts REAL)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_mv_model ON memory_vectors(model)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_mv_session ON memory_vectors(session_id)")


def _pack(v: list[float]) -> bytes:
    return array("f", v).tobytes()


def add(items: list[dict]) -> int:
    """items: {kind, ref, session_id, text, model, vec, ts?}"""
    if not items:
        return 0
    ensure_schema()
    now = time.time()
    with db() as c:
        c.executemany("INSERT INTO memory_vectors(kind,ref,session_id,text,model,dim,vec,ts) VALUES(?,?,?,?,?,?,?,?)",
                      [(i["kind"], i.get("ref", ""), i.get("session_id"), i["text"], i["model"], len(i["vec"]), _pack(i["vec"]), i.get("ts") or now) for i in items])
    return len(items)


def delete_session(sid: str) -> None:
    ensure_schema()
    with db() as c:
        c.execute("DELETE FROM memory_vectors WHERE session_id=?", (sid,))


def delete_kind(kind: str) -> None:
    ensure_schema()
    with db() as c:
        c.execute("DELETE FROM memory_vectors WHERE kind=?", (kind,))


def clear(model_id: str | None = None) -> None:
    ensure_schema()
    with db() as c:
        if model_id:
            c.execute("DELETE FROM memory_vectors WHERE model=?", (model_id,))
        else:
            c.execute("DELETE FROM memory_vectors")


def search(query_vec: list[float], model_id: str, k: int = 8, kinds: list[str] | None = None) -> list[dict]:
    ensure_schema()
    sql, args = "SELECT kind,ref,session_id,text,dim,vec,ts FROM memory_vectors WHERE model=?", [model_id]
    if kinds:
        sql += f" AND kind IN ({','.join('?' * len(kinds))})"
        args += list(kinds)
    with db() as c:
        rows = [r for r in c.execute(sql, args).fetchall() if r["dim"] == len(query_vec)]
    if not rows:
        return []
    try:
        import numpy as np
        m = np.vstack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        q = np.asarray(query_vec, dtype=np.float32)
        den = (np.linalg.norm(m, axis=1) * (np.linalg.norm(q) or 1.0)) + 1e-12
        scores = (m @ q / den).tolist()
    except ImportError:
        qn = sum(x * x for x in query_vec) ** 0.5 or 1.0
        scores = []
        for r in rows:
            v = struct.unpack(f"{r['dim']}f", r["vec"])
            scores.append(sum(a * b for a, b in zip(v, query_vec)) / ((sum(a * a for a in v) ** 0.5 or 1.0) * qn))
    order = sorted(range(len(rows)), key=lambda i: -scores[i])[:k]
    return [{"kind": rows[i]["kind"], "ref": rows[i]["ref"], "session_id": rows[i]["session_id"], "text": rows[i]["text"], "score": float(scores[i])} for i in order]


def stats() -> dict:
    ensure_schema()
    with db() as c:
        total = c.execute("SELECT COUNT(*) n FROM memory_vectors").fetchone()["n"]
        by_model = {r["model"]: r["n"] for r in c.execute("SELECT model, COUNT(*) n FROM memory_vectors GROUP BY model")}
        by_kind = {r["kind"]: r["n"] for r in c.execute("SELECT kind, COUNT(*) n FROM memory_vectors GROUP BY kind")}
    return {"total": total, "by_model": by_model, "by_kind": by_kind}
