set -u
printf '%s\n' '===HOST==='; date -Ins; hostname
printf '%s\n' '===CONTAINERS==='; docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}'
printf '%s\n' '===FIRMWARE TOP==='; docker top firmware-sensors -eo pid,ppid,etime,stat,cmd
printf '%s\n' '===HOST OAK/DEPTHAI PROCS==='; ps -eo pid,ppid,etime,stat,cmd | grep -E '[o]ak|[d]epthai|[Xx][Ll][Ii][Nn][Kk]' || true
printf '%s\n' '===USB==='; lsusb | grep -Ei '03e7|movidius|luxonis|oak' || true
printf '%s\n' '===ROS OAK NODES==='
docker exec firmware-sensors bash -lc 'source /opt/ros/noetic/setup.bash; source /root/SLAMIBOT_D360_Framework/install/setup.bash; rosnode list 2>/dev/null | grep -Ei "oak|camera|stitch" || true'
printf '%s\n' '===CAMERA TOPICS==='
docker exec firmware-sensors bash -lc 'source /opt/ros/noetic/setup.bash; source /root/SLAMIBOT_D360_Framework/install/setup.bash; for t in /SLB_CAM_A/compressed /SLB_CAM_B/compressed /SLB_CAM_C/compressed /keyframe; do echo ---$t; timeout 3 rostopic hz $t 2>&1 | tail -n 4; done'
