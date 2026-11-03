"""Lenh `argus`: dieu khien Argus Agent tu terminal."""
import argparse
import sys

from .ui import L, err, lang, set_lang

VERSION = "0.3.0"


def _pre_lang(argv: list[str]) -> None:
    """Doc --lang truoc khi dung parser, de chinh phan tro giup cung dung ngon ngu."""
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            set_lang(argv[i + 1])
        elif a.startswith("--lang="):
            set_lang(a.split("=", 1)[1])


def build_parser() -> argparse.ArgumentParser:
    from .daemon import default_host, default_port

    p = argparse.ArgumentParser(prog="argus", description=L("Argus Agent: trợ lý AI cá nhân chạy trên máy bạn.", "Argus Agent: a personal AI agent running on your machine."))
    p.add_argument("--version", action="version", version=f"argus-agent {VERSION}")
    p.add_argument("--lang", choices=["vi", "en"], help=L("ngôn ngữ của CLI (mặc định: theo cấu hình/hệ thống)", "CLI language (default: from config/system)"))
    sub = p.add_subparsers(dest="cmd", metavar=L("<lệnh>", "<command>"))

    def srv(sp) -> None:
        sp.add_argument("--host", default=default_host(), help=L("địa chỉ lắng nghe (0.0.0.0 để mở cho máy khác)", "address to listen on (0.0.0.0 to expose it)"))
        sp.add_argument("--port", type=int, default=default_port(), help=L("cổng (mặc định 8787)", "port (default 8787)"))

    s = sub.add_parser("start", help=L("chạy server nền", "start the server in the background"))
    srv(s)
    s.add_argument("-f", "--foreground", action="store_true", help=L("chạy ở foreground", "run in the foreground"))
    s.add_argument("--no-build", action="store_true", help=L("không tự build giao diện web", "do not build the web UI"))
    sub.add_parser("stop", help=L("dừng server", "stop the server"))
    s = sub.add_parser("restart", help=L("khởi động lại server", "restart the server"))
    srv(s)
    s.add_argument("--no-build", action="store_true", help=argparse.SUPPRESS)
    s = sub.add_parser("status", help=L("xem trạng thái", "show status"))
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("logs", help=L("xem log server", "show the server log"))
    s.add_argument("-f", "--follow", action="store_true", help=L("theo dõi liên tục", "follow the log"))
    s.add_argument("-n", type=int, default=50, help=L("số dòng cuối", "number of last lines"))
    s = sub.add_parser("open", help=L("mở giao diện web", "open the web UI"))
    srv(s)
    s = sub.add_parser("dev", help=L("chế độ phát triển (tự nạp lại)", "development mode (auto reload)"))
    s.add_argument("--port", type=int, default=default_port())

    s = sub.add_parser("doctor", help=L("chẩn đoán sự cố", "diagnose problems"))
    s.add_argument("--fix", action="store_true", help=L("tự sửa các lỗi an toàn", "fix safe problems automatically"))
    s.add_argument("--offline", action="store_true", help=L("bỏ qua kiểm tra mạng", "skip network checks"))
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("onboard", help=L("cài đặt lần đầu (trình hướng dẫn)", "first-time setup wizard"))
    s.add_argument("--non-interactive", action="store_true", help=L("không hỏi, dùng các cờ bên dưới", "do not prompt, use the flags below"))
    s.add_argument("--language", choices=["vi", "en"])
    s.add_argument("--name", default="")
    s.add_argument("--provider", help=L("id provider mẫu: ollama, gemini, openai, anthropic, openrouter, deepseek, mistral, groq, xai, lmstudio, custom", "preset id: ollama, gemini, openai, anthropic, openrouter, deepseek, mistral, groq, xai, lmstudio, custom"))
    s.add_argument("--model")
    s.add_argument("--base-url")
    s.add_argument("--api-key-env", help=L("tên biến môi trường chứa API key", "name of the environment variable holding the API key"))
    s.add_argument("--api-key-stdin", action="store_true", help=L("đọc API key từ stdin", "read the API key from stdin"))
    s.add_argument("--skip-test", action="store_true", help=L("không thử kết nối provider", "do not test the provider connection"))
    s.add_argument("--sandbox", choices=["none", "docker"], default="none")
    s.add_argument("--password-env", help=L("tên biến môi trường chứa mật khẩu giao diện", "env var holding the UI password"))
    s.add_argument("--telegram-token-env")
    s.add_argument("--start", dest="start", action="store_true", default=None, help=L("chạy server sau khi cài", "start the server afterwards"))
    s.add_argument("--no-start", dest="start", action="store_false")
    s.add_argument("--heartbeat", action="store_true", help=L("bật heartbeat", "enable heartbeat"))
    s.add_argument("--service", action="store_true", help=L("cài dịch vụ tự khởi động", "install the auto-start service"))

    s = sub.add_parser("chat", help=L("trò chuyện trong terminal", "chat in the terminal"))
    s.add_argument("-s", "--session", help=L("mở lại hội thoại theo id", "reopen a conversation by id"))
    s.add_argument("-p", "--provider")
    s.add_argument("--permission", choices=["default", "readonly", "guarded", "full"], default="default")
    s.add_argument("--effort", choices=["auto", "low", "medium", "high"], default="auto")

    s = sub.add_parser("run", help=L("giao một việc rồi thoát", "run one task and exit"))
    s.add_argument("prompt", help=L("yêu cầu (dùng - để đọc từ stdin)", "the request (use - to read from stdin)"))
    s.add_argument("-s", "--session")
    s.add_argument("-p", "--provider")
    s.add_argument("--permission", choices=["default", "readonly", "guarded", "full"], default="default")
    s.add_argument("--effort", choices=["auto", "low", "medium", "high"], default="auto")
    s.add_argument("--exec-policy", choices=["deny", "allow", "allowlist"], default="deny", help=L("quyền chạy lệnh khi không có người duyệt (mặc định: deny)", "command policy without a human (default: deny)"))
    s.add_argument("--allow", action="append", metavar="CMD", help=L("lệnh được phép (với allowlist), có thể lặp lại", "allowed command prefix (with allowlist), repeatable"))
    s.add_argument("--ask", action="store_true", help=L("hỏi y/N trực tiếp khi cần phê duyệt", "ask y/N interactively for approvals"))
    s.add_argument("--tools", help=L("chỉ cho dùng các tool này (cách nhau bằng dấu phẩy)", "only allow these tools (comma separated)"))
    s.add_argument("--timeout", type=int, default=300)
    s.add_argument("--json", action="store_true", help=L("in kết quả dạng JSON", "print the result as JSON"))
    s.add_argument("-v", "--verbose", action="store_true", help=L("in cả các bước tool ra stderr", "also print tool steps to stderr"))

    s = sub.add_parser("token", help=L("quản lý API token", "manage API tokens"))
    ts = s.add_subparsers(dest="sub", required=True)
    t = ts.add_parser("create", help=L("tạo token", "create a token"))
    t.add_argument("name")
    t.add_argument("--allow-exec", action="store_true", help=L("cho phép dùng exec_policy allow/allowlist", "allow exec_policy allow/allowlist"))
    t.add_argument("--json", action="store_true")
    t = ts.add_parser("list", help=L("liệt kê token", "list tokens"))
    t.add_argument("--json", action="store_true")
    t = ts.add_parser("revoke", help=L("thu hồi token", "revoke a token"))
    t.add_argument("id")

    s = sub.add_parser("skills", help=L("quản lý skill (ClawHub)", "manage skills (ClawHub)"))
    ks = s.add_subparsers(dest="sub", required=True)
    k = ks.add_parser("list", help=L("skill đã cài", "installed skills"))
    k.add_argument("--json", action="store_true")
    k = ks.add_parser("search", help=L("tìm trên ClawHub", "search ClawHub"))
    k.add_argument("query")
    k.add_argument("-n", "--limit", type=int, default=12)
    k.add_argument("--json", action="store_true")
    k = ks.add_parser("install", help=L("cài skill", "install a skill"))
    k.add_argument("ref", help="<owner>/<slug>")
    k.add_argument("-y", "--yes", action="store_true", help=L("không hỏi xác nhận", "do not ask for confirmation"))
    k.add_argument("--overwrite", action="store_true")
    k = ks.add_parser("remove", help=L("gỡ skill", "remove a skill"))
    k.add_argument("name")
    k.add_argument("-y", "--yes", action="store_true")
    k = ks.add_parser("update", help=L("cập nhật skill đã cài từ ClawHub", "update ClawHub-installed skills"))
    k.add_argument("name", nargs="?")

    s = sub.add_parser("service", help=L("dịch vụ chạy cùng máy (systemd/launchd)", "run-at-boot service (systemd/launchd)"))
    ss = s.add_subparsers(dest="sub", required=True)
    i = ss.add_parser("install", help=L("cài và bật dịch vụ", "install and enable the service"))
    srv(i)
    i.add_argument("--dry-run", action="store_true", help=L("chỉ in nội dung, không cài", "only print, do not install"))
    for name in ("uninstall", "start", "stop", "restart", "status"):
        ss.add_parser(name)

    s = sub.add_parser("backup", help=L("sao lưu cấu hình, cơ sở dữ liệu và workspace", "back up configuration, database and workspace"))
    s.add_argument("-o", "--output", help=L("file đầu ra (mặc định: backups/argus-backup-<giờ>.tar.gz)", "output file (default: backups/argus-backup-<time>.tar.gz)"))
    s.add_argument("--include-key", action="store_true", help=L("kèm khóa chủ (để khôi phục sang máy khác); nên dùng cùng --encrypt", "include the master key (to restore on another machine); use with --encrypt"))
    s.add_argument("--no-sessions", action="store_true", help=L("bỏ file của các phiên (workspace/sessions) cho nhẹ", "skip per-conversation files (workspace/sessions) to keep it small"))
    s.add_argument("--encrypt", action="store_true", help=L("mã hóa bản sao lưu bằng mật khẩu", "encrypt the backup with a passphrase"))
    s.add_argument("--passphrase-env", help=L("lấy mật khẩu từ biến môi trường", "read the passphrase from this environment variable"))
    s = sub.add_parser("restore", help=L("khôi phục từ bản sao lưu", "restore from a backup"))
    s.add_argument("archive")
    s.add_argument("--force", action="store_true", help=L("ghi đè dữ liệu hiện có (tự sao lưu bản hiện tại trước)", "overwrite existing data (the current data is backed up first)"))
    s.add_argument("--passphrase-env")
    s.add_argument("--master-key-file", help=L("file chứa khóa chủ (nếu bản sao lưu không kèm khóa)", "file holding the master key (if the backup does not include it)"))

    s = sub.add_parser("secrets", help=L("mã hóa khóa bí mật trong config.json", "encryption of secrets in config.json"))
    ss = s.add_subparsers(dest="sub", required=True)
    t = ss.add_parser("status", help=L("xem trạng thái", "show status"))
    t.add_argument("--json", action="store_true")
    ss.add_parser("encrypt", help=L("mã hóa mọi khóa còn ở dạng chữ thường", "encrypt any plaintext secrets"))
    t = ss.add_parser("decrypt", help=L("ghi khóa ra chữ thường (không khuyên)", "write secrets as plaintext (not recommended)"))
    t.add_argument("-y", "--yes", action="store_true")
    ss.add_parser("keychain", help=L("chuyển khóa chủ vào keychain của hệ điều hành", "move the master key into the OS keychain"))
    ss.add_parser("file", help=L("chuyển khóa chủ về file data/master.key", "move the master key back to data/master.key"))
    ss.add_parser("rotate", help=L("đổi khóa chủ và mã hóa lại", "rotate the master key and re-encrypt"))

    import importlib
    import pkgutil

    for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):  # lenh mo rong: cli/cmd_<ten>.py voi register(sub)
        if info.name.startswith("cmd_"):
            importlib.import_module(f"{__name__}.{info.name}").register(sub)

    s = sub.add_parser("config", help=L("xem cấu hình", "show the configuration"))
    cs = s.add_subparsers(dest="sub", required=True)
    cs.add_parser("path", help=L("đường dẫn file cấu hình", "path of the config file"))
    cs.add_parser("show", help=L("in cấu hình (đã che API key)", "print the configuration (API keys masked)"))
    return p


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    _pre_lang(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.lang:
        set_lang(args.lang)
    if not args.cmd:
        parser.print_help()
        raise SystemExit(0)
    try:
        code = dispatch(args)
    except KeyboardInterrupt:
        print()
        code = 130
    except Exception as e:  # noqa: BLE001 - nguoi dung khong nen thay traceback; dung ARGUS_DEBUG=1 de xem
        import os

        if os.environ.get("ARGUS_DEBUG"):
            raise
        err(f"{type(e).__name__}: {e}")
        code = 1
    raise SystemExit(code or 0)


def dispatch(a: argparse.Namespace) -> int:
    from . import daemon

    if getattr(a, "func", None):
        return a.func(a) or 0

    c = a.cmd
    if c == "start":
        return daemon.start(a.host, a.port, foreground=a.foreground, build=not a.no_build)
    if c == "stop":
        return daemon.stop()
    if c == "restart":
        return daemon.restart(a.host, a.port)
    if c == "status":
        return daemon.status(a.json)
    if c == "logs":
        return daemon.logs(a.follow, a.n)
    if c == "open":
        return daemon.open_ui(a.host, a.port)
    if c == "dev":
        return daemon.dev(a.port)
    if c == "doctor":
        from . import doctor

        return doctor.run(offline=a.offline, fix=a.fix, as_json=a.json)
    if c == "onboard":
        from . import onboard

        return onboard.run(a)
    if c == "chat":
        from . import chatcmd

        return chatcmd.chat(a)
    if c == "run":
        from . import chatcmd

        return chatcmd.run(a)
    if c == "token":
        from . import tokencmd

        return {"create": lambda: tokencmd.create(a.name, a.allow_exec, a.json), "list": lambda: tokencmd.list_tokens(a.json), "revoke": lambda: tokencmd.revoke(a.id)}[a.sub]()
    if c == "skills":
        from . import skillscmd

        return {"list": lambda: skillscmd.list_(a.json), "search": lambda: skillscmd.search(a.query, a.limit, a.json), "install": lambda: skillscmd.install(a.ref, a.yes, a.overwrite),
                "remove": lambda: skillscmd.remove(a.name, a.yes), "update": lambda: skillscmd.update(a.name)}[a.sub]()
    if c == "service":
        from . import service

        if a.sub == "install":
            return service.install(a.host, a.port, a.dry_run)
        if a.sub == "uninstall":
            return service.uninstall()
        return service.control(a.sub)
    if c == "backup":
        from . import backupcmd

        return backupcmd.create(a.output, a.include_key, not a.no_sessions, a.encrypt, a.passphrase_env)
    if c == "restore":
        from . import backupcmd

        return backupcmd.do_restore(a.archive, a.force, a.passphrase_env, a.master_key_file)
    if c == "secrets":
        from . import secretscmd

        return {"status": lambda: secretscmd.status(a.json), "encrypt": secretscmd.encrypt, "decrypt": lambda: secretscmd.decrypt(a.yes),
                "keychain": secretscmd.keychain, "file": secretscmd.file_, "rotate": secretscmd.rotate}[a.sub]()
    if c == "config":
        from ..core import config as cfgmod

        if a.sub == "path":
            print(cfgmod.CONFIG_PATH)
        else:
            import json

            print(json.dumps(cfgmod.masked(cfgmod.load()), ensure_ascii=False, indent=2))
        return 0
    return 2


__all__ = ["main", "lang"]
