set +e
C=scout-nav-product-3edc3b9-test-20260903
echo '=== rates after lidar online ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; for t in /clock /livox/lidar /livox_pcl0 /scan /odom /amcl_pose; do echo ---$t; timeout 5 rostopic hz $t 2>&1 | tail -8; done; echo STAMPS; timeout 5 rostopic echo -n1 /scan/header; timeout 5 rostopic echo -n1 /odom/header; timeout 5 rostopic echo -n1 /amcl_pose/header; echo TF; timeout 5 rosrun tf tf_echo map base_link || true'