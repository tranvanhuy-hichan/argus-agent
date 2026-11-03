"""Tool anh: sinh anh (Gemini native / OpenAI-compatible) va xem anh (provider co vision)."""
import base64
import time

import httpx

from ..core import config as cfgmod
from . import providers
from .tools import DENIED, _check_url, _resolve, tool

gemini_root = "https://generativelanguage.googleapis.com"  # test co the doi sang server gia
MAX_GEN_BYTES = 15 * 1024 * 1024
MAX_VIEW_BYTES = 5 * 1024 * 1024
_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}


def _is_gemini(base_url: str) -> bool:
    return "generativelanguage.googleapis.com" in (base_url or "")


def sniff_mime(data: bytes) -> str | None:
    """Nhan dang dinh dang anh qua magic bytes."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def _image_provider(cfg) -> tuple[str, "cfgmod.ProviderCfg"]:
    name = cfg.media.image_provider
    if name:
        if name not in cfg.providers:
            raise ValueError(f"Provider sinh ảnh '{name}' không tồn tại trong danh sách Providers.")
        return name, cfg.providers[name]
    for n, p in cfg.providers.items():
        if _is_gemini(p.base_url):
            return n, p
    raise ValueError("Chưa có provider sinh ảnh. Hãy thêm provider Gemini (generativelanguage.googleapis.com) hoặc chọn 'Provider sinh ảnh' trong cài đặt Media.")


def _vision_provider(cfg, current: str | None) -> tuple[str, "cfgmod.ProviderCfg"]:
    name = cfg.media.vision_provider
    if name and name in cfg.providers:
        return name, cfg.providers[name]
    if current and current in cfg.providers and cfg.providers[current].vision:
        return current, cfg.providers[current]
    for n, p in cfg.providers.items():
        if p.vision:
            return n, p
    raise ValueError("Không có provider nào xem được ảnh. Hãy bật 'Model hiểu được ảnh' cho một provider (trang Providers) hoặc chọn 'Provider xem ảnh' trong cài đặt Media.")


def _gen_gemini(pcfg, model: str, prompt: str) -> tuple[bytes, str]:
    url = f"{gemini_root.rstrip('/')}/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["IMAGE"]}}
    r = httpx.post(url, json=body, headers={"x-goog-api-key": providers._key(pcfg)}, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"API sinh ảnh lỗi {r.status_code}: {r.text[:300]}")
    data = r.json()
    pf = data.get("promptFeedback") or {}
    if pf.get("blockReason"):
        raise RuntimeError(f"Yêu cầu bị chặn ({pf['blockReason']}). Hãy đổi mô tả ảnh.")
    texts, reason = [], ""
    for c in data.get("candidates") or []:
        reason = reason or c.get("finishReason", "")
        for part in (c.get("content") or {}).get("parts") or []:
            inl = part.get("inlineData") or part.get("inline_data")
            if inl and inl.get("data"):
                return base64.b64decode(inl["data"]), inl.get("mimeType") or inl.get("mime_type") or ""
            if part.get("text"):
                texts.append(part["text"])
    detail = f" Model trả lời: {' '.join(texts)[:300]}" if texts else ""
    raise RuntimeError(f"Model không trả về ảnh (finishReason={reason or 'không rõ'}).{detail}")


def _gen_openai(pcfg, model: str, prompt: str, size: str) -> tuple[bytes, str]:
    url = pcfg.base_url.rstrip("/") + "/images/generations"
    key = providers._key(pcfg)
    body = {"model": model, "prompt": prompt, "size": size, "n": 1, "response_format": "b64_json"}
    r = httpx.post(url, json=body, headers={"Authorization": f"Bearer {key}"} if key else {}, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"API sinh ảnh lỗi {r.status_code}: {r.text[:300]}")
    items = r.json().get("data") or []
    if not items:
        raise RuntimeError("API không trả về ảnh nào.")
    it = items[0]
    if it.get("b64_json"):
        return base64.b64decode(it["b64_json"]), ""
    if it.get("url"):
        _check_url(it["url"])
        d = httpx.get(it["url"], timeout=60, follow_redirects=False)
        if d.status_code >= 400:
            raise RuntimeError(f"Không tải được ảnh ({d.status_code}).")
        return d.content, d.headers.get("content-type", "")
    raise RuntimeError("Phản hồi không có b64_json lẫn url.")


@tool("generate_image", "Sinh ảnh từ mô tả văn bản (có thể tốn phí API) và lưu vào thư mục media.",
      {"prompt": ("string", "mô tả ảnh cần tạo"), "size": ("string", "kích thước, vd 1024x1024 (chỉ áp dụng với API kiểu OpenAI)")}, required=["prompt"], risk="network")
def generate_image(ctx, prompt, size=None):
    if not (prompt or "").strip():
        raise ValueError("Thiếu mô tả ảnh.")
    cfg = cfgmod.load()
    _, pcfg = _image_provider(cfg)
    if ctx.confirm_writes and not ctx.full_access and not ctx.approve("image", prompt):
        return DENIED
    model, size = cfg.media.image_model, size or "1024x1024"
    data, mime = _gen_gemini(pcfg, model, prompt) if _is_gemini(pcfg.base_url) else _gen_openai(pcfg, model, prompt, size)
    if len(data) > MAX_GEN_BYTES:
        raise ValueError("Ảnh trả về quá lớn (>15 MB).")
    real = sniff_mime(data)
    if not real:
        raise ValueError("Dữ liệu trả về không phải ảnh hợp lệ.")
    out = ctx.workdir / "media"
    out.mkdir(parents=True, exist_ok=True)
    ts, n = int(time.time()), 1
    while (out / f"image-{ts}-{n}.{_EXT[real]}").exists():
        n += 1
    name = f"image-{ts}-{n}.{_EXT[real]}"
    (out / name).write_bytes(data)
    return f"[image: media/{name}]\nĐã tạo ảnh (prompt: {prompt[:200]}; model: {model}; size: {size if not _is_gemini(pcfg.base_url) else 'mặc định'})."


@tool("view_image", "Xem một file ảnh và mô tả hoặc trả lời câu hỏi về ảnh bằng provider có khả năng nhìn ảnh.",
      {"path": ("string", "đường dẫn ảnh (png/jpg/gif/webp)"), "question": ("string", "câu hỏi về ảnh, mặc định là mô tả chi tiết")}, required=["path"], risk="file")
def view_image(ctx, path, question=None):
    p = _resolve(ctx, path, "read")
    if not p.is_file():
        raise FileNotFoundError(f"Không tìm thấy ảnh: {path}")
    if p.stat().st_size > MAX_VIEW_BYTES:
        raise ValueError("Ảnh quá lớn (>5 MB).")
    data = p.read_bytes()
    mime = sniff_mime(data)
    if not mime:
        raise ValueError("File không phải ảnh png/jpg/gif/webp.")
    cfg = cfgmod.load()
    _, pcfg = _vision_provider(cfg, ctx.provider)
    msgs = [{"role": "user", "content": question or "Mô tả chi tiết ảnh này", "images": [{"mime": mime, "b64": base64.b64encode(data).decode()}]}]
    out = "".join(ev.get("text", "") for ev in providers.make_provider(pcfg).stream(msgs, []) if ev.get("type") == "delta")
    return out.strip() or "(model không trả lời)"


def status() -> dict:
    """Trang thai Media cho `argus doctor`."""
    cfg = cfgmod.load()
    res: dict = {"image_model": cfg.media.image_model}
    try:
        n, _ = _image_provider(cfg)
        res.update(image_provider=n, image_ok=True)
    except ValueError as e:
        res.update(image_provider=None, image_ok=False, image_hint=str(e))
    try:
        n, _ = _vision_provider(cfg, None)
        res.update(vision_provider=n, vision_ok=True)
    except ValueError as e:
        res.update(vision_provider=None, vision_ok=False, vision_hint=str(e))
    return res
