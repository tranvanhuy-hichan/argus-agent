"""Dang nhap giao dien web (tuy chon): mat khau bam scrypt + cookie ky HMAC."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from ..core import config as cfgmod
from ..core.paths import DATA

COOKIE = "argus_session"
TTL = 30 * 86400
_fails: dict[str, list[float]] = {}


def _secret() -> bytes:
    p = DATA / "secret.key"
    if not p.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        p.write_bytes(secrets.token_bytes(32))
        p.chmod(0o600)
    return p.read_bytes()


def _hash(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32).hex()


def set_password(cfg: cfgmod.Config, password: str) -> None:
    if not password:
        cfg.auth = cfgmod.AuthCfg()
    else:
        salt = os.urandom(16).hex()
        cfg.auth = cfgmod.AuthCfg(salt=salt, password_hash=_hash(password, salt))


def check_password(cfg: cfgmod.Config, password: str) -> bool:
    return bool(cfg.auth.password_hash) and hmac.compare_digest(_hash(password, cfg.auth.salt), cfg.auth.password_hash)


def make_token() -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"exp": time.time() + TTL}).encode()).decode()
    return f"{payload}.{hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()}"


def verify_token(token: str | None) -> bool:
    try:
        payload, sig = (token or "").rsplit(".", 1)
        if not hmac.compare_digest(sig, hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()):
            return False
        return json.loads(base64.urlsafe_b64decode(payload))["exp"] > time.time()
    except (ValueError, KeyError):
        return False


def throttled(ip: str) -> bool:
    now = time.time()
    _fails[ip] = [t for t in _fails.get(ip, []) if now - t < 300]
    return len(_fails[ip]) >= 5


def record_failure(ip: str) -> None:
    _fails.setdefault(ip, []).append(time.time())
