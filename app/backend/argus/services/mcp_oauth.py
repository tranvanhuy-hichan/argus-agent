"""OAuth 2.1 cho MCP server tu xa (Notion, Canva, Linear...): token luu MA HOA, dang nhap qua trinh duyet.

SDK MCP lo phan giao thuc (kham pha may chu cap quyen, dang ky client dong, PKCE, doi ma lay token, lam moi token). Phan cua Argus:
  Store : noi luu client + token (bang kv, ma hoa bang cung khoa chu voi API key)
  Flow  : redirect_handler ghi lai URL cap quyen cho giao dien; callback_handler cho ma tra ve tu /api/mcp/oauth/callback
"""
import asyncio
import json
import threading
import time
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import TokenStorage
from mcp.shared.auth import AuthorizationCodeResult, OAuthClientInformationFull, OAuthToken

from ..core import secrets
from ..core.db import db

LOGIN_TIMEOUT = 300  # so giay cho nguoi dung bam "Cho phep" tren trang cua nha cung cap
CALLBACK_PATH = "/api/mcp/oauth/callback"


class NeedsAuth(Exception):
    """Server can dang nhap nhung dang o che do khong tuong tac (khoi dong, ket noi lai): giao dien se hien nut 'Dang nhap'."""


class Store(TokenStorage):
    """Client dang ky dong + token cua mot MCP server, luu trong bang kv duoi dang JSON da ma hoa."""

    def __init__(self, name: str) -> None:
        self.key = f"mcp_oauth:{name}"

    def _load(self) -> dict:
        with db() as c:
            r = c.execute("SELECT value FROM kv WHERE key=?", (self.key,)).fetchone()
        if not r:
            return {}
        try:
            return json.loads(secrets.decrypt(r["value"], f"mcp_oauth:{self.key}") or "{}")
        except json.JSONDecodeError:
            return {}

    def _save(self, d: dict) -> None:
        raw = json.dumps(d)
        with db() as c:
            c.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (self.key, secrets.encrypt(raw) if secrets.enabled() else raw))

    async def get_tokens(self) -> OAuthToken | None:
        t = self._load().get("tokens")
        return OAuthToken.model_validate(t) if t else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        d = self._load()
        d["tokens"], d["saved"] = tokens.model_dump(mode="json"), time.time()
        self._save(d)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        c = self._load().get("client")
        return OAuthClientInformationFull.model_validate(c) if c else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        d = self._load()
        d["client"] = client_info.model_dump(mode="json")
        self._save(d)

    # ---- tien ich dong bo cho API
    def logged_in(self) -> bool:
        return bool(self._load().get("tokens"))

    def redirect_base(self) -> str:
        return self._load().get("redirect_base", "")

    def use_redirect_base(self, base: str) -> None:
        """Client dang ky gan voi redirect_uri; doi dia chi/cong thi phai dang ky lai (va dang nhap lai)."""
        d = self._load()
        if d.get("redirect_base") != base:
            d = {"redirect_base": base}
            self._save(d)

    def clear(self) -> None:
        with db() as c:
            c.execute("DELETE FROM kv WHERE key=?", (self.key,))


_pending: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Future]] = {}
_lock = threading.Lock()


class Flow:
    """Mot lan ket noi: neu interactive thi cho nguoi dung dang nhap, neu khong thi bao NeedsAuth."""

    def __init__(self, interactive: bool, on_url) -> None:
        self.interactive, self.on_url, self.state = interactive, on_url, ""

    async def redirect(self, url: str) -> None:
        if not self.interactive:
            raise NeedsAuth()
        self.state = parse_qs(urlparse(url).query).get("state", [""])[0]
        loop = asyncio.get_running_loop()
        with _lock:
            _pending[self.state] = (loop, loop.create_future())
        self.on_url(url)

    async def callback(self) -> AuthorizationCodeResult:
        with _lock:
            _, fut = _pending[self.state]
        try:
            return await asyncio.wait_for(fut, LOGIN_TIMEOUT)
        except asyncio.TimeoutError:
            raise RuntimeError(f"quá {LOGIN_TIMEOUT}s không thấy đăng nhập xong") from None
        finally:
            with _lock:
                _pending.pop(self.state, None)


def complete(state: str, code: str = "", error: str = "", iss: str = "") -> bool:
    """Goi tu /api/mcp/oauth/callback (thread khac): tra ma (hoac loi) cho ket noi dang cho. False neu khong co ket noi nao dang cho."""
    with _lock:
        entry = _pending.get(state)
    if not entry:
        return False
    loop, fut = entry

    def done() -> None:
        if fut.done():
            return
        if error or not code:
            fut.set_exception(RuntimeError(f"nhà cung cấp từ chối đăng nhập: {error or 'không có mã'}"))
        else:
            fut.set_result(AuthorizationCodeResult(code=code, state=state, iss=iss or None))

    loop.call_soon_threadsafe(done)
    return True
