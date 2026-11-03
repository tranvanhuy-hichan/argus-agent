"""AI dọn dẹp MEMORY.md: đề xuất bản mới (gộp trùng, bỏ lỗi thời), chỉ ghi khi apply_curation được gọi."""
import time

from . import providers

PROMPT = """Bạn là người biên tập tệp bộ nhớ dài hạn MEMORY.md của một trợ lý AI cá nhân.
Nhiệm vụ: dọn dẹp tệp dưới đây.
- Gộp các dòng trùng hoặc gần giống nhau thành một dòng.
- Bỏ thông tin đã lỗi thời hoặc bị mâu thuẫn bởi thông tin mới hơn (dòng ở dưới mới hơn).
- GIỮ MỌI thông tin còn hữu ích, không bịa thêm.
- Giữ nguyên định dạng: tiêu đề `# Memory` ở dòng đầu, mỗi ý là một gạch đầu dòng bắt đầu bằng `- `.
- Giữ nguyên ngôn ngữ gốc của từng dòng.
Chỉ trả lời bằng TOÀN BỘ nội dung tệp mới, không giải thích, không dùng khối code ```.

Nội dung hiện tại:
{text}
"""


def memory_path(cfg):
    return cfg.workspace_path() / "MEMORY.md"


def _bullets(t: str) -> list[str]:
    return [ln.rstrip() for ln in t.splitlines() if ln.strip().startswith("- ")]


def validate(old: str, new: str) -> tuple[bool, str]:
    if "```" in new:
        return False, "câu trả lời chứa khối code"
    if not new.lstrip().startswith("# Memory"):
        return False, "câu trả lời không bắt đầu bằng '# Memory'"
    ob, nb = _bullets(old), _bullets(new)
    if ob and not nb:
        return False, "bản mới không còn mục nào"
    if len(ob) >= 2 and len(new) < len(old) / 2 and len(set(map(str.lower, ob))) > len(ob) / 2:
        return False, "bản mới ngắn hơn một nửa bản gốc, có thể mất thông tin"
    return True, ""


def _clean(ans: str) -> str:
    return ans.strip()


def propose_curation(cfg, provider_name: str | None = None) -> dict:
    f = memory_path(cfg)
    old = f.read_text(errors="replace") if f.exists() else ""
    res = {"old": old, "new": old, "removed": [], "added": [], "ok": False, "reason": ""}
    if not _bullets(old):
        res["reason"] = "MEMORY.md chưa có mục nào để dọn"
        return res
    name = provider_name or cfg.default_provider
    if name not in cfg.providers:
        res["reason"] = f"không có provider '{name}'"
        return res
    try:
        prov = providers.make_provider(cfg.providers[name])
        msgs = [{"role": "user", "content": PROMPT.format(text=old)}]
        new = _clean("".join(ev.get("text", "") for ev in prov.stream(msgs, []) if ev.get("type") == "delta"))
    except Exception as e:  # noqa: BLE001
        res["reason"] = f"gọi model lỗi: {type(e).__name__}: {e}"[:300]
        return res
    ok, why = validate(old, new)
    ol, nl = _bullets(old), _bullets(new)
    res.update(new=new + ("\n" if not new.endswith("\n") else ""), removed=[x for x in ol if x not in nl], added=[x for x in nl if x not in ol], ok=ok, reason=why)
    return res


def apply_curation(cfg, new_text: str) -> dict:
    """Sao lưu MEMORY.md.bak-<giờ> rồi ghi bản mới; cập nhật lại chỉ mục ghi chú nếu bật."""
    f = memory_path(cfg)
    old = f.read_text(errors="replace") if f.exists() else ""
    ok, why = validate(old, new_text)
    if not ok:
        raise ValueError(why)
    backup = f.with_name(f"MEMORY.md.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    if f.exists():
        backup.write_text(old)
    f.write_text(new_text if new_text.endswith("\n") else new_text + "\n")
    try:
        if cfg.memory.embeddings != "off":
            from . import memory_index
            memory_index.index_notes(cfg)
    except Exception:  # noqa: BLE001
        pass
    return {"backup": str(backup) if f.exists() and old else "", "path": str(f)}
