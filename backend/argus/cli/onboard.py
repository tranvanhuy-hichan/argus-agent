"""argus onboard: trinh huong dan cai dat lan dau (ngon ngu, ten, provider, an toan, Telegram, khoi dong)."""
import os
import shutil
import subprocess
import sys

import httpx

from ..core import config as cfgmod
from ..core.presets import OLLAMA, PRESETS, Preset
from ..services import auth, providers
from . import daemon, runtime, service
from .ui import L, ask, ask_secret, ask_yes_no, bold, choose, cyan, dim, err, green, info, multiselect, ok, red, set_lang, warn, yellow


def _banner() -> None:
    print(bold(cyan("\n  Argus Agent")) + dim(f"  ·  {L('trình hướng dẫn cài đặt', 'setup wizard')}\n"))


def _ollama_models() -> list[str]:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=2)
        return [m["name"] for m in r.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return []


def _docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=8).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _unique(cfg: cfgmod.Config, base: str) -> str:
    name, i = base, 2
    while name in cfg.providers:
        name = f"{base}{i}"
        i += 1
    return name


def _test_provider(p: cfgmod.ProviderCfg) -> list[str] | None:
    """Tra ve danh sach model neu ket noi duoc, None neu loi (da in ly do)."""
    try:
        return providers.list_models(p, only_chat=True)
    except providers.ProviderError as e:
        print(red(f"  ✗ {e}"))
        return None


def _pick_model(models: list[str], default: str, interactive: bool) -> str:
    if not models:
        return ask(L("Tên model", "Model name"), default) if interactive else default
    shown = models[:12]
    default_i = shown.index(default) if default in shown else 0
    if not interactive:
        return default if default in models else models[0]
    i = choose(L("Chọn model", "Pick a model"), shown + [L("(nhập tên khác)", "(type another name)")], default_i)
    return ask(L("Tên model", "Model name"), default) if i == len(shown) else shown[i]


def add_provider(cfg: cfgmod.Config, preset: Preset, *, interactive: bool, model: str | None = None, base_url: str | None = None,
                 api_key_env: str | None = None, api_key: str | None = None, skip_test: bool = False) -> str | None:
    p = cfgmod.ProviderCfg(type=preset.type, base_url=base_url or preset.base_url, model=model or preset.model, api_key_env=api_key_env or preset.env)
    if preset.id == "custom" and interactive:
        p.base_url = ask("Base URL", p.base_url)
    if api_key:
        p.api_key = api_key  # moi provider deu nhan key, ke ca provider tu host (custom) khong co ten bien mac dinh
    if preset.env:
        have_env = bool(os.environ.get(p.api_key_env))
        if api_key:
            pass
        elif interactive:
            if have_env and ask_yes_no(L(f"Dùng API key trong biến môi trường {p.api_key_env}?", f"Use the API key from the {p.api_key_env} environment variable?"), True):
                pass
            else:
                p.api_key = ask_secret(L(f"Dán API key cho {preset.label}", f"Paste the API key for {preset.label}"))
                if not p.api_key:
                    p.api_key_env = ask(L("…hoặc tên biến môi trường chứa key", "…or the environment variable holding the key"), p.api_key_env)
    elif interactive and not preset.env and preset.id == "custom":
        p.api_key = ask_secret(L("API key (bỏ trống nếu không cần)", "API key (leave empty if not needed)"))
    if skip_test:
        models = []
    else:
        print(dim(L("  Đang kiểm tra kết nối…", "  Checking the connection…")))
        models = _test_provider(p)
        if models is None:
            if not interactive or not ask_yes_no(L("Vẫn lưu provider này?", "Save this provider anyway?"), False):
                return None
            models = []
        else:
            ok(L(f"Kết nối được ({len(models)} model).", f"Connected ({len(models)} models)."))
    p.model = _pick_model(models, p.model, interactive)
    name = _unique(cfg, preset.id)
    cfg.providers[name] = p
    return name


def _drop_untouched_local(cfg: cfgmod.Config) -> None:
    """Provider 'local' (Ollama qwen2.5:3b) la gia tri mac dinh; neu nguoi dung vua them provider khac thi bo no cho gon."""
    if "local" in cfg.providers and len(cfg.providers) > 1 and cfg.providers["local"] == cfgmod.Config().providers["local"] and cfg.default_provider != "local":
        del cfg.providers["local"]
        cfg.fallback = [f for f in cfg.fallback if f != "local"]


def _step_provider(cfg: cfgmod.Config, args, interactive: bool) -> None:
    _step_provider_inner(cfg, args, interactive)
    _drop_untouched_local(cfg)


def _step_provider_inner(cfg: cfgmod.Config, args, interactive: bool) -> None:
    print(f"\n{bold('1.')} {bold(L('Model AI', 'AI model'))}")
    if not interactive:
        if not args.provider:
            return
        preset = next((x for x in [OLLAMA, *PRESETS] if x.id == args.provider), None)
        if not preset:
            err(L(f"Không có provider mẫu '{args.provider}'.", f"Unknown provider preset '{args.provider}'."))
            return
        key = sys.stdin.read().strip() if args.api_key_stdin else None
        name = add_provider(cfg, preset, interactive=False, model=args.model, base_url=args.base_url, api_key_env=args.api_key_env, api_key=key, skip_test=args.skip_test)
        if name:
            cfg.default_provider = name
            ok(L(f"Đã thêm {name}.", f"Added {name}."))
        return
    first = True
    while True:
        models = _ollama_models()
        opts = ([f"{OLLAMA.label}  {green(L('đang chạy, ' + str(len(models)) + ' model', 'running, ' + str(len(models)) + ' models'))}" if models else f"{OLLAMA.label}  {dim(L('(chưa thấy Ollama chạy)', '(Ollama not detected)'))}"]
                + [x.label for x in PRESETS] + [L("Bỏ qua / giữ nguyên", "Skip / keep as is")])
        i = choose(L("Chọn nhà cung cấp", "Choose a provider"), opts, 0 if models else 1)
        if i == len(opts) - 1:
            break
        preset = OLLAMA if i == 0 else PRESETS[i - 1]
        name = add_provider(cfg, preset, interactive=True)
        if name:
            ok(L(f"Đã thêm {bold(name)}.", f"Added {bold(name)}."))
            if first or ask_yes_no(L(f"Đặt {name} làm model mặc định?", f"Make {name} the default model?"), first):
                if not first:
                    cfg.fallback = [cfg.default_provider, *[f for f in cfg.fallback if f != cfg.default_provider]]
                cfg.default_provider = name
                cfg.fallback = [f for f in cfg.fallback if f != name]
            first = False
        if not ask_yes_no(L("Thêm provider khác (làm dự phòng)?", "Add another provider (as a fallback)?"), False):
            break


def _set_password(cfg: cfgmod.Config) -> None:
    while True:
        pw = ask_secret(L("Mật khẩu giao diện (≥ 8 ký tự)", "Interface password (8+ characters)"))
        if len(pw) < 8:
            print(red(L("  Quá ngắn.", "  Too short.")))
            continue
        if pw != ask_secret(L("Nhập lại", "Repeat")):
            print(red(L("  Không khớp.", "  They do not match.")))
            continue
        auth.set_password(cfg, pw)
        return


def _connect_telegram(cfg: cfgmod.Config, token: str, uid: str) -> bool:
    if not token:
        return False
    try:
        r = httpx.post(f"{cfg.channels.telegram.api_base}/bot{token}/getMe", timeout=10).json()
    except httpx.HTTPError as e:
        warn(L(f"Không gọi được Telegram: {e}", f"Could not reach Telegram: {e}"))
        return False
    if not r.get("ok"):
        warn(L(f"Token không hợp lệ: {r.get('description')}", f"Invalid token: {r.get('description')}"))
        return False
    cfg.channels.telegram.enabled, cfg.channels.telegram.token = True, token
    if uid.isdigit():
        cfg.channels.telegram.allowed_users = [int(uid)]
    ok(L(f"Đã kết nối @{r['result']['username']}.", f"Connected @{r['result']['username']}.") + ("" if uid.isdigit() else dim(L(" Ghép đôi: giao diện web > Tích hợp > Kênh chat.", " Pair it in the web UI > Integrations > Chat channels."))))
    return True


def _enable_heartbeat(cfg: cfgmod.Config) -> None:
    from ..services import heartbeat

    cfg.heartbeat.enabled = True
    f = cfg.workspace_path() / "HEARTBEAT.md"
    if not f.exists():
        f.write_text(heartbeat.DEFAULT_FILE)
    ok(L("Đã bật heartbeat (mỗi 60 phút). Sửa danh sách việc trong HEARTBEAT.md.", "Heartbeat enabled (every 60 min). Edit the task list in HEARTBEAT.md."))


def _features(cfg: cfgmod.Config, args, interactive: bool) -> bool:
    """Buoc 'thiet lap them': mot danh sach tick (Space) thay cho hang loat cau hoi Co/Khong. Tra ve True neu can cai dich vu nen."""
    print(f"\n{bold('2.')} {bold(L('Tính năng', 'Features'))}")
    docker = _docker_ready()
    can_service = service._system() in ("Linux", "Darwin")
    catalog = [
        ("confirm", L("Hỏi xác nhận trước khi chạy lệnh shell", "Ask before running shell commands"), L("khuyên bật", "recommended"), cfg.agent.confirm_exec),
        ("docker", L("Chạy lệnh trong sandbox Docker", "Run commands in a Docker sandbox"), L("cách ly, không có mạng", "isolated, no network"), cfg.agent.exec_sandbox == "docker"),
        ("password", L("Đặt mật khẩu cho giao diện web", "Set a password for the web UI"), "", bool(cfg.auth.password_hash)),
        ("telegram", L("Kết nối Telegram", "Connect Telegram"), L("nhắn tin từ điện thoại", "message from your phone"), cfg.channels.telegram.enabled),
        ("heartbeat", L("Bật heartbeat", "Enable heartbeat"), L("agent chủ động báo tin", "the agent reports proactively"), cfg.heartbeat.enabled),
        ("service", L("Tự chạy khi bật máy", "Start automatically at boot"), L("dịch vụ nền", "background service"), False),
    ]
    catalog = [c for c in catalog if (c[0] != "docker" or docker) and (c[0] != "service" or can_service)]
    if not interactive:
        chosen = {"confirm"} if cfg.agent.confirm_exec else set()
        if args.sandbox == "docker":
            chosen.add("docker")
        if args.password_env:
            chosen.add("password")
        if args.telegram_token_env:
            chosen.add("telegram")
        if args.heartbeat:
            chosen.add("heartbeat")
        if args.service:
            chosen.add("service")
    else:
        picked = multiselect(L("Bạn muốn thiết lập gì? (Space để chọn, Enter để tiếp tục)", "What do you want to set up? (Space to toggle, Enter to continue)"),
                             [(c[1], c[2]) for c in catalog], {i for i, c in enumerate(catalog) if c[3]})
        chosen = {catalog[i][0] for i in picked}
    cfg.agent.confirm_exec = "confirm" in chosen
    cfg.agent.exec_sandbox = "docker" if "docker" in chosen else "none"
    if "password" in chosen and not cfg.auth.password_hash:
        if interactive:
            _set_password(cfg)
        else:
            pw = os.environ.get(args.password_env, "")
            if len(pw) >= 8:
                auth.set_password(cfg, pw)
            else:
                warn(L(f"Biến {args.password_env} trống hoặc ngắn hơn 8 ký tự, bỏ qua mật khẩu.", f"{args.password_env} is empty or shorter than 8 characters; password skipped."))
    elif "password" not in chosen and interactive and cfg.auth.password_hash:
        cfg.auth = cfgmod.AuthCfg()
    if "telegram" in chosen:
        if interactive:
            print(dim(L("  Chat với @BotFather, gửi /newbot và làm theo để nhận token.", "  Chat with @BotFather, send /newbot and follow the steps to get a token.")))
            token = ask_secret(L("Token bot Telegram", "Telegram bot token"))
            uid = ask(L("ID Telegram của bạn (gửi /id cho bot để biết; bỏ trống để ghép đôi sau bằng mã)", "Your Telegram ID (send /id to the bot to find out; leave empty to pair later with a code)"))
        else:
            token, uid = os.environ.get(args.telegram_token_env, ""), ""
        _connect_telegram(cfg, token, uid)
    elif interactive and cfg.channels.telegram.enabled:
        cfg.channels.telegram.enabled = False
    if "heartbeat" in chosen:
        _enable_heartbeat(cfg)
    elif interactive:
        cfg.heartbeat.enabled = False
    ok(L("Xác nhận lệnh shell: ", "Shell confirmation: ") + (L("bật", "on") if cfg.agent.confirm_exec else L("tắt", "off")) + f" · sandbox: {cfg.agent.exec_sandbox} · "
       + L("mật khẩu: ", "password: ") + (L("đã đặt", "set") if cfg.auth.password_hash else L("chưa", "not set")))
    return "service" in chosen


def run(args) -> int:
    interactive = not args.non_interactive
    if args.language:
        set_lang(args.language)
    _banner()
    cfg = runtime.bootstrap()
    print(dim(L(f"Dữ liệu sẽ nằm ở: {cfg.workspace_path().parent}", f"Your data will live in: {cfg.workspace_path().parent}")))

    # 0. ngon ngu + ten
    if interactive and not args.language:
        i = choose(L("Ngôn ngữ / Language", "Language / Ngôn ngữ"), ["Tiếng Việt", "English"], 0 if L("v", "e") == "v" else 1)
        set_lang(("vi", "en")[i])
    cfg.language = "vi" if L("v", "e") == "v" else "en"
    name = args.name if not interactive else ask(L("Bạn tên là gì? (để agent xưng hô, có thể bỏ trống)", "What is your name? (so the agent can address you; optional)"), args.name or "")
    user_md = cfg.workspace_path() / "USER.md"
    if name and not user_md.exists():
        user_md.write_text(f"# USER\n- {L('Tên', 'Name')}: {name}\n- {L('Ngôn ngữ ưu tiên', 'Preferred language')}: {'Tiếng Việt' if cfg.language == 'vi' else 'English'}\n")
        ok(L("Đã ghi USER.md.", "Wrote USER.md."))

    _step_provider(cfg, args, interactive)
    want_service = _features(cfg, args, interactive)
    print(f"\n{bold('3.')} {bold(L('Tính cách agent', 'Agent persona'))}")
    info(L("Sửa SOUL.md để đổi tính cách/quy tắc (giao diện web > Không gian làm việc).", "Edit SOUL.md to change the persona and rules (web UI > Workspace)."))

    cfgmod.save(cfg)
    ok(L(f"Đã lưu cấu hình: {cfgmod.CONFIG_PATH}", f"Configuration saved: {cfgmod.CONFIG_PATH}"))

    print(f"\n{bold('4.')} {bold(L('Khởi động', 'Launch'))}")
    host, port = daemon.default_host(), daemon.default_port()
    start_now = args.start if (not interactive or args.start is not None) else None
    if start_now is None:
        start_now = ask_yes_no(L("Chạy Argus Agent ngay bây giờ?", "Start Argus Agent now?"), True)
    if want_service:
        service.install(host, port)  # service tu dung server chay nen neu co, roi tu bat
    elif start_now:
        daemon.start(host, port)
    print(f"\n{green(L('Xong!', 'Done!'))} {L('Các lệnh hữu ích', 'Useful commands')}:")
    for cmd, vi, en in [("argus open", "mở giao diện web", "open the web UI"), ("argus chat", "trò chuyện ngay trong terminal", "chat right in the terminal"),
                        ("argus run \"…\"", "giao một việc rồi thoát", "run one task and exit"), ("argus doctor", "chẩn đoán sự cố", "diagnose problems"), ("argus --help", "mọi lệnh", "all commands")]:
        print(f"  {bold(cmd.ljust(16))}{dim(L(vi, en))}")
    return 0


__all__ = ["run", "add_provider", "yellow"]
