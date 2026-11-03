"""argus chat (REPL) va argus run (mot lan): chay agent ngay trong tien trinh, khong can server."""
import json
import sys
import time

from ..services import api_run, chat_runner, sessions
from . import runtime
from .ui import L, ask_yes_no, bold, cyan, dim, err, green, interactive, red, yellow

KIND = {"exec": ("chạy lệnh shell", "run a shell command"), "mcp": ("gọi tool MCP", "call an MCP tool"), "file_read": ("đọc file ngoài workspace", "read a file outside the workspace"),
        "file_write": ("ghi file", "write a file"), "http_request": ("gửi yêu cầu HTTP thay đổi dữ liệu", "send a state-changing HTTP request")}
PERMS = ("default", "readonly", "guarded", "full")
EFFORTS = ("auto", "low", "medium", "high")


def _trace(ev: dict) -> str | None:
    if ev["type"] == "tool":
        a = ev["args"]
        summary = a.get("command") if ev["name"] == "exec" else (a.get("path") or a.get("url") or a.get("query") or json.dumps(a, ensure_ascii=False))
        return f"⚙ {ev['name']} {str(summary)[:140]}"
    if ev["type"] == "tool_result":
        first = (ev["result"].strip().splitlines() or [""])[0][:120]
        return f"  {'→' if ev['ok'] else '✗'} {first}  ({ev.get('duration_ms', 0)}ms)"
    return None


def consume(events, *, live: bool, verbose: bool, ask: bool, deadline: float | None = None) -> dict:
    """Doc su kien tu stream_chat. live=True: in chu khi model dang sinh; ask=True: hoi y/N khi can phe duyet."""
    out = {"session": None, "output": "", "error": None, "timed_out": False, "provider": None, "usage": {"prompt": 0, "completion": 0}}
    streamed = False
    try:
        for ev in events:
            t = ev["type"]
            if t == "session":
                out["session"] = ev["id"]
            elif t == "delta" and live:
                print(ev["text"], end="", flush=True)
                streamed = True
            elif t == "thinking" and verbose:
                print(dim(ev["text"]), end="", file=sys.stderr, flush=True)
            elif t == "assistant":
                out["output"], out["provider"] = ev["content"], ev["provider"]
                out["usage"] = {k: out["usage"][k] + ev["usage"][k] for k in out["usage"]}
                if live and streamed:
                    print()
                elif live and ev["content"]:
                    print(ev["content"])
                streamed = False
            elif t in ("tool", "tool_result") and (verbose or live):
                line = _trace(ev)
                if line:
                    print(dim(line), file=sys.stdout if live else sys.stderr, flush=True)
            elif t == "approval":
                label = KIND.get(ev["kind"], (ev["kind"], ev["kind"]))
                print(f"\n{yellow('⚠')} {L('Agent muốn', 'The agent wants to')} {bold(L(label[0], label[1]))}:\n  {ev['detail'][:500]}", file=sys.stderr if not live else sys.stdout)
                allowed = ask and ask_yes_no(L("Cho phép?", "Allow?"), False)
                chat_runner.resolve_approval(ev["id"], allowed)
            elif t == "notice" and (verbose or live):
                print(dim(f"· {ev['message']}"), file=sys.stderr if not live else sys.stdout)
            elif t == "error":
                out["error"] = ev["message"]
            if deadline and time.time() > deadline:
                out["timed_out"], out["error"] = True, out["error"] or L("hết thời gian chờ", "timed out")
                break
    finally:
        events.close()
    return out


def _read_prompt(p: str) -> str:
    return sys.stdin.read().strip() if p == "-" else p


def run(args) -> int:
    prompt = _read_prompt(args.prompt)
    if not prompt:
        err(L("Thiếu nội dung yêu cầu.", "Missing prompt."))
        return 2
    runtime.bootstrap(with_mcp=True)
    tools = [t.strip() for t in args.tools.split(",")] if args.tools else None
    effort = None if args.effort == "auto" else args.effort
    if args.ask and not interactive():
        err(L("--ask cần terminal tương tác.", "--ask needs an interactive terminal."))
        return 2
    try:
        approver = None if args.ask else api_run.make_approver(args.exec_policy, args.allow or [], True)
    except api_run.PolicyError as e:
        err(str(e))
        return 2
    if args.json:
        res = api_run.run_once(prompt, session=args.session, provider=args.provider, approver=approver or (lambda k, d: False), only_tools=tools,
                               timeout=args.timeout, permission=args.permission, effort=effort, source="cli")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 1 if res["error"] else 0
    events = chat_runner.stream_chat(args.session, prompt, args.provider, approver_override=approver, source="cli", only_tools=tools, permission=args.permission, effort=effort)
    res = consume(events, live=False, verbose=args.verbose, ask=args.ask, deadline=time.time() + args.timeout)
    if res["output"]:
        print(res["output"])
    if res["error"]:
        err(res["error"])
        return 1
    return 0


HELP = {
    "/help": ("Hiện trợ giúp", "Show help"), "/new": ("Bắt đầu hội thoại mới", "Start a new conversation"), "/sessions": ("Liệt kê hội thoại gần đây", "List recent conversations"),
    "/open <id>": ("Mở lại một hội thoại", "Reopen a conversation"), "/model <name>": ("Đổi provider", "Switch provider"), "/perm <mode>": ("default | readonly | guarded | full", "default | readonly | guarded | full"),
    "/effort <level>": ("auto | low | medium | high", "auto | low | medium | high"), "/skills": ("Liệt kê skill", "List skills"), "/files": ("Liệt kê file của phiên", "List the conversation's files"), "/exit": ("Thoát (hoặc Ctrl+D)", "Quit (or Ctrl+D)"),
}


def chat(args) -> int:
    cfg = runtime.bootstrap(with_mcp=True)
    try:
        import readline  # noqa: F401 - bat lich su phim mui ten cho input()
    except ImportError:
        pass
    st = {"sid": args.session, "provider": args.provider or cfg.default_provider, "perm": args.permission, "effort": args.effort}
    if st["provider"] not in cfg.providers:
        err(L(f"Không có provider '{st['provider']}'. Có: {', '.join(cfg.providers)}", f"No provider '{st['provider']}'. Available: {', '.join(cfg.providers)}"))
        return 2
    print(f"{bold('Argus Agent')} {dim('· ' + L('gõ /help để xem lệnh, Ctrl+D để thoát', 'type /help for commands, Ctrl+D to quit'))}")
    print(dim(f"  {st['provider']} · {cfg.providers[st['provider']].model} · {L('quyền', 'permissions')}: {st['perm']}" + (f" · {L('phiên', 'session')} {st['sid']}" if st["sid"] else "")))
    while True:
        try:
            line = input(f"\n{cyan(st['provider'])} {bold('›')} ").strip()
            while line.endswith("\\"):
                line = line[:-1] + "\n" + input(dim("  … ")).rstrip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            continue
        if not line:
            continue
        if line.startswith("/"):
            cmd, _, rest = line.partition(" ")
            rest = rest.strip()
            if cmd in ("/exit", "/quit", "/q"):
                return 0
            if cmd == "/help":
                for k, (vi, en) in HELP.items():
                    print(f"  {bold(k.ljust(14))}{L(vi, en)}")
            elif cmd == "/new":
                st["sid"] = None
                print(dim(L("Đã bắt đầu hội thoại mới.", "Started a new conversation.")))
            elif cmd == "/sessions":
                for s in sessions.list_all(10):
                    print(f"  {s['id']}  {s['title'][:50]}  {dim(time.strftime('%m-%d %H:%M', time.localtime(s['updated'])))}")
            elif cmd == "/open" and sessions.get(rest):
                st["sid"] = rest
                print(dim(L(f"Đã mở {rest} ({len(sessions.messages(rest))} tin).", f"Opened {rest} ({len(sessions.messages(rest))} messages).")))
            elif cmd == "/model" and rest in cfg.providers:
                st["provider"] = rest
            elif cmd == "/perm" and rest in PERMS:
                st["perm"] = rest
                print(dim(f"{L('Quyền', 'Permissions')}: {rest}") + (red(L("  (không hỏi xác nhận!)", "  (no confirmations!)")) if rest == "full" else ""))
            elif cmd == "/effort" and rest in EFFORTS:
                st["effort"] = rest
            elif cmd == "/skills":
                from ..services import skills as skillmod

                for s in skillmod.discover(cfg).values():
                    print(f"  {s.name}  {dim(s.description[:70])}")
            elif cmd == "/files" and st["sid"]:
                from ..services import workfiles

                for f in workfiles.tree(workfiles.session_dir(cfg, st["sid"])):
                    print(f"  {f['path']}{'/' if f['dir'] else ''}")
            else:
                print(red(L("Lệnh không hợp lệ. Gõ /help.", "Unknown or invalid command. Type /help.")))
            continue
        print()
        effort = None if st["effort"] == "auto" else st["effort"]
        t0 = time.time()
        events = chat_runner.stream_chat(st["sid"], line, st["provider"], source="cli", permission=st["perm"], effort=effort)
        try:
            res = consume(events, live=True, verbose=False, ask=True)
        except KeyboardInterrupt:
            print(dim(f"\n({L('đã dừng', 'stopped')})"))
            continue
        st["sid"] = res["session"] or st["sid"]
        if res["error"]:
            print(red(f"✗ {res['error']}"))
        elif res["provider"]:
            u = res["usage"]
            print(dim(f"  {res['provider']} · {time.time() - t0:.1f}s" + (f" · {u['prompt']}+{u['completion']} tokens" if u["prompt"] else "") + f" · {L('phiên', 'session')} {st['sid']}"))


__all__ = ["run", "chat", "green"]
