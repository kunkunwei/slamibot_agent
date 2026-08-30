#!/bin/bash
set +e
echo '=== 5001 OWNER/HTTP ==='
ss -ltnp 'sport = :5001'
for p in / /health /stream /video_feed; do echo PATH=$p; curl -sS --max-time 3 -D - http://127.0.0.1:5001$p -o /tmp/codex-5001-body; head -c 200 /tmp/codex-5001-body; echo; done
echo '=== LAUNCH STATUS ==='
curl -sS --max-time 3 http://127.0.0.1:5000/api/launch/status; echo
echo '=== TOPIC PUBLISHERS ==='
docker exec core bash -lc 'source /opt/ros/noetic/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:11311; for t in /map /global_cloud_navigation /keyframe /SLB_CAM_A/compressed /SLB_CAM_B/compressed /SLB_CAM_C/compressed; do echo TOPIC=$t; rostopic info $t 2>&1 | grep -E "Type:|Publishers:| * /" | head -12; done'
echo '=== NODE PINGS ==='
docker exec core bash -lc 'source /opt/ros/noetic/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:11311; for n in /oak_hardware_trigger_ros /camera_service /map_server /move_base /fast_lio /scout_nav_rosbridge /rosbridge_websocket; do echo NODE=$n; rosnode ping -c 1 $n 2>&1; done'
echo '=== OAK PROCESS/ROS LOG ==='
docker exec core bash -lc 'ps -ef | grep -E "oak_hardware|depthai" | grep -v grep || true; LOGDIR=$(readlink -f /root/.ros/log/latest); echo LOGDIR=$LOGDIR; grep -RniE "oak_hardware_trigger_ros|Device likely crashed|X_LINK|process.*died|USB" "$LOGDIR" 2>/dev/null | tail -120' || true
