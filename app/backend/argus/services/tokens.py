"""API token cho ung dung ben ngoai goi /v1/*. Chi luu bam SHA-256; token goc chi hien mot lan luc tao."""
import hashlib
import secrets
import time
import uuid

from ..core.db import db


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create(name: str, allow_exec: bool) -> tuple[dict, str]:
    token = "agt_" + secrets.token_urlsafe(32)
    tid = uuid.uuid4().hex[:8]
    with db() as c:
        c.execute("INSERT INTO api_tokens(id,name,hash,prefix,allow_exec,created) VALUES(?,?,?,?,?,?)",
                  (tid, name[:60] or "token", _hash(token), token[:10], int(allow_exec), time.time()))
    return {"id": tid, "name": name, "prefix": token[:10], "allow_exec": allow_exec}, token


def verify(token: str) -> dict | None:
    with db() as c:
        r = c.execute("SELECT * FROM api_tokens WHERE hash=?", (_hash(token),)).fetchone()
        if not r:
            return None
        c.execute("UPDATE api_tokens SET last_used=? WHERE id=?", (time.time(), r["id"]))
    return {"id": r["id"], "name": r["name"], "allow_exec": bool(r["allow_exec"])}


def list_all() -> list[dict]:
    with db() as c:
        rows = c.execute("SELECT id,name,prefix,allow_exec,created,last_used FROM api_tokens ORDER BY created DESC").fetchall()
    return [dict(r) | {"allow_exec": bool(r["allow_exec"])} for r in rows]


def revoke(tid: str) -> None:
    with db() as c:
        c.execute("DELETE FROM api_tokens WHERE id=?", (tid,))
