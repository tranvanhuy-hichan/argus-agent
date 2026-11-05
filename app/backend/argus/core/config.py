import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from . import secrets
from .paths import CONFIG_PATH, ROOT

MASK = "***"


class ProviderCfg(BaseModel):
    description: str = ""  # mo ta cua nguoi dung cho model
    type: Literal["openai", "anthropic", "cli"] = "openai"  # cli: dung CLI da dang nhap san (khong can API key)
    cli: Literal["claude", "agy", "codex", "custom"] = "claude"  # type=cli: CLI nao
    command: str = ""  # type=cli: duong dan toi `claude`/`agy`/`codex`, hoac (cli=custom) ca dong lenh nhan prompt qua stdin va in tra loi ra stdout
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    api_key_env: str = ""
    temperature: float = Field(0.7, ge=0, le=2)
    vision: bool = False  # model nhan duoc anh (gui anh dinh kem dang data URL)
    context_window: int = Field(0, ge=0)  # so token toi da model nhan trong mot luot; 0 = tu nhan theo ten model
    price_in: float = Field(0.0, ge=0)  # USD / 1 trieu token vao, de uoc tinh chi phi
    price_out: float = Field(0.0, ge=0)


class AgentCfg(BaseModel):
    workspace: str = "workspace"
    max_steps: int = Field(10, ge=1, le=50)
    max_history: int = Field(30, ge=4, le=500)
    confirm_exec: bool = True
    tools_enabled: dict[str, bool] = {}
    compact_chars: int = Field(24000, ge=4000)  # vuot nguong nay thi tom tat phan hoi thoai cu
    exec_sandbox: Literal["none", "docker"] = "none"
    sandbox_image: str = "python:3.12-slim"
    sandbox_network: bool = False
    fast_provider: str = ""  # model nhanh/re cho cau don gian khi dang dung model mac dinh; rong = tat
    suggest_habits: bool = True  # nhận ra việc lặp lại và gợi ý tạo skill/automation


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
    service: bool = False  # them tu tab 'MCP dich vu' (danh muc / thu vien): hien o tab do thay vi tab truyen thong
    oauth: bool = False  # server tu xa dang nhap bang OAuth (Notion, Canva, Linear...): token luu ma hoa, khong nam trong config
    oauth_scope: str = ""
    enabled: bool = True
    confirm: bool = True  # hoi truoc khi goi tool (tru tool danh dau read-only)


class HeartbeatCfg(BaseModel):
    enabled: bool = False
    interval_minutes: int = Field(60, ge=5, le=1440)
    provider: str | None = None


class TelegramCfg(BaseModel):
    enabled: bool = False
    token: str = ""
    allowed_users: list[int] = []
    api_base: str = "https://api.telegram.org"


class ChannelsCfg(BaseModel):
    telegram: TelegramCfg = TelegramCfg()


class AuthCfg(BaseModel):
    salt: str = ""
    password_hash: str = ""


class BrowserCfg(BaseModel):
    enabled: bool = True
    headless: bool = True
    executable: str = ""  # trong = tu tim chromium/chrome trong may
    allow_private: bool = False  # cho phep mo localhost / dia chi noi bo
    idle_minutes: int = Field(10, ge=1, le=240)


class MemoryCfg(BaseModel):
    embeddings: Literal["off", "auto", "ollama", "openai", "hash"] = "auto"
    provider: str | None = None  # ten provider dung de lay embedding (openai/ollama); None = tu chon
    model: str = ""  # trong = model mac dinh cua backend
    auto_index: bool = True


class MediaCfg(BaseModel):
    image_provider: str | None = None  # ten provider co API sinh anh
    image_model: str = "gemini-2.5-flash-image"
    vision_provider: str | None = None  # provider dung de mo ta anh khi model chinh khong biet xem anh


class ComputerCfg(BaseModel):
    enabled: bool = False  # tat mac dinh; bat = agent co the xem man hinh va dieu khien chuot/ban phim (luon hoi phe duyet)


class AgentProfile(BaseModel):
    description: str = ""
    prompt: str = ""
    tools: list[str] = []  # trong = moi tool tru tool tao agent con
    provider: str | None = None
    max_steps: int = Field(20, ge=1, le=100)


class AgentsCfg(BaseModel):
    max_depth: int = Field(2, ge=0, le=4)
    max_parallel: int = Field(3, ge=1, le=8)
    task_max_steps: int = Field(40, ge=5, le=200)
    profiles: dict[str, AgentProfile] = {
        "researcher": AgentProfile(description="Tìm kiếm và tổng hợp thông tin trên web", prompt="Bạn là nhà nghiên cứu cẩn thận. Tìm nhiều nguồn, đối chiếu, nêu nguồn và nói rõ điều chưa chắc chắn.",
                                   tools=["web_search", "web_fetch", "read", "list_dir", "memory_search"], max_steps=15),
        "coder": AgentProfile(description="Viết, chạy và sửa code", prompt="Bạn là lập trình viên. Viết code ngắn gọn, chạy thử để kiểm chứng, sửa lỗi cho tới khi chạy đúng.",
                              tools=["read", "write", "edit", "exec", "list_dir"], max_steps=25),
        "reviewer": AgentProfile(description="Đọc và đánh giá (chỉ đọc)", prompt="Bạn là người phản biện kỹ tính. Chỉ đọc, không sửa gì. Nêu lỗi, rủi ro và đề xuất cụ thể.",
                                 tools=["read", "list_dir", "memory_search"], max_steps=12),
    }


class Config(BaseModel):
    default_provider: str = "local"
    fallback: list[str] = []
    providers: dict[str, ProviderCfg] = {
        "local": ProviderCfg(base_url="http://localhost:11434/v1", model="qwen2.5:3b"),
    }
    agent: AgentCfg = AgentCfg()
    skills: dict[str, SkillEntry] = {}
    mcp_servers: dict[str, McpServerCfg] = {}
    heartbeat: HeartbeatCfg = HeartbeatCfg()
    browser: BrowserCfg = BrowserCfg()
    memory: MemoryCfg = MemoryCfg()
    media: MediaCfg = MediaCfg()
    computer: ComputerCfg = ComputerCfg()
    agents: AgentsCfg = AgentsCfg()
    channels: ChannelsCfg = ChannelsCfg()
    auth: AuthCfg = AuthCfg()
    clawhub_url: str = "https://clawhub.ai"
    language: Literal["auto", "vi", "en"] = "auto"  # ngon ngu cua CLI (giao dien web tu chon theo trinh duyet)

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
    return Config.model_validate(secrets.decrypt_tree(raw))


def save(cfg: Config, encrypt: bool | None = None) -> None:
    """Ghi config.json. Khoa bi mat duoc ma hoa (neu bat) va file duoc tao voi quyen 600 ngay tu dau, ghi nguyen tu qua file tam."""
    data = cfg.model_dump()
    if secrets.enabled() if encrypt is None else encrypt:
        secrets.encrypt_tree(data)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, CONFIG_PATH)


def masked(cfg: Config) -> dict:
    out = cfg.model_dump()
    for p in out["providers"].values():
        if p["api_key"]:
            p["api_key"] = MASK
    for s in out["skills"].values():
        if s["api_key"]:
            s["api_key"] = MASK
        s["env"] = {k: (MASK if v else "") for k, v in s["env"].items()}
    if out["channels"]["telegram"]["token"]:
        out["channels"]["telegram"]["token"] = MASK
    out["auth"] = {"has_password": bool(cfg.auth.password_hash)}
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
    if new.channels.telegram.token == MASK:
        new.channels.telegram.token = old.channels.telegram.token
    new.auth = old.auth  # mat khau chi doi qua /api/auth
    return new


def merge_mcp_secrets(new: dict[str, McpServerCfg], old: dict[str, McpServerCfg]) -> None:
    for name, m in new.items():
        o = old.get(name)
        for field in ("env", "headers"):
            cur: dict[str, str] = getattr(m, field)
            for k, v in list(cur.items()):
                if v == MASK:
                    cur[k] = getattr(o, field).get(k, "") if o else ""
