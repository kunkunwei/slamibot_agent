set +e
C=scout-nav-product-3edc3b9-test-20260903
echo '=== containers ==='
docker ps --filter name=firmware-sensors --filter name="$C" --format '{{.Names}}|{{.Status}}|{{.Image}}'
echo '=== firmware service ==='
curl -sS --max-time 5 -o /dev/null -w 'port5001 HTTP=%{http_code} TYPE=%{content_type} SIZE=%{size_download}\n' http://127.0.0.1:5001/ || true
echo '=== sensor/nav topics ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; for t in /clock /livox/lidar /livox/lidar/pointcloud /livox_pcl0 /scan /odom /amcl_pose; do echo ---$t; timeout 5 rostopic hz $t 2>&1 | tail -8; done; echo STAMPS; timeout 5 rostopic echo -n1 /clock; timeout 5 rostopic echo -n1 /livox_pcl0/header; timeout 5 rostopic echo -n1 /scan/header; timeout 5 rostopic echo -n1 /odom/header; timeout 5 rostopic echo -n1 /amcl_pose/header; echo TF; timeout 5 rosrun tf tf_echo map base_link || true'
echo '=== sensor logs ==='
docker logs --since 3m firmware-sensors 2>&1 | tail -120