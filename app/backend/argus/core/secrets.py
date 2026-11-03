"""Ma hoa khoa bi mat trong config.json (API key, token Telegram, env/header MCP, khoa skill).

Khoa chu lay theo thu tu: ARGUS_MASTER_KEY -> keychain he dieu hanh (neu co goi `keyring`) -> data/master.key (quyen 600).
Muc dich: file config.json bi lo (gui kem bao loi, lo len git, sao luu rieng) khong keo theo lo khoa API.
KHONG bao ve truoc ke truy cap duoc ca config.json lan khoa chu, hoac truoc tien trinh dang chay.
"""
import os
from collections.abc import Callable

from cryptography.fernet import Fernet, InvalidToken

from .env import getenv
from .paths import DATA

PREFIX = "enc:v1:"
KEY_FILE = DATA / "master.key"
SERVICE, ACCOUNT = "argus-agent", "master-key"
failures: set[str] = set()  # truong khong giai ma duoc (mat/sai khoa chu)


def enabled() -> bool:
    return getenv("ENCRYPT", "1") not in ("0", "false", "no")


def _keyring():
    try:
        import keyring
        from keyring.backends import fail, null
    except ImportError:
        return None
    backend = keyring.get_keyring()
    return None if isinstance(backend, (fail.Keyring, null.Keyring)) else keyring


def source() -> str:
    """Noi dang giu khoa chu: env | keychain | file | none."""
    if getenv("MASTER_KEY"):
        return "env"
    kr = _keyring()
    if kr and kr.get_password(SERVICE, ACCOUNT):
        return "keychain"
    return "file" if KEY_FILE.exists() else "none"


def load_key(create: bool = False) -> bytes | None:
    if env := getenv("MASTER_KEY"):
        return env.encode()
    kr = _keyring()
    if kr and (v := kr.get_password(SERVICE, ACCOUNT)):
        return v.encode()
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes().strip()
    if not create:
        return None
    key = Fernet.generate_key()
    write_key_file(key)
    return key


def write_key_file(key: bytes) -> None:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # 600 ngay tu luc tao, khong co khoang thoi gian ai cung doc duoc
    with os.fdopen(fd, "wb") as f:
        f.write(key + b"\n")
    KEY_FILE.chmod(0o600)


def encrypt(value: str) -> str:
    if not value or value.startswith(PREFIX):
        return value
    return PREFIX + Fernet(load_key(create=True)).encrypt(value.encode()).decode()


def decrypt(value: str, where: str = "") -> str:
    if not value.startswith(PREFIX):
        return value  # file cu luu chu thuong van doc duoc
    key = load_key()
    if key:
        try:
            return Fernet(key).decrypt(value[len(PREFIX):].encode()).decode()
        except (InvalidToken, ValueError):
            pass
    failures.add(where or "?")
    return ""


def _fields(data: dict):
    """Liet ke (dict_chua, ten_khoa, duong_dan) cua moi truong bi mat trong cau hinh dang dict."""
    for name, p in (data.get("providers") or {}).items():
        yield p, "api_key", f"providers.{name}.api_key"
    tg = (data.get("channels") or {}).get("telegram")
    if tg:
        yield tg, "token", "channels.telegram.token"
    for name, m in (data.get("mcp_servers") or {}).items():
        for bucket in ("env", "headers"):
            for k in (m.get(bucket) or {}):
                yield m[bucket], k, f"mcp_servers.{name}.{bucket}.{k}"
    for name, s in (data.get("skills") or {}).items():
        yield s, "api_key", f"skills.{name}.api_key"
        for k in (s.get("env") or {}):
            yield s["env"], k, f"skills.{name}.env.{k}"


def transform(data: dict, fn: Callable[[str, str], str]) -> dict:
    for holder, key, path in _fields(data):
        if isinstance(holder.get(key), str):
            holder[key] = fn(holder[key], path)
    return data


def decrypt_tree(data: dict) -> dict:
    return transform(data, lambda v, path: decrypt(v, path))


def encrypt_tree(data: dict) -> dict:
    return transform(data, lambda v, path: encrypt(v))


def status(raw: dict | None) -> dict:
    """Thong ke tren noi dung file config.json tho (chua giai ma)."""
    enc = plain = 0
    for holder, key, _ in _fields(raw or {}):
        v = holder.get(key)
        if isinstance(v, str) and v:
            enc, plain = (enc + 1, plain) if v.startswith(PREFIX) else (enc, plain + 1)
    return {"enabled": enabled(), "source": source(), "encrypted": enc, "plaintext": plain, "failed": sorted(failures)}
