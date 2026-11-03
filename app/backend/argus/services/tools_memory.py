"""memory_search lai: FTS từ khóa + dòng MEMORY.md + vector, gộp bằng reciprocal-rank fusion."""
import logging

from ..core import config as cfgmod
from ..core.text import fold
from . import embeddings, sessions, vectorstore
from .tools import tool

log = logging.getLogger("argus.memory")
RRF_K = 60


def _vector_hits(query: str, k: int) -> list[dict]:
    try:
        cfg = cfgmod.load()
        e = embeddings.get_embedder(cfg)
        if e is None:
            return []
        vecs, model = e.embed([query])
        return [h for h in vectorstore.search(vecs[0], model, k) if h["score"] > 0.15]
    except Exception as ex:  # noqa: BLE001 - lùi về từ khóa
        log.info("vector search không khả dụng: %s", ex)
        return []


def _snip(t: str, n: int = 150) -> str:
    t = " ".join(t.split())
    return t[:n] + ("…" if len(t) > n else "")


@tool("memory_search", "Tìm lại thông tin trong các cuộc hội thoại cũ và bộ nhớ dài hạn (MEMORY.md), kết hợp tìm từ khóa và tìm theo ý nghĩa.",
      {"query": ("string", "từ khóa hoặc câu mô tả cần tìm"), "limit": ("integer", "số kết quả tối đa (mặc định 6)")}, required=["query"])
def memory_search(ctx, query, limit=6):
    limit = max(1, min(int(limit), 15))
    terms = fold(query).split()
    mem = ctx.workspace / "MEMORY.md"
    notes = [ln for ln in (mem.read_text().splitlines() if mem.exists() else []) if any(t in fold(ln) for t in terms)]
    fts = sessions.search(query, limit)
    vec = _vector_hits(query, limit * 2)
    items: dict[tuple, dict] = {}

    def put(key: tuple, rank: int, how: str, line: str) -> None:
        it = items.setdefault(key, {"score": 0.0, "how": [], "line": line})
        it["score"] += 1.0 / (RRF_K + rank)
        if how not in it["how"]:
            it["how"].append(how)

    for i, ln in enumerate(notes[:6]):
        put(("n", fold(ln.lstrip("- ").strip())), i, "từ khóa", f"[ghi nhớ] {ln}")
    for i, h in enumerate(fts):
        put(("m", h["session_id"], fold(h["snip"])[:40]), i, "từ khóa", f"[phiên {h['session_id']} · {h['title']}] ({h['role']}) {h['snip']}")
    titles: dict[str, str] = {}
    for i, h in enumerate(vec):
        if h["kind"] == "note":
            key = ("n", fold(h["text"]))
            if key in items:
                put(key, i, "ngữ nghĩa", "")
            else:
                put(key, i, "ngữ nghĩa", f"[ghi nhớ] - {h['text']}")
        else:
            sid = h["session_id"]
            if sid not in titles:
                s = sessions.get(sid)
                titles[sid] = s["title"] if s else "?"
            # trùng với kết quả FTS cùng phiên thì cộng điểm vào đó
            dup = next((k for k in items if k[0] == "m" and k[1] == sid and fold(h["text"]).startswith(k[2].strip("…")[:20])), None)
            put(dup or ("v", sid, fold(h["text"])[:40]), i, "ngữ nghĩa", f"[phiên {sid} · {titles[sid]}] ({h['ref']}) {_snip(h['text'])}")
    ranked = sorted(items.values(), key=lambda x: -x["score"])[:limit]
    out = [f"{it['line']}  <{' + '.join(it['how'])}>" for it in ranked]
    return "\n".join(out) or "không tìm thấy gì liên quan"
