# Argus Agent

Trợ lý AI cá nhân chạy trên máy bạn, kiến trúc kiểu OpenClaw: một gateway chạy nền, giao diện web, skill dạng `SKILL.md`, bộ nhớ bằng file markdown, tool, MCP và automations.

- **Model**: Ollama và các server local (LM Studio, vLLM), cùng Gemini, Claude, OpenAI, OpenRouter, DeepSeek, Mistral, xAI, Groq, Cerebras, Together, Fireworks, Qwen và mọi API tương thích OpenAI. Có fallback giữa các provider.
- **Skills**: đọc định dạng skill của OpenClaw, duyệt và cài trực tiếp từ [ClawHub](https://clawhub.ai).
- **MCP client**: nối MCP server của bạn (stdio, HTTP, SSE), tool xuất hiện cho agent dưới dạng `tênserver__têntool`.
- **Cho app khác gọi agent**: `POST /v1/run` với API token, hoặc MCP server `agent_run` (dùng được trong Claude Code, Cursor...).
- **Automations**: chạy prompt theo lịch cron. **Dashboard**: token, lượt gọi, tool, độ trễ.
- **An toàn mặc định**: lệnh shell, file ngoài workspace và tool MCP đều hỏi xác nhận; server chỉ nhận kết nối từ localhost; token API chỉ lưu bản băm.

## Chạy

Cần Python 3.11+ và Node 20+.

```bash
python3 -m venv .venv
.venv/bin/pip install -e backend
(cd frontend && npm install && npm run build)
./run.sh bg        # mở http://127.0.0.1:8787   |   ./run.sh stop để dừng
```

Chế độ phát triển (hot reload, cổng 5173): `./run.sh dev`. Dùng từ máy khác: `AGENT_HOST=0.0.0.0 ./run.sh bg` (chỉ `/v1/*` có token nhận kết nối từ xa).

Lần đầu, vào **Providers** để thêm model (mặc định trỏ tới Ollama `localhost:11434`, model `qwen2.5:3b`).

## Cấu trúc

```
backend/app/
  api/        # router FastAPI: chat, skills, providers, tích hợp, API ngoài (/v1)
  services/   # agent loop, providers, tools, skills, ClawHub, MCP, scheduler
  core/       # cấu hình, SQLite
  mcp_server.py   # MCP server (stdio) đưa agent ra ngoài như một tool
frontend/src/     # React + TypeScript + Tailwind (features/ theo từng trang)
examples/         # MCP server mẫu để thử tích hợp
workspace/        # SOUL.md, USER.md, MEMORY.md, skills/ (persona và bộ nhớ của agent)
```

## Lưu ý bảo mật

- Skill tải từ internet chỉ là hướng dẫn, nhưng có thể bảo agent chạy lệnh. Đọc `SKILL.md` trước khi cài và giữ xác nhận lệnh shell luôn bật.
- MCP server stdio chạy lệnh bạn khai báo với quyền của chính bạn. Chỉ thêm server bạn tin tưởng.
- `config.json` chứa API key (quyền 600) và đã được đưa vào `.gitignore`.
