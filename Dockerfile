# --- build giao dien
FROM node:22-slim AS web
WORKDIR /web
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY app/frontend/ ./
RUN npm run build

# --- chay
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 ARGUS_HOME=/app ARGUS_CONFIG=/app/data/config.json ARGUS_TEMPLATE=/app/template/workspace
WORKDIR /app
COPY app/backend/ app/backend/
RUN pip install --no-cache-dir -e app/backend
COPY --from=web /web/dist app/frontend/dist
# ban mau de server tu tao lai workspace khi nguoi dung mount thu muc trong
COPY app/templates/workspace /app/template/workspace
# du lieu (DB, config.json co API key) va workspace nen mount volume de khong mat khi build lai
VOLUME ["/app/data", "/app/workspace"]
EXPOSE 8787
WORKDIR /app/app/backend
# Bind 0.0.0.0 trong container; ben ngoai hay publish cong ve 127.0.0.1 (xem docker-compose.yml)
CMD ["uvicorn", "argus.main:app", "--host", "0.0.0.0", "--port", "8787"]
