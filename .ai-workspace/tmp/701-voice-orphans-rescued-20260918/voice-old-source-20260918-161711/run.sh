#!/bin/bash
# 自包含语音对话启动脚本（无需 ROS2）
# Standalone voice-chat launcher (no ROS2)

set -e
cd "$(dirname "$0")"

# 控制串口（唤醒/原始音频）。按实际设备修改，例如 /dev/ttyUSB0
PORT="${PORT:-/dev/lg_speech_serial}"

# ALSA 麦克风阵列设备名关键词（audio_source=alsa 时用）
DEVICE_KEYWORD="${DEVICE_KEYWORD:-ListenGo}"

exec python3 xf_mic_chat_standalone.py \
    --port "$PORT" \
    --device-keyword "$DEVICE_KEYWORD" \
    "$@"
