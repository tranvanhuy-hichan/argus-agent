#!/usr/bin/env bash
# Tuong thich cu: ./run.sh [start|bg|stop|dev]  ->  dung lenh `argus` (xem: argus --help)
cd "$(dirname "$0")"
ARGUS=".venv/bin/argus"
if [ ! -x "$ARGUS" ]; then
  echo "Chua cai Argus. Chay: python3 -m venv .venv && .venv/bin/pip install -e app/backend" >&2
  exit 1
fi
case "${1:-start}" in
  start) exec "$ARGUS" start -f ;;   # foreground nhu truoc
  bg)    exec "$ARGUS" start ;;
  *)     exec "$ARGUS" "$@" ;;
esac
