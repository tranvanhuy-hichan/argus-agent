"""Nha cung cap CLI (vd. Claude Code da dang nhap): dung CLI gia, khong goi Claude that."""
import json
import os
import stat
import sys

import pytest

from argus.core import config as cfgmod
from argus.services import agent as agent_mod
from argus.services import cli_provider, providers, sessions

FAKE = '''import json, os, sys
prompt = sys.stdin.read()
open(os.environ["FAKE_LOG"], "a").write(json.dumps({{"argv": sys.argv[1:], "prompt": prompt, "has_key": "ANTHROPIC_API_KEY" in os.environ, "cwd": os.getcwd()}}) + "\\n")
def ev(t):
    print(json.dumps({{"type": "stream_event", "event": {{"type": "content_block_delta", "index": 0, "delta": {{"type": "text_delta", "text": t}}}}}}), flush=True)
if os.environ.get("FAKE_MODE") == "login":
    print(json.dumps({{"type": "result", "is_error": True, "result": "Not logged in · Please run /login"}}))
    sys.exit(1)
if "[Tool result for" in prompt:
    ev("Kết quả: "); ev("xong")
else:
    ev("Để mình xem. <tool"); ev('_call>{{"name": "list_dir", "arguments": {{"path": "."}}}}</tool_call>')
print(json.dumps({{"type": "result", "is_error": False, "result": "x", "usage": {{"input_tokens": 10, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 1, "output_tokens": 7}}}}))
'''
TOOLS = [{"name": "list_dir", "description": "Liet ke file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}]


def make_exe(path, source):
    """Script Python chay qua lop boc sh co dau nhay (duong dan Python co the chua dau cach, shebang thi khong)."""
    py = path.with_suffix(".py")
    py.write_text(source)
    path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py}" "$@"\n')
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


@pytest.fixture
def fake(tmp_env, monkeypatch):
    exe = make_exe(tmp_env / "fake-claude", FAKE.format())
    log = tmp_env / "calls.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.delenv("FAKE_MODE", raising=False)
    cfg = cfgmod.ProviderCfg(type="cli", cli="claude", command=str(exe), model="sonnet")
    return cfg, lambda: [json.loads(x) for x in log.read_text().splitlines()]


def run(cfg, messages, tools=()):
    return list(providers.make_provider(cfg).stream(messages, list(tools)))


def test_tool_call_is_parsed_and_hidden_from_text(fake):
    cfg, _ = fake
    ev = run(cfg, [{"role": "user", "content": "xem thu muc"}], TOOLS)
    shown = "".join(e["text"] for e in ev if e["type"] == "delta")
    final = ev[-1]
    assert shown == "Để mình xem. " and "<tool" not in shown  # ke ca khi the bi cat doi giua hai manh
    assert final["tool_calls"][0]["name"] == "list_dir" and final["tool_calls"][0]["args"] == {"path": "."}
    assert final["content"] == "Để mình xem." and final["usage"] == {"prompt": 16, "completion": 7}


def test_plain_answer_after_tool_result(fake):
    cfg, calls = fake
    msgs = [{"role": "user", "content": "xem"}, {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "list_dir", "args": {"path": "."}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "a.txt"}]
    final = run(cfg, msgs, TOOLS)[-1]
    assert final["content"] == "Kết quả: xong" and final["tool_calls"] == []
    prompt = calls()[-1]["prompt"]
    assert "list_dir: Liet ke file" in prompt and "[Tool result for c1]\na.txt" in prompt and '<tool_call>{"name": "list_dir"' in prompt


def test_cli_flags_neutral_dir_and_no_api_key(fake, monkeypatch):
    cfg, calls = fake
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-khong-duoc-dung")
    run(cfg, [{"role": "user", "content": "hi"}])
    c = calls()[-1]
    assert not c["has_key"]  # phai dung tai khoan dang nhap, khong phai khoa API trong moi truong
    assert c["cwd"].endswith("cli-run")
    a = c["argv"]
    assert "-p" in a and a[a.index("--tools") + 1] == "" and "--no-session-persistence" in a and a[a.index("--model") + 1] == "sonnet"


def test_login_error_is_reported(fake, monkeypatch):
    cfg, _ = fake
    monkeypatch.setenv("FAKE_MODE", "login")
    with pytest.raises(providers.ProviderError, match="Not logged in"):
        run(cfg, [{"role": "user", "content": "hi"}])


def test_missing_cli(tmp_env):
    cfg = cfgmod.ProviderCfg(type="cli", command="khong-co-lenh-nay-xyz")
    with pytest.raises(providers.ProviderError, match="không tìm thấy lệnh"):
        run(cfg, [{"role": "user", "content": "hi"}])
    assert cli_provider.find(cfg) is None


def test_custom_command_reads_stdin_prints_stdout(tmp_env):
    exe = make_exe(tmp_env / "echo-cli", "import sys\nsys.stdin.read()\nprint('xin chao')\n")
    cfg = cfgmod.ProviderCfg(type="cli", cli="custom", command=str(exe))
    final = run(cfg, [{"role": "user", "content": "hi"}])[-1]
    assert final["content"] == "xin chao"


def test_filter_holds_back_partial_tag():
    f = cli_provider._Filter()
    assert f.feed("chao <tool_") == "chao " and f.feed('call>{"x":1}</tool_call>') == "" and f.flush() == ""
    g = cli_provider._Filter()
    assert g.feed("a <b") + g.feed(" c") + g.flush() == "a <b c"  # dau < khong phai the thi van hien ra


def test_agent_runs_tools_through_cli_provider(fake):
    cfg, _ = fake
    full = cfgmod.load()
    full.providers = {"claude-cli": cfg}
    full.default_provider = "claude-cli"
    cfgmod.save(full)
    events = []
    sid = sessions.create("x")
    agent_mod.run_turn(sid, "liet ke file", None, lambda k, d: True, events.append)
    kinds = [e["type"] for e in events]
    assert "tool" in kinds and "tool_result" in kinds
    assert next(e for e in events if e["type"] == "tool")["name"] == "list_dir"
    assert [e for e in events if e["type"] == "assistant"][-1]["content"] == "Kết quả: xong"
