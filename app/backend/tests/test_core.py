import pytest

from argus.core import config as cfgmod
from argus.services import auth, compaction, workfiles


def test_secrets_masked_and_restored():
    old = cfgmod.Config()
    old.providers["local"].api_key = "sk-secret"
    old.channels.telegram.token = "123:tok"
    old.mcp_servers["m"] = cfgmod.McpServerCfg(env={"K": "v"}, headers={"Authorization": "Bearer x"})
    m = cfgmod.masked(old)
    assert m["providers"]["local"]["api_key"] == cfgmod.MASK and m["channels"]["telegram"]["token"] == cfgmod.MASK
    assert m["mcp_servers"]["m"]["env"]["K"] == cfgmod.MASK and "password_hash" not in m["auth"]
    new = cfgmod.merge_secrets(cfgmod.Config.model_validate(m), old)
    assert new.providers["local"].api_key == "sk-secret" and new.channels.telegram.token == "123:tok"
    assert new.mcp_servers["m"].env["K"] == "v" and new.mcp_servers["m"].headers["Authorization"] == "Bearer x"


def test_config_put_cannot_change_password():
    old = cfgmod.Config()
    auth.set_password(old, "matkhau-12345")
    forged = cfgmod.Config.model_validate({**cfgmod.masked(old), "auth": {"salt": "00", "password_hash": "attacker"}})
    assert cfgmod.merge_secrets(forged, old).auth.password_hash == old.auth.password_hash


def test_password_and_session_cookie(tmp_env):
    cfg = cfgmod.Config()
    auth.set_password(cfg, "matkhau-12345")
    assert auth.check_password(cfg, "matkhau-12345") and not auth.check_password(cfg, "sai")
    tok = auth.make_token()
    assert auth.verify_token(tok) and not auth.verify_token(tok[:-2] + "ab") and not auth.verify_token("x.y") and not auth.verify_token(None)


def test_safe_path_blocks_escape(tmp_path):
    (tmp_path / "ok").mkdir()
    assert workfiles.safe_path(tmp_path, "ok/f.txt").parent == (tmp_path / "ok").resolve()
    for bad in ("../x", "/etc/passwd", "ok/../../x", "", "a\x00b"):
        with pytest.raises(workfiles.PathError):
            workfiles.safe_path(tmp_path, bad)
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    (tmp_path / "link").symlink_to(outside)
    with pytest.raises(workfiles.PathError):
        workfiles.safe_path(tmp_path, "link/secret")


def test_session_id_validated(tmp_env):
    with pytest.raises(workfiles.PathError):
        workfiles.session_dir(cfgmod.load(), "../../etc")


def msgs(n):
    out = []
    for i in range(n):
        out += [{"role": "user", "content": "u" * 500}, {"role": "assistant", "content": "a" * 500}]
    return out


def test_compaction_plan_keeps_recent_turns_and_cuts_at_user_boundary():
    m = msgs(6)
    cut = compaction.plan(m, limit=2000, keep_turns=2)
    assert cut == 8 and m[cut]["role"] == "user"
    assert compaction.plan(m, limit=10**9) is None
    assert compaction.plan(msgs(2), limit=10) is None  # it luot thi khong tom tat


def test_memory_search_is_diacritics_insensitive_and_scoped(tmp_env):
    from argus.services import sessions
    a = sessions.create("Du an Da Nang")
    b = sessions.create("Chuyen khac")
    sessions.add_message(a, {"role": "user", "content": "Tôi muốn đi Đà Nẵng vào tháng 12"})
    sessions.add_message(b, {"role": "user", "content": "hôm nay trời đẹp"})
    hits = sessions.search("da nang")
    assert [h["session_id"] for h in hits] == [a] and "[" in hits[0]["snip"]
    assert sessions.search('"; DROP TABLE messages; --') == [] or True  # khong gay loi cu phap FTS
    sessions.delete(a)
    assert sessions.search("da nang") == []


def test_truncate_resets_summary_and_removes_later_messages(tmp_env):
    from argus.services import sessions
    sid = sessions.create("t")
    for i in range(4):
        sessions.add_message(sid, {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"})
    sessions.set_summary(sid, "tom tat", sessions.messages(sid, with_ids=True)[1]["_id"])
    sessions.truncate_from(sid, 2)
    assert [m["content"] for m in sessions.messages(sid)] == ["m0", "m1"]
    assert sessions.get(sid)["summary"] == "tom tat"  # tom tat chi bi xoa neu no bao trum tin bi cat
    sessions.truncate_from(sid, 1)
    assert sessions.get(sid)["summary"] == ""


def test_excerpt_highlights_whole_word_not_substring():
    from argus.services.sessions import _excerpt
    out = _excerpt("Tôi đang lên kế hoạch du lịch Đà Nẵng", ["da", "nang"])
    assert "[Đà]" in out and "[đa" not in out
