import re
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
                       COALESCE(SUM(prompt_tokens),0) p, COALESCE(SUM(completion_tokens),0) c,
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


# Cửa sổ ngữ cảnh (số token model nhận trong một lượt) theo tên model; các dịch vụ đổi nhanh nên người dùng có thể ghi đè ở `context_window`.
_WINDOWS = [
    (r"\[1m\]|-1m\b", 1_000_000), (r"gemini", 1_048_576), (r"claude|sonnet|opus|haiku", 200_000), (r"gpt-4\.1", 1_047_576), (r"gpt-5", 400_000),
    (r"gpt-4o|gpt-4-turbo|gpt-4\.5", 128_000), (r"\bo[134](-|\b)", 200_000), (r"gpt-3\.5", 16_385), (r"deepseek", 128_000),
    (r"grok", 256_000), (r"llama-?3|llama3", 128_000), (r"mistral|mixtral|codestral", 128_000), (r"qwen", 128_000),
]


def context_window(pcfg) -> int | None:
    """Số token tối đa của model: ghi đè trong cấu hình, nếu không thì đoán theo tên. Model chạy local (Ollama...) phụ thuộc num_ctx nên không đoán."""
    if getattr(pcfg, "context_window", 0):
        return int(pcfg.context_window)
    if "11434" in (pcfg.base_url or "") or any(h in (pcfg.base_url or "") for h in ("localhost", "127.0.0.1")):
        return None
    name = (pcfg.model or "").lower()
    return next((n for pat, n in _WINDOWS if re.search(pat, name)), None)


def session_usage(sid: str, providers: dict) -> dict:
    """Tổng token đã dùng trong phiên và mức ngữ cảnh còn lại (theo lượt gọi model gần nhất)."""
    with db() as c:
        t = c.execute("SELECT COUNT(*) calls, COALESCE(SUM(prompt_tokens),0) p, COALESCE(SUM(completion_tokens),0) c, COALESCE(SUM(1-ok),0) err FROM usage WHERE session_id=?", (sid,)).fetchone()
        by = c.execute("SELECT provider, COALESCE(SUM(prompt_tokens),0) p, COALESCE(SUM(completion_tokens),0) c FROM usage WHERE session_id=? GROUP BY provider", (sid,)).fetchall()
        last = c.execute("SELECT provider, model, prompt_tokens, completion_tokens FROM usage WHERE session_id=? AND ok=1 AND prompt_tokens>0 ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    cost = sum((r["p"] * providers[r["provider"]].price_in + r["c"] * providers[r["provider"]].price_out) / 1e6 for r in by if r["provider"] in providers)
    out = {"calls": t["calls"], "errors": t["err"], "prompt_tokens": t["p"], "completion_tokens": t["c"], "cost": round(cost, 4),
           "provider": None, "model": None, "context_used": 0, "context_window": None, "context_left": None}
    if last:
        used = last["prompt_tokens"] + last["completion_tokens"]  # lượt sau sẽ gửi lại cả câu trả lời này
        win = context_window(providers[last["provider"]]) if last["provider"] in providers else None
        out.update(provider=last["provider"], model=last["model"], context_used=used, context_window=win, context_left=max(0, win - used) if win else None)
    return out
