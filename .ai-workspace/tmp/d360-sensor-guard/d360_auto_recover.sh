#!/usr/bin/env bash
set -o pipefail

LOCK=/run/lock/d360-auto-recover.lock
STAMP=/run/d360-auto-recover.last
COOLDOWN=180
RECOVER=/usr/local/sbin/d360-quick-recover
CLEAR_STALE=/usr/local/sbin/d360-clear-stale-clients
ROS_SETUP=/opt/ros/noetic/setup.bash
FRAMEWORK_SETUP=/root/SLAMIBOT_D360_Framework/install/setup.bash
BLOCKER_RE='rosbag|record_node|run_mapping_online|laserMapping|lidar_add_rgb'

log() { printf '[d360-auto-recover] %s\n' "$*"; }

exec 9>"$LOCK"
flock -n 9 || exit 0

[[ ${EUID:-$(id -u)} -eq 0 ]] || { log '必须以root运行'; exit 1; }
[[ -x "$RECOVER" ]] || { log "恢复脚本不存在: $RECOVER"; exit 1; }
[[ -x "$CLEAR_STALE" ]] || { log "旧连接清理脚本不存在: $CLEAR_STALE"; exit 1; }
"$CLEAR_STALE" || log '旧连接清理失败，本轮继续只读健康检查'
# shellcheck disable=SC1090
source "$ROS_SETUP"

ntp="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || true)"
hotspot_active="$(nmcli -t -f NAME connection show --active 2>/dev/null | grep -Fx 'Hotspot' || true)"
if [[ "$ntp" != yes && "$hotspot_active" != Hotspot ]]; then
  log 'NTP未同步且不在Hotspot模式，仅监控'
  exit 0
fi
[[ "$ntp" == yes ]] || log 'Hotspot离线模式'

duration_output="$(timeout 3 rostopic echo -n 1 /project_duration 2>/dev/null || true)"
duration="$(printf '%s\n' "$duration_output" | sed -n 's/^[[:space:]]*data:[[:space:]]*//p' | head -n1)"
[[ "$duration" == 0 || "$duration" == 0.0 ]] || { log "项目非空闲或状态未知: ${duration:-UNKNOWN}"; exit 0; }

core_top="$(docker top core 2>/dev/null || true)"
if printf '%s\n' "$core_top" | grep -Eq "$BLOCKER_RE"; then
  log '检测到标定/采集进程，仅告警不恢复'
  exit 0
fi

# 常态轻量检查：只读SystemMonitor已经汇总好的末端频率和状态位。
frequencies_output="$(timeout 3 rostopic echo -n 1 /topic_frequencies 2>/dev/null || true)"
read -r lidar_rate keyframe_rate <<EOF
$(printf '%s\n' "$frequencies_output" | python3 -c '
import json, re, sys
text = sys.stdin.read()
match = re.search(r"^data:\s*\"(.*)\"\s*$", text, re.M)
if not match:
    print("NA NA")
    raise SystemExit
data = json.loads(bytes(match.group(1), "utf-8").decode("unicode_escape"))
print(data.get("/livox/lidar", "NA"), data.get("/keyframe", "NA"))
' 2>/dev/null || printf 'NA NA')
EOF
status_output="$(timeout 3 rostopic echo -n 1 /driver_status 2>/dev/null || true)"
driver_status="$(printf '%s\n' "$status_output" | sed -n 's/^[[:space:]]*data:[[:space:]]*//p' | head -n1)"

reason=''
running="$(docker inspect -f '{{.State.Running}}' firmware-sensors 2>/dev/null || true)"
if [[ "$running" != true ]]; then
  reason='container_not_running'
else
  sensor_top="$(docker top firmware-sensors 2>/dev/null || true)"
  if ! printf '%s\n' "$sensor_top" | grep -q livox_ros_driver2_node; then
    reason='livox_process_missing'
  elif ! printf '%s\n' "$sensor_top" | grep -q oak_hardware_trigger_ros; then
    reason='oak_process_missing'
  elif [[ ! "$lidar_rate" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    reason='terminal_lidar_missing'
  elif awk -v r="$lidar_rate" 'BEGIN { exit !(r < 5 || r > 20) }'; then
    reason="terminal_lidar_rate_${lidar_rate}"
  elif [[ ! "$keyframe_rate" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    reason='terminal_keyframe_missing'
  elif awk -v r="$keyframe_rate" 'BEGIN { exit !(r < 1 || r > 10) }'; then
    reason="terminal_keyframe_rate_${keyframe_rate}"
  elif [[ ! "$driver_status" =~ ^[0-9]+$ ]]; then
    reason='driver_status_unknown'
  elif (( (driver_status & 3) != 3 )); then
    reason="driver_status_${driver_status}"
  fi
fi

[[ -n "$reason" ]] || { log "健康: lidar=${lidar_rate}Hz keyframe=${keyframe_rate}Hz status=${driver_status}"; exit 0; }
log "末端异常=$reason，开始一次深度确认"

# 仅在末端异常后订阅大消息或读取底层共享时间。
confirmed=''
case "$reason" in
  container_not_running|livox_process_missing|oak_process_missing)
    confirmed="$reason"
    ;;
  terminal_lidar_*|driver_status_*)
    point_num="$(docker exec firmware-sensors bash -lc "source '$ROS_SETUP'; source '$FRAMEWORK_SETUP'; timeout 4 rostopic echo -n 1 /livox/lidar/point_num" 2>/dev/null | awk '/^[[:space:]]*[0-9]+[[:space:]]*$/{print $1; exit}')"
    first="$(docker exec firmware-sensors sh -lc 'cat /dev/shm/timeshare | od -An -td8 -N16' 2>/dev/null | awk '{print $2}')"
    sleep 1
    second="$(docker exec firmware-sensors sh -lc 'cat /dev/shm/timeshare | od -An -td8 -N16' 2>/dev/null | awk '{print $2}')"
    if [[ -z "$point_num" || "$point_num" -lt 1000 ]]; then
      confirmed="livox_point_num_${point_num:-missing}"
    elif [[ -z "$first" || -z "$second" || "$first" == "$second" ]]; then
      confirmed='timeshare_frozen'
    elif [[ "$lidar_rate" =~ ^[0-9]+([.][0-9]+)?$ ]] && awk -v r="$lidar_rate" 'BEGIN { exit !(r > 100) }'; then
      confirmed="livox_packet_mode_${lidar_rate}Hz_${point_num}points"
    fi
    ;;
  terminal_keyframe_*)
    keyframe_header="$(timeout 4 rostopic echo -n 1 /keyframe/header 2>/dev/null || true)"
    if ! printf '%s\n' "$keyframe_header" | grep -q 'stamp:'; then
      confirmed='keyframe_no_frames'
      for topic in /SLB_CAM_A/compressed /SLB_CAM_B/compressed /SLB_CAM_C/compressed; do
        info="$(rostopic info "$topic" 2>/dev/null || true)"
        header="$(timeout 4 rostopic echo -n 1 "$topic/header" 2>/dev/null || true)"
        if ! printf '%s\n' "$info" | grep -q oak_hardware_trigger_ros; then
          confirmed="camera_publisher_missing_${topic}"
          break
        elif ! printf '%s\n' "$header" | grep -q 'stamp:'; then
          confirmed="camera_no_frames_${topic}"
          break
        fi
      done
    fi
    ;;
esac

[[ -n "$confirmed" ]] || { log '深度确认未复现，判定为瞬时抖动，不恢复'; exit 0; }

now="$(date +%s)"
last=0
[[ -f "$STAMP" ]] && read -r last < "$STAMP" || true
if [[ "$last" =~ ^[0-9]+$ ]] && (( now - last < COOLDOWN )); then
  log "确认故障=$confirmed，但处于冷却期$((COOLDOWN-now+last))秒"
  exit 0
fi
printf '%s\n' "$now" > "$STAMP"

log "确认故障=$confirmed，开始自动恢复"
if "$RECOVER"; then
  log '自动恢复PASS'
else
  rc=$?
  log "自动恢复FAIL rc=$rc；等待冷却后再检查"
  exit "$rc"
fi
