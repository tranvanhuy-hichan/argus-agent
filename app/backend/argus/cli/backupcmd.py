"""argus backup / argus restore."""
import os
import re
from pathlib import Path

from ..services import backup
from . import daemon, runtime
from .ui import L, ask_secret, bad, bold, confirm, dim, err, interactive, lang, ok, warn, yellow


_EN = [
    (r"^không phải file sao lưu đã mã hóa của Argus$", "Not an encrypted Argus backup"),
    (r"^file sao lưu bị cắt cụt$", "The backup file is truncated"),
    (r"^sai mật khẩu hoặc file sao lưu bị hỏng/bị sửa$", "Wrong passphrase, or the backup file is damaged or was modified"),
    (r"^file sao lưu chứa mục không an toàn: (.+)$", r"The backup contains an unsafe entry: \1"),
    (r"^mục lạ trong file sao lưu: (.+)$", r"Unexpected entry in the backup: \1"),
    (r"^file sao lưu quá lớn$", "The backup is too large"),
    (r"^không phải file sao lưu của Argus \(thiếu manifest.json\)$", "Not an Argus backup (manifest.json missing)"),
    (r"^không phải file sao lưu của Argus$", "Not an Argus backup"),
    (r"^đã có dữ liệu Argus ở đây; dùng --force.*$", "Argus data already exists here; use --force to overwrite (the current data is backed up first)"),
    (r"^file sao lưu được mã hóa, cần mật khẩu$", "The backup is encrypted, a passphrase is required"),
    (r"^không thấy file (.+)$", r"File not found: \1"),
    (r"^không đọc được file sao lưu: (.+)$", r"Could not read the backup: \1"),
]


def _msg(e: Exception) -> str:
    text = str(e)
    if lang() == "en":
        for pattern, repl in _EN:
            if re.match(pattern, text):
                return re.sub(pattern, repl, text)
    return text


def _passphrase(env_name: str | None, confirm_twice: bool) -> str | None:
    if env_name:
        value = os.environ.get(env_name, "")
        if not value:
            err(L(f"Biến môi trường {env_name} trống.", f"The environment variable {env_name} is empty."))
        return value or None
    value = ask_secret(L("Mật khẩu mã hóa bản sao lưu", "Backup passphrase"))
    if confirm_twice and value != ask_secret(L("Nhập lại", "Repeat")):
        err(L("Hai lần nhập không khớp.", "The two entries do not match."))
        return None
    return value or None


def create(out: str | None, include_key: bool, include_sessions: bool, encrypt: bool, passphrase_env: str | None) -> int:
    runtime.bootstrap()
    pw = None
    if encrypt or passphrase_env:
        pw = _passphrase(passphrase_env, confirm_twice=not passphrase_env)
        if not pw:
            return 1
        if len(pw) < 8:
            err(L("Mật khẩu cần ít nhất 8 ký tự.", "The passphrase needs at least 8 characters."))
            return 1
    try:
        path, manifest = backup.create(backup.Home.default(), Path(out) if out else None, include_key=include_key, include_sessions=include_sessions, passphrase=pw)
    except backup.BackupError as e:
        err(_msg(e))
        return 1
    size = path.stat().st_size / (1024 * 1024)
    ok(L(f"Đã sao lưu: {bold(str(path))}  ({size:.1f} MB, {len(manifest['files'])} tệp)", f"Backup written: {bold(str(path))}  ({size:.1f} MB, {len(manifest['files'])} files)"))
    print(dim(L(f"  Gồm: cấu hình, cơ sở dữ liệu, workspace{'' if include_sessions else ' (không có file của các phiên)'}{', khóa chủ' if manifest['has_key'] else ''}",
                f"  Contains: configuration, database, workspace{'' if include_sessions else ' (without per-conversation files)'}{', master key' if manifest['has_key'] else ''}")))
    if manifest["has_key"] and not pw:
        warn(L("Bản sao lưu chứa cả khóa chủ lẫn khóa bí mật đã mã hóa: ai có file này đọc được API key của bạn. Nên thêm --encrypt.",
               "The archive holds both the master key and the encrypted secrets: anyone with it can read your API keys. Add --encrypt."))
    elif not manifest["has_key"]:
        print(yellow(L("  Không chứa khóa chủ: khôi phục sang máy khác sẽ phải nhập lại API key (hoặc dùng --include-key --encrypt).",
                       "  The master key is not included: on another machine you will have to re-enter API keys (or use --include-key --encrypt).")))
    return 0


def do_restore(archive: str, force: bool, passphrase_env: str | None, key_file: str | None) -> int:
    if daemon.read_pid():
        bad(L("Server đang chạy. Dừng bằng `argus stop` trước khi khôi phục.", "The server is running. Stop it with `argus stop` before restoring."))
        return 1
    path = Path(archive)
    pw = None
    if path.exists() and backup.is_encrypted(path):
        pw = _passphrase(passphrase_env, confirm_twice=False)
        if not pw:
            return 1
    if force and interactive() and not confirm(L("Ghi đè dữ liệu hiện tại bằng bản sao lưu này? (bản hiện tại sẽ được tự sao lưu trước)", "Overwrite the current data with this backup? (the current data is backed up first)"), False):
        return 1
    try:
        res = backup.restore(backup.Home.default(), path, force=force, passphrase=pw, master_key_file=Path(key_file) if key_file else None)
    except backup.BackupError as e:
        err(_msg(e))
        return 1
    m = res["manifest"]
    ok(L(f"Đã khôi phục bản sao lưu {m['created']} (v{m['version']}).", f"Restored the backup from {m['created']} (v{m['version']})."))
    if res["pre_backup"]:
        print(dim(L(f"  Dữ liệu cũ được sao lưu ở {res['pre_backup']}", f"  The previous data was backed up to {res['pre_backup']}")))
    if res["old_workspace"]:
        print(dim(L(f"  Workspace cũ được giữ ở {res['old_workspace']}", f"  The previous workspace was kept at {res['old_workspace']}")))
    from ..core import config as cfgmod
    from ..core import secrets

    secrets.failures.clear()
    cfgmod.load()
    if secrets.failures:
        warn(L(f"{len(secrets.failures)} khóa bí mật không giải mã được vì thiếu khóa chủ. Dùng --master-key-file <file> hoặc đặt ARGUS_MASTER_KEY, hoặc nhập lại trong giao diện.",
               f"{len(secrets.failures)} secret(s) could not be decrypted because the master key is missing. Use --master-key-file <file>, set ARGUS_MASTER_KEY, or re-enter them in the UI."))
    print(dim(L("  Khởi động lại bằng: argus start", "  Start again with: argus start")))
    return 0
