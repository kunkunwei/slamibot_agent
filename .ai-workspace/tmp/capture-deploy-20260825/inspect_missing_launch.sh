#!/bin/bash
set +e
echo '=== SENSOR LAUNCH DEFINITIONS ==='
docker exec core bash -lc 'source /opt/ros/noetic/setup.bash; P=$(rospack find project_control); echo PROJECT_CONTROL=$P; grep -RniE "oak_hardware|ros1_oak|camera_control|5001" "$P/launch" "$P" 2>/dev/null | head -120'
echo '=== OAK LOG FILES ==='
docker exec core bash -lc 'L=$(readlink -f /root/.ros/log/latest); find "$L" -maxdepth 1 -type f | grep -Ei "oak|camera" | sort; for f in $(find "$L" -maxdepth 1 -type f | grep -Ei "oak_hardware|oak.*stdout|oak.*stderr" | sort); do echo FILE=$f; tail -120 "$f"; done'
echo '=== ROSLAUNCH PROCESS STATE ==='
docker exec core bash -lc 'ps -eo pid,ppid,stat,lstart,cmd | grep -E "roslaunch.*(sensors|core)" | grep -v grep'
