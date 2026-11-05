"""Luot chay agent song doc lap voi ket noi: dong stream khong dung agent, attach() phat lai, stop() dung that."""
import threading
import time

from argus.services import chat_runner, tools


def _fake_turn(release: threading.Event):
    def run_turn(sid, text, provider, approver, emit, cancel, *a, **k):
        emit({"type": "delta", "text": "xin "})
        release.wait(5)
        if cancel.is_set():
            return
        emit({"type": "delta", "text": "chao"})
    return run_turn


def test_disconnect_keeps_running_and_attach_replays(tmp_env, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(chat_runner.agent, "run_turn", _fake_turn(release))
    gen = chat_runner.stream_chat(None, "hi", None, detach=True)
    sid = next(gen)["id"]
    assert next(gen) == {"type": "delta", "text": "xin "}
    gen.close()  # client roi trang
    assert chat_runner.active(sid)
    st = chat_runner.state(sid)
    assert st["active"] and st["cursor"] == 1
    release.set()
    evs = list(chat_runner.attach(sid, 1))  # noi lai tu cursor
    assert [e["type"] for e in evs] == ["delta", "done"]
    assert list(chat_runner.attach(sid, 0))[0]["text"] == "xin "  # phat lai day du khi xong


def test_non_detached_close_cancels(tmp_env, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(chat_runner.agent, "run_turn", _fake_turn(release))
    gen = chat_runner.stream_chat(None, "hi", None)
    sid = next(gen)["id"]
    next(gen)
    gen.close()
    release.set()
    time.sleep(0.2)
    assert chat_runner._runs[sid].cancel.is_set()


def test_stop_cancels_and_second_turn_rejected(tmp_env, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(chat_runner.agent, "run_turn", _fake_turn(release))
    gen = chat_runner.stream_chat(None, "hi", None, detach=True)
    sid = next(gen)["id"]
    next(gen)
    busy = list(chat_runner.stream_chat(sid, "again", None, detach=True))
    assert any(e["type"] == "error" for e in busy)
    assert chat_runner.stop(sid)
    release.set()
    assert [e["type"] for e in gen][-1] == "done"


def test_grep_and_glob(tmp_path, tmp_env):
    (tmp_path / "a.py").write_text("def foo():\n    return 1\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.py").write_text("def foo(): pass\n")
    ctx = tools.ToolContext(workspace=tmp_path, cwd=tmp_path, full_access=True)
    out, ok = tools.call(ctx, "grep", {"pattern": r"def \w+", "include": "*.py"})
    assert ok and "a.py:1" in out and "node_modules" not in out
    out, ok = tools.call(ctx, "glob", {"pattern": "**/*.py"})
    assert ok and out == "a.py"


def test_toggle_project_on_existing_session(tmp_env, tmp_path):
    from fastapi.testclient import TestClient

    from argus.main import app
    from argus.services import sessions
    c = TestClient(app)
    sid = sessions.create("x")
    r = c.post(f"/api/sessions/{sid}/project", json={"path": str(tmp_path)})
    assert r.status_code == 200 and sessions.get(sid)["project"] == str(tmp_path.resolve())
    assert c.post(f"/api/sessions/{sid}/project", json={"path": None}).json() == {"project": ""}
    assert sessions.get(sid)["project"] == ""
    assert c.post(f"/api/sessions/{sid}/project", json={"path": str(tmp_path / "nope")}).status_code == 400
