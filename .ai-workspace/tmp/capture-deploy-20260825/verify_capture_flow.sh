#!/bin/bash
set -eu
echo ---MANUAL-PHOTO---
curl -sS -X POST http://127.0.0.1:5000/api/capture/photo -H 'Content-Type: application/json' -d '{"source":"manual"}'
echo
echo ---CAPTURE-LIST---
curl -sS http://127.0.0.1:5000/api/capture/list
echo
echo ---STATIC-MOUNT---
curl -sS -o /tmp/codex-static-body -w 'status=%{http_code} content_type=%{content_type}
' http://127.0.0.1:5000/captures/not-found.jpg
head -c 200 /tmp/codex-static-body; echo
echo ---POINT-EVENT-INJECT---
docker exec scout-nav bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:11311; rostopic pub -1 /nav_multi/point_arrived std_msgs/String "data: '''{"arrivalId":"codex-capture-20260825-1835","runId":"codex-safe-test","taskId":900001,"pointIndex":0,"pointName":"部署验证点","action":"photo","actionContent":""}'''"'
sleep 2
echo ---DB-AFTER---
python3 - <<'PY'
import sqlite3
c=sqlite3.connect('/home/jetson/Scout_mini_navigation/src/nav_api/db/nav_api.db')
print(c.execute('select count(*) from Captures').fetchone()[0])
PY
echo ---LOG-MATCHES---
docker logs --since 2026-08-25T10:34:00Z scout-nav 2>&1 | grep -E 'capture|相机|camera|point_action|point-arrival' | tail -60 || true
