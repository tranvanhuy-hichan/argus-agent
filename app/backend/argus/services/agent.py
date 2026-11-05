"""Vong lap agent: dung prompt, goi LLM (stream, tu thu lai), chay tool, ghi lich su va nhat ky."""
import base64
import re
import mimetypes
import time
from pathlib import Path
from collections.abc import Callable, Iterator
from datetime import datetime
from threading import Event

from ..core import config as cfgmod
from . import audit, checkpoints, commands, compaction, knowledge, mcp_client, tools_kb, plans, sessions, skills as skillmod, tools, usage, workfiles
from .providers import ProviderError, make_provider

PROMPT_FILES = ("SOUL.md", "USER.md", "MEMORY.md")
RETRIES = 4  # tong so lan thu cho loi tam thoi (429/503/timeout)
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_IMAGES, MAX_IMAGE_BYTES = 4, 5 * 1024 * 1024


def ui_event(kind: str, tpl: str, **vars) -> dict:
    """Su kien hien cho nguoi dung: `tpl` la mau tieng Viet co {bien}; giao dien tu dich theo ngon ngu dang chon."""
    text = tpl.format(**vars)
    return {"type": kind, "message" if kind != "status" else "text": text, "tpl": tpl, "vars": vars}


def knowledge_note() -> str:
    """Có tài liệu trong kho thì nhắc agent dùng kb_search và luôn trích nguồn."""
    if not knowledge.has_docs():
        return ""
    s = knowledge.stats()
    return (f"Người dùng đã thêm {s['docs']} tài liệu vào kho. Chỉ dùng tool kb_search khi câu hỏi rõ ràng nói về nội dung tài liệu của họ (nhắc tới tài liệu, hợp đồng, báo cáo, bảng tính, tài liệu nội bộ, hoặc một chủ đề chỉ có trong đó). "
            "KHÔNG dùng kb_search cho chào hỏi, trò chuyện, kiến thức chung, ngày giờ, thời tiết, tin tức, sự kiện, lễ hội: những câu đó hãy trả lời trực tiếp hoặc dùng công cụ web. "
            "Khi đã dùng kb_search thì chỉ dựa vào các đoạn tìm được. Sau mỗi ý, chèn nguyên văn thẻ nguồn [[src:...]] của đoạn bạn dựa vào (lấy từ kết quả kb_search), đặt ở cuối câu; không viết lại tên file, không bọc thẻ trong ngoặc hay dấu * . "
            "Nếu không tìm thấy, nói rõ là tài liệu không đề cập, không tự bịa.")


DOCS_PROMPT = ("CHẾ ĐỘ HỎI TỪ TÀI LIỆU. Chỉ trả lời dựa trên kho tài liệu của người dùng: LUÔN gọi kb_search trước (có thể gọi nhiều lần với cách diễn đạt khác để tìm đủ), "
               "rồi trả lời ngắn gọn, đúng trọng tâm bằng ngôn ngữ của người dùng. Sau mỗi ý, chèn nguyên văn thẻ nguồn [[src:...]] của đoạn bạn dựa vào (lấy từ kết quả kb_search), đặt ở cuối câu; không viết lại tên file, không bọc thẻ trong ngoặc hay dấu *. Trình bày gọn: tiêu đề ngắn, gạch đầu dòng, không lặp lại cùng một thẻ nhiều lần liên tiếp. "
               "Nếu các đoạn tìm được không có thông tin, nói rõ \"tài liệu không đề cập\" và gợi ý người dùng hỏi lại hoặc thêm tài liệu; tuyệt đối không bịa.")

CODING_DOCS = ("AGENTS.md", "CLAUDE.md", "README.md")


AUTONOMY = ("Cách làm việc: hãy tự quyết và làm cho xong, đừng dừng lại hỏi người dùng những điều bạn tự suy ra được hoặc tự tra được bằng tool "
            "(đọc file, tìm kiếm, chạy thử). Chỉ hỏi khi thiếu thông tin thật sự không thể đoán và sai sẽ tốn công làm lại; khi đó hỏi MỘT câu ngắn kèm lựa chọn bạn đề xuất. "
            "Không xin phép cho từng bước nhỏ, không hỏi \"bạn có muốn tôi tiếp tục không\". Việc nhiều bước thì làm liền một mạch rồi báo kết quả. "
            "Gặp lỗi thì tự đọc lỗi, sửa và thử lại vài lần trước khi báo cáo. Gọi nhiều tool độc lập trong cùng một lượt khi có thể. "
            "Trước khi báo xong, TỰ KIỂM CHỨNG kết quả: chạy lại/mở lại thứ vừa làm (test, file vừa tạo, trang web, số liệu) và đối chiếu với yêu cầu ban đầu; chưa kiểm chứng được thì nói rõ. "
            "Khi cần hỏi người dùng, dùng tool ask_user với vài lựa chọn bấm nhanh thay vì viết câu hỏi dài. Tiến trình chạy lâu (dev server, watcher) dùng exec_bg/exec_read/exec_stop.")


def coding_prompt(project, workspace=None) -> str:
    """Chế độ Code: thư mục làm việc là một dự án thật của người dùng."""
    text = (f"CHẾ ĐỘ LẬP TRÌNH. Thư mục làm việc là dự án của người dùng: {project}. Làm việc như một kỹ sư cẩn thận: "
            "khám phá trước (list_dir, glob, grep để tìm đúng chỗ, rồi read file liên quan), sửa nhỏ và đúng chỗ (dùng edit thay vì ghi đè cả file), giữ phong cách code hiện có, "
            "tự tìm cách chạy test/lint/build của dự án (package.json, pyproject, Makefile...) và chạy sau mỗi thay đổi, đọc kết quả để tự sửa lỗi cho đến khi qua. "
            "Việc lớn thì lập kế hoạch bằng plan_set trước. Đừng hỏi lại những gì có thể xem trong code. Không xóa file, không đổi git (commit, push, reset) "
            "trừ khi người dùng yêu cầu rõ; người dùng đã có nút Git trong chat để tự tạo nhánh, commit và push nên đừng tự làm. Nếu được nhờ commit thì chỉ `git add` đúng các file bạn đã sửa (không `git add -A`), không force push, không commit thẳng lên main/master. Cuối cùng báo ngắn gọn đã đổi gì; người dùng xem diff ở tab Thay đổi.")
    if workspace is not None:
        np = tools.project_notes_path(workspace, project)
        if np.is_file():
            text += f"\n\n## Ghi nhớ của bạn về dự án này (project_note)\n{np.read_text(errors='replace')[-2000:].strip()}"
        text += "\nKhi học được điều hữu ích về dự án (cách chạy test, quy ước, cấu trúc), ghi lại bằng project_note."
    for name in CODING_DOCS:
        p = Path(project) / name
        if p.is_file():
            try:
                text += f"\n\n## {name} của dự án\n{p.read_text(errors='replace')[:3000].strip()}"
            except OSError:
                pass
            break  # một tài liệu là đủ; AGENTS.md/CLAUDE.md được ưu tiên
    return text


def build_system_prompt(cfg: cfgmod.Config, skills: dict, workdir, summary: str = "", sid: str | None = None, has_planning: bool = False, coding: bool = False) -> str:
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
    if kb_note := knowledge_note():
        parts.append(kb_note)
    if note := tools.shell_note():
        parts.append(note)
    parts.append(AUTONOMY)
    if coding:
        parts.append(coding_prompt(workdir, ws))
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


MENTION_RE = re.compile(r"(?<![\w@])@([\w][\w./-]*)")


def _mentioned_paths(text: str, workdir) -> list[str]:
    """`@duong/dan` trong tin nhan tro toi file/thu muc co that trong thu muc lam viec (khong the thoat ra ngoai)."""
    out: list[str] = []
    if workdir is None:
        return out
    for m in MENTION_RE.finditer(text):
        rel = m.group(1).rstrip(".")
        try:
            p = workfiles.safe_path(Path(workdir), rel)
        except workfiles.PathError:
            continue
        if p.exists() and rel not in out:
            out.append(rel + ("/" if p.is_dir() else ""))
    return out[:10]


def _augment(m: dict, workdir=None) -> dict:
    """Them dong liet ke tep dinh kem / tep duoc @nhac toi, va mo rong lenh `/` dung san, vao noi dung gui cho model."""
    if m["role"] != "user":
        return {k: v for k, v in m.items() if k not in ("attachments", "_id")}
    content = commands.expand(m["content"]) or m["content"]
    if m.get("attachments"):
        content = f"{content}\n\n[Tệp đính kèm trong thư mục làm việc: {', '.join(m['attachments'])}]"
    if mentioned := _mentioned_paths(m["content"], workdir):
        content += f"\n\n[Người dùng nhắc tới các tệp/thư mục này bằng @: {', '.join(mentioned)}. Hãy đọc chúng (read/list_dir/grep) trước khi làm.]"
    return {"role": "user", "content": content} if content != m["content"] else {k: v for k, v in m.items() if k not in ("attachments", "_id")}


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


_HARD = re.compile(r"(code|script|file|tệp|tập tin|sửa|viết|tạo|chạy|cài|lỗi|bug|debug|build|test|tìm|phân tích|so sánh|báo cáo|excel|pdf|docx|web|http|```)", re.I)


def is_simple(text: str, attachments, in_project: bool, only_tools) -> bool:
    """Cau ngan, khong dinh kem, khong co dau hieu can cong cu/viec nang: dung duoc model nhanh."""
    return not (attachments or in_project or only_tools is not None) and len(text) <= 140 and text.count("\n") < 2 and not _HARD.search(text)


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
        note += " Dịch vụ chưa kết nối: " + ", ".join(down) + ". Nếu không có công cụ tương ứng, hãy bảo người dùng vào mục Tiện ích, tìm dịch vụ đó rồi bấm Đăng nhập."
    return note, down


def _window(history: list[dict], limit: int) -> list[dict]:
    rest = history[-limit:]
    while rest and (rest[0]["role"] == "tool" or rest[0].get("tool_calls")):
        rest = rest[1:]
    return rest


def _stream_with_retry(name: str, pcfg: cfgmod.ProviderCfg, messages: list[dict], schemas: list[dict],
                       emit: Callable[[dict], None], cancel: Event | None, effort: str | None = None,
                       temperature: float | None = None, max_tokens: int | None = None) -> Iterator[dict]:
    delay = 1.5
    for attempt in range(RETRIES):
        started = False
        try:
            prov = make_provider(pcfg)
            prov.cancel = cancel  # CLI provider dung de kill tien trinh ngay khi bam Dung
            kwargs = {}
            if effort is not None:
                kwargs["effort"] = effort
            if temperature is not None:
                kwargs["temperature"] = temperature
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            import inspect
            sig = inspect.signature(prov.stream)
            if not any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
            gen = prov.stream(messages, schemas, **kwargs)
            try:
                for ev in gen:
                    if cancel and cancel.is_set():
                        return  # bam Dung: bo luong dang doc (dong ket noi / kill CLI)
                    if ev["type"] in ("delta", "thinking"):
                        started = True
                    yield ev
            finally:
                close = getattr(gen, "close", None)
                if close:
                    close()
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
             system_extra: str = "", max_steps: int | None = None, depth: int = 0, job_id: str | None = None, workdir_sid: str | None = None,
             use_docs: bool = False, docs_pre: str | None = None, temperature: float | None = None, max_tokens: int | None = None,
             asker: Callable[[str, list[str]], str] | None = None) -> None:
    cfg = cfgmod.load()
    skills = skillmod.discover(cfg)
    workdir = workfiles.workdir_for(cfg, workdir_sid or sid)  # agent con/viec nen dung chung thu muc voi phien da giao viec
    project = (sessions.get(workdir_sid or sid) or {}).get("project") or ""
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
    ctx.asker = asker
    if depth == 0:
        checkpoints.begin(sid)
    ctx.project = workdir if project else None
    # khong gui dinh nghia cua cong cu khong dung duoc (moi cong cu ton ~100 token o MOI luot goi mo hinh)
    hidden = [n for n in tools.TOOLS if (n.startswith("computer_") and not cfg.computer.enabled) or (n.startswith("browser_") and not cfg.browser.enabled)]
    if not knowledge.has_docs():
        hidden.append("kb_search")
    ctx.enabled = {**ctx.enabled, **{n: False for n in hidden}}
    ctx.session_id, ctx.permission, ctx.provider, ctx.emit, ctx.cancel = sid, permission if permission in ("default", "readonly", "guarded", "full") else "default", provider, emit, cancel
    ctx.extra = mcp_client.manager.tool_defs()
    if use_docs and not knowledge.has_docs():
        emit(ui_event("notice", "Chưa có tài liệu nào sẵn sàng nên Argus trả lời như bình thường"))
    elif use_docs:  # "Hỏi từ tài liệu": chỉ cho dùng công cụ tìm tài liệu, trả lời có nguồn
        only_tools = only_tools if only_tools is not None else ["kb_search"]
        emit(ui_event("status", "Đang tìm trong tài liệu…"))
        found = docs_pre if docs_pre is not None else tools_kb.format_hits(knowledge.search(user_text, 6))  # tìm sẵn trước khi hỏi model: bớt được một lượt gọi model
        pre = (f"\n\nCác đoạn tài liệu liên quan tới câu hỏi (đã tìm sẵn):\n{found}\n\nNếu các đoạn trên đủ để trả lời thì trả lời ngay, không cần gọi kb_search; "
               "chỉ gọi thêm kb_search (với từ khóa khác) khi còn thiếu thông tin.") if found else ""
        system_extra = f"{system_extra}\n\n{DOCS_PROMPT}{pre}".strip()
    if only_tools is not None:  # gioi han tool cho rieng luot nay (dung cho API ben ngoai)
        ctx.enabled = {n: n in only_tools for n in [*tools.TOOLS, *ctx.extra]}
    mention_note = ""
    if names_at := mentioned_servers(user_text, cfg):
        mention_note, down = apply_mentions(ctx, names_at)
        if down:
            emit(ui_event("notice", "Dịch vụ {names} chưa kết nối: vào mục Tiện ích để đăng nhập", names=", ".join(down)))
    if permission not in PERMISSIONS:
        permission = "default"
    perm_note = apply_permission(ctx, permission)
    first = provider if provider in cfg.providers else cfg.default_provider
    if first == cfg.default_provider and cfg.agent.fast_provider in cfg.providers and cfg.agent.fast_provider != first and is_simple(user_text, attachments, bool(project), only_tools):
        first = cfg.agent.fast_provider  # cau don gian: dung model nhanh/re de tiet kiem
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
    current = _augment(user_msg, workdir)
    if attachments and cfg.providers[first].vision:
        current["images"] = _images(workdir, attachments)
    has_planning = "plan_set" in tools.TOOLS and ctx.enabled.get("plan_set", True)
    system = build_system_prompt(cfg, skills, workdir, sess.get("summary", ""), sid, has_planning, bool(project)) + (f"\n\n{perm_note}" if perm_note else "") + (f"\n\n{mention_note}" if mention_note else "") + (f"\n\n{system_extra}" if system_extra else "")
    messages = [{"role": "system", "content": system}] \
        + [_augment(m, workdir) for m in _window(history, cfg.agent.max_history)] + [current]

    limit = max_steps or cfg.agent.max_steps
    empty_retries = 0
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
                for ev in _stream_with_retry(name, pcfg, shrink_stale(messages), tools.schemas(ctx), emit, cancel, effort, temperature=temperature, max_tokens=max_tokens):
                    if ev["type"] in ("delta", "thinking"):
                        started = True
                        emit(ev)
                    else:
                        result = ev
                if cancel and cancel.is_set():
                    emit(ui_event("notice", "Đã dừng"))
                    return
                u = result["usage"]
                usage.record_llm(name, pcfg.model, u["prompt"], u["completion"], int((time.time() - t0) * 1000), True, sid)
                result["provider"] = name
                break
            except ProviderError as e:
                if cancel and cancel.is_set():
                    emit(ui_event("notice", "Đã dừng"))
                    return
                usage.record_llm(name, pcfg.model, 0, 0, int((time.time() - t0) * 1000), False, sid)
                if started or name == names[-1]:
                    emit({"type": "error", "message": f"{name}: {e}"})
                    return
                emit(ui_event("notice", "{name} lỗi ({error}), chuyển sang provider dự phòng", name=name, error=str(e)[:200]))
        if not result["content"].strip() and not result["tool_calls"] and empty_retries < 2:
            # model tra ve rong (hay gap sau khi nhan ket qua tool): nhac no viet cau tra loi thay vi dung im lang
            empty_retries += 1
            messages.append({"role": "user", "content": "[system] Your last reply was empty. Using the tool results above, write the final answer to the user now (or call the next tool if you still need one, using the host tool-call format; your own built-in tools are not available)."})
            continue
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
