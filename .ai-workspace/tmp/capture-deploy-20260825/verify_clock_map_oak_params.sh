#!/bin/bash
set +e
echo ===ROS_TIME===
docker exec scout-nav bash -lc 'source /opt/ros/noetic/setup.bash; echo -n use_sim_time=; rosparam get /use_sim_time 2>&1; echo CLOCK_INFO; rostopic info /clock 2>&1; echo CLOCK_SAMPLE; timeout 3 rostopic echo -n 1 /clock 2>&1'
echo ===MAP_INFO===
docker exec scout-nav bash -lc 'source /opt/ros/noetic/setup.bash; rostopic info /map 2>&1; echo MAP_SAMPLE; timeout 5 rostopic echo -n 1 /map 2>&1 | head -30'
echo ===MAP_SERVER_LOG===
docker exec scout-nav bash -lc 'L=$(readlink -f /root/.ros/log/latest); echo LOGDIR=$L; tail -100 "$L"/map_server-*.log 2>&1'
echo ===OAK_PARAMS===
docker exec core bash -lc 'source /root/SLAMIBOT_D360_Framework/install/setup.bash; rosparam get /oak_hardware_trigger_ros 2>&1; echo URI; rosnode info /oak_hardware_trigger_ros 2>&1 | tail -12'
