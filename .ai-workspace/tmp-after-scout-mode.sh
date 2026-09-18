set +e
C=scout-nav-product-3edc3b9-test-20260903
echo '=== API/base ==='
curl -sS --max-time 5 http://127.0.0.1:5000/api/base_mode/status; echo
curl -sS --max-time 5 http://127.0.0.1:5000/api/status/; echo
echo '=== ROS rates ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; for t in /odom /scout_status /livox/lidar /livox_pcl0 /scan /amcl_pose; do echo ---$t; timeout 4 rostopic hz $t 2>&1 | tail -7; done; echo HEADERS; timeout 4 rostopic echo -n1 /odom/header; timeout 4 rostopic echo -n1 /scan/header; timeout 4 rostopic echo -n1 /amcl_pose/header; echo TF; timeout 5 rosrun tf tf_echo map base_link || true'