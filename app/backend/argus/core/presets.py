"""Provider mau dung cho `argus onboard` (giong danh sach trong trang Providers cua giao dien web)."""
from typing import NamedTuple


class Preset(NamedTuple):
    id: str
    label: str
    type: str  # openai | anthropic
    base_url: str
    model: str
    env: str  # ten bien moi truong chua API key ("" = khong can key)


PRESETS: list[Preset] = [
    Preset("gemini", "Google Gemini", "openai", "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash", "GEMINI_API_KEY"),
    Preset("openai", "OpenAI", "openai", "https://api.openai.com/v1", "gpt-4o-mini", "OPENAI_API_KEY"),
    Preset("anthropic", "Anthropic (Claude)", "anthropic", "", "claude-sonnet-5-5", "ANTHROPIC_API_KEY"),
    Preset("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini", "OPENROUTER_API_KEY"),
    Preset("deepseek", "DeepSeek", "openai", "https://api.deepseek.com/v1", "deepseek-chat", "DEEPSEEK_API_KEY"),
    Preset("mistral", "Mistral AI", "openai", "https://api.mistral.ai/v1", "mistral-small-latest", "MISTRAL_API_KEY"),
    Preset("groq", "Groq", "openai", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "GROQ_API_KEY"),
    Preset("xai", "xAI (Grok)", "openai", "https://api.x.ai/v1", "grok-4", "XAI_API_KEY"),
    Preset("lmstudio", "LM Studio (local)", "openai", "http://localhost:1234/v1", "local-model", ""),
    Preset("custom", "Custom (OpenAI-compatible)", "openai", "http://", "", ""),
]
OLLAMA = Preset("ollama", "Ollama (local)", "openai", "http://localhost:11434/v1", "qwen2.5:3b", "")
