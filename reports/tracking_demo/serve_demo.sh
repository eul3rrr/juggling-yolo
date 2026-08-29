#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Be friendly when a previous demo server is already running.
if curl -fsS --max-time 2 http://127.0.0.1:8765/index.html 2>/dev/null | grep -q "Tracking Reconstruction Review"; then
  printf 'Demo server is already running at http://127.0.0.1:8765/\n'
  exit 0
fi

if ss -ltn 'sport = :8765' 2>/dev/null | grep -q ':8765'; then
  printf 'Port 8765 is occupied by another service; stop it or choose another port.\n' >&2
  exit 1
fi

exec python3 -m http.server 8765 --bind 127.0.0.1
