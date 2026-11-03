#!/usr/bin/env bash
# Chay Agent: ./run.sh [start|stop|dev]   (mac dinh start, cong 8787)
set -euo pipefail
cd "$(dirname "$0")"
PORT="${AGENT_PORT:-8787}"
HOST="${AGENT_HOST:-127.0.0.1}"   # 0.0.0.0 de ung dung may khac goi /v1/* (can token)
PIDFILE=data/server.pid
mkdir -p data
case "${1:-start}" in
  stop)
    [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null && rm -f "$PIDFILE" && echo "da dung" || echo "khong co server dang chay" ;;
  start)
    [ -d frontend/dist ] || (cd frontend && npm install --no-fund --no-audit && npm run build)
    cd backend
    exec ../.venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT" ;;
  bg)
    cd backend
    nohup ../.venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT" > ../data/server.log 2>&1 &
    echo $! > "../$PIDFILE"; echo "chay nen, pid $(cat "../$PIDFILE"): http://127.0.0.1:$PORT" ;;
  dev)
    cd backend
    AGENT_DEV_ORIGINS="http://localhost:5173,http://127.0.0.1:5173" ../.venv/bin/uvicorn app.main:app --port "$PORT" --reload &
    cd ../frontend && npm run dev ;;
esac
