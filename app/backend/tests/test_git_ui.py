"""Thao tac git trong chat: nhanh, commit chon file, push co xac nhan, chan main."""
import subprocess

import pytest

from argus.services import sessions


@pytest.fixture
def setup(tmp_env, tmp_path):
    from fastapi.testclient import TestClient

    from argus.main import app
    remote = tmp_path / "remote.git"
    repo = tmp_path / "proj"
    repo.mkdir()
    g = lambda cwd, *a: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)  # noqa: E731
    g(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    g(repo, "init", "-q", "-b", "main"); g(repo, "config", "user.email", "t@t"); g(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("1\n"); g(repo, "add", "-A"); g(repo, "commit", "-qm", "init"); g(repo, "remote", "add", "origin", str(remote))
    sid = sessions.create("x", project=str(repo))
    return TestClient(app), sid, repo, g


def test_status_flags_protected(setup):
    c, sid, repo, g = setup
    st = c.get(f"/api/sessions/{sid}/git").json()
    assert st["branch"] == "main" and st["protected"] is True


def test_commit_blocked_on_main_then_branch_and_commit_selected_only(setup):
    c, sid, repo, g = setup
    (repo / "a.txt").write_text("2\n"); (repo / "mine.txt").write_text("x"); (repo / "other.txt").write_text("y")
    body = {"message": "feat: x", "files": ["a.txt", "mine.txt"]}
    assert c.post(f"/api/sessions/{sid}/git/commit", json=body).status_code == 409
    assert c.post(f"/api/sessions/{sid}/git/branch", json={"name": "feat/x"}).status_code == 200
    assert c.post(f"/api/sessions/{sid}/git/branch", json={"name": "-bad"}).status_code == 400
    r = c.post(f"/api/sessions/{sid}/git/commit", json=body)
    assert r.status_code == 200, r.text
    assert "other.txt" in g(repo, "status", "--porcelain").stdout and "mine.txt" not in g(repo, "status", "--porcelain").stdout
    assert c.post(f"/api/sessions/{sid}/git/commit", json={"message": " ", "files": ["a.txt"]}).status_code == 400
    assert c.post(f"/api/sessions/{sid}/git/commit", json={"message": "x", "files": ["../etc/passwd"]}).status_code == 400


def test_push_needs_confirm_and_blocks_main(setup):
    c, sid, repo, g = setup
    assert c.post(f"/api/sessions/{sid}/git/push", json={}).status_code == 400
    assert c.post(f"/api/sessions/{sid}/git/push", json={"confirm": True}).status_code == 409  # main
    c.post(f"/api/sessions/{sid}/git/branch", json={"name": "feat/y"})
    assert c.post(f"/api/sessions/{sid}/git/push", json={"confirm": True}).status_code == 200
    st = c.get(f"/api/sessions/{sid}/git").json()
    assert st["upstream"] == "origin/feat/y" and st["ahead"] == 0
