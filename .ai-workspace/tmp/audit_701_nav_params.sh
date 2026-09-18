#!/usr/bin/env bash
set -u
C=scout-nav-video-link-5ad6000-test-20260904
echo '===INSPECT==='
docker inspect "$C" --format 'image={{.Config.Image}} imageid={{.Image}} status={{.State.Status}} restart={{.HostConfig.RestartPolicy.Name}}'
echo '===PARAM_FILES==='
for f in costmap_common_params_tuned.yaml global_costmap_params_tuned.yaml local_costmap_params_tuned.yaml teb_local_planner_params_tuned.yaml; do
  p="/Scout_mini_navigation/install/share/my_nav/config/tuned2/$f"
  h=$(docker exec "$C" sh -lc "sed 's/\r$//' '$p' | sha256sum | cut -d' ' -f1")
  printf '%s  %s\n' "$h" "$p"
done
p=/Scout_mini_navigation/install/share/my_nav/launch/move_base_tuned2.launch
h=$(docker exec "$C" sh -lc "sed 's/\r$//' '$p' | sha256sum | cut -d' ' -f1")
printf '%s  %s\n' "$h" "$p"
echo '===LIVE_NAV_PARAMS==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; rosparam get /move_base/TebLocalPlannerROS 2>/dev/null | grep -E "^(xy_goal_tolerance|yaw_goal_tolerance|max_vel_x|min_vel_x|max_vel_theta|min_vel_theta|acc_lim_x|acc_lim_theta):" || true; printf "controller_frequency="; rosparam get /move_base/controller_frequency 2>/dev/null || true; printf "planner_frequency="; rosparam get /move_base/planner_frequency 2>/dev/null || true'
