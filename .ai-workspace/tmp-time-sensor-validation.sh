set +e
C=scout-nav-product-3edc3b9-test-20260903
echo '=== host time ==='
date '+%F %T %z epoch=%s'
echo '=== clock publisher ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; rostopic info /clock; echo SAMPLE1; timeout 4 rostopic echo -n1 /clock; sleep 3; echo SAMPLE2; timeout 4 rostopic echo -n1 /clock; echo HZ; timeout 5 rostopic hz /clock'
echo '=== source topics ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; for t in /livox/lidar /livox_pcl0 /scan /odom /amcl_pose; do echo ---$t; rostopic info $t 2>&1; timeout 4 rostopic echo -n1 $t/header 2>&1 | head -10; done'
echo '=== relevant nodes ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; rosnode info /livox_lidar_publisher2 2>&1 | head -100; echo ---SCOUT; rosnode info /scout_base_node 2>&1 | head -120; echo ---PCL2SCAN; rosnode info /pointcloud_to_laserscan 2>&1 | head -120'
echo '=== nav process/logs ==='
docker exec "$C" bash -lc 'ps -ef | grep -E "[r]oslaunch|[a]mcl|[m]ove_base|[p]ointcloud_to_laserscan|[s]cout_base"; grep -hEi "jump back|time|transform|error|failed|odom|scan" /root/.ros/log/latest/*.log 2>/dev/null | tail -160 || true'
echo '=== firmware logs ==='
docker logs --since 10m firmware-sensors 2>&1 | grep -Ei 'clock|time|jump|error|livox' | tail -160 || true