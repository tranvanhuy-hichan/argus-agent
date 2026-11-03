"""Embedding cho bộ nhớ ngữ nghĩa: backend hash (offline), ollama, openai-compatible."""
import hashlib
import math
import re
from dataclasses import dataclass

import httpx

from ..core.text import fold

OLLAMA_URL = "http://localhost:11434"  # có thể ghi đè (test)
BATCH = 32
TIMEOUT = 30.0
HASH_DIM = 512


class EmbeddingError(RuntimeError):
    pass


def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def hash_embed(text: str, dim: int = HASH_DIM) -> list[float]:
    """Feature hashing của từ đơn + n-gram ký tự (đã bỏ dấu). Chỉ là độ giống từ vựng mờ, KHÔNG phải ngữ nghĩa thật."""
    t = re.sub(r"[^\w]+", " ", fold(text)).strip()
    v = [0.0] * dim
    feats: list[tuple[str, float]] = []
    words = t.split()
    feats += [("w:" + w, 1.0) for w in words]
    feats += [("b:" + a + " " + b, 0.7) for a, b in zip(words, words[1:])]
    for w in words:
        p = f"#{w}#"
        for n in (3, 4):
            feats += [("c:" + p[i:i + n], 0.4) for i in range(max(0, len(p) - n + 1))]
    for f, wt in feats:
        h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
        v[h % dim] += wt if (h >> 40) & 1 else -wt
    return _norm(v)


@dataclass
class Embedder:
    kind: str  # hash | ollama | openai
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    dim: int = 0

    @property
    def model_id(self) -> str:
        return f"hash-{HASH_DIM}" if self.kind == "hash" else f"{self.kind}:{self.model}"

    def embed(self, texts: list[str]) -> tuple[list[list[float]], str]:
        """Trả (vectors, model_id). Gọi theo lô, lỗi rõ ràng bằng EmbeddingError."""
        if not texts:
            return [], self.model_id
        if self.kind == "hash":
            return [hash_embed(t) for t in texts], self.model_id
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH):
            chunk = [t[:8000] or " " for t in texts[i:i + BATCH]]
            out += self._remote(chunk)
        if out:
            self.dim = len(out[0])
        return out, self.model_id

    def _remote(self, chunk: list[str]) -> list[list[float]]:
        try:
            if self.kind == "ollama":
                r = httpx.post(self.base_url.rstrip("/") + "/api/embed", json={"model": self.model, "input": chunk}, timeout=TIMEOUT)
                key = "embeddings"
            else:
                h = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                r = httpx.post(self.base_url.rstrip("/") + "/embeddings", json={"model": self.model, "input": chunk}, headers=h, timeout=TIMEOUT)
                key = "data"
        except httpx.HTTPError as e:
            raise EmbeddingError(f"{self.kind}: không kết nối được ({type(e).__name__}: {e})") from e
        if r.status_code >= 400:
            raise EmbeddingError(f"{self.kind}: HTTP {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()[key]
            if key == "data":
                data = [d["embedding"] for d in sorted(data, key=lambda d: d.get("index", 0))]
        except (ValueError, KeyError, TypeError) as e:
            raise EmbeddingError(f"{self.kind}: phản hồi không hợp lệ") from e
        if len(data) != len(chunk):
            raise EmbeddingError(f"{self.kind}: số vector ({len(data)}) khác số văn bản ({len(chunk)})")
        return [_norm([float(x) for x in v]) for v in data]


def _ollama_url(cfg) -> str:
    p = cfg.providers.get(cfg.memory.provider or "")
    if p and "11434" in p.base_url:
        return p.base_url.rstrip("/").removesuffix("/v1")
    return OLLAMA_URL


def ollama_models(url: str) -> list[str]:
    r = httpx.get(url.rstrip("/") + "/api/tags", timeout=3)
    r.raise_for_status()
    return [m["name"] for m in r.json().get("models", [])]


def _pick_ollama(cfg, url: str) -> Embedder | None:
    """Chọn model Ollama: cfg.memory.model, hoặc model có 'embed' trong tên, hoặc model bất kỳ nếu allow_any."""
    if cfg.memory.model:
        return Embedder("ollama", cfg.memory.model, url)
    try:
        names = ollama_models(url)
    except (httpx.HTTPError, ValueError):
        return None
    emb = [n for n in names if "embed" in n.lower()]
    return Embedder("ollama", emb[0], url) if emb else None


def _openai(cfg) -> Embedder:
    from .providers import _key
    name = cfg.memory.provider
    p = cfg.providers.get(name or "")
    if not p:
        raise EmbeddingError(f"không có provider '{name}' để lấy embedding")
    return Embedder("openai", cfg.memory.model or "text-embedding-3-small", p.base_url, _key(p))


def get_embedder(cfg) -> Embedder | None:
    """Chọn backend theo cfg.memory; None nếu tắt."""
    mode = cfg.memory.embeddings
    if mode == "off":
        return None
    if mode == "hash":
        return Embedder("hash")
    if mode == "openai":
        return _openai(cfg)
    if mode == "ollama":
        url = _ollama_url(cfg)
        e = _pick_ollama(cfg, url)
        if e:
            return e
        try:
            names = ollama_models(url)
        except (httpx.HTTPError, ValueError) as ex:
            raise EmbeddingError(f"ollama không truy cập được: {ex}") from ex
        if not names:
            raise EmbeddingError("ollama chưa cài model nào")
        return Embedder("ollama", names[0], url)
    # auto
    pname = cfg.memory.provider
    if pname and pname in cfg.providers:
        p = cfg.providers[pname]
        if "11434" in p.base_url:
            e = _pick_ollama(cfg, _ollama_url(cfg))
            if e:
                return e
        elif p.type == "openai":
            return _openai(cfg)
    e = _pick_ollama(cfg, OLLAMA_URL)
    return e or Embedder("hash")


def embed(cfg, texts: list[str]) -> tuple[list[list[float]], str]:
    e = get_embedder(cfg)
    if e is None:
        raise EmbeddingError("embedding đang tắt")
    return e.embed(texts)


def status(cfg) -> dict:
    """Backend đang dùng, số chiều và khả năng kết nối."""
    out = {"mode": cfg.memory.embeddings, "backend": None, "model_id": None, "dim": 0, "reachable": False, "error": ""}
    try:
        e = get_embedder(cfg)
        if e is None:
            return out
        out.update(backend=e.kind, model_id=e.model_id)
        vecs, _ = e.embed(["kiểm tra"])
        out.update(dim=len(vecs[0]), reachable=True)
    except Exception as ex:  # noqa: BLE001
        out["error"] = str(ex)[:200]
    return out
