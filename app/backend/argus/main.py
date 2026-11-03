import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .api import activity, channels, chat, dashboard, external, files, integrations, skills, system
from .core import db
from .core.env import getenv
from .core.paths import DIST
from .core.workspace import ensure_workspace
from .core import config as cfgmod
from .services import auth, heartbeat, scheduler
from .services.telegram_channel import channel as telegram
from .services.mcp_client import manager as mcp_manager

# httpx mac dinh ghi ca URL vao log, ma URL cua Telegram chua token bot
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "testserver"} | set(filter(None, getenv("ALLOWED_HOSTS").split(",")))
DEV_ORIGINS = set(filter(None, getenv("DEV_ORIGINS").split(",")))


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    ensure_workspace(cfgmod.load())
    scheduler.start()
    mcp_manager.start()
    cfg = cfgmod.load()
    mcp_manager.apply(cfg.mcp_servers)
    telegram.apply(cfg.channels.telegram)
    heartbeat.start()
    yield
    heartbeat.stop()
    mcp_manager.stop()
    scheduler.stop()


app = FastAPI(title="Argus Agent", version="0.3.0", lifespan=lifespan)


@app.middleware("http")
async def guard(request: Request, call_next):
    """Chong DNS-rebinding/CSRF: agent co tool chay lenh nen chi nhan request tu dung host."""
    if request.url.path.startswith("/v1/"):  # API ben ngoai: xac thuc bang Bearer token (khong dung cookie nen khong lo CSRF)
        return await call_next(request)
    host = request.headers.get("host", "")
    name = host.split("]")[0] + "]" if host.startswith("[") else host.split(":")[0]
    if name not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "forbidden host"}, 403)
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/auth/") and path != "/api/health":
        cfg = cfgmod.load()
        if cfg.auth.password_hash and not auth.verify_token(request.cookies.get(auth.COOKIE)):
            return JSONResponse({"detail": "cần đăng nhập"}, 401)
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin.split("://", 1)[-1] != host and origin not in DEV_ORIGINS:
        return JSONResponse({"detail": "forbidden origin"}, 403)
    return await call_next(request)


@app.exception_handler(ValidationError)
async def validation_handler(_, exc: ValidationError):
    return JSONResponse({"detail": str(exc)}, 422)


for module in (system, chat, skills, dashboard, integrations, files, activity, channels):
    app.include_router(module.router, prefix="/api")
app.include_router(external.router)

if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"))

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "v1/")):
            return JSONResponse({"detail": "Not Found"}, 404)
        f = (DIST / path).resolve()
        if path and DIST.resolve() in f.parents and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
