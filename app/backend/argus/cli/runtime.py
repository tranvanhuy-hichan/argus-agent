"""Khoi dong 'tai cho' (khong qua server HTTP): DB, workspace mau, MCP. Dung cho chat/run/token/skills."""
import time

from ..core import config as cfgmod
from ..core import db
from ..core.paths import ROOT
from ..core.workspace import ensure_workspace


def bootstrap(with_mcp: bool = False, wait: float = 8.0) -> cfgmod.Config:
    ROOT.mkdir(parents=True, exist_ok=True)
    db.init()
    cfg = cfgmod.load()
    ensure_workspace(cfg)
    if with_mcp and any(s.enabled for s in cfg.mcp_servers.values()):
        from ..services.mcp_client import manager

        manager.start()
        manager.apply(cfg.mcp_servers)
        end = time.time() + wait
        while time.time() < end and any(s["status"] == "connecting" for s in manager.status().values()):
            time.sleep(0.2)
    return cfg
