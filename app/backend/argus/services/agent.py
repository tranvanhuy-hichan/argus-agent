"""Vong lap agent: dung prompt, goi LLM (stream, tu thu lai), chay tool, ghi lich su va nhat ky."""
import base64
import re
import mimetypes
import time
from collections.abc import Callable, Iterator
from datetime import datetime
from threading import Event

from ..core import config as cfgmod
from . import audit, compaction, mcp_client, plans, sessions, skills as skillmod, tools, usage, workfiles
from .providers import ProviderError, make_provider

PROMPT_FILES = ("SOUL.md", "USER.md", "MEMORY.md")
RETRIES = 4  # tong so lan thu cho loi tam thoi (429/503/timeout)
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_IMAGES, MAX_IMAGE_BYTES = 4, 5 * 1024 * 1024


def ui_event(kind: str, tpl: str, **vars) -> dict:
    """Su kien hien cho nguoi dung: `tpl` la mau tieng Viet co {bien}; giao dien tu dich theo ngon ngu dang chon."""
    text = tpl.format(**vars)
    return {"type": kind, "message" if kind != "status" else "text": text, "tpl": tpl, "vars": vars}


def build_system_prompt(cfg: cfgmod.Config, skills: dict, workdir, summary: str = "", sid: str | None = None, has_planning: bool = False) -> str:
    ws = cfg.workspace_path()
    parts = []
    for name in PROMPT_FILES:
        p = ws / name
        if p.exists() and p.read_text().strip():
            parts.append(f"## {name}\n{p.read_text()[-4000:].strip()}")
    parts.append(f"Hiện tại: {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}.\n"
                 f"Thư mục làm việc của phiên này: {workdir}. Mọi file bạn tạo (script, dữ liệu trung gian, kết quả) hãy đặt ở đây; "
                 "đường dẫn tương đối được tính từ thư mục này và người dùng nhìn thấy chúng trong panel Workspace. "
                 "Khi cần nhớ chuyện đã nói trước đây, dùng tool memory_search.")
    if summary:
        parts.append(f"Tóm tắt phần hội thoại trước đó:\n{summary}")
    block = skillmod.prompt_block(skills)
    if block:
        parts.append(block)
    if sid and (plan := plans.prompt_block(sid)):
        parts.append(plan)
    if has_planning:
        parts.append("Với việc phức tạp nhiều bước: lập kế hoạch bằng plan_set trước rồi làm lần lượt. Việc cần chuyên môn riêng hoặc làm song song: giao cho agent con bằng delegate. Việc rất dài: task_start để chạy nền.")
    return "\n\n".join(parts)


def _augment(m: dict) -> dict:
    """Them dong liet ke tep dinh kem vao noi dung gui cho model."""
    if m["role"] == "user" and m.get("attachments"):
        return {"role": "user", "content": f"{m['content']}\n\n[Tệp đính kèm trong thư mục làm việc: {', '.join(m['attachments'])}]"}
    return {k: v for k, v in m.items() if k not in ("attachments", "_id")}


def _images(workdir, names: list[str]) -> list[dict]:
    out = []
    for n in names:
        try:
            p = workfiles.safe_path(workdir, n)
        except workfiles.PathError:
            continue
        if p.suffix.lower() in IMAGE_EXT and p.is_file() and p.stat().st_size <= MAX_IMAGE_BYTES and len(out) < MAX_IMAGES:
            out.append({"mime": mimetypes.guess_type(p.name)[0] or "image/png", "b64": base64.b64encode(p.read_bytes()).decode()})
    return out


PERMISSIONS = ("default", "readonly", "guarded", "full")
READONLY_BLOCKED = {"write", "edit", "remember", "http_request", "generate_image", "browser_click", "browser_type", "browser_press", "task_start"} | {
    "computer_screenshot", "computer_click", "computer_type", "computer_key", "computer_move", "computer_scroll"}
READONLY_NOTE = "Chế độ CHỈ ĐỌC: bạn không được ghi/sửa file, chạy lệnh shell hay thay đổi dữ liệu; các tool đó đã bị tắt. Hãy chỉ đọc và tra cứu."


def apply_permission(ctx: tools.ToolContext, mode: str) -> str:
    """Che do quyen cho mot hoi thoai. Tra ve doan nhac them cho system prompt (co the rong)."""
    if mode == "readonly":
        every = {**tools.TOOLS, **ctx.extra}
        blocked = {n for n, t in every.items() if t.risk == "exec" or n in READONLY_BLOCKED or (t.risk == "mcp" and not t.read_only)}
        ctx.enabled = {**ctx.enabled, **{n: False for n in blocked}}
        return READONLY_NOTE
    if mode == "guarded":
        ctx.confirm_exec = ctx.confirm_writes = True
    elif mode == "full":
        ctx.confirm_exec, ctx.full_access = False, True
    return ""


STALE_CHARS = 800  # ket qua cong cu cu hon luot hien tai: dai hon muc nay thi bi rut gon khi gui cho model
STALE_BROWSER_CHARS = 350  # anh chup trang cu da bi trang moi thay the, chi can nho tieu de/URL


def shrink_stale(messages: list[dict]) -> list[dict]:
    """Rut gon ket qua cong cu cu (chi ban gui di, khong sua lich su da luu). Ket qua cua luot goi cong cu gan nhat giu nguyen."""
    last = max((i for i, m in enumerate(messages) if m["role"] == "assistant" and m.get("tool_calls")), default=-1)
    names = {c["id"]: c["name"] for m in messages if m.get("tool_calls") for c in m["tool_calls"]}
    out = []
    for i, m in enumerate(messages):
        if m["role"] == "tool" and i < last:
            limit = STALE_BROWSER_CHARS if names.get(m.get("tool_call_id", ""), "").startswith("browser_") else STALE_CHARS
            c = m["content"]
            if len(c) > limit:
                m = {**m, "content": c[:limit].rstrip() + f"\n…(đã rút gọn {len(c) - limit} ký tự của kết quả cũ; gọi lại công cụ nếu cần)"}
        out.append(m)
    return out


MENTION = re.compile(r"(?<![\w@./-])@([a-z0-9][a-z0-9_-]{0,30})(?![\w@-])")  # @notion, khong khop dia chi email (a@b.com)


def mentioned_servers(text: str, cfg) -> list[str]:
    """Ten MCP server duoc goi bang dau @ trong tin nhan (chi nhung ten dang co trong cau hinh)."""
    return list(dict.fromkeys(n for n in MENTION.findall(text or "") if n in cfg.mcp_servers))


def apply_mentions(ctx: tools.ToolContext, names: list[str]) -> tuple[str, list[str]]:
    """Nguoi dung goi dich vu bang @: chi giu cong cu cua cac dich vu do (do ton token, do chon nham) va nhac agent dung chung.
    Tra ve (doan nhac cho system prompt, cac dich vu chua ket noi)."""
    live = mcp_client.manager.status()
    prefix = {n: re.sub(r"[^a-zA-Z0-9_-]", "_", n) + "__" for n in names}
    ctx.enabled = {**ctx.enabled, **{t: False for t in ctx.extra if not any(t.startswith(p) for p in prefix.values())}}
    down = [n for n in names if live.get(n, {}).get("status") != "connected"]
    note = ("Người dùng chỉ định dịch vụ bằng dấu @: " + ", ".join(f"@{n}" for n in names) + ". Hãy làm yêu cầu bằng các công cụ có tên bắt đầu bằng "
            + ", ".join(f"'{prefix[n]}'" for n in names) + "; không dùng công cụ của dịch vụ khác.")
    if down:
        note += " Dịch vụ chưa kết nối: " + ", ".join(down) + ". Nếu không có công cụ tương ứng, hãy bảo người dùng vào Kết nối, tab MCP dịch vụ, rồi bấm Đăng nhập."
    return note, down


def _window(history: list[dict], limit: int) -> list[dict]:
    rest = history[-limit:]
    while rest and (rest[0]["role"] == "tool" or rest[0].get("tool_calls")):
        rest = rest[1:]
    return rest


def _stream_with_retry(name: str, pcfg: cfgmod.ProviderCfg, messages: list[dict], schemas: list[dict],
                       emit: Callable[[dict], None], cancel: Event | None, effort: str | None = None) -> Iterator[dict]:
    delay = 1.5
    for attempt in range(RETRIES):
        started = False
        try:
            for ev in make_provider(pcfg).stream(messages, schemas, effort=effort):
                if ev["type"] in ("delta", "thinking"):
                    started = True
                yield ev
            return
        except ProviderError as e:
            if started or not e.retryable or attempt == RETRIES - 1:
                raise
            emit(ui_event("notice", "{name} đang bận ({status}), thử lại sau {delay}s (lần {attempt}/{total})",
                          name=name, status=e.status or "timeout", delay=round(delay), attempt=attempt + 2, total=RETRIES))
            waited = 0.0
            while waited < delay and not (cancel and cancel.is_set()):
                time.sleep(0.25)
                waited += 0.25
            delay *= 2


def run_turn(sid: str, user_text: str, provider: str | None, approver: Callable[[str, str], bool],
             emit: Callable[[dict], None], cancel: Event | None = None, only_tools: list[str] | None = None,
             source: str = "chat", attachments: list[str] | None = None, permission: str = "default", effort: str | None = None,
             system_extra: str = "", max_steps: int | None = None, depth: int = 0, job_id: str | None = None, workdir_sid: str | None = None) -> None:
    cfg = cfgmod.load()
    skills = skillmod.discover(cfg)
    workdir = workfiles.session_dir(cfg, workdir_sid or sid)  # agent con/viec nen dung chung thu muc voi phien da giao viec
    workdir.mkdir(parents=True, exist_ok=True)
    decision: dict[str, str] = {}

    def recording_approver(kind: str, detail: str) -> bool:
        ok = approver(kind, detail)
        decision["last"] = "approved" if ok else "denied"
        return ok

    ctx = tools.ToolContext(workspace=cfg.workspace_path(), cwd=workdir, approver=recording_approver, confirm_exec=cfg.agent.confirm_exec,
                            env=skillmod.env_for(skills, cfg), enabled=cfg.agent.tools_enabled, skills={n: s for n, s in skills.items() if s.active},
                            sandbox={"mode": cfg.agent.exec_sandbox, "image": cfg.agent.sandbox_image, "network": cfg.agent.sandbox_network})
    ctx.depth = depth
    # khong gui dinh nghia cua cong cu khong dung duoc (moi cong cu ton ~100 token o MOI luot goi mo hinh)
    hidden = [n for n in tools.TOOLS if (n.startswith("computer_") and not cfg.computer.enabled) or (n.startswith("browser_") and not cfg.browser.enabled)]
    ctx.enabled = {**ctx.enabled, **{n: False for n in hidden}}
    ctx.session_id, ctx.permission, ctx.provider, ctx.emit, ctx.cancel = sid, permission if permission in ("default", "readonly", "guarded", "full") else "default", provider, emit, cancel
    ctx.extra = mcp_client.manager.tool_defs()
    if only_tools is not None:  # gioi han tool cho rieng luot nay (dung cho API ben ngoai)
        ctx.enabled = {n: n in only_tools for n in [*tools.TOOLS, *ctx.extra]}
    mention_note = ""
    if names_at := mentioned_servers(user_text, cfg):
        mention_note, down = apply_mentions(ctx, names_at)
        if down:
            emit(ui_event("notice", "Dịch vụ {names} chưa kết nối: vào Kết nối, tab MCP dịch vụ để đăng nhập", names=", ".join(down)))
    if permission not in PERMISSIONS:
        permission = "default"
    perm_note = apply_permission(ctx, permission)
    first = provider if provider in cfg.providers else cfg.default_provider
    names = [first] + [n for n in cfg.fallback if n != first and n in cfg.providers]

    emit(ui_event("status", "Đang chuẩn bị…"))
    if compaction.maybe_compact(sid, cfg, first):
        emit(ui_event("notice", "Đã tóm tắt phần đầu hội thoại để tiết kiệm bộ nhớ của model"))
    sess = sessions.get(sid) or {}
    history = sessions.messages(sid, after_id=sess.get("summary_upto", 0))
    attachments = attachments or []
    user_msg = {"role": "user", "content": user_text}
    if attachments:
        user_msg["attachments"] = attachments
    sessions.add_message(sid, user_msg)
    current = _augment(user_msg)
    if attachments and cfg.providers[first].vision:
        current["images"] = _images(workdir, attachments)
    has_planning = "plan_set" in tools.TOOLS and ctx.enabled.get("plan_set", True)
    system = build_system_prompt(cfg, skills, workdir, sess.get("summary", ""), sid, has_planning) + (f"\n\n{perm_note}" if perm_note else "") + (f"\n\n{mention_note}" if mention_note else "") + (f"\n\n{system_extra}" if system_extra else "")
    messages = [{"role": "system", "content": system}] \
        + [_augment(m) for m in _window(history, cfg.agent.max_history)] + [current]

    limit = max_steps or cfg.agent.max_steps
    for step in range(limit):
        if cancel and cancel.is_set():
            return
        result = None
        for name in names:
            pcfg = cfg.providers[name]
            t0, started = time.time(), False
            emit(ui_event("status", "Đang gọi {name} · {model}…", name=name, model=pcfg.model) if step == 0
                 else ui_event("status", "{name} đang xử lý kết quả tool…", name=name))
            try:
                for ev in _stream_with_retry(name, pcfg, shrink_stale(messages), tools.schemas(ctx), emit, cancel, effort):
                    if ev["type"] in ("delta", "thinking"):
                        started = True
                        emit(ev)
                    else:
                        result = ev
                u = result["usage"]
                usage.record_llm(name, pcfg.model, u["prompt"], u["completion"], int((time.time() - t0) * 1000), True, sid)
                result["provider"] = name
                break
            except ProviderError as e:
                usage.record_llm(name, pcfg.model, 0, 0, int((time.time() - t0) * 1000), False, sid)
                if started or name == names[-1]:
                    emit({"type": "error", "message": f"{name}: {e}"})
                    return
                emit(ui_event("notice", "{name} lỗi ({error}), chuyển sang provider dự phòng", name=name, error=str(e)[:200]))
        msg = {"role": "assistant", "content": result["content"]}
        if result["tool_calls"]:
            msg["tool_calls"] = result["tool_calls"]
        messages.append(msg)
        sessions.add_message(sid, msg)
        if result["content"] or not result["tool_calls"]:
            emit({"type": "assistant", "content": result["content"], "provider": result["provider"], "usage": result["usage"],
                  "duration_ms": int((time.time() - t0) * 1000)})
        if not result["tool_calls"]:
            return
        parallel = {}  # nhieu delegate trong cung mot luot => chay dong thoi
        delegates = [c for c in result["tool_calls"] if c["name"] == "delegate"]
        if len(delegates) > 1:
            from concurrent.futures import ThreadPoolExecutor

            pool = ThreadPoolExecutor(max_workers=min(len(delegates), cfg.agents.max_parallel + 4))
            for c in delegates:
                emit({"type": "tool", "id": c["id"], "name": c["name"], "args": c["args"], "risk": "agent"})
            parallel = {c["id"]: (pool.submit(tools.call, ctx, c["name"], c["args"]), time.time()) for c in delegates}
        for c in result["tool_calls"]:
            if cancel and cancel.is_set():
                return
            tdef = tools.TOOLS.get(c["name"]) or ctx.extra.get(c["name"])
            if c["id"] not in parallel:
                emit({"type": "tool", "id": c["id"], "name": c["name"], "args": c["args"], "risk": tdef.risk if tdef else "unknown"})
            decision.clear()
            t0 = time.time()
            if c["id"] in parallel:
                (fut, t0) = parallel[c["id"]]
                out, ok = fut.result()
            else:
                out, ok = tools.call(ctx, c["name"], c["args"])
            ms = int((time.time() - t0) * 1000)
            usage.record_tool(c["name"], ok, ms, sid)
            dec = decision.get("last") or ("full_access" if permission == "full" and tdef and tdef.risk in ("exec", "mcp", "file", "network") else "auto")
            audit.record(sid, source, c["name"], c["args"], dec, ok, ms, out)
            nudge = ""
            if not c["name"].startswith("plan_"):
                if (items := plans.auto_advance(sid)) is not None:
                    emit({"type": "plan", "items": items})
                nudge = plans.hint(sid)  # chi gui cho model
            tmsg = {"role": "tool", "tool_call_id": c["id"], "content": out + nudge}
            messages.append(tmsg)
            sessions.add_message(sid, tmsg)
            emit({"type": "tool_result", "id": c["id"], "result": out[:4000], "ok": ok, "duration_ms": ms, "decision": dec})
            emit({"type": "files"})
    emit(ui_event("error", "Vượt quá số bước tối đa ({n})", n=limit))
