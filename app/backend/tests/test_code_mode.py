"""Chế độ Code: mở dự án bất kỳ, file/git trong dự án, quyền truy cập và prompt lập trình."""
import subprocess
from pathlib import Path

import pytest

from argus.core import config as cfgmod
from argus.services import agent, sessions, tools, workfiles


@pytest.fixture
def client(tmp_env):
    from fastapi.testclient import TestClient

    from argus.main import app
    return TestClient(app)


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "myapp"
    (p / "src").mkdir(parents=True)
    (p / "node_modules" / "x").mkdir(parents=True)
    (p / "node_modules" / "x" / "big.js").write_text("x")
    (p / "src" / "app.py").write_text("print('v1')\n")
    (p / "AGENTS.md").write_text("Chạy pytest trước khi báo xong.")
    run = lambda *a: subprocess.run(["git", *a], cwd=p, check=True, capture_output=True)  # noqa: E731
    run("init", "-q"); run("config", "user.email", "t@t"); run("config", "user.name", "t")
    run("add", "-A"); run("commit", "-qm", "init")
    return p


def _open(client, path):
    r = client.post("/api/code/open", json={"path": str(path)})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_open_any_directory_and_browse(client, repo):
    sid = _open(client, repo)
    s = sessions.get(sid)
    assert s["project"] == str(repo) and s["source"] == "code"
    assert client.post("/api/code/open", json={"path": str(repo / "nope")}).status_code == 400
    b = client.get("/api/code/browse", params={"path": str(repo.parent)}).json()
    assert any(d["name"] == "myapp" and d["git"] for d in b["dirs"])
    assert client.get("/api/code/projects").json()[0]["path"] == str(repo)


def test_files_use_project_and_skip_heavy_dirs(client, repo):
    sid = _open(client, repo)
    paths = [f["path"] for f in client.get(f"/api/sessions/{sid}/files").json()]
    assert "src/app.py" in paths and not any("node_modules" in p for p in paths)
    assert client.get(f"/api/sessions/{sid}/file", params={"path": "src/app.py"}).json()["content"].startswith("print")
    assert client.get(f"/api/sessions/{sid}/file", params={"path": "../outside"}).status_code == 400


def test_git_status_diff_and_revert(client, repo):
    sid = _open(client, repo)
    assert client.get(f"/api/sessions/{sid}/git").json()["files"] == []
    (repo / "src" / "app.py").write_text("print('v2')\n")
    (repo / "src" / "new.py").write_text("a = 1\n")
    g = client.get(f"/api/sessions/{sid}/git").json()
    assert g["repo"] and {(f["path"], f["status"]) for f in g["files"]} == {("src/app.py", "modified"), ("src/new.py", "new")}
    assert "+print('v2')" in client.get(f"/api/sessions/{sid}/git/diff", params={"path": "src/app.py"}).json()["diff"]
    assert "+a = 1" in client.get(f"/api/sessions/{sid}/git/diff", params={"path": "src/new.py"}).json()["diff"]
    assert client.post(f"/api/sessions/{sid}/git/revert", json={"path": "src/app.py"}).status_code == 200
    assert client.post(f"/api/sessions/{sid}/git/revert", json={"path": "src/new.py"}).status_code == 200
    assert (repo / "src" / "app.py").read_text() == "print('v1')\n" and not (repo / "src" / "new.py").exists()
    assert client.post(f"/api/sessions/{sid}/git/revert", json={"path": "../x"}).status_code == 400


def test_non_repo_and_plain_session(client, tmp_path):
    plain = tmp_path / "plain"; plain.mkdir()
    sid = _open(client, plain)
    assert client.get(f"/api/sessions/{sid}/git").json() == {"repo": False, "branch": "", "files": []}
    chat = sessions.create("x")
    assert client.get(f"/api/sessions/{chat}/git").status_code == 400


def test_project_files_need_no_approval_but_outside_does(tmp_env, repo, tmp_path):
    asked = []
    ctx = tools.ToolContext(workspace=cfgmod.load().workspace_path(), approver=lambda k, d: asked.append(d) or False)
    ctx.project = repo
    assert tools._resolve(ctx, str(repo / "src" / "app.py"), "write") == (repo / "src" / "app.py").resolve() and not asked
    other = tmp_path / "other.txt"
    with pytest.raises(PermissionError):
        tools._resolve(ctx, str(other), "read")
    assert asked == [str(other.resolve())]


def test_coding_prompt_includes_project_doc_and_workdir(tmp_env, repo):
    p = agent.coding_prompt(repo)
    assert str(repo) in p and "Chạy pytest" in p and "Thay đổi" in p
    assert workfiles.workdir_for(cfgmod.load(), sessions.create("x", project=str(repo))) == repo
