# --- build giao dien
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

# --- chay
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 ARGUS_CONFIG=/app/data/config.json ARGUS_TEMPLATE=/app/template/workspace
WORKDIR /app
COPY backend/ backend/
RUN pip install --no-cache-dir -e backend
COPY --from=web /web/dist frontend/dist
# ban mau de server tu tao lai workspace khi nguoi dung mount thu muc trong
COPY workspace/SOUL.md /app/template/workspace/SOUL.md
COPY workspace/skills/example /app/template/workspace/skills/example
# du lieu (DB, config.json co API key) va workspace nen mount volume de khong mat khi build lai
VOLUME ["/app/data", "/app/workspace"]
EXPOSE 8787
WORKDIR /app/backend
# Bind 0.0.0.0 trong container; ben ngoai hay publish cong ve 127.0.0.1 (xem docker-compose.yml)
CMD ["uvicorn", "argus.main:app", "--host", "0.0.0.0", "--port", "8787"]
