import time

from ..core.db import db


def record_llm(provider: str, model: str, prompt: int, completion: int, latency_ms: int, ok: bool, session_id: str | None) -> None:
    with db() as c:
        c.execute("INSERT INTO usage(ts,provider,model,prompt_tokens,completion_tokens,latency_ms,ok,session_id) VALUES(?,?,?,?,?,?,?,?)",
                  (time.time(), provider, model, prompt, completion, latency_ms, int(ok), session_id))


def record_tool(name: str, ok: bool, duration_ms: int, session_id: str | None) -> None:
    with db() as c:
        c.execute("INSERT INTO tool_events(ts,name,ok,duration_ms,session_id) VALUES(?,?,?,?,?)", (time.time(), name, int(ok), duration_ms, session_id))


def dashboard(days: int) -> dict:
    since = time.time() - days * 86400
    day = "strftime('%Y-%m-%d', ts, 'unixepoch', 'localtime')"
    with db() as c:
        q = lambda sql, *a: c.execute(sql, a).fetchall()  # noqa: E731
        t = q("""SELECT COUNT(*) calls, COALESCE(SUM(prompt_tokens),0) p, COALESCE(SUM(completion_tokens),0) c,
                 COALESCE(AVG(latency_ms),0) lat, COALESCE(SUM(1-ok),0) err FROM usage WHERE ts>=?""", since)[0]
        tools = q("SELECT COUNT(*) n, COALESCE(SUM(1-ok),0) err FROM tool_events WHERE ts>=?", since)[0]
        sessions = q("SELECT COUNT(*) n FROM sessions WHERE created>=?", since)[0]["n"]
        messages = q("SELECT COUNT(*) n FROM messages WHERE role='user' AND ts>=?", since)[0]["n"]
        llm_by_day = {r["d"]: r for r in q(f"SELECT {day} d, COUNT(*) calls, SUM(prompt_tokens) p, SUM(completion_tokens) c FROM usage WHERE ts>=? GROUP BY d", since)}
        tool_by_day = {r["d"]: r["n"] for r in q(f"SELECT {day} d, COUNT(*) n FROM tool_events WHERE ts>=? GROUP BY d", since)}
        by_provider = [dict(r) for r in q("""SELECT provider, model, COUNT(*) calls, COALESCE(SUM(prompt_tokens+completion_tokens),0) tokens,
                       CAST(AVG(latency_ms) AS INTEGER) latency, COALESCE(SUM(1-ok),0) errors FROM usage WHERE ts>=?
                       GROUP BY provider, model ORDER BY calls DESC""", since)]
        top_tools = [dict(r) for r in q("""SELECT name, COUNT(*) n, COALESCE(SUM(1-ok),0) errors, CAST(AVG(duration_ms) AS INTEGER) avg_ms
                     FROM tool_events WHERE ts>=? GROUP BY name ORDER BY n DESC LIMIT 8""", since)]
    series = []
    for i in range(days - 1, -1, -1):
        d = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
        r = llm_by_day.get(d)
        series.append({"date": d, "calls": r["calls"] if r else 0, "prompt": r["p"] or 0 if r else 0,
                       "completion": r["c"] or 0 if r else 0, "tools": tool_by_day.get(d, 0)})
    return {"days": days, "totals": {"llm_calls": t["calls"], "prompt_tokens": t["p"], "completion_tokens": t["c"], "avg_latency_ms": int(t["lat"]),
                                     "llm_errors": t["err"], "tool_calls": tools["n"], "tool_errors": tools["err"], "sessions": sessions, "messages": messages},
            "series": series, "by_provider": by_provider, "top_tools": top_tools}
