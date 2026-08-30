#!/bin/bash
set +e
docker exec core bash -lc '
source /root/SLAMIBOT_D360_Framework/install/setup.bash
echo ===CORE_LAUNCH===
sed -n "1,240p" /root/SLAMIBOT_D360_Framework/install/share/project_control/launch/core.launch
echo ===OAK_REFERENCES===
grep -RniE "oak_hardware|oak-camera|oak_camera|hardware_trigger|camera_service" /root/SLAMIBOT_D360_Framework/install/share/project_control /root/SLAMIBOT_D360_Framework/install/share 2>/dev/null | head -200
echo ===ROSLAUNCH_LOG_OAK===
L=$(readlink -f /root/.ros/log/latest)
echo LOGDIR=$L
grep -RniE "oak_hardware|Device.*crash|X_LINK|XLink|depthai|camera" "$L" 2>/dev/null | tail -240
echo ===MASTER_NODE_INFO===
rosnode info /oak_hardware_trigger_ros 2>&1
'
