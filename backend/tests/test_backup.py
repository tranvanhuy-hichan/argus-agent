import io
import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

from argus.core import config as cfgmod
from argus.core import secrets
from argus.services import backup, sessions


@pytest.fixture
def home(tmp_env):
    cfg = cfgmod.load()
    cfg.providers["local"].api_key = "sk-backup-secret"
    cfgmod.save(cfg)
    ws = tmp_env / "workspace"
    (ws / "sessions" / "abc12345").mkdir(parents=True)
    (ws / "sessions" / "abc12345" / "result.txt").write_text("MARKER-SESSION-FILE")
    (ws / "SOUL.md").write_text("MARKER-SOUL")
    (ws / "skills" / "x").mkdir(parents=True)
    (ws / "skills" / "x" / "SKILL.md").write_text("---\nname: x\n---\nb")
    sid = sessions.create("hoi thoai thu")
    sessions.add_message(sid, {"role": "user", "content": "noi dung can giu"})
    return backup.Home(tmp_env, tmp_env / "config.json", tmp_env / "agent.db", tmp_env / "master.key", ws)


def wipe(h: backup.Home, keep_key=True):
    import shutil

    h.config.unlink()
    for suffix in ("", "-wal", "-shm"):
        Path(str(h.db) + suffix).unlink(missing_ok=True)
    shutil.rmtree(h.workspace)
    if not keep_key:
        h.key_file.unlink()


def test_roundtrip_restores_everything(home):
    path, manifest = backup.create(home, include_key=False)
    assert set(manifest["files"]) >= {"config.json", "agent.db", "workspace/SOUL.md", "workspace/skills/x/SKILL.md", "workspace/sessions/abc12345/result.txt"}
    wipe(home)
    res = backup.restore(home, path)
    assert (home.workspace / "SOUL.md").read_text() == "MARKER-SOUL" and (home.workspace / "sessions" / "abc12345" / "result.txt").exists()
    assert sqlite3.connect(home.db).execute("select content from messages").fetchone()[0] == "noi dung can giu"
    assert cfgmod.load().providers["local"].api_key == "sk-backup-secret" and oct(home.config.stat().st_mode & 0o777) == "0o600"
    assert res["pre_backup"] is None


def test_backup_keeps_secrets_encrypted_and_excludes_key_by_default(home):
    path, manifest = backup.create(home)
    assert not manifest["has_key"]
    with tarfile.open(path) as tar:
        assert "master.key" not in tar.getnames()
        assert b"sk-backup-secret" not in tar.extractfile("config.json").read()


def test_no_sessions_option(home):
    _, manifest = backup.create(home, include_sessions=False)
    assert not any(n.startswith("workspace/sessions/") for n in manifest["files"]) and "workspace/SOUL.md" in manifest["files"]


def test_restore_on_another_machine_needs_key(home, tmp_env):
    path, _ = backup.create(home, include_key=False)
    wipe(home, keep_key=False)
    secrets.failures.clear()
    backup.restore(home, path)
    assert cfgmod.load().providers["local"].api_key == "" and secrets.failures  # khong co khoa chu -> bao ro, khong sap
    secrets.failures.clear()


def test_include_key_restores_secrets_on_empty_machine(home):
    path, manifest = backup.create(home, include_key=True)
    assert manifest["has_key"]
    wipe(home, keep_key=False)
    res = backup.restore(home, path)
    assert res["key_restored"] and cfgmod.load().providers["local"].api_key == "sk-backup-secret"
    assert oct(home.key_file.stat().st_mode & 0o777) == "0o600"


def test_master_key_file_option(home, tmp_env):
    key = home.key_file.read_bytes()
    path, _ = backup.create(home, include_key=False)
    wipe(home, keep_key=False)
    kf = tmp_env / "saved.key"
    kf.write_bytes(key)
    backup.restore(home, path, master_key_file=kf)
    assert cfgmod.load().providers["local"].api_key == "sk-backup-secret"


def test_refuses_to_overwrite_without_force_then_makes_safety_copies(home):
    path, _ = backup.create(home)
    (home.workspace / "SOUL.md").write_text("EDITED-AFTER-BACKUP")
    with pytest.raises(backup.BackupError, match="--force"):
        backup.restore(home, path)
    assert (home.workspace / "SOUL.md").read_text() == "EDITED-AFTER-BACKUP"  # khong bi dung vao
    res = backup.restore(home, path, force=True)
    assert (home.workspace / "SOUL.md").read_text() == "MARKER-SOUL"
    assert res["pre_backup"].exists() and (res["old_workspace"] / "SOUL.md").read_text() == "EDITED-AFTER-BACKUP"


def test_encrypted_backup_roundtrip_and_no_plaintext_leak(home):
    path, _ = backup.create(home, include_key=True, passphrase="correct horse battery")
    raw = path.read_bytes()
    assert backup.is_encrypted(path) and b"MARKER-SOUL" not in raw and b"sk-backup-secret" not in raw and b"tar" not in raw[:20]
    wipe(home, keep_key=False)
    backup.restore(home, path, passphrase="correct horse battery")
    assert cfgmod.load().providers["local"].api_key == "sk-backup-secret"


def test_encrypted_backup_rejects_wrong_passphrase_tampering_and_truncation(home, tmp_path):
    path, _ = backup.create(home, passphrase="correct horse battery")
    wipe(home)
    with pytest.raises(backup.BackupError, match="mật khẩu"):
        backup.restore(home, path, passphrase="wrong passphrase!")
    with pytest.raises(backup.BackupError, match="cần mật khẩu"):
        backup.restore(home, path)
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    bad = tmp_path / "tampered.enc"
    bad.write_bytes(bytes(data))
    with pytest.raises(backup.BackupError):
        backup.restore(home, bad, passphrase="correct horse battery")
    cut = tmp_path / "cut.enc"
    cut.write_bytes(path.read_bytes()[:-40])
    with pytest.raises(backup.BackupError):
        backup.restore(home, cut, passphrase="correct horse battery")
    assert not home.config.exists()  # khong ghi gi khi that bai


def _evil_tar(tmp_path, build) -> Path:
    p = tmp_path / "evil.tar.gz"
    with tarfile.open(p, "w:gz") as tar:
        manifest = json.dumps({"app": "argus-agent", "version": "x", "created": "t", "files": {}}).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest)
        tar.addfile(info, io.BytesIO(manifest))
        build(tar)
    return p


def test_rejects_path_traversal_symlinks_and_foreign_archives(home, tmp_path):
    def traversal(tar):
        i = tarfile.TarInfo("workspace/../../evil.txt")
        i.size = 4
        tar.addfile(i, io.BytesIO(b"evil"))

    def symlink(tar):
        i = tarfile.TarInfo("workspace/link")
        i.type, i.linkname = tarfile.SYMTYPE, "/etc/passwd"
        tar.addfile(i)

    def stranger(tar):
        i = tarfile.TarInfo("etc/cron.d/x")
        i.size = 1
        tar.addfile(i, io.BytesIO(b"x"))

    wipe(home)
    for build in (traversal, symlink, stranger):
        with pytest.raises(backup.BackupError):
            backup.restore(home, _evil_tar(tmp_path, build))
    assert not (tmp_path.parent / "evil.txt").exists() and not home.workspace.exists()
    notarg = tmp_path / "x.tar.gz"
    notarg.write_bytes(b"not a tar")
    with pytest.raises(backup.BackupError):
        backup.restore(home, notarg)
    with pytest.raises(backup.BackupError):
        backup.restore(home, tmp_path / "missing.tar.gz")


def test_snapshot_is_consistent_while_db_is_open(home):
    conn = sqlite3.connect(home.db)
    conn.execute("BEGIN IMMEDIATE")
    path, _ = backup.create(home)
    conn.rollback()
    conn.close()
    with tarfile.open(path) as tar:
        data = tar.extractfile("agent.db").read()
    assert data[:15] == b"SQLite format 3"
