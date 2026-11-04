"""Nha cung cap CLI (vd. Claude Code da dang nhap): dung CLI gia, khong goi Claude that."""
import json
import os
import stat
import sys
from pathlib import Path

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


# ---------------- Antigravity (agy) va Codex: CLI gia theo dung dinh dang da quan sat / theo tai lieu
FAKE_AGY = '''import json, os, sys
argv = sys.argv[1:]
if argv and argv[0] == "models":
    print("Fetching available models...")
    print("gemini-3.8-flash-high\\tGemini 3.8 Flash (High)")
    print("claude-sonnet-4-6\\tClaude Sonnet 4.6 (Thinking)")
    sys.exit(0)
prompt = argv[argv.index("-p") + 1] if "-p" in argv else ""
open(os.environ["FAKE_LOG"], "a").write(json.dumps({"argv": argv, "stdin": sys.stdin.read(), "cwd": os.getcwd()}) + "\\n")
def step(t, **kw):
    print(json.dumps({"event": "step_update", "step_update": {"step_index": 1, "state": "ACTIVE", "step_type": "agent_response", "text_delta": t, **kw}}), flush=True)
if os.environ.get("FAKE_MODE") == "fail":
    print(json.dumps({"event": "result", "result": {"status": "FAILED", "error": "quota exceeded"}}))
    sys.exit(0)
if "[Tool result for" in prompt:
    step("Kết quả: "); step("xong")
else:
    step("Để xem. <tool"); step('_call>{"name": "list_dir", "arguments": {"path": "."}}</tool_call>')
print(json.dumps({"event": "result", "result": {"status": "SUCCESS", "response": "x", "usage": {"input_tokens": 100, "cache_read_tokens": 5, "output_tokens": 7}}}))
'''
FAKE_CODEX = '''import json, os, sys
argv = sys.argv[1:]
out = argv[argv.index("-o") + 1] if "-o" in argv else ""
open(os.environ["FAKE_LOG"], "a").write(json.dumps({"argv": argv, "has_key": "OPENAI_API_KEY" in os.environ, "cwd": os.getcwd()}) + "\\n")
def ev(**d): print(json.dumps(d), flush=True)
mode = os.environ.get("FAKE_MODE", "")
ev(type="thread.started", thread_id="t1"); ev(type="turn.started")
if mode == "fail":
    ev(type="turn.failed", error={"message": "usage limit reached"}); sys.exit(1)
if mode == "file":  # khong co su kien agent_message: chi ghi cau tra loi cuoi ra file -o
    open(out, "w").write("Đọc từ file."); ev(type="turn.completed", usage={"input_tokens": 3, "output_tokens": 1}); sys.exit(0)
ev(type="item.completed", item={"id": "i1", "type": "reasoning", "text": "nghi"})
ev(type="item.completed", item={"id": "i2", "type": "agent_message", "text": 'Để xem. <tool_call>{"name": "list_dir", "arguments": {"path": "."}}</tool_call>'})
ev(type="turn.completed", usage={"input_tokens": 50, "cached_input_tokens": 10, "output_tokens": 9})
'''


def kind(tmp_env, monkeypatch, name, source, **cfg_kw):
    exe = make_exe(tmp_env / name, source)
    log = tmp_env / "calls.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.delenv("FAKE_MODE", raising=False)
    cfg = cfgmod.ProviderCfg(type="cli", cli=name if name in ("agy", "codex") else "claude", command=str(exe), **cfg_kw)
    return cfg, lambda: [json.loads(x) for x in log.read_text().splitlines()]


def test_agy_prompt_goes_last_after_all_flags_and_tool_call_is_parsed(tmp_env, monkeypatch):
    cfg, calls = kind(tmp_env, monkeypatch, "agy", FAKE_AGY, model="gemini-3.8-flash-high")
    ev = run(cfg, [{"role": "user", "content": "xem thu muc"}], TOOLS)
    a = calls()[-1]["argv"]
    assert a[-2] == "-p" and "[User]\nxem thu muc" in a[-1]  # -p lay tham so ngay sau no lam loi nhac, nen phai dung cuoi cung
    assert a[a.index("--model") + 1] == "gemini-3.8-flash-high" and a[a.index("--output-format") + 1] == "stream-json"
    assert a.index("--model") < a.index("-p") and calls()[-1]["stdin"] == ""
    assert "".join(e["text"] for e in ev if e["type"] == "delta") == "Để xem. "
    final = ev[-1]
    assert final["tool_calls"][0]["name"] == "list_dir" and final["usage"] == {"prompt": 105, "completion": 7}


def test_agy_failure_and_prompt_size_guard(tmp_env, monkeypatch):
    cfg, _ = kind(tmp_env, monkeypatch, "agy", FAKE_AGY)
    monkeypatch.setenv("FAKE_MODE", "fail")
    with pytest.raises(providers.ProviderError, match="quota exceeded"):
        run(cfg, [{"role": "user", "content": "hi"}])
    monkeypatch.delenv("FAKE_MODE")
    with pytest.raises(providers.ProviderError, match="vượt giới hạn tham số"):
        run(cfg, [{"role": "user", "content": "x" * (cli_provider.MAX_ARG + 10)}])


def test_agy_lists_real_models(tmp_env, monkeypatch):
    cfg, _ = kind(tmp_env, monkeypatch, "agy", FAKE_AGY)
    assert providers.list_models(cfg) == ["gemini-3.8-flash-high", "claude-sonnet-4-6"]  # bo dong "Fetching…", lay cot id
    assert providers.list_models(cfgmod.ProviderCfg(type="cli", cli="claude")) == cli_provider.CLAUDE_MODELS


def test_codex_exec_json_events_sandbox_and_env(tmp_env, monkeypatch):
    cfg, calls = kind(tmp_env, monkeypatch, "codex", FAKE_CODEX, model="gpt-5-codex")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-khong-duoc-dung")
    ev = run(cfg, [{"role": "user", "content": "xem"}], TOOLS)
    c = calls()[-1]
    a = c["argv"]
    assert a[0] == "exec" and "--json" in a and a[a.index("--sandbox") + 1] == "read-only" and a[a.index("--model") + 1] == "gpt-5-codex"
    assert "[User]\nxem" in a[-1] and not c["has_key"] and c["cwd"].endswith("cli-run")
    assert "".join(e["text"] for e in ev if e["type"] == "delta") == "Để xem. "  # khoi tool_call bi an, suy luan (reasoning) khong lot vao cau tra loi
    assert ev[-1]["tool_calls"][0]["args"] == {"path": "."} and ev[-1]["usage"] == {"prompt": 50, "completion": 9}


def test_codex_reads_final_message_file_and_reports_failure(tmp_env, monkeypatch):
    cfg, calls = kind(tmp_env, monkeypatch, "codex", FAKE_CODEX)
    monkeypatch.setenv("FAKE_MODE", "file")
    final = run(cfg, [{"role": "user", "content": "hi"}])[-1]
    assert final["content"] == "Đọc từ file." and not Path(calls()[-1]["argv"][calls()[-1]["argv"].index("-o") + 1]).exists()
    monkeypatch.setenv("FAKE_MODE", "fail")
    with pytest.raises(providers.ProviderError, match="usage limit reached"):
        run(cfg, [{"role": "user", "content": "hi"}])
