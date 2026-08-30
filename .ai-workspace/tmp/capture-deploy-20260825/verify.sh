#!/bin/bash
set -eu
sleep 5
echo ---CONTAINER---
docker ps --filter name=^/scout-nav$ --format '{{.Names}} {{.Status}}'
echo restart_count=$(docker inspect scout-nav --format '{{.RestartCount}}')
echo ---PORTS---
ss -ltn | grep -E ':(5000|19090|80|9090) '
echo ---OPENAPI---
curl -fsS http://127.0.0.1:5000/openapi.json > /tmp/codex-openapi.json
python3 - <<'PY'
import json
p=json.load(open('/tmp/codex-openapi.json'))['paths']
print([(k, sorted(p[k])) for k in sorted(p) if 'capture' in k])
print('photo_post_count', int('post' in p.get('/api/capture/photo', {})))
PY
echo ---DB---
python3 - <<'PY'
import sqlite3
c=sqlite3.connect('/home/jetson/Scout_mini_navigation/src/nav_api/db/nav_api.db')
print(c.execute("select sql from sqlite_master where type='table' and name='Captures'").fetchone()[0])
print('capture_count', c.execute('select count(*) from Captures').fetchone()[0])
PY
echo ---ROS---
docker exec scout-nav bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:11311; echo POINT_ARRIVED; rostopic info /nav_multi/point_arrived; for t in /SLB_CAM_A/compressed /SLB_CAM_B/compressed /SLB_CAM_C/compressed; do echo CAMERA=$t; rostopic info $t 2>&1 | sed -n "1,12p"; done'
echo ---PROCESSES---
docker exec scout-nav pgrep -af nav_multi_node
docker exec scout-nav pgrep -af uvicorn
docker exec scout-nav pgrep -af rosbridge_websocket
echo ---RECENT-LOGS---
docker logs --since 2026-08-25T10:33:00Z scout-nav 2>&1 | tail -100
