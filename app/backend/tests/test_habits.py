"""Gợi ý kỹ năng: nhận ra việc lặp lại, soạn bản nháp, duyệt thành skill/automation."""
import json

import pytest

from argus.core import config as cfgmod
from argus.services import habits, notifications, scheduler, sessions, skills

REQ = "Tóm tắt tin tức công nghệ hôm nay giúp tôi"


@pytest.fixture(autouse=True)
def sync(tmp_env, monkeypatch):
    monkeypatch.setattr(habits, "_spawn", lambda fn, *a: fn(*a))


class Fake:
    def __init__(self, out):
        self.out = out

    def stream(self, msgs, tools):
        yield {"type": "delta", "text": self.out}


def _send(text=REQ):
    return habits.observe(sessions.create(text), text)


def test_tokens_fold_accents_and_drop_stopwords():
    assert "tin" in habits.tokens("Tóm tắt TIN tức") and "voi" not in habits.tokens("với bạn")
    assert habits.similar(habits.tokens(REQ), habits.tokens("tóm tắt tin tức công nghệ hôm nay nhé"))
    assert not habits.similar(habits.tokens(REQ), habits.tokens("kiểm tra dung lượng ổ đĩa của máy"))


def test_no_suggestion_before_threshold_and_repeats_in_one_session_dont_count():
    sid = sessions.create("x")
    for _ in range(4):
        habits.observe(sid, REQ)
    assert habits.list_pending() == []
    assert _send() is None  # mới 2 phiên


def test_third_session_creates_draft_and_notification(monkeypatch):
    monkeypatch.setattr(habits, "make_provider", lambda cfg: Fake("lỗi"))
    _send(); _send()
    assert _send()
    (s,) = habits.list_pending()
    assert s["count"] == 3 and s["draft"]["kind"] == "skill" and s["draft"]["name"]  # model trả rác -> bản nháp dự phòng
    assert any(n["source"] == "habit" for n in notifications.list_all())
    assert _send() is None  # không gợi ý lại cùng việc


def test_model_draft_automation_and_accept(monkeypatch):
    out = json.dumps({"kind": "automation", "name": "tin-cong-nghe", "title": "Tin công nghệ", "description": "d",
                      "prompt": "Tóm tắt tin công nghệ", "schedule": "0 8 * * *"})
    monkeypatch.setattr(habits, "make_provider", lambda cfg: Fake("```json\n" + out + "\n```"))
    for _ in range(3):
        _send()
    (s,) = habits.list_pending()
    assert s["draft"]["kind"] == "automation"
    assert habits.accept(s["id"], s["draft"])["kind"] == "automation"
    assert scheduler.list_jobs()[0]["schedule"] == "0 8 * * *"
    assert habits.list_pending() == []
    with pytest.raises(ValueError):
        habits.accept(s["id"], s["draft"])


def test_accept_skill_and_dismiss(monkeypatch):
    monkeypatch.setattr(habits, "make_provider", lambda cfg: Fake(""))
    for _ in range(3):
        _send()
    (s,) = habits.list_pending()
    d = s["draft"] | {"name": "tom-tat-tin", "body": "Bước 1"}
    habits.accept(s["id"], d)
    assert "tom-tat-tin" in skills.discover(cfgmod.load())
    other = "Kiểm tra dung lượng ổ đĩa và báo cáo thư mục lớn nhất"
    for _ in range(3):
        _send(other)
    (s2,) = habits.list_pending()
    assert habits.dismiss(s2["id"]) and habits.list_pending() == []
    assert _send(other) is None  # đã bỏ qua thì không nhắc lại


def test_parse_draft_rejects_bad_cron_and_names():
    assert habits.parse_draft('{"kind":"automation","name":"a","prompt":"p","schedule":"nope"}') is None
    assert habits.parse_draft('{"kind":"skill","name":"Tên Hay","body":"b"}')["name"] == "ten-hay"
    assert habits.parse_draft("không phải json") is None


def test_disabled_by_config():
    cfg = cfgmod.load(); cfg.agent.suggest_habits = False; cfgmod.save(cfg)
    for _ in range(3):
        _send()
    assert habits.list_pending() == []


def test_api_is_mounted_and_accept_dismiss(monkeypatch):
    from fastapi.testclient import TestClient

    from argus.main import app
    c = TestClient(app)
    monkeypatch.setattr(habits, "make_provider", lambda cfg: Fake(""))
    for _ in range(3):
        _send()
    (s,) = c.get("/api/habits").json()
    assert c.post(f"/api/habits/{s['id']}/accept", json={**s["draft"], "name": "tom-tat"}).json()["kind"] == "skill"
    assert c.post(f"/api/habits/{s['id']}/dismiss").status_code == 404  # đã duyệt thì không còn
    assert c.get("/api/habits").json() == []
