#!/usr/bin/env bash
set -u
RUNTIME=/home/jetson/assistant_runtime
LOG="$RUNTIME/logs/xf_gateway.log"
export XF_CHAT_DIR=/home/jetson/xf_chat_standalone
while true; do
  "$RUNTIME/xf_gateway/run_gateway_demo.sh" >>"$LOG" 2>&1
  rc=$?
  printf '%s gateway exited rc=%s; retrying in 3s\n' "$(date -Is)" "$rc" >>"$LOG"
  sleep 3
done
