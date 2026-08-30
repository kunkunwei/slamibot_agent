#!/bin/bash
set +e
echo '=== TIME/HOST ==='
date '+%F %T %Z'; hostname
echo '=== CONTAINERS ==='
docker ps -a --no-trunc --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}}'
echo '=== SCOUT INSPECT ==='
docker inspect scout-nav --format 'id={{.Id}} status={{.State.Status}} restart={{.RestartCount}} pid={{.State.Pid}} started={{.State.StartedAt}}'
echo '=== PORTS ==='
ss -ltnp | grep -E ':(80|5000|5001|9090|19090|11311) ' || true
echo '=== HOST ROS/VIDEO PROCESSES ==='
ps -eo pid,ppid,lstart,cmd | grep -E 'roscore|rosmaster|roslaunch|rosbridge|depthai|oak|camera|mjpeg|5001|move_base|map_server|fast_lio|livox' | grep -v grep || true
echo '=== API HEALTH/LAUNCH ==='
curl -sS --max-time 3 http://127.0.0.1:5000/health; echo
curl -sS --max-time 3 http://127.0.0.1:5000/api/launch/status; echo
echo '=== CORE LOG TAIL ==='
docker logs --tail 120 core 2>&1 || true
echo '=== SCOUT LOG TAIL ==='
docker logs --tail 160 scout-nav 2>&1 || true
echo '=== ROS NODE LIST ==='
docker exec core bash -lc 'source /opt/ros/noetic/setup.bash 2>/dev/null || true; export ROS_MASTER_URI=http://127.0.0.1:11311; rosnode list 2>&1' || true
echo '=== ROS TOPICS ==='
docker exec core bash -lc 'source /opt/ros/noetic/setup.bash 2>/dev/null || true; export ROS_MASTER_URI=http://127.0.0.1:11311; for t in /map /livox/lidar /cloud_registered /Odometry /SLB_CAM_A/compressed /SLB_CAM_B/compressed /SLB_CAM_C/compressed /nav_multi/status; do echo TOPIC=$t; rostopic info $t 2>&1 | sed -n "1,20p"; done' || true
echo '=== KEY NODE INFO ==='
docker exec core bash -lc 'source /opt/ros/noetic/setup.bash 2>/dev/null || true; export ROS_MASTER_URI=http://127.0.0.1:11311; for n in /map_server /move_base /scout_nav_rosbridge /rosbridge_websocket /nav_multi /oak_hardware_trigger_ros /oak_keyframe_stitcher; do echo NODE=$n; timeout 3 rosnode info $n 2>&1 | sed -n "1,35p"; done' || true
