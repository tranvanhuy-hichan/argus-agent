"""Tool điều khiển trình duyệt (Chromium qua Playwright). Tải playwright lười, import module này không bao giờ lỗi.

Tải xuống bị chặn (accept_downloads=False). Hộp thoại JS tự đóng, nội dung được báo ở kết quả kế tiếp.
"""
from __future__ import annotations

import ipaddress
import time
from urllib.parse import urlparse

from ..core import config as cfgmod
from .browser import manager
from .tools import DENIED, ToolContext, _check_url, tool

MAX_ELEMS = 80
BAD_SCHEMES = ("file", "chrome", "about", "javascript", "data", "view-source", "blob", "ftp")

SNAP_JS = r"""
() => {
  document.querySelectorAll('[data-argus-ref]').forEach(e => e.removeAttribute('data-argus-ref'));
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[contenteditable=""],[contenteditable="true"],[role=button],[role=link],[role=checkbox],[role=tab],[role=menuitem]';
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const clip = (t, n=80) => (t || '').replace(/\s+/g, ' ').trim().slice(0, n);
  const out = []; let n = 0;
  for (const e of document.querySelectorAll(sel)) {
    if (out.length >= %d) break;
    if (!vis(e)) continue;
    const tag = e.tagName.toLowerCase(); const type = (e.getAttribute('type') || '').toLowerCase();
    let role = e.getAttribute('role') || '';
    if (!role) {
      if (tag === 'a') role = 'link';
      else if (tag === 'button' || (tag === 'input' && ['button','submit','reset','image'].includes(type))) role = 'button';
      else if (tag === 'input' && type === 'checkbox') role = 'checkbox';
      else if (tag === 'input' && type === 'radio') role = 'radio';
      else if (tag === 'select') role = 'combobox';
      else if (tag === 'summary') role = 'summary';
      else if (tag === 'input' || tag === 'textarea' || e.isContentEditable) role = 'textbox';
      else role = tag;
    }
    let name = e.getAttribute('aria-label');
    if (!name && e.labels && e.labels.length) name = e.labels[0].innerText;
    if (!name && e.id) { const l = document.querySelector('label[for="' + CSS.escape(e.id) + '"]'); if (l) name = l.innerText; }
    if (!name) name = e.getAttribute('placeholder');
    if (!name && !(tag === 'input' || tag === 'textarea')) name = e.innerText;
    if (!name) name = e.getAttribute('title') || e.getAttribute('alt');
    if (!name) { const im = e.querySelector && e.querySelector('img[alt]'); if (im) name = im.getAttribute('alt'); }
    if (!name) name = e.getAttribute('value') || e.getAttribute('name');
    n++; const ref = 'e' + n; e.setAttribute('data-argus-ref', ref);
    const o = {ref, role, name: clip(name), type};
    if (tag === 'input' || tag === 'textarea') o.value = type === 'password' ? '••••' : clip(e.value, 60);
    else if (tag === 'select') o.value = clip(e.options[e.selectedIndex] ? e.options[e.selectedIndex].text : '', 60);
    if (type === 'checkbox' || type === 'radio' || e.getAttribute('aria-checked') === 'true') o.checked = !!(e.checked || e.getAttribute('aria-checked') === 'true');
    if (e.disabled) o.disabled = true;
    if (tag === 'a') o.href = clip(e.getAttribute('href'), 100);
    out.push(o);
  }
  return {title: document.title, url: location.href, text: (document.body ? document.body.innerText : '').slice(0, 20000), elems: out};
}
""" % MAX_ELEMS


# ---------- tiện ích
def validate_url(url: str, allow_private: bool, resolve: bool = True) -> None:
    """Chỉ cho http/https (và about:blank); chặn địa chỉ nội bộ nếu không allow_private."""
    u = urlparse((url or "").strip())
    if u.scheme == "about" and url.strip() == "about:blank":
        return
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("chỉ hỗ trợ URL http/https (không mở file:, chrome:, about: …)")
    if allow_private:
        return
    host = u.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise PermissionError("chặn truy cập địa chỉ nội bộ (localhost); bật browser.allow_private nếu cần")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise PermissionError(f"chặn truy cập địa chỉ nội bộ ({ip}); bật browser.allow_private nếu cần")
    except ValueError:
        pass
    if resolve:
        try:
            _check_url(url)
        except PermissionError as e:
            raise PermissionError(f"{e}; bật browser.allow_private nếu cần") from None


def _cfg():
    c = cfgmod.load().browser
    if not c.enabled:
        raise RuntimeError("Trình duyệt đang tắt (browser.enabled = false trong cấu hình).")
    return c


def _run(ctx: ToolContext, fn, timeout: float = 60):
    _cfg()
    return manager.with_session(ctx.session_id or "default", fn, timeout, ctx.cancel)


def _need_ok(ctx: ToolContext, what: str, url_hint: str = "") -> bool:
    if not (ctx.confirm_writes and not ctx.full_access):
        return True
    url = url_hint or _run(ctx, lambda s: s.current().url)
    return bool(ctx.approve("browser", f"{what} (trang: {url})"))


def _settle(page, ms: int = 3000) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=ms)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(0.3)


def _guard_final(s, allow_private: bool) -> None:
    """Kiểm tra lại URL hiện tại (sau redirect/điều hướng)."""
    page = s.current()
    try:
        validate_url(page.url, allow_private)
    except Exception:
        try:
            page.goto("about:blank")
        except Exception:  # noqa: BLE001
            pass
        raise


def _snapshot(s, allow_private: bool, full: bool = True) -> str:
    page = s.current()
    _guard_final(s, allow_private)
    d = page.evaluate(SNAP_JS)
    lines = [f"Trang: {d['title'] or '(không tiêu đề)'}", f"URL: {d['url']}"]
    if s.dialogs:
        lines.append("Hộp thoại JS đã tự đóng: " + " | ".join(s.dialogs))
        s.dialogs.clear()
    if len(s.pages) > 1:
        lines.append(f"Số tab: {len(s.pages)} (đang ở tab mới nhất)")
    text = "\n".join(ln.strip() for ln in d["text"].splitlines() if ln.strip())
    limit = 4000 if full else 1500
    lines.append("Nội dung:\n" + (text[:limit] + ("…" if len(text) > limit else "")))
    el = []
    for o in d["elems"]:
        t = f'[{o["ref"]}] {o["role"]} "{o["name"]}"'
        if "value" in o:
            t += f' value="{o["value"]}"'
        if "checked" in o:
            t += " checked" if o["checked"] else " unchecked"
        if o.get("disabled"):
            t += " disabled"
        if o.get("href"):
            t += f' -> {o["href"]}'
        el.append(t)
    lines.append("Phần tử tương tác:\n" + ("\n".join(el) if el else "(không có)"))
    if len(d["elems"]) >= MAX_ELEMS:
        lines.append(f"(chỉ liệt kê {MAX_ELEMS} phần tử đầu; cuộn rồi gọi browser_snapshot để xem tiếp)")
    return "\n".join(lines)


def _loc(s, ref: str):
    ref = (ref or "").strip().strip("[]")
    page = s.current()
    loc = page.locator(f'[data-argus-ref="{ref}"]')
    if not ref or loc.count() == 0:
        raise ValueError(f'không có phần tử "{ref}": hãy gọi browser_snapshot để lấy lại danh sách ref (ref được gán lại sau mỗi snapshot).')
    return loc.first


def _after(s, allow_private: bool, msg: str) -> str:
    _settle(s.current())
    return f"{msg}\n\n{_snapshot(s, allow_private, full=False)}"


# ---------- tools
@tool("browser_open", "Mở một trang web (http/https) trong trình duyệt và trả về ảnh chụp văn bản của trang cùng các phần tử có thể bấm.",
      {"url": ("string", "địa chỉ http/https")}, risk="network")
def browser_open(ctx: ToolContext, url: str):
    c = _cfg()
    validate_url(url, c.allow_private)

    def job(s):
        page = s.current()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:  # noqa: BLE001
            if "ERR_ABORTED" not in str(e):  # tải xuống bị chặn cũng báo ERR_ABORTED
                raise
        _settle(page, 4000)
        return _snapshot(s, c.allow_private)
    return _run(ctx, job, 75)


@tool("browser_snapshot", "Xem lại trang hiện tại: tiêu đề, văn bản chính và danh sách phần tử tương tác với ref [eN].", {}, risk="network")
def browser_snapshot(ctx: ToolContext):
    c = _cfg()
    return _run(ctx, lambda s: _snapshot(s, c.allow_private))


@tool("browser_click", "Bấm vào một phần tử theo ref (lấy từ browser_snapshot).", {"ref": ("string", "ref như e3")}, risk="network")
def browser_click(ctx: ToolContext, ref: str):
    c = _cfg()

    def desc(s):
        loc = _loc(s, ref)
        return (loc.get_attribute("aria-label") or loc.inner_text(timeout=2000) or ref).strip()[:60], s.current().url
    name, url = _run(ctx, desc)
    if not _need_ok(ctx, f'bấm "{name}" [{ref}]', url):
        return DENIED

    def job(s):
        _loc(s, ref).click(timeout=10000)
        return _after(s, c.allow_private, f"Đã bấm [{ref}].")
    return _run(ctx, job, 75)


@tool("browser_type", "Điền văn bản vào ô nhập theo ref; nếu submit=true thì nhấn Enter sau đó.",
      {"ref": ("string", "ref của ô nhập"), "text": ("string", "nội dung cần điền"), "submit": ("boolean", "nhấn Enter sau khi điền")},
      required=["ref", "text"], risk="network")
def browser_type(ctx: ToolContext, ref: str, text: str, submit: bool = False):
    c = _cfg()
    url = _run(ctx, lambda s: (_loc(s, ref), s.current().url)[1])
    if not _need_ok(ctx, f"nhập văn bản vào [{ref}]" + (" rồi Enter" if submit else ""), url):
        return DENIED

    def job(s):
        loc = _loc(s, ref)
        if loc.get_attribute("contenteditable") is not None and loc.evaluate("e => e.isContentEditable"):
            loc.click()
            s.current().keyboard.press("Control+A")
            s.current().keyboard.type(text)
        else:
            loc.fill(text, timeout=10000)
        if submit:
            loc.press("Enter")
            return _after(s, c.allow_private, f"Đã nhập vào [{ref}] và nhấn Enter.")
        pw = loc.get_attribute("type") == "password"
        return _after(s, c.allow_private, f"Đã nhập {len(text)} ký tự vào [{ref}]" + (" (mật khẩu, đã ẩn)." if pw else "."))
    return _run(ctx, job, 75)


@tool("browser_press", "Nhấn một phím trên trang (Enter, Tab, Escape, PageDown, ArrowDown…).", {"key": ("string", "tên phím")}, risk="network")
def browser_press(ctx: ToolContext, key: str):
    c = _cfg()
    if not _need_ok(ctx, f"nhấn phím {key}"):
        return DENIED

    def job(s):
        s.current().keyboard.press(key)
        return _after(s, c.allow_private, f"Đã nhấn {key}.")
    return _run(ctx, job)


@tool("browser_scroll", "Cuộn trang lên hoặc xuống.", {"direction": ("string", "up hoặc down"), "amount": ("integer", "số pixel (mặc định 600)")},
      required=["direction"], risk="network")
def browser_scroll(ctx: ToolContext, direction: str, amount: int = 600):
    c = _cfg()
    if direction not in ("up", "down"):
        raise ValueError('direction phải là "up" hoặc "down"')
    dy = abs(int(amount)) * (1 if direction == "down" else -1)

    def job(s):
        s.current().evaluate("dy => window.scrollBy(0, dy)", dy)
        return _after(s, c.allow_private, f"Đã cuộn {direction} {abs(dy)}px.")
    return _run(ctx, job)


@tool("browser_back", "Quay lại trang trước trong lịch sử.", {}, risk="network")
def browser_back(ctx: ToolContext):
    c = _cfg()

    def job(s):
        s.current().go_back(wait_until="domcontentloaded", timeout=10000)
        return _after(s, c.allow_private, "Đã quay lại.")
    return _run(ctx, job)


@tool("browser_text", "Lấy toàn bộ văn bản của trang, hoặc của một phần tử nếu có ref (tối đa ~12000 ký tự).",
      {"ref": ("string", "ref của phần tử (bỏ trống = cả trang)")}, required=[], risk="network")
def browser_text(ctx: ToolContext, ref: str = ""):
    c = _cfg()

    def job(s):
        _guard_final(s, c.allow_private)
        t = _loc(s, ref).inner_text(timeout=10000) if ref else s.current().inner_text("body", timeout=10000)
        t = "\n".join(ln.strip() for ln in t.splitlines() if ln.strip())
        return t[:12000] + ("\n…(đã cắt bớt)" if len(t) > 12000 else "")
    return _run(ctx, job)


@tool("browser_screenshot", "Chụp ảnh trang hiện tại và lưu vào thư mục làm việc.", {"full_page": ("boolean", "chụp cả trang thay vì khung nhìn")},
      required=[], risk="network")
def browser_screenshot(ctx: ToolContext, full_page: bool = False):
    c = _cfg()
    media = ctx.workdir / "media"
    media.mkdir(parents=True, exist_ok=True)

    def job(s):
        _guard_final(s, c.allow_private)
        n = 1
        while (media / f"browser-{n}.png").exists():
            n += 1
        page = s.current()
        page.screenshot(path=str(media / f"browser-{n}.png"), full_page=bool(full_page))
        return f"[image: media/browser-{n}.png]\nẢnh chụp trang \"{page.title()}\" ({page.url})"
    return _run(ctx, job)


@tool("browser_close", "Đóng trình duyệt của cuộc hội thoại này.", {}, risk="network")
def browser_close(ctx: ToolContext):
    _cfg()
    return "Đã đóng trình duyệt." if manager.close(ctx.session_id or "default") else "Trình duyệt chưa được mở."
