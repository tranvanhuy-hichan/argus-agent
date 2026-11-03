import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .paths import CONFIG_PATH, ROOT

MASK = "***"


class ProviderCfg(BaseModel):
    type: Literal["openai", "anthropic"] = "openai"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    api_key_env: str = ""
    temperature: float = Field(0.7, ge=0, le=2)


class AgentCfg(BaseModel):
    workspace: str = "workspace"
    max_steps: int = Field(10, ge=1, le=50)
    max_history: int = Field(30, ge=4, le=500)
    confirm_exec: bool = True
    tools_enabled: dict[str, bool] = {}


class SkillEntry(BaseModel):
    enabled: bool = True
    api_key: str = ""
    env: dict[str, str] = {}


class McpServerCfg(BaseModel):
    transport: Literal["stdio", "http", "sse"] = "stdio"
    command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}
    cwd: str = ""
    url: str = ""
    headers: dict[str, str] = {}
    enabled: bool = True
    confirm: bool = True  # hoi truoc khi goi tool (tru tool danh dau read-only)


class Config(BaseModel):
    default_provider: str = "local"
    fallback: list[str] = []
    providers: dict[str, ProviderCfg] = {
        "local": ProviderCfg(base_url="http://localhost:11434/v1", model="qwen2.5:3b"),
    }
    agent: AgentCfg = AgentCfg()
    skills: dict[str, SkillEntry] = {}
    mcp_servers: dict[str, McpServerCfg] = {}
    clawhub_url: str = "https://clawhub.ai"

    def workspace_path(self) -> Path:
        p = Path(self.agent.workspace)
        return p if p.is_absolute() else ROOT / p


def load() -> Config:
    if not CONFIG_PATH.exists():
        return Config()
    raw = json.loads(CONFIG_PATH.read_text())
    agent = raw.get("agent", {})
    if "confirm_shell" in agent:  # cau hinh cu
        agent.setdefault("confirm_exec", agent.pop("confirm_shell"))
    return Config.model_validate(raw)


def save(cfg: Config) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg.model_dump(), indent=2, ensure_ascii=False))
    CONFIG_PATH.chmod(0o600)


def masked(cfg: Config) -> dict:
    out = cfg.model_dump()
    for p in out["providers"].values():
        if p["api_key"]:
            p["api_key"] = MASK
    for s in out["skills"].values():
        if s["api_key"]:
            s["api_key"] = MASK
        s["env"] = {k: (MASK if v else "") for k, v in s["env"].items()}
    for m in out["mcp_servers"].values():
        m["env"] = {k: (MASK if v else "") for k, v in m["env"].items()}
        m["headers"] = {k: (MASK if v else "") for k, v in m["headers"].items()}
    return out


def merge_secrets(new: Config, old: Config) -> Config:
    """Gia tri MASK tu UI nghia la 'giu nguyen bi mat cu'."""
    for name, p in new.providers.items():
        if p.api_key == MASK:
            p.api_key = old.providers[name].api_key if name in old.providers else ""
    for name, s in new.skills.items():
        o = old.skills.get(name)
        if s.api_key == MASK:
            s.api_key = o.api_key if o else ""
        for k, v in list(s.env.items()):
            if v == MASK:
                s.env[k] = o.env.get(k, "") if o else ""
    merge_mcp_secrets(new.mcp_servers, old.mcp_servers)
    return new


def merge_mcp_secrets(new: dict[str, McpServerCfg], old: dict[str, McpServerCfg]) -> None:
    for name, m in new.items():
        o = old.get(name)
        for field in ("env", "headers"):
            cur: dict[str, str] = getattr(m, field)
            for k, v in list(cur.items()):
                if v == MASK:
                    cur[k] = getattr(o, field).get(k, "") if o else ""
