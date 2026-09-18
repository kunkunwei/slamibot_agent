set +e
C=scout-nav-product-3edc3b9-test-20260903
echo '=== new container processes ==='
docker exec "$C" bash -lc 'ps -ef | grep -E "[s]cout_base|[p]ointcloud_to_laserscan|[a]mcl|[m]ove_base|[m]ap_server|[l]idar_to_scan|[r]oslaunch"'
echo '=== node pings ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; for n in /livox_lidar_publisher2 /livox_repub /pointcloud_to_laserscan /scout_base_node /amcl /move_base; do echo ---$n; rosnode ping -c1 $n 2>&1; done'
echo '=== topic rates with product install sourced ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; for t in /livox/lidar /livox/lidar/pointcloud /livox_pcl0 /scan /scout_status /odom; do echo ---$t; timeout 5 rostopic hz $t 2>&1; done'
echo '=== one source header ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; timeout 5 rostopic echo -n1 /livox/lidar/header 2>&1; timeout 5 rostopic echo -n1 /livox/lidar/pointcloud/header 2>&1'
echo '=== process ownership by container ==='
for x in firmware-sensors core "$C"; do echo ---$x; docker top "$x" -eo pid,ppid,stat,cmd 2>/dev/null | grep -E 'livox|repub|scout_base|pointcloud_to_laserscan|roslaunch' || true; done
echo '=== targeted ros logs ==='
docker exec "$C" bash -lc 'for f in /root/.ros/log/latest/scout_base_node-*.log /root/.ros/log/latest/pointcloud_to_laserscan-*.log /root/.ros/log/latest/amcl-*.log; do [ -f "$f" ] && { echo ---$f; tail -100 "$f"; }; done'