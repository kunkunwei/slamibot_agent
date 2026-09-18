#!/usr/bin/env bash
set -o pipefail

CONTAINER="firmware-sensors"
ROS_SETUP="/opt/ros/noetic/setup.bash"
FRAMEWORK_SETUP="/root/SLAMIBOT_D360_Framework/install/setup.bash"
BLOCKER_RE='rosbag|record_node|run_mapping_online|laserMapping|lidar_add_rgb'
SENSOR_RE='livox_ros_driver2_node|oak_hardware_trigger_ros|oak_keyframe_stitcher'

log() { printf '[d360-quick-recover] %s\n' "$*"; }
fail() { log "FAIL: $*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || fail "请使用 sudo d360-quick-recover"
[[ -f "$ROS_SETUP" ]] || fail "缺少 $ROS_SETUP"
# shellcheck disable=SC1090
source "$ROS_SETUP"

log "1/8 安全检查"
ntp="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || true)"
hotspot_active="$(nmcli -t -f NAME connection show --active 2>/dev/null | grep -Fx 'Hotspot' || true)"
if [[ "$ntp" != "yes" && "$hotspot_active" != "Hotspot" ]]; then
  fail "NTP尚未同步且不在Hotspot模式（当前: ${ntp:-UNKNOWN}）"
fi
[[ "$ntp" == "yes" ]] || log "Hotspot离线模式：使用当前稳定时间基准"

duration_output="$(timeout 5 rostopic echo -n 1 /project_duration 2>/dev/null || true)"
duration="$(printf '%s\n' "$duration_output" | sed -n 's/^[[:space:]]*data:[[:space:]]*//p' | head -n 1)"
[[ "$duration" == "0.0" || "$duration" == "0" ]] || fail "项目状态不是空闲（project_duration=${duration:-UNKNOWN}）"

core_top="$(docker top core 2>/dev/null || true)"
if printf '%s\n' "$core_top" | grep -Eq "$BLOCKER_RE"; then
  printf '%s\n' "$core_top" | grep -E "$BLOCKER_RE" >&2 || true
  fail "检测到真实采集/标定进程，拒绝恢复"
fi

docker inspect "$CONTAINER" >/dev/null 2>&1 || fail "容器不存在: $CONTAINER"

log "2/8 停止容器（20秒）"
docker stop -t 20 "$CONTAINER" >/dev/null || fail "docker stop失败"

log "3/8 确认容器完全退出"
state="$(docker inspect -f '{{.State.Running}} {{.State.Pid}} {{.State.Status}}' "$CONTAINER" 2>/dev/null || true)"
[[ "$state" == "false 0 exited" ]] || fail "停止状态异常: ${state:-UNKNOWN}"

log "4/8 确认无残留真实进程"
remaining="$(pgrep -af "$SENSOR_RE" 2>/dev/null || true)"
[[ -z "$remaining" ]] || { printf '%s\n' "$remaining" >&2; fail "存在残留sensor进程，不自动kill"; }

log "5/8 清理ROS Master失效注册"
printf 'y\n' | rosnode cleanup || fail "rosnode cleanup失败"

log "6/8 启动容器"
docker start "$CONTAINER" >/dev/null || fail "docker start失败"
sleep 15

running="$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null || true)"
[[ "$running" == "true" ]] || fail "容器启动失败"

top="$(docker top "$CONTAINER" 2>/dev/null || true)"
for process in livox_ros_driver2_node oak_hardware_trigger_ros oak_keyframe_stitcher; do
  printf '%s\n' "$top" | grep -q "$process" || fail "缺少进程: $process"
done

log "7/8 验证雷达"
lidar_output="$(docker exec "$CONTAINER" bash -lc "source '$ROS_SETUP'; source '$FRAMEWORK_SETUP'; timeout 10 rostopic hz /livox/lidar" 2>&1 || true)"
printf '%s\n' "$lidar_output"
lidar_rate="$(printf '%s\n' "$lidar_output" | sed -n 's/.*average rate:[[:space:]]*\([0-9.]*\).*/\1/p' | tail -n 1)"
[[ -n "$lidar_rate" ]] || fail "雷达无频率"
awk -v r="$lidar_rate" 'BEGIN { exit !(r >= 5 && r <= 20) }' || fail "雷达频率异常: $lidar_rate Hz"

point_num="$(docker exec "$CONTAINER" bash -lc "source '$ROS_SETUP'; source '$FRAMEWORK_SETUP'; timeout 5 rostopic echo -n 1 /livox/lidar/point_num" 2>/dev/null | awk '/^[[:space:]]*[0-9]+[[:space:]]*$/{print $1; exit}')"
[[ -n "$point_num" && "$point_num" -ge 1000 ]] || fail "point_num异常: ${point_num:-UNKNOWN}"

first="$(docker exec "$CONTAINER" sh -lc "cat /dev/shm/timeshare | od -An -td8 -N16" 2>/dev/null | awk '{print $2}')"
sleep 1
second="$(docker exec "$CONTAINER" sh -lc "cat /dev/shm/timeshare | od -An -td8 -N16" 2>/dev/null | awk '{print $2}')"
[[ -n "$first" && -n "$second" && "$first" != "$second" ]] || fail "timeshare未更新"

log "8/8 验证三路相机和keyframe"
for topic in /SLB_CAM_A/compressed /SLB_CAM_B/compressed /SLB_CAM_C/compressed /keyframe; do
  output="$(timeout 8 rostopic hz "$topic" 2>&1 || true)"
  printf '%s\n' "$output"
  rate="$(printf '%s\n' "$output" | sed -n 's/.*average rate:[[:space:]]*\([0-9.]*\).*/\1/p' | tail -n 1)"
  [[ -n "$rate" ]] || fail "$topic 无数据"
done

log "PASS: lidar=${lidar_rate}Hz point_num=${point_num} timeshare更新，A/B/C/keyframe均有数据"
