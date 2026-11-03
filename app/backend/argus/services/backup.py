"""Sao luu / khoi phuc toan bo du lieu: config.json (khoa bi mat van ma hoa), co so du lieu, workspace; tuy chon khoa chu va ma hoa bang mat khau."""
import io
import json
import os
import shutil
import sqlite3
import struct
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from ..core import config as cfgmod
from ..core import secrets
from ..core.paths import CONFIG_PATH, DB_PATH, ROOT

MAGIC = b"ARGUSENC2"
CHUNK = 1 << 20
MAX_BYTES, MAX_FILES = 8 * 1024**3, 200_000
VERSION = "0.3.0"


class BackupError(Exception):
    pass


@dataclass
class Home:
    root: Path
    config: Path
    db: Path
    key_file: Path
    workspace: Path

    @classmethod
    def default(cls) -> "Home":
        return cls(ROOT, CONFIG_PATH, DB_PATH, secrets.KEY_FILE, cfgmod.load().workspace_path())

    @property
    def backups(self) -> Path:
        return self.root / "backups"


# ---------------- ma hoa archive bang mat khau (AES-GCM chia khoi, chong cat bot/doi thu tu)
def _kdf(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode())


def encrypt_file(src: Path, dst: Path, passphrase: str) -> None:
    salt, prefix = os.urandom(16), os.urandom(4)
    header = MAGIC + salt + prefix
    aes = AESGCM(_kdf(passphrase, salt))
    with open(src, "rb") as f, open(dst, "wb") as out:
        out.write(header)
        chunk, counter = f.read(CHUNK), 0
        while True:
            nxt = f.read(CHUNK)
            final = not nxt
            ct = aes.encrypt(prefix + struct.pack(">Q", counter), chunk, header + struct.pack(">QB", counter, final))
            out.write(struct.pack(">I", len(ct)) + ct)
            if final:
                break
            chunk, counter = nxt, counter + 1


def decrypt_file(src: Path, dst: Path, passphrase: str) -> None:
    size = src.stat().st_size
    with open(src, "rb") as f, open(dst, "wb") as out:
        header = f.read(len(MAGIC) + 20)
        if header[: len(MAGIC)] != MAGIC:
            raise BackupError("không phải file sao lưu đã mã hóa của Argus")
        salt, prefix = header[len(MAGIC): len(MAGIC) + 16], header[-4:]
        aes, counter = AESGCM(_kdf(passphrase, salt)), 0
        while f.tell() < size:
            (n,) = struct.unpack(">I", f.read(4))
            ct = f.read(n)
            if len(ct) != n:
                raise BackupError("file sao lưu bị cắt cụt")
            final = f.tell() == size
            try:
                out.write(aes.decrypt(prefix + struct.pack(">Q", counter), ct, header + struct.pack(">QB", counter, final)))
            except InvalidTag as e:
                raise BackupError("sai mật khẩu hoặc file sao lưu bị hỏng/bị sửa") from e
            counter += 1


def is_encrypted(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(len(MAGIC)) == MAGIC


# ---------------- tao ban sao luu
def create(home: Home, out: Path | None = None, *, include_key: bool = False, include_sessions: bool = True, passphrase: str | None = None) -> tuple[Path, dict]:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = out or home.backups / f"argus-backup-{stamp}.tar.gz{'.enc' if passphrase else ''}"
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest: dict = {"app": "argus-agent", "version": VERSION, "created": stamp, "has_key": False, "has_sessions": include_sessions, "files": {}}
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=".backup-") as tmp:
        tar_path = Path(tmp) / "backup.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            def add_bytes(name: str, data: bytes) -> None:
                info = tarfile.TarInfo(name)
                info.size, info.mtime, info.mode = len(data), time.time(), 0o600
                tar.addfile(info, io.BytesIO(data))
                manifest["files"][name] = len(data)

            def add_path(name: str, path: Path) -> None:
                tar.add(path, arcname=name, recursive=False)
                manifest["files"][name] = path.stat().st_size

            if home.config.exists():
                add_path("config.json", home.config)
            if home.db.exists():
                snap = Path(tmp) / "agent.db"
                src, dst = sqlite3.connect(home.db), sqlite3.connect(snap)
                with dst:
                    src.backup(dst)  # ban chup nhat quan ke ca khi server dang ghi
                src.close()
                dst.close()
                add_path("agent.db", snap)
            if home.workspace.is_dir():
                for p in sorted(home.workspace.rglob("*")):
                    rel = p.relative_to(home.workspace)
                    if p.is_symlink() or p.is_dir() or any(part.startswith(".install-") for part in rel.parts):
                        continue
                    if rel.parts[0] == "sessions" and not include_sessions:
                        continue
                    add_path(f"workspace/{rel.as_posix()}", p)
            if include_key:
                key = secrets.load_key()
                if key:
                    add_bytes("master.key", key + b"\n")
                    manifest["has_key"] = True
            add_bytes("manifest.json", json.dumps(manifest, indent=2).encode())
        if passphrase:
            encrypt_file(tar_path, out, passphrase)
        else:
            shutil.move(tar_path, out)
    out.chmod(0o600)
    return out, manifest


# ---------------- khoi phuc
def _check_members(tar: tarfile.TarFile) -> dict:
    total, names = 0, []
    for m in tar.getmembers():
        p = PurePosixPath(m.name)
        if m.name.startswith("/") or ".." in p.parts or not (m.isfile() or m.isdir()):
            raise BackupError(f"file sao lưu chứa mục không an toàn: {m.name}")
        top = p.parts[0] if p.parts else ""
        if top not in ("manifest.json", "config.json", "agent.db", "master.key", "workspace"):
            raise BackupError(f"mục lạ trong file sao lưu: {m.name}")
        total += m.size
        names.append(m.name)
    if total > MAX_BYTES or len(names) > MAX_FILES:
        raise BackupError("file sao lưu quá lớn")
    if "manifest.json" not in names:
        raise BackupError("không phải file sao lưu của Argus (thiếu manifest.json)")
    manifest = json.loads(tar.extractfile("manifest.json").read())
    if manifest.get("app") != "argus-agent":
        raise BackupError("không phải file sao lưu của Argus")
    return manifest


def restore(home: Home, archive: Path, *, force: bool = False, passphrase: str | None = None, master_key_file: Path | None = None) -> dict:
    if not archive.exists():
        raise BackupError(f"không thấy file {archive}")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    staging = home.root / f".restore-{stamp}"
    staging.mkdir(parents=True, exist_ok=True)
    try:
        src = archive
        if is_encrypted(archive):
            if not passphrase:
                raise BackupError("file sao lưu được mã hóa, cần mật khẩu")
            src = staging / "decrypted.tar.gz"
            decrypt_file(archive, src, passphrase)
        try:
            tar = tarfile.open(src, "r:*")
        except tarfile.TarError as e:
            raise BackupError(f"không đọc được file sao lưu: {e}") from e
        with tar:
            manifest = _check_members(tar)
            existing = home.config.exists() or home.db.exists() or (home.workspace.is_dir() and any(home.workspace.iterdir()))
            if existing and not force:
                raise BackupError("đã có dữ liệu Argus ở đây; dùng --force để ghi đè (bản hiện tại sẽ được tự sao lưu trước)")
            pre = None
            if existing:
                pre, _ = create(home, home.backups / f"pre-restore-{stamp}.tar.gz", include_key=True)
            data_dir = staging / "data"
            for m in tar.getmembers():
                target = data_dir / m.name
                if m.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(m) as f, open(target, "wb") as out:
                    shutil.copyfileobj(f, out)
        result = {"manifest": manifest, "pre_backup": pre, "old_workspace": None}
        if (data_dir / "config.json").exists():
            home.config.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(data_dir / "config.json", 0o600)
            os.replace(data_dir / "config.json", home.config)
        if (data_dir / "agent.db").exists():
            home.db.parent.mkdir(parents=True, exist_ok=True)
            for suffix in ("", "-wal", "-shm"):
                Path(str(home.db) + suffix).unlink(missing_ok=True)
            os.replace(data_dir / "agent.db", home.db)
        if (data_dir / "workspace").is_dir():
            if home.workspace.exists():
                result["old_workspace"] = home.workspace.with_name(f"{home.workspace.name}.bak-{stamp}")
                os.replace(home.workspace, result["old_workspace"])
            home.workspace.parent.mkdir(parents=True, exist_ok=True)
            os.replace(data_dir / "workspace", home.workspace)
        key_src = data_dir / "master.key" if (data_dir / "master.key").exists() else master_key_file
        if key_src:
            home.key_file.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(home.key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Path(key_src).read_bytes())
            result["key_restored"] = True
        return result
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def list_backups(home: Home) -> list[Path]:
    return sorted(home.backups.glob("*.tar.gz*"), reverse=True) if home.backups.is_dir() else []
