"""Giam token: rut gon ket qua cong cu cu va an cong cu khong dung duoc."""
import json

from argus.core import config as cfgmod
from argus.services import agent as agent_mod
from argus.services import tools


def _msgs():
    big = "x" * 5000
    return [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "lam di"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "a", "name": "browser_open", "args": {}}, {"id": "b", "name": "read", "args": {}}]},
        {"role": "tool", "tool_call_id": "a", "content": big},
        {"role": "tool", "tool_call_id": "b", "content": big},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c", "name": "browser_snapshot", "args": {}}]},
        {"role": "tool", "tool_call_id": "c", "content": big},
    ]


def test_old_tool_results_are_shrunk_latest_kept():
    out = agent_mod.shrink_stale(_msgs())
    a, b, c = out[3]["content"], out[4]["content"], out[6]["content"]
    assert len(c) == 5000  # ket qua cua luot goi gan nhat giu nguyen
    assert len(a) < 500 and "đã rút gọn" in a  # anh chup trang cu: rat ngan
    assert 800 < len(b) < 1000 and "đã rút gọn" in b  # ket qua cu khac: ngan vua phai
    assert out[3]["tool_call_id"] == "a" and len(_msgs()[3]["content"]) == 5000  # khong sua ban goc


def test_short_old_results_untouched():
    m = _msgs()
    m[3]["content"] = "ngan"
    assert agent_mod.shrink_stale(m)[3]["content"] == "ngan"


def test_disabled_features_hide_their_tool_schemas(tmp_env, monkeypatch):
    seen = {}

    class Fake:
        def __init__(self, cfg):
            pass

        def stream(self, messages, schemas, effort=None):
            seen["names"] = {s["name"] for s in schemas}
            yield {"type": "final", "content": "ok", "tool_calls": [], "usage": {"prompt": 1, "completion": 1}}

    monkeypatch.setattr(agent_mod, "make_provider", Fake)
    from argus.services import sessions

    sid = sessions.create("x")
    agent_mod.run_turn(sid, "hi", None, lambda k, d: True, lambda e: None)
    assert not any(n.startswith("computer_") for n in seen["names"])  # computer.enabled mac dinh tat
    assert any(n.startswith("browser_") for n in seen["names"])
    cfg = cfgmod.load()
    cfg.browser.enabled = False
    cfgmod.save(cfg)
    agent_mod.run_turn(sid, "hi", None, lambda k, d: True, lambda e: None)
    assert not any(n.startswith("browser_") for n in seen["names"])
