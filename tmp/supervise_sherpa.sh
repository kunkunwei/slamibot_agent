#!/usr/bin/env bash
set -u
RUNTIME=/home/jetson/assistant_runtime
SHERPA=/home/jetson/run_mic_sherpa
LOG="$RUNTIME/logs/sherpa.log"
while true; do
  until [ -e /dev/lg_speech_serial ] \
    && [ -x "$SHERPA/.venv/bin/python" ] \
    && /usr/bin/arecord -l 2>/dev/null | /bin/grep -q "ListenGo Circular 6-Microphone" \
    && /usr/bin/aplay -l 2>/dev/null | /bin/grep -q "USB Audio Device" \
    && curl --max-time 2 -fsS http://127.0.0.1:5000/health >/dev/null \
    && curl --max-time 2 -fsS http://127.0.0.1:5011/health >/dev/null; do
    sleep 2
  done
  "$SHERPA/.venv/bin/python" -u "$SHERPA/run_mic.py" \
    --server http://127.0.0.1:5000 \
    --serial-port /dev/lg_speech_serial \
    --status-interval 0.25 >>"$LOG" 2>&1
  rc=$?
  printf '%s sherpa exited rc=%s; retrying in 5s\n' "$(date -Is)" "$rc" >>"$LOG"
  sleep 5
done
