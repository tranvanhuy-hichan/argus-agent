import json
import time

from ..core.db import db


def record(session_id: str | None, source: str, tool: str, args: dict, decision: str, ok: bool, duration_ms: int, result: str) -> None:
    with db() as c:
        c.execute("INSERT INTO audit(ts,session_id,source,tool,args,decision,ok,duration_ms,result) VALUES(?,?,?,?,?,?,?,?,?)",
                  (time.time(), session_id, source, tool, json.dumps(args, ensure_ascii=False)[:2000], decision, int(ok), duration_ms, result[:1500]))


def list_events(limit: int = 100, offset: int = 0, tool: str = "", decision: str = "", source: str = "") -> dict:
    where, params = ["1=1"], []
    for col, val in (("tool", tool), ("decision", decision), ("source", source)):
        if val:
            where.append(f"{col}=?")
            params.append(val)
    with db() as c:
        total = c.execute(f"SELECT COUNT(*) n FROM audit WHERE {' AND '.join(where)}", params).fetchone()["n"]
        rows = c.execute(f"SELECT * FROM audit WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
    return {"total": total, "items": [dict(r) | {"ok": bool(r["ok"])} for r in rows]}
