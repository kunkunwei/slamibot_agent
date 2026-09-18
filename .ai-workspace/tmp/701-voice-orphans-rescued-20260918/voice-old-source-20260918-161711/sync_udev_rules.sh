#!/bin/bash
# 同步 ListenGo 六麦串口别名到系统 udev 规则
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/99-serial-aliases.rules"
DST="/etc/udev/rules.d/99-serial-aliases.rules"

if [[ ! -f "$SRC" ]]; then
  echo "缺少规则文件: $SRC" >&2
  exit 1
fi

sudo cp "$SRC" "$DST"
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty
# 权限：加入 dialout，避免 MODE 未生效时无法打开串口
sudo usermod -aG dialout "$USER" || true

sleep 1
echo "=== 当前别名 ==="
ls -la /dev/lg_speech_serial /dev/ttySTM32 /dev/ttyRTK /dev/ttyDOG /dev/ttySBUS /dev/ttyGimbal 2>&1 || true
echo
if [[ -e /dev/lg_speech_serial ]]; then
  echo "OK: /dev/lg_speech_serial -> $(readlink -f /dev/lg_speech_serial)"
else
  echo "WARN: /dev/lg_speech_serial 未出现，请确认六麦已插入后重新插拔或重启"
fi
echo
echo "若刚加入 dialout 组，请重新登录后再运行语音程序。"
