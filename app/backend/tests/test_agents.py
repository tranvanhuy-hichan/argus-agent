"""Ke hoach, agent con, viec chay nen: dung provider gia (kich ban theo luat) de kiem tra vong lap that."""
import threading
import time
import uuid

import pytest

from argus.core import config as cfgmod
from argus.services import agent as agent_mod
from argus.services import jobs, notifications, plans, sessions


class Fake:
    def __init__(self, rule):
        self.rule = rule

    def stream(self, messages, tools, effort=None):
        out = self.rule(messages, [t["name"] for t in tools])
        if out.get("content"):
            yield {"type": "delta", "text": out["content"]}
        yield {"type": "final", "content": out.get("content", ""), "tool_calls": out.get("calls", []), "usage": {"prompt": 1, "completion": 1}}


def call(name, **args):
    return {"id": "c" + uuid.uuid4().hex[:6], "name": name, "args": args}


@pytest.fixture
def llm(tmp_env, monkeypatch):
    def install(rule):
        monkeypatch.setattr(agent_mod, "make_provider", lambda cfg: Fake(rule))
    return install


def run_chat(text="hi", approver=None, **kw):
    events = []
    sid = sessions.create(text)
    agent_mod.run_turn(sid, text, None, approver or (lambda k, d: True), events.append, **kw)
    return sid, events


def last_is_tool(messages):
    return messages[-1]["role"] == "tool"


def test_plan_tools_persist_emit_and_feed_the_prompt(llm):
    seen = []

    def rule(messages, tool_names):
        sys0 = messages[0]["content"]
        seen.append(sys0)
        n = sum(m["role"] == "tool" for m in messages)
        if n == 0:
            return {"calls": [call("plan_set", steps=["tìm dữ liệu", "viết báo cáo"])]}
        if n == 1:
            return {"calls": [call("plan_update", step=1, status="done", note="ok")]}
        return {"content": "xong"}

    llm(rule)
    sid, events = run_chat()
    agent_mod.run_turn(sid, "tiếp tục", None, lambda k, d: True, lambda e: None)  # luot sau: ke hoach duoc dua vao prompt he thong
    items = plans.get(sid)
    assert [(i["id"], i["status"]) for i in items] == [(1, "done"), (2, "pending")]
    assert [e["items"][0]["status"] for e in events if e["type"] == "plan"] == ["pending", "done"]
    assert "Kế hoạch hiện tại của hội thoại (1/2 xong)" in seen[-1] and "plan_set" in seen[0]


@pytest.mark.parametrize("steps,err", [([], "ít nhất"), (["x"] * 26, "tối đa")])
def test_plan_validation(tmp_env, steps, err):
    sid = sessions.create("p")
    with pytest.raises(ValueError, match=err):
        plans.set_items(sid, steps)


def test_plan_update_validation(tmp_env):
    sid = sessions.create("p")
    plans.set_items(sid, ["a"])
    with pytest.raises(ValueError, match="trạng thái"):
        plans.update(sid, 1, "weird")
    with pytest.raises(ValueError, match="không có bước"):
        plans.update(sid, 9, "done")


def test_delegate_runs_child_with_role_tools_and_returns_result(llm, monkeypatch):
    child_tools = {}
    seen_dirs = []
    real = agent_mod.workfiles.session_dir
    monkeypatch.setattr(agent_mod.workfiles, "session_dir", lambda cfg, s: (seen_dirs.append(s), real(cfg, s))[1])

    def rule(messages, tool_names):
        if "nhà nghiên cứu" in messages[0]["content"]:  # prompt cua vai tro researcher => day la agent con
            child_tools["names"] = tool_names
            return {"content": "KET QUA CON"}
        if last_is_tool(messages):
            return {"content": "tong hop: " + messages[-1]["content"]}
        return {"calls": [call("delegate", role="researcher", task="tìm hiểu X")]}

    llm(rule)
    sid, events = run_chat()
    result = next(e for e in events if e["type"] == "tool_result")["result"]
    assert "KET QUA CON" in result and "researcher" in result
    assert set(child_tools["names"]) >= {"web_search", "read", "plan_set"} and not {"exec", "write", "delegate", "task_start"} & set(child_tools["names"])
    job = jobs.list_jobs(kind="subagent")[0]
    assert job["status"] == "done" and job["parent_session"] == sid and job["role"] == "researcher" and job["result"] == "KET QUA CON"
    assert sessions.get(job["session_id"])["source"] == "subagent"
    assert seen_dirs.count(sid) == 2 and job["session_id"] not in seen_dirs  # agent con dung thu muc cua phien cha


def test_parallel_delegates_run_concurrently(llm):
    running = {"now": 0, "max": 0}
    lock = threading.Lock()

    def rule(messages, tool_names):
        if "lập trình viên" in messages[0]["content"] or "nhà nghiên cứu" in messages[0]["content"]:
            with lock:
                running["now"] += 1
                running["max"] = max(running["max"], running["now"])
            time.sleep(0.4)
            with lock:
                running["now"] -= 1
            return {"content": "ok"}
        if last_is_tool(messages):
            return {"content": "xong"}
        return {"calls": [call("delegate", role="researcher", task="a"), call("delegate", role="coder", task="b")]}

    llm(rule)
    t0 = time.time()
    _, events = run_chat()
    assert running["max"] == 2 and time.time() - t0 < 0.75  # 2 viec x 0.4s nhung chay song song
    assert [e["type"] for e in events if e["type"] == "tool_result"] == ["tool_result", "tool_result"]


def test_unknown_role_and_empty_task_are_reported(llm):
    llm(lambda m, t: {"content": "x"} if last_is_tool(m) else {"calls": [call("delegate", role="wizard", task="x"), ]})
    _, events = run_chat()
    res = next(e for e in events if e["type"] == "tool_result")
    assert not res["ok"] and "không có vai trò 'wizard'" in res["result"]


def test_subagent_depth_is_limited(llm):
    cfg = cfgmod.load()
    cfg.agents.max_depth = 1
    cfgmod.save(cfg)
    names = {}

    def rule(messages, tool_names):
        if "nhà nghiên cứu" in messages[0]["content"]:
            names["child"] = tool_names
            return {"content": "con xong"}
        return {"content": "xong"} if last_is_tool(messages) else {"calls": [call("delegate", role="researcher", task="x")]}

    llm(rule)
    run_chat()
    assert "delegate" not in names["child"] and "task_start" not in names["child"]  # tang cuoi khong duoc tao them agent con


def test_readonly_permission_is_inherited_by_children(llm):
    names = {}

    def rule(messages, tool_names):
        if "lập trình viên" in messages[0]["content"]:
            names["child"] = tool_names
            return {"content": "ok"}
        return {"content": "xong"} if last_is_tool(messages) else {"calls": [call("delegate", role="coder", task="x")]}

    llm(rule)
    run_chat(permission="readonly")
    assert not {"exec", "write", "edit"} & set(names["child"])  # coder co exec/write, nhung che do chi doc cua cha chan het


def test_background_task_completes_notifies_and_records(llm):
    def rule(messages, tool_names):
        n = sum(m["role"] == "tool" for m in messages)
        return {"calls": [call("plan_set", steps=["a", "b"])]} if n == 0 else {"content": "BAO CAO CUOI"}

    llm(rule)
    jid = jobs.start_background("làm báo cáo", title="Báo cáo")
    for _ in range(100):
        if jobs.get(jid)["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    job = jobs.get(jid)
    assert job["status"] == "done" and job["result"] == "BAO CAO CUOI" and job["steps"] == 1 and job["finished"]
    note = notifications.list_all()[0]
    assert "Báo cáo" in note["title"] and note["body"] == "BAO CAO CUOI" and note["source"] == "task"


def test_background_task_can_be_cancelled(llm):
    def rule(messages, tool_names):
        time.sleep(0.05)
        return {"calls": [call("plan_show")]}  # lap vo han

    llm(rule)
    jid = jobs.start_background("lặp mãi", title="Lặp")
    time.sleep(0.4)
    assert jobs.get(jid)["status"] == "running" and jobs.get(jid)["steps"] > 0
    assert jobs.request_cancel(jid)
    for _ in range(100):
        if jobs.get(jid)["status"] not in jobs.ACTIVE:
            break
        time.sleep(0.05)
    assert jobs.get(jid)["status"] == "cancelled"
    assert not jobs.request_cancel(jid)  # da ket thuc


def test_step_budget_marks_job_failed_but_keeps_partial_result(llm):
    cfg = cfgmod.load()
    cfg.agents.task_max_steps = 5
    cfgmod.save(cfg)
    llm(lambda m, t: {"content": "dở dang", "calls": [call("plan_show")]})
    jid = jobs.start_background("quá dài")
    for _ in range(100):
        if jobs.get(jid)["status"] not in jobs.ACTIVE:
            break
        time.sleep(0.05)
    job = jobs.get(jid)
    assert job["status"] == "failed" and "quá số bước" in job["error"] and job["result"] == "dở dang" and job["steps"] == 5


def test_max_parallel_jobs_is_enforced(llm):
    cfg = cfgmod.load()
    cfg.agents.max_parallel = 2
    cfgmod.save(cfg)
    jobs._slots = None
    state = {"now": 0, "max": 0}
    lock = threading.Lock()

    def rule(messages, tool_names):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.3)
        with lock:
            state["now"] -= 1
        return {"content": "ok"}

    llm(rule)
    ids = [jobs.start_background(f"việc {i}") for i in range(4)]
    for _ in range(200):
        if all(jobs.get(i)["status"] == "done" for i in ids):
            break
        time.sleep(0.05)
    assert all(jobs.get(i)["status"] == "done" for i in ids) and state["max"] == 2


def test_interrupted_jobs_are_marked_on_startup(tmp_env):
    a, b = jobs.create("x"), jobs.create("y")
    jobs._update(b, status="running")
    done = jobs.create("z")
    jobs._update(done, status="done")
    assert jobs.recover_interrupted() == 2
    assert jobs.get(a)["status"] == jobs.get(b)["status"] == "interrupted" and jobs.get(done)["status"] == "done"


def test_delete_only_finished_jobs(tmp_env):
    a = jobs.create("x")
    assert not jobs.delete(a)
    jobs._update(a, status="done")
    assert jobs.delete(a) and jobs.get(a) is None


# ---------------- API
@pytest.fixture
def client(llm):
    from fastapi.testclient import TestClient

    from argus.main import app

    llm(lambda m, t: {"content": "ok từ nền"})
    return TestClient(app)


def test_tasks_api_roundtrip(client):
    r = client.post("/api/tasks", json={"goal": "việc thử", "title": "Thử"})
    assert r.status_code == 200
    jid = r.json()["id"]
    for _ in range(100):
        if client.get(f"/api/tasks/{jid}").json()["status"] == "done":
            break
        time.sleep(0.05)
    job = client.get(f"/api/tasks/{jid}").json()
    assert job["status"] == "done" and job["result"] == "ok từ nền"
    assert [t["id"] for t in client.get("/api/tasks?kind=task").json()] == [jid]
    assert client.delete(f"/api/tasks/{jid}").status_code == 200 and client.get(f"/api/tasks/{jid}").status_code == 404


def test_tasks_api_validation_and_plan_endpoint(client):
    assert client.post("/api/tasks", json={"goal": "x", "role": "wizard"}).status_code == 400
    assert client.post("/api/tasks", json={"goal": "x", "permission": "root"}).status_code == 400
    assert client.get("/api/tasks/nope").status_code == 404
    sid = sessions.create("t")
    plans.set_items(sid, ["a", "b"])
    plans.update(sid, 1, "done")
    p = client.get(f"/api/sessions/{sid}/plan").json()
    assert p["done"] == 1 and p["total"] == 2 and p["items"][0]["status"] == "done"
    assert client.get("/api/sessions/zzzzzzzz/plan").status_code == 404


def test_subagent_sessions_hidden_from_chat_list(client, llm):
    visible = sessions.create("thường")
    jid = jobs.create("con", kind="subagent")
    jobs._update(jid, session_id=sessions.create("con", source="subagent"))
    titles = [s["id"] for s in client.get("/api/sessions").json()]
    assert visible in titles and jobs.get(jid)["session_id"] not in titles


def test_plan_progress_is_nudged_and_auto_started(llm):
    seen = {}

    def rule(messages, tool_names):
        if last_is_tool(messages):
            if "bước 1 đang làm" in messages[-1]["content"]:
                seen["tool_msg"] = messages[-1]["content"]
                return {"content": "xong"}
            return {"calls": [call("list_dir", path=".")]}
        return {"calls": [call("plan_set", steps=["buoc 1", "buoc 2"])]}

    llm(rule)
    sid, events = run_chat()
    items = plans.get(sid)
    assert items[0]["status"] == "in_progress" and items[1]["status"] == "pending"  # tu dong bat dau buoc 1 khi agent lam viec khac
    assert any(e["type"] == "plan" and e["items"][0]["status"] == "in_progress" for e in events)
    assert 'plan_update(step=1, status="done")' in seen["tool_msg"]  # model duoc nhac cap nhat
    shown = next(e for e in events if e["type"] == "tool_result" and "bước 1 đang làm" not in e["result"] and e["result"] != "")
    assert "Kế hoạch: bước" not in "".join(e["result"] for e in events if e["type"] == "tool_result" and e["id"] == shown["id"])  # nguoi dung khong thay loi nhac


# ---------------- goi MCP dich vu bang dau @
def _mcp_world(monkeypatch, connected=("notion", "linear")):
    from argus.services import mcp_client
    from argus.services.tools import ToolDef

    defs = {f"{s}__{t}": ToolDef(name=f"{s}__{t}", description=f"[MCP:{s}] {t}", parameters={"type": "object", "properties": {}}, fn=lambda ctx, **a: "ok", risk="mcp", read_only=True)
            for s, t in (("notion", "search"), ("linear", "list_issues"))}
    monkeypatch.setattr(mcp_client.manager, "tool_defs", lambda: defs)
    monkeypatch.setattr(mcp_client.manager, "status", lambda: {s: {"status": "connected"} for s in connected})
    full = cfgmod.load()
    full.mcp_servers = {"notion": cfgmod.McpServerCfg(transport="http", url="https://mcp.notion.com/mcp", oauth=True), "linear": cfgmod.McpServerCfg(transport="http", url="https://mcp.linear.app/mcp", oauth=True)}
    cfgmod.save(full)


def _capture(llm):
    seen = {}

    def rule(messages, tool_names):
        seen["system"], seen["tools"] = messages[0]["content"], set(tool_names)
        return {"content": "ok"}
    llm(rule)
    return seen


def test_at_mention_keeps_only_that_service_tools_and_hints_the_model(llm, monkeypatch):
    _mcp_world(monkeypatch)
    seen = _capture(llm)
    run_chat("Trong @notion tìm trang họp tuần trước")
    assert "notion__search" in seen["tools"] and "linear__list_issues" not in seen["tools"] and "read" in seen["tools"]  # cong cu cot loi van con
    assert "@notion" in seen["system"] and "'notion__'" in seen["system"]


def test_without_or_with_email_no_filtering(llm, monkeypatch):
    _mcp_world(monkeypatch)
    seen = _capture(llm)
    run_chat("tìm trang họp")
    assert {"notion__search", "linear__list_issues"} <= seen["tools"] and "@" not in seen["system"].split("Hiện tại")[-1]
    run_chat("gửi mail cho an@notion.com và @khong-co-dich-vu-nay")
    assert {"notion__search", "linear__list_issues"} <= seen["tools"]  # dia chi email va ten khong ton tai khong kich hoat


def test_mention_of_disconnected_service_warns_user(llm, monkeypatch):
    _mcp_world(monkeypatch, connected=("linear",))
    seen = _capture(llm)
    _, events = run_chat("@notion tìm trang họp")
    assert any(e["type"] == "notice" and "notion" in e["message"] for e in events)
    assert "chưa kết nối" in seen["system"] and "mục Tiện ích" in seen["system"]


def test_mention_filter_survives_only_tools(llm, monkeypatch):
    _mcp_world(monkeypatch)
    seen = _capture(llm)
    run_chat("@linear liệt kê issue", only_tools=["linear__list_issues", "notion__search", "read"])
    assert "linear__list_issues" in seen["tools"] and "notion__search" not in seen["tools"]


# ---------- dung luong token cua phien va ngu canh con lai
def test_context_window_by_model_name_and_override():
    from argus.core import config as cfgmod
    from argus.services import usage as u
    P = lambda model, base="https://api.example.com/v1", cw=0: cfgmod.ProviderCfg(type="openai", base_url=base, model=model, context_window=cw)  # noqa: E731
    assert u.context_window(P("gemini-2.5-flash")) == 1_048_576
    assert u.context_window(P("claude-sonnet-5-5", cw=0)) == 200_000 and u.context_window(P("sonnet[1m]")) == 1_000_000
    assert u.context_window(P("gpt-4o-mini")) == 128_000 and u.context_window(P("model-la")) is None
    assert u.context_window(P("qwen2.5:3b", base="http://localhost:11434/v1")) is None  # local: phụ thuộc num_ctx nên không đoán
    assert u.context_window(P("qwen2.5:3b", base="http://localhost:11434/v1", cw=8192)) == 8192


def test_session_usage_totals_cost_and_remaining_context(tmp_env):
    from argus.core import config as cfgmod
    from argus.services import sessions, usage as u
    cfg = cfgmod.load()
    cfg.providers["g"] = cfgmod.ProviderCfg(type="openai", base_url="https://x/v1", model="gemini-2.5-flash", price_in=1.0, price_out=2.0)
    sid = sessions.create("x")
    assert u.session_usage(sid, cfg.providers)["context_left"] is None  # chưa có lượt nào
    u.record_llm("g", "gemini-2.5-flash", 1000, 200, 500, True, sid)
    u.record_llm("g", "gemini-2.5-flash", 5000, 800, 700, True, sid)
    u.record_llm("g", "gemini-2.5-flash", 0, 0, 100, False, sid)  # lượt lỗi không tính vào ngữ cảnh hiện tại
    r = u.session_usage(sid, cfg.providers)
    assert (r["calls"], r["errors"], r["prompt_tokens"], r["completion_tokens"]) == (3, 1, 6000, 1000)
    assert r["context_used"] == 5800 and r["context_window"] == 1_048_576 and r["context_left"] == 1_048_576 - 5800
    assert r["cost"] == round((6000 * 1.0 + 1000 * 2.0) / 1e6, 4) and r["provider"] == "g"


def test_session_usage_endpoint(tmp_env):
    from fastapi.testclient import TestClient

    from argus.main import app
    from argus.services import sessions
    c = TestClient(app)
    assert c.get("/api/sessions/khong-co/usage").status_code == 404
    sid = sessions.create("x")
    assert c.get(f"/api/sessions/{sid}/usage").json()["calls"] == 0


# ---------- han muc 5 gio / theo tuan
CLAUDE_USAGE = """You are currently using your subscription to power your Claude Code usage

Current session: 14% used · resets Nov 4, 10:29pm (Asia/Bangkok)
Current week (all models): 25% used · resets Nov 10, 9:59pm (Asia/Bangkok)
Current week (Opus): 3% used

What's contributing to your usage?
"""


def test_parse_claude_usage_lines():
    from argus.services import limits
    w = limits.parse_claude_usage(CLAUDE_USAGE)
    assert [(x["kind"], x["used"]) for x in w] == [("session", 14), ("week", 25), ("week", 3)]
    assert w[0]["resets"] == "Nov 4, 10:29pm (Asia/Bangkok)" and w[2]["model"] == "Opus" and w[2]["resets"] == "" and w[1]["model"] == "all models"
    assert limits.parse_claude_usage("không có gì") == []


def test_limits_endpoint_uses_claude_usage_and_argus_windows(tmp_env, monkeypatch):
    import subprocess
    import types

    from fastapi.testclient import TestClient

    from argus.core import config as cfgmod
    from argus.main import app
    from argus.services import limits, sessions, usage
    cfg = cfgmod.load()
    cfg.providers["cc"] = cfgmod.ProviderCfg(type="cli", cli="claude", model="sonnet")
    cfg.providers["g"] = cfgmod.ProviderCfg(type="openai", base_url="https://x/v1", model="gemini-2.5-flash")
    cfgmod.save(cfg)
    calls = []
    monkeypatch.setattr(limits.cli_provider, "find", lambda c: "/usr/bin/claude")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd) or types.SimpleNamespace(stdout=CLAUDE_USAGE, stderr="", returncode=0))
    sid = sessions.create("x")
    usage.record_llm("g", "gemini-2.5-flash", 1000, 500, 100, True, sid)
    c = TestClient(app)
    r = c.get("/api/providers/cc/limits").json()
    assert r["official"] and r["limits"]["windows"][0]["used"] == 14 and calls[0][-2:] == ["-p", "/usage"]
    c.get("/api/providers/cc/limits")
    assert len(calls) == 1  # bộ nhớ đệm
    c.get("/api/providers/cc/limits", params={"refresh": True})
    assert len(calls) == 2
    g = c.get("/api/providers/g/limits").json()
    assert g["official"] is False and g["limits"] is None and g["argus"]["h5"] == {"calls": 1, "tokens": 1500, "share": 1.0}
    assert c.get("/api/providers/khong-co/limits").status_code == 404


def test_empty_reply_after_tool_is_retried(llm):
    """Model tra ve rong sau khi nhan ket qua tool: agent nhac no viet cau tra loi cuoi thay vi im lang."""
    def rule(messages, tool_names):
        if not any(m["role"] == "tool" for m in messages):
            return {"calls": [call("plan_show")]}
        if any("Your last reply was empty" in str(m.get("content")) for m in messages):
            return {"content": "Day la cau tra loi"}
        return {"content": ""}

    llm(rule)
    _, events = run_chat()
    assert [e["content"] for e in events if e["type"] == "assistant" and e["content"]] == ["Day la cau tra loi"]


def test_read_document_pptx_and_offset(tmp_env, tmp_path):
    import zipfile
    from argus.services import tools
    pp = tmp_path / "d.pptx"
    with zipfile.ZipFile(pp, "w") as z:
        z.writestr("ppt/slides/slide1.xml", '<p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>Hello slide</a:t></p>')
    txt = tmp_path / "long.txt"
    txt.write_text("x" * 70000)
    ctx = tools.ToolContext(workspace=tmp_path, full_access=True)
    assert "Hello slide" in tools.read_document(ctx, str(pp))
    first = tools.read_document(ctx, str(txt))
    assert "offset=30000" in first and "offset=60000" in tools.read_document(ctx, str(txt), 30000)
    assert "offset" not in tools.read_document(ctx, str(txt), 60000)
