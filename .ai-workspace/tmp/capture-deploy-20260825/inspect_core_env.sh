#!/bin/bash
set +e
docker exec core bash -lc '
echo ===PID1_ENV===
tr "\0" "\n" </proc/1/environ | grep -E "^(ROS_PACKAGE_PATH|CMAKE_PREFIX_PATH|PWD|ROS_MASTER_URI|ROS_IP|ROS_HOSTNAME)="
echo ===PID1_CWD===
readlink -f /proc/1/cwd
echo ===CMDLINE===
tr "\0" " " </proc/1/cmdline
echo
echo ===PROJECT_CONTROL_DIRS===
find / -xdev -type d -name project_control 2>/dev/null | head -20
echo ===CORE_LAUNCH_FILES===
find / -xdev -type f -path "*/project_control/launch/core.launch" 2>/dev/null | head -20
'
