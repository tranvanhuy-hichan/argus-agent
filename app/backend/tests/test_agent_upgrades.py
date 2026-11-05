"""Checkpoint/hoan tac, ask_user, lenh nen, ghi nho du an, dinh tuyen model nhanh."""
import threading
import time

from argus.services import agent, chat_runner, checkpoints, tools


def _ctx(tmp_path, sid="s1", **kw):
    return tools.ToolContext(workspace=tmp_path, cwd=tmp_path, session_id=sid, full_access=True, confirm_exec=False, **kw)


def test_checkpoint_summary_and_undo(tmp_env, tmp_path):
    (tmp_path / "a.txt").write_text("1\n2\n3\n")
    ctx = _ctx(tmp_path)
    checkpoints.begin("s1")
    assert tools.call(ctx, "edit", {"path": "a.txt", "old": "2", "new": "two\nextra"})[1]
    assert tools.call(ctx, "write", {"path": "b.txt", "content": "new"})[1]
    summary = checkpoints.finish("s1")
    by = {f["path"].rsplit("/", 1)[1]: f for f in summary["files"]}
    assert by["a.txt"]["added"] == 2 and by["a.txt"]["removed"] == 1 and by["b.txt"]["status"] == "new"
    assert len(checkpoints.last("s1")) == 2
    assert len(checkpoints.undo("s1")) == 2
    assert (tmp_path / "a.txt").read_text() == "1\n2\n3\n" and not (tmp_path / "b.txt").exists()
    assert checkpoints.last("s1") == []


def test_no_change_no_checkpoint(tmp_env, tmp_path):
    checkpoints.begin("s2")
    assert checkpoints.finish("s2") is None


def test_ask_user_roundtrip(tmp_env, monkeypatch):
    def fake_turn(sid, text, provider, approver, emit, cancel, *a, asker=None, **k):
        emit({"type": "delta", "text": asker("Chon?", ["A", "B"])})
    monkeypatch.setattr(chat_runner.agent, "run_turn", fake_turn)
    gen = chat_runner.stream_chat(None, "hi", None, detach=True)
    sid = next(gen)["id"]
    q = next(e for e in gen if e["type"] == "question")
    assert q["options"] == ["A", "B"] and chat_runner.state(sid)["questions"][0]["id"] == q["id"]
    assert chat_runner.answer_question(q["id"], "B")
    evs = list(gen)
    assert any(e["type"] == "delta" and e["text"] == "B" for e in evs)


def test_ask_user_tool_without_asker(tmp_path):
    out, ok = tools.call(_ctx(tmp_path), "ask_user", {"question": "x"})
    assert ok and "tự chọn" in out
    out, _ = tools.call(_ctx(tmp_path, asker=lambda q, o: "Có"), "ask_user", {"question": "x"})
    assert out == "Người dùng trả lời: Có"


def test_background_exec(tmp_env, tmp_path):
    ctx = _ctx(tmp_path)
    out, ok = tools.call(ctx, "exec_bg", {"command": "echo hello; sleep 30"})
    assert ok
    job = out.split("job ")[1].split(" ")[0]
    time.sleep(0.5)
    out, _ = tools.call(ctx, "exec_read", {"job": job})
    assert "hello" in out and "đang chạy" in out
    tools.call(ctx, "exec_stop", {"job": job})
    time.sleep(0.5)
    assert "đã thoát" in tools.call(ctx, "exec_read", {"job": job})[0]
    assert tools.call(ctx, "exec_read", {"job": "zzz"})[1] is False


def test_project_note(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    ctx = tools.ToolContext(workspace=tmp_path, cwd=proj, project=proj)
    assert tools.call(ctx, "project_note", {"note": "test: pytest -x"})[1]
    assert "pytest -x" in agent.coding_prompt(proj, tmp_path)
    assert "chi dung" in tools.call(tools.ToolContext(workspace=tmp_path), "project_note", {"note": "x"})[0]


def test_is_simple():
    assert agent.is_simple("Chào bạn, hôm nay thế nào?", [], False, None)
    assert not agent.is_simple("Viết script đọc file csv", [], False, None)
    assert not agent.is_simple("Xin chào", ["a.pdf"], False, None)
    assert not agent.is_simple("Xin chào", [], True, None)
    assert not agent.is_simple("x" * 200, [], False, None)


def test_stop_interrupts_running_exec(tmp_path):
    cancel = threading.Event()
    ctx = _ctx(tmp_path)
    ctx.cancel = cancel
    threading.Timer(0.4, cancel.set).start()
    t0 = time.time()
    out, ok = tools.call(ctx, "exec", {"command": "sleep 30"})
    assert time.time() - t0 < 5 and "dung" in out


def test_exec_still_returns_output_and_exit_code(tmp_path):
    out, ok = tools.call(_ctx(tmp_path), "exec", {"command": "echo hi; echo err >&2; exit 3"})
    assert ok and "hi" in out and "err" in out and "[exit code 3]" in out


def test_stop_interrupts_model_stream(tmp_env, monkeypatch):
    from argus.services import sessions

    class Slow:
        def stream(self, messages, tools, **k):
            for i in range(100):
                time.sleep(0.1)
                yield {"type": "delta", "text": "x"}
            yield {"type": "final", "content": "x", "tool_calls": [], "usage": {"prompt": 0, "completion": 0}}

    monkeypatch.setattr(agent, "make_provider", lambda cfg: Slow())
    sid = sessions.create("t")
    cancel, events = threading.Event(), []
    threading.Timer(0.5, cancel.set).start()
    t0 = time.time()
    agent.run_turn(sid, "hi", None, lambda k, d: True, events.append, cancel)
    assert time.time() - t0 < 4
    assert not any(e["type"] == "error" for e in events)
