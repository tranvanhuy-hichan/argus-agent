import pytest

from argus.core import config as cfgmod
from argus.core import db as dbmod
from argus.core import secrets


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    """Co lap moi thu: DB, config.json va workspace nam trong thu muc tam."""
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "agent.db")
    monkeypatch.setattr(dbmod, "DATA", tmp_path)
    monkeypatch.setattr(cfgmod, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(secrets, "KEY_FILE", tmp_path / "master.key")
    monkeypatch.delenv("ARGUS_MASTER_KEY", raising=False)
    monkeypatch.delenv("AGENT_MASTER_KEY", raising=False)
    secrets.failures.clear()
    ws = tmp_path / "workspace"
    ws.mkdir()
    cfg = cfgmod.Config()
    cfg.agent.workspace = str(ws)
    cfgmod.save(cfg)
    dbmod.init()
    return tmp_path
