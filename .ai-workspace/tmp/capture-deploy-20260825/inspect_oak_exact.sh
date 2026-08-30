#!/bin/bash
set +e
docker exec core bash -lc '
source /root/SLAMIBOT_D360_Framework/install/setup.bash
echo ===SENSORS_LAUNCH===
sed -n "1,140p" /root/SLAMIBOT_D360_Framework/install/share/project_control/launch/sensors.launch
echo ===OAK_PACKAGE_LAUNCH===
sed -n "1,120p" /root/SLAMIBOT_D360_Framework/install/share/ros1_oak_ffc_sync/launch/oak_hardware_trigger_ros.launch
echo ===PROJECT_CONTROL_LAUNCH_OAK_SECTION===
sed -n "45,85p" /root/SLAMIBOT_D360_Framework/install/share/project_control/launch/project_control.launch
echo ===CURRENT_RELEVANT_PROCESSES===
ps -eo pid,ppid,stat,lstart,cmd | grep -E "roslaunch|oak_hardware|depthai|camera_control|device_basic" | grep -v grep
echo ===ALL_OAK_LOG_FILES===
find /root/.ros/log -type f | grep -Ei "oak|hardware_trigger" | tail -80
echo ===PROCESS_DEATH_LINES===
grep -RhiE "oak_hardware_trigger_ros.*(died|exit|started)|process\[oak_hardware|Device likely crashed|X_LINK_ERROR|XLinkError" /root/.ros/log 2>/dev/null | tail -160
'
