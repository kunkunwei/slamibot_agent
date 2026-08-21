#!/bin/bash
# Scout Mini 导航 Docker 入口
# 前置条件: 宿主机已启动 roscore + livox 雷达驱动 + /clock + CAN 底盘

set -e

# -------- ROS 环境 --------
source /opt/ros/noetic/setup.bash
source /Scout_mini_navigation/install/setup.bash
export ROS_PACKAGE_PATH=/Scout_mini_navigation/src:$ROS_PACKAGE_PATH


# 指向宿主机 roscore (host 网络模式下即本机)
export ROS_MASTER_URI="${ROS_MASTER_URI:-http://127.0.0.1:11311}"

echo "=========================================="
echo " ROS Master : $ROS_MASTER_URI"
echo " 工作空间   : /app"
echo "=========================================="

# -------- 1. rosbridge (WebSocket 19090, 非阻塞) --------
echo "[INFO] 启动 rosbridge_server (端口 19090)..."
rosrun rosbridge_server rosbridge_websocket __name:=scout_nav_rosbridge _port:=19090 _use_compression:=true > /tmp/rosbridge.log 2>&1 &
ROSBRIDGE_PID=$!
ROSBRIDGE_READY=0
for _ in $(seq 1 10); do
    if ! kill -0 "$ROSBRIDGE_PID" 2>/dev/null; then
        break
    fi
    if rosnode info /scout_nav_rosbridge >/dev/null 2>&1 && \
       timeout 1 bash -c 'exec 3<>/dev/tcp/127.0.0.1/19090' >/dev/null 2>&1; then
        ROSBRIDGE_READY=1
        break
    fi
    sleep 1
done
if [ "$ROSBRIDGE_READY" -eq 1 ]; then
    echo "[OK]   rosbridge 已启动 (PID=$ROSBRIDGE_PID)"
else
    echo "[ERROR] rosbridge 启动失败, 日志: /tmp/rosbridge.log"
    tail -n 50 /tmp/rosbridge.log || true
    exit 1
fi

# -------- 2. nav_multi_node (后台) --------
echo "[INFO] 启动 nav_multi_node ..."
rosrun nav_api nav_multi_node.py > /tmp/nav_multi.log 2>&1 &
NAV_PID=$!
sleep 1
if kill -0 "$NAV_PID" 2>/dev/null; then
    echo "[OK]   nav_multi_node 已启动 (PID=$NAV_PID)"
else
    echo "[ERROR] nav_multi_node 启动失败, 日志: /tmp/nav_multi.log"
    exit 1
fi

# -------- 3. Nginx Web 网关 --------
echo "[INFO] 启动 React Web + Nginx (端口 80)..."
nginx -t
nginx -g "daemon off;" > /tmp/nginx.log 2>&1 &
NGINX_PID=$!
sleep 1
if kill -0 "$NGINX_PID" 2>/dev/null; then
    echo "[OK]   Web 网关已启动 (PID=$NGINX_PID)"
else
    echo "[ERROR] Web 网关启动失败, 日志: /tmp/nginx.log"
    exit 1
fi

# -------- 4. FastAPI + MCP --------
cleanup() {
    trap - SIGINT SIGTERM
    echo ""
    echo "[INFO] 收到退出信号, 正在停止子进程..."
    for pid in "${API_PID:-}" "$NGINX_PID" "$ROSBRIDGE_PID" "$NAV_PID"; do
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    echo "[OK]   已退出"
}
trap 'cleanup; exit 0' SIGINT SIGTERM

echo "[INFO] 启动 FastAPI + MCP (端口 5000)..."
echo "=========================================="
echo " Web : http://<jetson-ip>/app/"
echo " API : http://<jetson-ip>:5000"
echo " 文档: http://<jetson-ip>:5000/docs"
echo " MCP : http://<jetson-ip>:5000/mcp"
echo "=========================================="

cd /Scout_mini_navigation/src/nav_api
export PYTHONPATH=/Scout_mini_navigation/src/nav_api
export SCOUT_NAV_WS=/Scout_mini_navigation
export ROSBRIDGE_HOST=127.0.0.1
export ROSBRIDGE_PORT=19090
export AUDIO_MIC_DEVICE=plughw:3,0
# Android WebView 通过 appassets 安全域加载本地前端，再跨域访问 BOX API。
# 保留环境变量覆盖能力，方便部署方追加浏览器或管理端来源。
export NAV_API_CORS_ORIGINS="${NAV_API_CORS_ORIGINS:-https://appassets.androidplatform.net}"
/opt/python-api/bin/python3 -m uvicorn fastapi_service.app:app \
    --host 0.0.0.0 --port 5000 &
API_PID=$!

set +e
wait "$API_PID"
STATUS=$?
cleanup
exit "$STATUS"
