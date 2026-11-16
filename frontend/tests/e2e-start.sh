#!/usr/bin/env bash
set -euo pipefail

python tests/e2e_server.py &
API_PID=$!
cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

for attempt in $(seq 1 60); do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "E2E API fixture exited before becoming ready" >&2
    exit 1
  fi
  sleep 1
done

curl --fail --silent http://127.0.0.1:8000/health >/dev/null
npm run dev -- --host 127.0.0.1
