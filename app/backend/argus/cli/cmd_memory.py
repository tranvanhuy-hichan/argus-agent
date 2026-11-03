"""argus memory status|search|reindex|curate: bộ nhớ ngữ nghĩa và dọn MEMORY.md bằng AI."""
import difflib
import json
import sys
from pathlib import Path

from . import runtime
from .ui import L, bad, bold, dim, green, ok, red, warn


def _status(args) -> int:
    from ..core import db as dbmod
    from ..services import embeddings, memory_index, vectorstore
    cfg = runtime.bootstrap()
    e, st = embeddings.status(cfg), vectorstore.stats()
    if args.json:
        print(json.dumps({"embedding": e, "vectors": st, "notes": len(memory_index.note_lines(cfg))}, ensure_ascii=False, indent=2))
        return 0
    print(bold(L("Bộ nhớ ngữ nghĩa", "Semantic memory")))
    print(f"  {L('chế độ', 'mode')}: {e['mode']}  ·  backend: {e['backend'] or '-'}  ·  model: {e['model_id'] or '-'}  ·  dim: {e['dim']}")
    print("  " + (green(L("kết nối được", "reachable")) if e["reachable"] else red(L("không dùng được", "unavailable")) + (f" ({e['error']})" if e["error"] else "")))
    print(f"  {L('vector đã lưu', 'stored vectors')}: {st['total']} {dim(str(st['by_model']))}")
    print(f"  {L('ghi chú MEMORY.md', 'MEMORY.md notes')}: {len(memory_index.note_lines(cfg))}  ·  FTS: {dbmod.fts_enabled}")
    return 0


def _search(args) -> int:
    from ..services import tools
    cfg = runtime.bootstrap()
    ctx = tools.ToolContext(workspace=Path(cfg.workspace_path()))
    print(tools.TOOLS["memory_search"].fn(ctx, " ".join(args.query), args.limit))
    return 0


def _reindex(args) -> int:
    from ..services import memory_index
    cfg = runtime.bootstrap()

    def cb(d: int, t: int) -> None:
        print(f"\r  {d}/{t}", end="", file=sys.stderr, flush=True)

    try:
        r = memory_index.reindex(cfg, cb)
    except Exception as e:  # noqa: BLE001
        print(file=sys.stderr)
        bad(L(f"Reindex thất bại: {e}", f"Reindex failed: {e}"))
        return 1
    print(file=sys.stderr)
    ok(L(f"Đã nhúng {r['messages']} đoạn tin nhắn và {r['notes']} ghi chú ({r['model']}).", f"Embedded {r['messages']} message chunks and {r['notes']} notes ({r['model']})."))
    return 0


def _curate(args) -> int:
    from ..services import memory
    cfg = runtime.bootstrap()
    p = memory.propose_curation(cfg, args.provider)
    if not p["ok"]:
        bad(L(f"Không có đề xuất hợp lệ: {p['reason']}", f"No valid proposal: {p['reason']}"))
        return 1
    diff = list(difflib.unified_diff(p["old"].splitlines(), p["new"].splitlines(), "MEMORY.md", "MEMORY.md (new)", lineterm=""))
    if not diff:
        ok(L("MEMORY.md đã gọn, không cần đổi.", "MEMORY.md is already tidy, nothing to change."))
        return 0
    for ln in diff:
        print(green(ln) if ln.startswith("+") and not ln.startswith("+++") else red(ln) if ln.startswith("-") and not ln.startswith("---") else ln)
    if not args.apply:
        warn(L("dry-run: chưa ghi gì. Thêm --apply để áp dụng (có sao lưu).", "dry-run: nothing written. Add --apply to apply (a backup is made)."))
        return 0
    r = memory.apply_curation(cfg, p["new"])
    ok(L(f"Đã áp dụng. Bản sao lưu: {r['backup']}", f"Applied. Backup: {r['backup']}"))
    return 0


def register(sub) -> None:
    s = sub.add_parser("memory", help=L("bộ nhớ ngữ nghĩa và dọn MEMORY.md", "semantic memory and MEMORY.md curation"))
    ms = s.add_subparsers(dest="sub", required=True)
    t = ms.add_parser("status", help=L("trạng thái embedding", "embedding status"))
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=_status)
    t = ms.add_parser("search", help=L("tìm trong bộ nhớ (từ khóa + ngữ nghĩa)", "search memory (keyword + semantic)"))
    t.add_argument("query", nargs="+")
    t.add_argument("-n", "--limit", type=int, default=6)
    t.set_defaults(func=_search)
    t = ms.add_parser("reindex", help=L("nhúng lại toàn bộ", "re-embed everything"))
    t.set_defaults(func=_reindex)
    t = ms.add_parser("curate", help=L("nhờ AI dọn MEMORY.md", "let the AI tidy MEMORY.md"))
    t.add_argument("--apply", action="store_true", help=L("ghi thật (mặc định chỉ xem diff)", "write for real (default: diff only)"))
    t.add_argument("--provider", help=L("provider dùng để dọn", "provider to use"))
    t.set_defaults(func=_curate)
