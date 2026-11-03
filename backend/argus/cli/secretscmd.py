"""argus secrets status|encrypt|decrypt|keychain|file|rotate: quan ly viec ma hoa khoa bi mat trong config.json."""
import json

from cryptography.fernet import Fernet

from ..core import config as cfgmod
from ..core import secrets
from ..core.paths import CONFIG_PATH
from .ui import L, bad, bold, confirm, dim, green, info, ok, warn, yellow

def _src(key: str) -> str:
    return {"env": L("biến môi trường ARGUS_MASTER_KEY", "ARGUS_MASTER_KEY environment variable"), "keychain": L("keychain của hệ điều hành", "OS keychain"),
            "file": "data/master.key", "none": L("chưa có", "none yet")}[key]


def _raw() -> dict:
    return json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}


def status(as_json: bool) -> int:
    cfgmod.load()  # nap de ghi nhan cac truong khong giai ma duoc
    st = secrets.status(_raw())
    if as_json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 1 if st["failed"] else 0
    print(f"  {dim(L('Mã hóa', 'Encryption').ljust(22))}{green(L('bật', 'on')) if st['enabled'] else yellow(L('tắt (ARGUS_ENCRYPT=0)', 'off (ARGUS_ENCRYPT=0)'))}")
    print(f"  {dim(L('Khóa chủ nằm ở', 'Master key stored in').ljust(22))}{_src(st['source'])}")
    print(f"  {dim(L('Đã mã hóa', 'Encrypted').ljust(22))}{st['encrypted']}")
    print(f"  {dim(L('Còn chữ thường', 'Still plaintext').ljust(22))}{yellow(str(st['plaintext'])) if st['plaintext'] else 0}")
    if st["failed"]:
        bad(L("Không giải mã được (mất/sai khóa chủ): ", "Could not decrypt (master key lost or wrong): ") + ", ".join(st["failed"]))
        print(dim(L("  Nhập lại các khóa đó trong giao diện, hoặc khôi phục khóa chủ (ARGUS_MASTER_KEY / restore).", "  Re-enter those keys in the UI, or restore the master key (ARGUS_MASTER_KEY / restore).")))
        return 1
    if st["plaintext"] and st["enabled"]:
        warn(L("Còn khóa chưa mã hóa. Chạy: argus secrets encrypt", "Some secrets are still plaintext. Run: argus secrets encrypt"))
    return 0


def encrypt() -> int:
    cfg = cfgmod.load()
    cfgmod.save(cfg, encrypt=True)
    st = secrets.status(_raw())
    ok(L(f"Đã mã hóa {st['encrypted']} khóa bí mật. Khóa chủ: {_src(st['source'])}", f"Encrypted {st['encrypted']} secret(s). Master key: {_src(st['source'])}"))
    if st["source"] == "file":
        info(L("Hãy sao lưu data/master.key cùng nơi an toàn: mất nó thì không giải mã lại được (argus backup --include-key --encrypt).",
               "Keep data/master.key safe: without it the secrets cannot be decrypted (argus backup --include-key --encrypt)."))
    return 0


def decrypt(yes: bool) -> int:
    if not yes and not confirm(L("Ghi khóa bí mật ra config.json dạng CHỮ THƯỜNG?", "Write the secrets to config.json as PLAINTEXT?"), False):
        return 1
    cfgmod.save(cfgmod.load(), encrypt=False)
    ok(L("Đã giải mã. Đặt ARGUS_ENCRYPT=0 nếu muốn giữ chữ thường.", "Decrypted. Set ARGUS_ENCRYPT=0 to keep it plaintext."))
    return 0


def keychain() -> int:
    kr = secrets._keyring()
    if not kr:
        bad(L("Máy này chưa có keychain dùng được. Cài: pip install keyring (trên Linux cần Secret Service/GNOME Keyring hoặc KWallet).",
              "No usable keychain here. Install: pip install keyring (Linux needs Secret Service/GNOME Keyring or KWallet)."))
        return 1
    cfg = cfgmod.load()
    key = secrets.load_key(create=True)
    kr.set_password(secrets.SERVICE, secrets.ACCOUNT, key.decode())
    if kr.get_password(secrets.SERVICE, secrets.ACCOUNT) != key.decode():
        bad(L("Không đọc lại được khóa từ keychain, giữ nguyên file.", "Could not read the key back from the keychain; keeping the file."))
        return 1
    secrets.KEY_FILE.unlink(missing_ok=True)
    cfgmod.save(cfg, encrypt=True)
    ok(L("Khóa chủ đã chuyển vào keychain, file data/master.key đã xóa.", "The master key moved to the keychain and data/master.key was deleted."))
    return 0


def file_() -> int:
    kr = secrets._keyring()
    key = kr.get_password(secrets.SERVICE, secrets.ACCOUNT) if kr else None
    if not key:
        info(L("Khóa chủ không nằm trong keychain.", "The master key is not in the keychain."))
        return 0
    secrets.write_key_file(key.encode())
    kr.delete_password(secrets.SERVICE, secrets.ACCOUNT)
    ok(L("Đã chuyển khóa chủ về file data/master.key.", "Master key moved back to data/master.key."))
    return 0


def rotate() -> int:
    cfg = cfgmod.load()
    if secrets.failures:
        bad(L("Có khóa không giải mã được; sửa trước khi đổi khóa chủ (argus secrets status).", "Some secrets cannot be decrypted; fix that before rotating (argus secrets status)."))
        return 1
    src = secrets.source()
    new = Fernet.generate_key()
    if src == "env":
        bad(L("Khóa chủ đang lấy từ biến môi trường; hãy tự đổi ARGUS_MASTER_KEY.", "The master key comes from the environment; rotate ARGUS_MASTER_KEY yourself."))
        print(new.decode())
        return 1
    if src == "keychain":
        secrets._keyring().set_password(secrets.SERVICE, secrets.ACCOUNT, new.decode())
    else:
        secrets.write_key_file(new)
    cfgmod.save(cfg, encrypt=True)
    ok(L("Đã đổi khóa chủ và mã hóa lại mọi khóa bí mật. Các bản sao lưu cũ cần khóa cũ để khôi phục.", "Master key rotated and all secrets re-encrypted. Old backups need the old key to restore."))
    return 0


__all__ = ["status", "encrypt", "decrypt", "keychain", "file_", "rotate", "bold"]
