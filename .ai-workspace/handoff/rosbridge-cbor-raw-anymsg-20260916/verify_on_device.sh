#!/bin/bash
# 在【设备】上执行（只读）：收集 rosbridge 侧证据，判断 /global_cloud_navigation 是否被通配类型毒化
#
# 用法：  bash verify_on_device.sh            # 默认 core 容器
#         bash verify_on_device.sh core
#
# 判读（每张表现场都应当满足）：
#   1) "already established with type *" 次数 = 0
#   2) "AnyMsg" 次数 = 0
#   3) "is not a valid type string" 次数 = 0
#   任意一项 > 0 → 有客户端订阅姿势不对（不带 type / 把 compression 填进 type），先修客户端。

set -u
C="${1:-core}"
TOPIC="/global_cloud_navigation"

echo "=============================================================="
echo " 容器: $C       目标话题: $TOPIC"
echo "=============================================================="

echo "--- 1) 当前监听与连接 ---"
ss -ltn 2>/dev/null | grep -E ':(9090|19090)\b' || echo "(9090/19090 未监听)"
ss -tn state established 2>/dev/null | awk '$4 ~ /:9090$/ {print "  已连接对端:", $5}' | sort | uniq -c

echo
echo "--- 2) rosbridge 日志：客户端订阅/连线序列（最近 20 条）---"
docker exec "$C" bash -c "
L=\$(ls -t /root/.ros/log/*/rosbridge_websocket-*.log 2>/dev/null | head -1)
echo \"  log=\$L\"
grep -E 'Client connected|Client disconnected|Subscribed to ${TOPIC}|Subscribed to /map$' \"\$L\" 2>/dev/null | tail -20
"

echo
echo "--- 3) 关键错误计数（都应为 0）---"
docker exec "$C" bash -c "
L=\$(ls -t /root/.ros/log/*/rosbridge_websocket-*.log 2>/dev/null | head -1)
printf '  already established with type * : %s\n' \"\$(grep -c 'already established with type' \"\$L\" 2>/dev/null)\"
printf '  AnyMsg                          : %s\n' \"\$(grep -c 'AnyMsg' \"\$L\" 2>/dev/null)\"
printf '  is not a valid type string      : %s\n' \"\$(grep -c 'is not a valid type string' \"\$L\" 2>/dev/null)\"
printf '  当前话题订阅成功次数            : %s\n' \"\$(grep -c 'Subscribed to ${TOPIC}' \"\$L\" 2>/dev/null)\"
"

echo
echo "--- 4) 最近一条拒绝/异常原文（若有）---"
docker exec "$C" bash -c "
L=\$(ls -t /root/.ros/log/*/rosbridge_websocket-*.log 2>/dev/null | head -1)
grep -n -A9 -m1 '_slot_types' \"\$L\" 2>/dev/null
grep -n -m3 'already established with type\|is not a valid type string' \"\$L\" 2>/dev/null
"

echo
echo "--- 5) 对照：话题发布者与频率（发布侧健康时应有稳定频率）---"
C_NAV="$(docker ps --format '{{.Names}}' | grep scout-nav | head -1)"
if [ -n "$C_NAV" ]; then
  docker exec "$C_NAV" bash -lc "
source /opt/ros/noetic/setup.bash >/dev/null 2>&1; source /Scout_mini_navigation/install/setup.bash >/dev/null 2>&1
timeout 8 rostopic hz ${TOPIC} 2>&1 | grep -m1 'average rate' || echo '  (无数据)'
timeout 8 rostopic info ${TOPIC} 2>&1 | sed -n '/Publishers/,/^$/p'
"
else
  echo "  (未找到 scout-nav 容器)"
fi

echo
echo "提示：APP 侧订阅报文由客户端直接决定，本机可用 repro_ws_probe.py 对照验证。"
