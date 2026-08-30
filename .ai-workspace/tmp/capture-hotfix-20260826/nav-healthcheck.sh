#!/bin/bash
# nav-healthcheck: 容器节点/话题自检与自愈(全面版)。
# 由 nav-api-entrypoint 启动后调用, 也可手动运行(无需参数)。
# 覆盖: 常驻节点 / 底盘 / 相机 / 地图 / 雷达时钟, 容器内可自愈的自愈,
# 宿主机依赖项输出明确原因与建议。全部只读检测 + 受控重启容器内节点。
set +e
source /opt/ros/noetic/setup.bash
source /Scout_mini_navigation/install/setup.bash
export ROS_MASTER_URI="${ROS_MASTER_URI:-http://127.0.0.1:11311}"
API="${API_HEALTHCHECK_URL:-http://127.0.0.1:5000}"

log()  { echo "[healthcheck] $*"; }
ok()   { log "[OK] $*"; }
warn() { log "[WARN] $*"; }
fail() { log "[FAIL] $*"; }

NAV_MULTI_CMD=(rosrun nav_api nav_multi_node.py)
ROSB_CMD=(rosrun rosbridge_server rosbridge_websocket __name:=scout_nav_rosbridge _port:=19090 _use_compression:=true)

log "===== 容器节点/话题自检与自愈开始 ====="

# 0) 等待 ROS Master
for i in $(seq 1 15); do
    rosnode list >/dev/null 2>&1 && { ok "ROS Master 可达"; break; }
    sleep 1
done

# 0.5) 确保 /use_sim_time=true (master 重启后参数服务器清空, nav_multi 时间门控会拒绝启动)
if [ "$(rosparam get /use_sim_time 2>/dev/null)" != "true" ]; then
    warn "/use_sim_time 非 true(master 重启后参数丢失), 重新设置"
    rosparam set /use_sim_time true
    if [ "$(rosparam get /use_sim_time 2>/dev/null)" = "true" ]; then
        ok "/use_sim_time=true 已恢复"
    else
        fail "无法设置 /use_sim_time=true"
    fi
else
    ok "/use_sim_time=true 正常"
fi

# 1) 常驻节点: nav_multi (服务注册=时间门控通过)
if timeout 8 rosservice list 2>/dev/null | grep -q "/nav_multi/execute"; then
    ok "nav_multi 服务已注册"
else
    warn "nav_multi 服务未注册, 尝试重启节点"
    pkill -f nav_multi_node.py 2>/dev/null; sleep 1
    "${NAV_MULTI_CMD[@]}" > /tmp/nav_multi.log 2>&1 &
    sleep 4
    if timeout 8 rosservice list 2>/dev/null | grep -q "/nav_multi/execute"; then
        ok "nav_multi 重启后已注册"
    else
        fail "nav_multi 仍未注册, 日志尾部:"; tail -5 /tmp/nav_multi.log 2>/dev/null
    fi
fi

# 2) 常驻节点: rosbridge (19090)
if timeout 5 rosnode info /scout_nav_rosbridge >/dev/null 2>&1; then
    ok "rosbridge 节点已注册"
else
    warn "rosbridge 未注册, 尝试重启"
    pkill -f rosbridge_websocket 2>/dev/null; sleep 1
    "${ROSB_CMD[@]}" > /tmp/rosbridge.log 2>&1 &
    sleep 3
    if timeout 5 rosnode info /scout_nav_rosbridge >/dev/null 2>&1; then
        ok "rosbridge 重启后已注册"
    else
        fail "rosbridge 未恢复, 日志尾部:"; tail -5 /tmp/rosbridge.log 2>/dev/null
    fi
fi

# 3) 底盘: /scout_base_node 注册 + /odom 发布 (自愈: 调 switch 触发自动重连)
if timeout 5 rosnode info /scout_base_node >/dev/null 2>&1; then
    ok "底盘节点 scout_base_node 已注册"
else
    warn "底盘节点未注册, 尝试通过 API 触发自动重连 (switch?mode=scout)"
    curl -s -m 25 "$API/api/base_mode/switch?mode=scout" >/dev/null 2>&1
    sleep 2
    if timeout 5 rosnode info /scout_base_node >/dev/null 2>&1; then
        ok "底盘节点已自动重连"
    else
        fail "底盘节点仍未注册(CAN 未通或驱动失败, 见 /tmp/scout_base_mode.log)"
    fi
fi
if timeout 6 rostopic echo -n 1 /odom >/dev/null 2>&1; then
    ok "/odom 有消息(底盘数据)"
else
    warn "/odom 无消息(底盘驱动未运行或 CAN 失联)"
fi

# 3.5) SystemMonitor 遥测 (电池/温度/存储/频率, core 容器 core.launch 发布)
#   注意: 依赖 core 容器先于 scout-nav 启动(容器启动顺序: core -> firmware-sensors -> scout-nav)。
#   SystemMonitor 因 STM32 串口(/dev/ttySTM32)故障会崩溃, 跨容器无法在此自愈, 只检测报告;
#   STM32 串口恢复后由 core.launch 重启或人工拉起。
if timeout 4 rostopic echo -n 1 /battery >/dev/null 2>&1; then
    ok "/battery 有消息(STM32 遥测正常)"
else
    warn "/battery 无消息(SystemMonitor 崩溃或 STM32 串口故障; 检查 core 容器 + /dev/ttySTM32 USB 掉线)"
fi
if timeout 4 rostopic echo -n 1 /cpu_temperature >/dev/null 2>&1; then
    ok "/cpu_temperature 有消息(SystemMonitor 正常)"
else
    warn "/cpu_temperature 无消息(SystemMonitor 未发布; STM32 串口故障时同 /battery)"
fi

# 4) 相机话题 (宿主机 oak 发布, 容器只检测不自愈)
if timeout 6 rostopic echo -n 1 /SLB_CAM_B/compressed >/dev/null 2>&1; then
    ok "/SLB_CAM_B/compressed 有消息(相机正常)"
else
    warn "/SLB_CAM_B/compressed 无消息(宿主机 oak 相机未运行或未发布, 检查 sensors.launch)"
fi

# 5) 地图话题 (map_server 在导航模式激活时运行)
if timeout 6 rostopic echo -n 1 /map >/dev/null 2>&1; then
    ok "/map 有消息(地图已加载)"
else
    warn "/map 无消息(导航模式未激活或无已选地图; 调 /api/control/mode/navigation 激活)"
fi

# 6) 雷达/时钟 (宿主机 livox 发布)
if timeout 6 rostopic echo -n 1 /clock >/dev/null 2>&1; then
    ok "/clock 有消息(虚拟时钟正常)"
else
    warn "/clock 无消息(宿主机 livox 雷达未启动, 容器无法自愈)"
fi
if timeout 6 rostopic echo -n 1 /scan >/dev/null 2>&1; then
    ok "/scan 有消息(2D 激光可用)"
else
    warn "/scan 无消息(点云转激光未运行, 需导航模式)"
fi

log "===== 自检与自愈完成 ====="
