"""argus tasks list|show|cancel|run: việc chạy nền và agent con."""
import json
import threading
import time

from . import runtime
from .ui import L, bad, bold, dim, green, ok, red, warn, yellow

_TONE = {"done": green, "running": yellow, "queued": dim, "failed": red, "cancelled": yellow, "interrupted": yellow}


def _fmt(j: dict) -> str:
    st = _TONE.get(j["status"], str)(j["status"].ljust(11))
    return f"{j['id']}  {st} {j['kind'][:4]:<4} {j['steps']:>3} {L('bước', 'steps')}  {j['title']}"


def _list(args) -> int:
    from ..services import jobs
    runtime.bootstrap()
    rows = jobs.list_jobs(args.status or "", args.kind or "", args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print(dim(L("Chưa có việc nào.", "No tasks yet.")))
    for j in rows:
        print(_fmt(j))
    return 0


def _show(args) -> int:
    from ..services import jobs
    runtime.bootstrap()
    j = jobs.get(args.id)
    if not j:
        bad(L(f"Không có việc '{args.id}'.", f"No task '{args.id}'."))
        return 1
    if args.json:
        print(json.dumps(j, ensure_ascii=False, indent=2))
        return 0
    print(bold(j["title"]), dim(f"({j['id']})"))
    print(f"  {L('trạng thái', 'status')}: {j['status']}  ·  {L('vai trò', 'role')}: {j['role'] or 'general'}  ·  {L('bước', 'steps')}: {j['steps']}/{j['max_steps'] or '?'}")
    print(f"  {L('mục tiêu', 'goal')}: {j['goal']}")
    if j["error"]:
        print(red(f"  {L('lỗi', 'error')}: {j['error']}"))
    if j["result"]:
        print(f"\n{j['result']}")
    return 0


def _cancel(args) -> int:
    from ..services import jobs
    runtime.bootstrap()
    if jobs.request_cancel(args.id):
        ok(L("Đã yêu cầu dừng.", "Stop requested."))
        return 0
    bad(L("Không có việc đang chạy với id đó.", "No running task with that id."))
    return 1


def _run(args) -> int:
    """Chạy một việc ngay trong tiến trình CLI (Ctrl+C để dừng); khác với giao diện web, CLI không giữ việc sống sau khi thoát."""
    from ..services import jobs
    cfg = runtime.bootstrap()
    if args.role != "general" and args.role not in cfg.agents.profiles:
        bad(L(f"Không có vai trò '{args.role}'. Có: {', '.join(cfg.agents.profiles)}, general", f"No role '{args.role}'. Available: {', '.join(cfg.agents.profiles)}, general"))
        return 1
    jid = jobs.create(args.goal, kind="task", title=args.goal[:60], role=args.role, permission=args.permission, provider=args.provider, notify=False)
    cancel = threading.Event()
    out: dict = {}
    t = threading.Thread(target=lambda: out.update(jobs.execute(jid, approver=lambda k, d: False, cancel=cancel)), daemon=True)
    t.start()
    print(dim(f"{L('Việc', 'Task')} {jid}"))
    last = ""
    try:
        while t.is_alive():
            j = jobs.get(jid) or {}
            line = f"  {j.get('steps', 0)} {L('bước', 'steps')} · {j.get('progress') or ''}"[:100]
            if line != last:
                print(dim(line))
                last = line
            time.sleep(0.5)
    except KeyboardInterrupt:
        cancel.set()
        warn(L("Đang dừng…", "Stopping…"))
        t.join(15)
    j = jobs.get(jid) or out
    print()
    print(j.get("result") or j.get("error") or "")
    return 0 if j.get("status") == "done" else 1


def register(sub) -> None:
    s = sub.add_parser("tasks", help=L("việc chạy nền và agent con", "background tasks and sub-agents"))
    ts = s.add_subparsers(dest="sub", required=True)
    t = ts.add_parser("list", help=L("liệt kê", "list"))
    t.add_argument("--status", choices=["queued", "running", "done", "failed", "cancelled", "interrupted"])
    t.add_argument("--kind", choices=["task", "subagent"])
    t.add_argument("--limit", type=int, default=30)
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=_list)
    t = ts.add_parser("show", help=L("xem chi tiết và kết quả", "details and result"))
    t.add_argument("id")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=_show)
    t = ts.add_parser("cancel", help=L("dừng một việc đang chạy", "stop a running task"))
    t.add_argument("id")
    t.set_defaults(func=_cancel)
    t = ts.add_parser("run", help=L("chạy một việc ngay tại đây", "run a task right here"))
    t.add_argument("goal")
    t.add_argument("--role", default="general")
    t.add_argument("--permission", choices=["readonly", "default", "guarded", "full"], default="default",
                   help=L("default: tạo file trong thư mục làm việc, từ chối việc nguy hiểm", "default: may create files in the working folder, refuses risky actions"))
    t.add_argument("--provider")
    t.set_defaults(func=_run)
