"""Gemini 3: thought_signature cua loi goi ham phai duoc luu va gui lai o luot sau, neu khong API tra HTTP 400."""
import json

from argus.core import config as cfgmod
from argus.services import providers

GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _provider(url: str) -> providers.OpenAICompat:
    return providers.OpenAICompat(cfgmod.ProviderCfg(type="openai", base_url=url, model="m", api_key="k"))


class _Resp:
    status_code = 200

    def __init__(self, chunks):
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_lines(self):
        for c in self.chunks:
            yield "data: " + json.dumps(c)
        yield "data: [DONE]"


def test_signature_is_captured_and_resent(monkeypatch):
    sig = {"google": {"thought_signature": "SIG123"}}
    chunks = [{"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "extra_content": sig, "function": {"name": "plan_set", "arguments": "{\"steps\": [\"a\"]}"}}]}}]}]
    monkeypatch.setattr(providers.httpx, "stream", lambda *a, **k: _Resp(chunks))
    final = [e for e in _provider(GEMINI).stream([{"role": "user", "content": "x"}], []) if e["type"] == "final"][0]
    call = final["tool_calls"][0]
    assert call["extra_content"] == sig and call["name"] == "plan_set"

    wire = _provider(GEMINI)._wire([{"role": "assistant", "content": "", "tool_calls": [call]}])
    assert wire[0]["tool_calls"][0]["extra_content"] == sig


def test_old_history_gets_skip_signature_only_on_first_call():
    calls = [{"id": "a", "name": "t", "args": {}}, {"id": "b", "name": "t", "args": {}}]
    w = _provider(GEMINI)._wire([{"role": "assistant", "content": "", "tool_calls": calls}])[0]["tool_calls"]
    assert w[0]["extra_content"]["google"]["thought_signature"] == providers.SKIP_SIGNATURE
    assert "extra_content" not in w[1]


def test_other_providers_never_get_extra_content():
    calls = [{"id": "a", "name": "t", "args": {}, "extra_content": {"google": {"thought_signature": "S"}}}]
    w = _provider("https://api.openai.com/v1")._wire([{"role": "assistant", "content": "", "tool_calls": calls}])[0]["tool_calls"]
    assert "extra_content" not in w[0]
