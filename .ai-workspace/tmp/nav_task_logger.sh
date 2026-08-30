#!/usr/bin/env bash
# ============================================================================
# nav_task_logger.sh — 导航任务日志自动采集器（只读，不修改任何 ROS 状态）
#
# 功能：
#   - 监听 /nav_multi/status；检测到任务开始（state != IDLE）即自动采集，
#     任务回到 IDLE（结束/失败）或超时后停止并归档。
#   - 采集内容：相关节点、/map、/amcl_pose、/nav_multi/status、/move_base/goal、
#     /move_base/status（含 ABORTED text）、/move_base/feedback、/rosout、/tf、
#     以及任务结束瞬间的 global_costmap / /map 快照。
#
# 部署：Jetson 宿主机 /home/jetson/nav_task_logger.sh
# 用法：
#   bash nav_task_logger.sh daemon          # 守护模式：后台持续监听，每次任务自动采集
#   bash nav_task_logger.sh once [sec]      # 单次模式：立即采集 N 秒（默认 20），用于复现
# 输出目录：/home/jetson/nav_logs/<task_时间戳>/  （可用 NAV_LOG_ROOT 覆盖）
#
# 约束遵守：不使用 set -e / pipefail；只 kill 自己 fork 的采集子进程，不碰系统进程。
# ============================================================================

set +u

LOG_ROOT="${NAV_LOG_ROOT:-/home/jetson/nav_logs}"
ROS_SETUP="/opt/ros/noetic/setup.bash"
STATUS_TOPIC="/nav_multi/status"
MAX_SESSION_SECS=900
DEFAULT_ONCE_SECS=20
WAIT_POLL_SECS=3

mkdir -p "$LOG_ROOT" 2>/dev/null || { echo "无法创建 $LOG_ROOT"; exit 1; }
[ -f "$ROS_SETUP" ] && . "$ROS_SETUP" 2>/dev/null

say() { echo "[$(date '+%F %T')] $*"; }

# 读取 /nav_multi/status 的 state 字段；取不到返回空
get_state() {
  timeout 3 rostopic echo "$STATUS_TOPIC" -n 1 2>/dev/null \
    | grep -o '"state": *"[^"]*"' | head -1 \
    | sed -E 's/.*"state": *"([^"]*)".*/\1/'
}

# 任务终态快照（结束后补抓一次，保证有 ABORTED 的 text 和代价图）
final_snapshot() {
  local dir="$1"
  {
    echo "--- /move_base/status (final) ---"
    timeout 3 rostopic echo /move_base/status -n 1 --noarr 2>/dev/null | head -24
    echo "--- $STATUS_TOPIC (final) ---"
    timeout 3 rostopic echo "$STATUS_TOPIC" -n 1 2>/dev/null
    echo "--- /move_base/global_costmap/costmap (final) ---"
    timeout 4 rostopic echo /move_base/global_costmap/costmap -n 1 --noarr 2>/dev/null | head -14
    echo "--- /map (final) ---"
    timeout 4 rostopic echo /map -n 1 --noarr 2>/dev/null | head -14
  } > "$dir/final.txt" 2>&1
  # 尝试导出 move_base 文件日志（jetson 无 sudo 时自动跳过）
  if sudo -n cat /root/.ros/log/*/move_base*.log > "$dir/move_base_file.log" 2>/dev/null; then
    say "已导出 move_base 文件日志 ($(wc -l < "$dir/move_base_file.log") 行)"
  else
    say "跳过 move_base 文件日志（无权限；依赖 /move_base/status text + rosout）"
    rm -f "$dir/move_base_file.log"
  fi
}

# 采集一个任务周期，$1=输出目录；任务回到 IDLE 或超时即停止
collect_until_idle() {
  local dir="$1"
  mkdir -p "$dir"
  say "任务开始，采集到 $dir"

  {
    echo "# nav-task log  $(date '+%F %T %z')  host=$(hostname)"
    echo "--- relevant nodes ---"
    timeout 4 rosnode list 2>/dev/null | grep -Ei 'nav_multi|move_base|amcl|map_server|robot_state_publisher'
    echo "--- /map info ---"
    timeout 3 rostopic info /map 2>/dev/null
    echo "--- /amcl_pose ---"
    timeout 3 rostopic echo /amcl_pose -n 1 --noarr 2>/dev/null | head -14
    echo "--- $STATUS_TOPIC (baseline) ---"
    timeout 3 rostopic echo "$STATUS_TOPIC" -n 1 2>/dev/null
  } > "$dir/baseline.txt" 2>&1

  # 并行采集（全部无 timeout，结束时统一 kill）
  rostopic echo /rosout --noarr            > "$dir/rosout.txt" 2>&1 & P_ROS=$!
  rostopic echo /move_base/status --noarr  > "$dir/move_base_status.txt" 2>&1 & P_MB=$!
  rostopic echo /move_base/goal --noarr    > "$dir/move_base_goal.txt" 2>&1 & P_GOAL=$!
  rostopic echo /move_base/feedback --noarr > "$dir/move_base_feedback.txt" 2>&1 & P_FB=$!
  rostopic echo "$STATUS_TOPIC" --noarr    > "$dir/nav_multi_status.txt" 2>&1 & P_NM=$!
  rostopic echo /amcl_pose --noarr         > "$dir/amcl_pose.txt" 2>&1 & P_POSE=$!
  rostopic echo /tf --noarr                > "$dir/tf.txt" 2>&1 & P_TF=$!

  local elapsed=0
  while [ "$elapsed" -lt "$MAX_SESSION_SECS" ]; do
    sleep "$WAIT_POLL_SECS"; elapsed=$((elapsed + WAIT_POLL_SECS))
    local st; st="$(get_state)"
    if [ "$st" = "IDLE" ]; then say "任务回到 IDLE，停止采集"; break; fi
    if [ -z "$st" ]; then say "状态读取丢失（ROS 不可达？），停止采集"; break; fi
  done
  if [ "$elapsed" -ge "$MAX_SESSION_SECS" ]; then say "达到上限 ${MAX_SESSION_SECS}s，停止采集"; fi

  # 只 kill 本脚本 fork 的采集子进程
  for p in "$P_ROS" "$P_MB" "$P_GOAL" "$P_FB" "$P_NM" "$P_POSE" "$P_TF"; do
    kill "$p" 2>/dev/null
  done
  wait 2>/dev/null

  final_snapshot "$dir"
  say "完成 -> $dir  ($(du -sh "$dir" 2>/dev/null | cut -f1))"
}

# 单次模式：立即采集 N 秒
collect_once() {
  local secs="${1:-$DEFAULT_ONCE_SECS}"
  local dir="$LOG_ROOT/once_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$dir"
  say "单次采集 ${secs}s -> $dir"
  timeout "$secs" rostopic echo /rosout --noarr            > "$dir/rosout.txt" 2>&1 &
  timeout "$secs" rostopic echo /move_base/status --noarr  > "$dir/move_base_status.txt" 2>&1 &
  timeout "$secs" rostopic echo "$STATUS_TOPIC" --noarr    > "$dir/nav_multi_status.txt" 2>&1 &
  timeout "$secs" rostopic echo /amcl_pose --noarr         > "$dir/amcl_pose.txt" 2>&1 &
  wait 2>/dev/null
  final_snapshot "$dir"
  say "完成 -> $dir  ($(du -sh "$dir" 2>/dev/null | cut -f1))"
}

case "${1:-daemon}" in
  once)   collect_once "$2" ;;
  daemon)
    say "守护模式启动，流式监听 $STATUS_TOPIC ..."
    prev=""
    # 阻塞式订阅：任何一条非 IDLE 状态都会触发采集（不轮询，不漏快速任务）
    rostopic echo "$STATUS_TOPIC" --noarr 2>/dev/null | while IFS= read -r line; do
      # 从 JSON 行中提取 state；仅处理 data: "..." 行
      if echo "$line" | grep -q '"state"'; then
        st="$(echo "$line" | grep -o '"state": *"[^"]*"' | head -1 | sed -E 's/.*"state": *"([^"]*)".*/\1/')"
        if [ -n "$st" ] && [ "$st" != "IDLE" ] && [ "$prev" = "IDLE" -o -z "$prev" ]; then
          collect_until_idle "$LOG_ROOT/task_$(date +%Y%m%d_%H%M%S)"
        fi
        prev="$st"
      fi
    done
    ;;
  *) echo "用法: bash $0 [daemon|once [sec]]"; exit 1 ;;
esac
