"""Kenh chat (Telegram), heartbeat va dang nhap giao dien."""
import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import auth, heartbeat
from ..services.telegram_channel import channel, new_pair_code

router = APIRouter()


# ---------- Telegram
@router.get("/channels")
def channels_status():
    cfg = cfgmod.load().channels.telegram
    return {"telegram": {**channel.status, "enabled": cfg.enabled, "has_token": bool(cfg.token), "allowed_users": cfg.allowed_users, "api_base": cfg.api_base}}


class TgConfig(BaseModel):
    enabled: bool
    token: str = ""  # de trong = giu token cu
    api_base: str = "https://api.telegram.org"


@router.put("/channels/telegram")
def channels_save(b: TgConfig):
    cfg = cfgmod.load()
    tg = cfg.channels.telegram
    tg.enabled, tg.api_base = b.enabled, b.api_base.rstrip("/")
    if b.token and b.token != cfgmod.MASK:
        tg.token = b.token.strip()
    if tg.enabled and not tg.token:
        raise HTTPException(400, "cần nhập token bot")
    cfgmod.save(cfg)
    channel.apply(tg)
    return {"ok": True}


@router.post("/channels/telegram/pair-code")
def pair_code():
    return {"code": new_pair_code(), "expires_in": 600}


class RemoveUser(BaseModel):
    user_id: int


@router.post("/channels/telegram/remove-user")
def remove_user(b: RemoveUser):
    cfg = cfgmod.load()
    cfg.channels.telegram.allowed_users = [u for u in cfg.channels.telegram.allowed_users if u != b.user_id]
    cfgmod.save(cfg)
    channel.apply(cfg.channels.telegram)
    return {"ok": True}


class TgTest(BaseModel):
    token: str = ""
    api_base: str = "https://api.telegram.org"


@router.post("/channels/telegram/test")
def channels_test(b: TgTest):
    token = b.token if b.token and b.token != cfgmod.MASK else cfgmod.load().channels.telegram.token
    try:
        r = httpx.post(f"{b.api_base.rstrip('/')}/bot{token}/getMe", timeout=15).json()
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "bot": "@" + r["result"].get("username", "")} if r.get("ok") else {"ok": False, "error": r.get("description", "token không hợp lệ")}


# ---------- Heartbeat
@router.get("/heartbeat")
def hb_status():
    return heartbeat.status()


class HbBody(BaseModel):
    enabled: bool
    interval_minutes: int
    provider: str | None = None


@router.put("/heartbeat")
def hb_save(b: HbBody):
    cfg = cfgmod.load()
    cfg.heartbeat = cfgmod.HeartbeatCfg(**b.model_dump())
    cfgmod.save(cfg)
    f = cfg.workspace_path() / "HEARTBEAT.md"
    if b.enabled and not f.exists():
        f.write_text(heartbeat.DEFAULT_FILE)
    return heartbeat.status()


@router.post("/heartbeat/run")
def hb_run():
    import threading
    threading.Thread(target=heartbeat.run_once, daemon=True).start()
    return {"ok": True}


# ---------- Dang nhap
class Login(BaseModel):
    password: str


@router.get("/auth/status")
def auth_status(request: Request):
    cfg = cfgmod.load()
    return {"required": bool(cfg.auth.password_hash), "authenticated": not cfg.auth.password_hash or auth.verify_token(request.cookies.get(auth.COOKIE))}


@router.post("/auth/login")
def auth_login(b: Login, request: Request, response: Response):
    ip = request.client.host if request.client else "?"
    if auth.throttled(ip):
        raise HTTPException(429, "thử sai quá nhiều lần, vui lòng đợi vài phút")
    if not auth.check_password(cfgmod.load(), b.password):
        auth.record_failure(ip)
        raise HTTPException(401, "sai mật khẩu")
    response.set_cookie(auth.COOKIE, auth.make_token(), max_age=auth.TTL, httponly=True, samesite="strict", secure=request.url.scheme == "https")
    return {"ok": True}


@router.post("/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


class SetPassword(BaseModel):
    current: str = ""
    new: str = ""


@router.post("/auth/password")
def auth_password(b: SetPassword, request: Request):
    cfg = cfgmod.load()
    if cfg.auth.password_hash and not auth.check_password(cfg, b.current):
        raise HTTPException(403, "mật khẩu hiện tại không đúng")
    if b.new and len(b.new) < 8:
        raise HTTPException(400, "mật khẩu mới cần ít nhất 8 ký tự")
    auth.set_password(cfg, b.new)
    cfgmod.save(cfg)
    return {"ok": True, "required": bool(b.new)}
