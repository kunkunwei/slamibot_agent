#!/bin/bash
set +e
echo ===SCOUT_PROCESSES===
docker exec scout-nav bash -lc 'source /opt/ros/noetic/setup.bash; ps -eo pid,ppid,stat,lstart,cmd | grep -E "roslaunch|map_server|amcl|move_base|pcd_map_publisher|nav_multi" | grep -v grep'
echo ===NODE_PINGS===
for n in /map_server /amcl /move_base /nav_multi /pcd_map_publisher; do
  echo NODE=$n
  docker exec scout-nav bash -lc "source /opt/ros/noetic/setup.bash; rosnode ping -c 1 $n 2>&1 | tail -3"
done
echo ===MAP_MESSAGE===
docker exec scout-nav bash -lc 'source /opt/ros/noetic/setup.bash; timeout 5 rostopic echo -n 1 /map/map_load_time 2>&1'
echo ===PCD_TOPIC===
docker exec scout-nav bash -lc 'source /opt/ros/noetic/setup.bash; rostopic info /global_cloud_navigation 2>&1'
echo ===MAP25_FILES===
docker exec scout-nav bash -lc 'ls -l /Scout_mini_navigation/src/my_nav/maps/api_map/map25/ 2>&1; test -f /Scout_mini_navigation/src/my_nav/maps/api_map/map25/map25_display.pcd; echo DISPLAY_PCD_EXIT=$?'
echo ===OAK===
docker exec core bash -lc 'source /root/SLAMIBOT_D360_Framework/install/setup.bash; ps -eo pid,ppid,stat,lstart,cmd | grep -E "oak_hardware_trigger_ros|depthai" | grep -v grep; for t in /SLB_CAM_A/compressed /SLB_CAM_B/compressed /SLB_CAM_C/compressed; do echo TOPIC=$t; rostopic info $t 2>&1 | sed -n "1,8p"; done'
