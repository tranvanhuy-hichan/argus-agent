import pytest

from argus.services import api_run, tokens


def test_deny_blocks_everything():
    a = api_run.make_approver("deny", ["ls"], True)
    assert not a("exec", "ls") and not a("mcp", "demo__add {}") and not a("file_read", "/etc/passwd")


def test_allowlist_prefix_and_chaining():
    a = api_run.make_approver("allowlist", ["git status", "ls"], True)
    assert a("exec", "git status") and a("exec", "ls -la")
    assert not a("exec", "lsblk")  # khong phai tien to theo tu
    for evil in ("ls; rm -rf /", "ls && id", "ls | sh", "ls > x", "ls $(id)", "ls `id`", "ls\nid"):
        assert not a("exec", evil), evil


def test_allowlist_mcp_glob():
    a = api_run.make_approver("allowlist", ["mcp:demo__*"], True)
    assert a("mcp", 'demo__add {"a": 1}') and not a("mcp", "other__x {}")


def test_allow_needs_token_permission_and_never_files():
    with pytest.raises(api_run.PolicyError):
        api_run.make_approver("allow", [], False)
    a = api_run.make_approver("allow", [], True)
    assert a("exec", "anything") and not a("file_write", "/etc/x")


def test_invalid_policy():
    with pytest.raises(api_run.PolicyError):
        api_run.make_approver("yolo", [], True)


def test_token_lifecycle_only_hash_stored(tmp_env):
    info, token = tokens.create("ci", allow_exec=True)
    assert token.startswith("agt_") and tokens.verify(token) == {"id": info["id"], "name": "ci", "allow_exec": True}
    assert tokens.verify("agt_wrong") is None
    import sqlite3
    raw = sqlite3.connect(tmp_env / "agent.db").execute("select hash, prefix from api_tokens").fetchone()
    assert token not in "".join(raw) and len(raw[0]) == 64
    tokens.revoke(info["id"])
    assert tokens.verify(token) is None
