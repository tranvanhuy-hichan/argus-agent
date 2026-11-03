import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from argus.core import config as cfgmod
from argus.services import embeddings, memory, memory_index, providers, sessions, tools, tools_memory, vectorstore


def _cfg(mode="hash", **kw):
    cfg = cfgmod.load()
    cfg.memory.embeddings = mode
    for k, v in kw.items():
        setattr(cfg.memory, k, v)
    cfgmod.save(cfg)
    return cfg


def _ctx(cfg):
    return tools.ToolContext(workspace=cfg.workspace_path())


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_hash_embedder(tmp_env):
    a = embeddings.hash_embed("Kế hoạch du lịch Đà Nẵng")
    assert a == embeddings.hash_embed("Kế hoạch du lịch Đà Nẵng")
    assert len(a) == 512
    assert _cos(a, embeddings.hash_embed("ke hoach du lich da nang")) > 0.999
    q = embeddings.hash_embed("tôi muốn đi du lịch Đà Nẵng")
    assert _cos(q, a) > _cos(q, embeddings.hash_embed("công thức nấu phở bò với hành tây"))


def test_vectorstore(tmp_env):
    vectorstore.add([{"kind": "message", "session_id": "s1", "text": "a", "model": "m1", "vec": [1.0, 0.0]},
                     {"kind": "note", "session_id": None, "text": "b", "model": "m1", "vec": [0.0, 1.0]},
                     {"kind": "message", "session_id": "s2", "text": "c", "model": "m2", "vec": [1.0, 0.0]}])
    r = vectorstore.search([1.0, 0.1], "m1", 5)
    assert [x["text"] for x in r] == ["a", "b"]
    assert vectorstore.search([1.0, 0.0], "m1", 5, kinds=["note"])[0]["text"] == "b"
    assert vectorstore.search([1.0, 0.0], "m3", 5) == []
    vectorstore.delete_session("s1")
    assert vectorstore.stats()["total"] == 2
    vectorstore.clear("m2")
    assert vectorstore.stats()["by_model"] == {"m1": 1}


def test_chunking():
    assert memory_index.chunk_text("  ") == []
    assert memory_index.chunk_text("ngắn") == ["ngắn"]
    text = "\n\n".join(f"Đoạn số {i}. " + "chữ " * 60 for i in range(8))
    ch = memory_index.chunk_text(text)
    assert len(ch) > 1 and all(len(c) <= 800 for c in ch)
    assert len(memory_index.chunk_text("x" * 3000)) >= 4


def test_hook_indexes_and_hybrid_search(tmp_env):
    cfg = _cfg("hash")
    s1 = sessions.create("Du lịch")
    s2 = sessions.create("Nấu ăn")
    sessions.add_message(s1, {"role": "user", "content": "kế hoạch du lịch Đà Nẵng vào mùa hè"})
    sessions.add_message(s2, {"role": "user", "content": "công thức nấu phở bò với hành tây"})
    sessions.add_message(s2, {"role": "tool", "content": "bỏ qua tool message dài dài"})
    assert memory_index.flush(10)
    assert vectorstore.stats()["total"] == 2
    (cfg.workspace_path() / "MEMORY.md").write_text("# Memory\n- Thích đi biển ở Đà Nẵng\n")
    out = tools.TOOLS["memory_search"].fn(_ctx(cfg), "tôi muốn đi du lịch Đà Nẵng")
    lines = out.splitlines()
    assert any(l.startswith("[phiên " + s1) for l in lines)
    assert any(l.startswith("[ghi nhớ]") for l in lines)
    assert all("<" in l and ">" in l for l in lines)
    first_session = next(l for l in lines if l.startswith("[phiên"))
    assert s1 in first_session
    sessions.delete(s1)
    assert all(h["session_id"] != s1 for h in vectorstore.search(embeddings.hash_embed("du lịch"), "hash-512", 10))


def test_keyword_fallback_when_backend_raises(tmp_env, monkeypatch):
    cfg = _cfg("hash")
    sid = sessions.create("t")
    sessions.add_message(sid, {"role": "user", "content": "mật khẩu wifi nhà là banana"})
    memory_index.flush(10)

    def boom(*a, **k):
        raise embeddings.EmbeddingError("hỏng")
    monkeypatch.setattr(embeddings.Embedder, "embed", boom)
    out = tools.TOOLS["memory_search"].fn(_ctx(cfg), "banana")
    assert out.startswith(f"[phiên {sid} · t] (user)") and "từ khóa" in out
    assert tools.TOOLS["memory_search"].fn(_ctx(cfg), "zzzzqq") == "không tìm thấy gì liên quan"


def test_enqueue_nonblocking_and_failures(tmp_env, monkeypatch):
    _cfg("hash")

    def boom(*a, **k):
        raise RuntimeError("x")
    real_add = vectorstore.add
    monkeypatch.setattr(vectorstore, "add", boom)
    memory_index.enqueue_message("s", "user", "một tin nhắn đủ dài để lập chỉ mục", 1.0)
    assert memory_index.flush(10)
    memory_index.enqueue_message("s", "tool", "bị bỏ qua", 1.0)
    memory_index.enqueue_message("s", "user", "ngắn", 1.0)
    assert memory_index.flush(5)
    monkeypatch.setattr(vectorstore, "add", real_add)  # undo() would also drop the tmp_env isolation
    _cfg("off")
    memory_index.enqueue_message("s", "user", "tắt embedding thì không lưu gì cả", 1.0)
    memory_index.flush(5)
    assert vectorstore.stats()["total"] == 0


class _Fake(BaseHTTPRequestHandler):
    calls: list = []
    models = ["qwen2.5:3b", "nomic-embed-text:latest"]

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._send({"models": [{"name": m} for m in self.models]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Fake.calls.append((self.path, self.headers.get("Authorization"), body))
        vecs = [[float(len(t)), 1.0, 2.0] for t in body["input"]]
        if self.path.endswith("/api/embed"):
            self._send({"embeddings": vecs})
        elif self.path.endswith("/embeddings"):
            self._send({"data": [{"index": i, "embedding": v} for i, v in reversed(list(enumerate(vecs)))]})
        else:
            self._send({}, 404)


@pytest.fixture
def fake_server():
    _Fake.calls = []
    srv = HTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_openai_backend(tmp_env, fake_server):
    cfg = _cfg("openai", provider="emb", model="gemini-embedding-001")
    cfg.providers["emb"] = cfgmod.ProviderCfg(base_url=fake_server + "/v1beta/openai/", api_key="K1")
    e = embeddings.get_embedder(cfg)
    vecs, mid = e.embed(["a", "bbb", "cc"] * 20)  # 60 -> 2 lô
    assert mid == "openai:gemini-embedding-001" and len(vecs) == 60 and len(_Fake.calls) == 2
    assert _Fake.calls[0][0] == "/v1beta/openai/embeddings" and _Fake.calls[0][1] == "Bearer K1"
    assert vecs[1][0] > vecs[0][0]  # đúng thứ tự dù server trả đảo
    assert abs(sum(x * x for x in vecs[0]) - 1) < 1e-6
    assert embeddings.status(cfg)["reachable"]
    with pytest.raises(embeddings.EmbeddingError):
        embeddings.Embedder("openai", "m", "http://127.0.0.1:1").embed(["x"])


def test_ollama_backend_and_auto(tmp_env, fake_server, monkeypatch):
    monkeypatch.setattr(embeddings, "OLLAMA_URL", fake_server)
    cfg = _cfg("ollama")
    e = embeddings.get_embedder(cfg)
    assert e.model_id == "ollama:nomic-embed-text:latest"
    vecs, _ = e.embed(["xin chào"])
    assert _Fake.calls[-1][0] == "/api/embed" and len(vecs[0]) == 3
    assert embeddings.get_embedder(_cfg("auto")).kind == "ollama"
    monkeypatch.setattr(_Fake, "models", ["qwen2.5:3b"])
    assert embeddings.get_embedder(_cfg("auto")).kind == "hash"
    assert embeddings.get_embedder(_cfg("ollama")).model == "qwen2.5:3b"
    monkeypatch.setattr(embeddings, "OLLAMA_URL", "http://127.0.0.1:1")
    assert embeddings.get_embedder(_cfg("auto")).kind == "hash"
    assert embeddings.get_embedder(_cfg("off")) is None


class _FakeProv:
    answer = ""

    def __init__(self, cfg):
        pass

    def stream(self, messages, tools):
        yield {"type": "delta", "text": self.answer[:5]}
        yield {"type": "delta", "text": self.answer[5:]}
        yield {"type": "final", "content": self.answer, "tool_calls": [], "usage": {}}


OLD = "# Memory\n- Tên: Huy\n- Tên: Huy\n- Ở Hà Nội\n- Thích cà phê\n- Dùng Python 3.9\n- Dùng Python 3.11\n"


def test_curation(tmp_env, monkeypatch):
    cfg = _cfg("off")
    f = cfg.workspace_path() / "MEMORY.md"
    f.write_text(OLD)
    monkeypatch.setattr(providers, "make_provider", lambda c: _FakeProv(c))
    good = "# Memory\n- Tên: Huy\n- Ở Hà Nội\n- Thích cà phê\n- Dùng Python 3.11\n"
    _FakeProv.answer = good
    p = memory.propose_curation(cfg)
    assert p["ok"] and "- Dùng Python 3.9" in p["removed"] and p["added"] == []
    assert f.read_text() == OLD  # chưa ghi
    for bad in ("# Memory\n- Tên: Huy\n", "```\n# Memory\n- a\n```", "Đây là bản mới\n- a\n"):
        _FakeProv.answer = bad
        assert not memory.propose_curation(cfg)["ok"]
    with pytest.raises(ValueError):
        memory.apply_curation(cfg, "linh tinh")
    r = memory.apply_curation(cfg, good)
    assert f.read_text() == good and Path(r["backup"]).read_text() == OLD
    assert Path(r["backup"]).name.startswith("MEMORY.md.bak-")
