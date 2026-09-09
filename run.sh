#!/bin/sh
# Start the Touchline server (installs nothing; stdlib only).
cd "$(dirname "$0")"
if [ -f /tmp/fm.pid ]; then kill "$(cat /tmp/fm.pid)" 2>/dev/null; fi
mkdir -p data/saves
PORT="${PORT:-8000}" nohup python3 fm/app.py > /tmp/fm_server.log 2>&1 &
echo $! > /tmp/fm.pid
for i in $(seq 1 40); do
  if curl -s -m 2 -o /dev/null "http://localhost:${PORT:-8000}/api/boot"; then
    echo "Touchline is up on port ${PORT:-8000} (pid $(cat /tmp/fm.pid))"; exit 0
  fi
  sleep 0.5
done
echo "Server failed to start; last log lines:"; tail -20 /tmp/fm_server.log; exit 1
