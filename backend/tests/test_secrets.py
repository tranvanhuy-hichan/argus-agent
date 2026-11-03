import json

import pytest

from argus.core import config as cfgmod
from argus.core import secrets


def full_cfg() -> cfgmod.Config:
    c = cfgmod.Config()
    c.providers["local"].api_key = "sk-provider-secret"
    c.channels.telegram.token = "123:telegram-secret"
    c.mcp_servers["m"] = cfgmod.McpServerCfg(env={"DB_PASSWORD": "hunter2"}, headers={"Authorization": "Bearer mcp-secret"})
    c.skills["weather"] = cfgmod.SkillEntry(api_key="skill-key", env={"X": "skill-env-secret"})
    return c


def test_secrets_written_encrypted_and_read_back(tmp_env):
    cfgmod.save(full_cfg())
    text = (tmp_env / "config.json").read_text()
    for plain in ("sk-provider-secret", "123:telegram-secret", "hunter2", "mcp-secret", "skill-key", "skill-env-secret"):
        assert plain not in text, plain
    assert text.count("enc:v1:") == 6
    back = cfgmod.load()
    assert back.providers["local"].api_key == "sk-provider-secret" and back.channels.telegram.token == "123:telegram-secret"
    assert back.mcp_servers["m"].env["DB_PASSWORD"] == "hunter2" and back.skills["weather"].env["X"] == "skill-env-secret"


def test_files_have_private_permissions(tmp_env):
    cfgmod.save(full_cfg())
    assert oct((tmp_env / "config.json").stat().st_mode & 0o777) == "0o600"
    assert oct((tmp_env / "master.key").stat().st_mode & 0o777) == "0o600"


def test_legacy_plaintext_config_loads_and_is_encrypted_on_next_save(tmp_env):
    (tmp_env / "config.json").write_text(json.dumps({"providers": {"local": {"type": "openai", "base_url": "http://x/v1", "model": "m", "api_key": "legacy-plain"}}}))
    cfg = cfgmod.load()
    assert cfg.providers["local"].api_key == "legacy-plain"
    cfgmod.save(cfg)
    assert "legacy-plain" not in (tmp_env / "config.json").read_text()
    assert cfgmod.load().providers["local"].api_key == "legacy-plain"


def test_lost_or_wrong_key_blanks_secret_and_reports_it(tmp_env):
    cfgmod.save(full_cfg())
    (tmp_env / "master.key").write_bytes(secrets.Fernet.generate_key())  # khoa chu bi thay
    cfg = cfgmod.load()
    assert cfg.providers["local"].api_key == "" and "providers.local.api_key" in secrets.failures
    assert cfg.default_provider == "local"  # phan con lai cua cau hinh van dung duoc


def test_missing_key_file_is_reported_not_crashing(tmp_env):
    cfgmod.save(full_cfg())
    (tmp_env / "master.key").unlink()
    assert cfgmod.load().channels.telegram.token == "" and secrets.failures


def test_env_master_key_overrides_file(tmp_env, monkeypatch):
    key = secrets.Fernet.generate_key().decode()
    monkeypatch.setenv("ARGUS_MASTER_KEY", key)
    cfgmod.save(full_cfg())
    assert not (tmp_env / "master.key").exists()  # khong tao file khi da co khoa trong env
    assert secrets.source() == "env" and cfgmod.load().providers["local"].api_key == "sk-provider-secret"


def test_encryption_can_be_disabled(tmp_env, monkeypatch):
    monkeypatch.setenv("ARGUS_ENCRYPT", "0")
    cfgmod.save(full_cfg())
    assert "sk-provider-secret" in (tmp_env / "config.json").read_text()


def test_empty_values_and_non_secrets_untouched(tmp_env):
    cfgmod.save(cfgmod.Config())
    text = (tmp_env / "config.json").read_text()
    assert "enc:v1:" not in text and '"model": "qwen2.5:3b"' in text


def test_status_counts(tmp_env):
    cfgmod.save(full_cfg())
    raw = json.loads((tmp_env / "config.json").read_text())
    st = secrets.status(raw)
    assert st["encrypted"] == 6 and st["plaintext"] == 0 and st["source"] == "file"


def test_masking_still_hides_decrypted_values(tmp_env):
    cfgmod.save(full_cfg())
    shown = json.dumps(cfgmod.masked(cfgmod.load()))
    assert "sk-provider-secret" not in shown and "enc:v1:" not in shown


def test_ciphertext_is_not_deterministic_but_both_decrypt(tmp_env):
    a, b = secrets.encrypt("same"), secrets.encrypt("same")
    assert a != b and secrets.decrypt(a) == secrets.decrypt(b) == "same"
