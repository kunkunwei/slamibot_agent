#!/usr/bin/env bash
set -u
C=scout-nav-product-v1-dc05f79-mapping-test-20260905
echo '=== docker ==='
docker ps -a --filter name="$C" --format '{{.Names}}|{{.Image}}|{{.Status}}'
echo '=== health ==='
curl -sS --max-time 5 http://127.0.0.1:5000/health || true
echo
echo '=== recent logs ==='
docker logs --since 20m --tail 400 "$C" 2>&1 || true
echo '=== processes ==='
docker exec "$C" sh -lc "ps -ef | grep -E 'laserMapping|map_server|pcd_to_map|fastlio|uvicorn|roslaunch' | grep -v grep || true"
echo '=== ros nodes ==='
docker exec "$C" sh -lc ". /opt/ros/noetic/setup.sh; . /Scout_mini_navigation/install/setup.sh; rosnode list 2>&1 | sort | grep -E 'map|laser|fast|livox|nav|amcl|move_base' || true"
echo '=== map topic ==='
docker exec "$C" sh -lc ". /opt/ros/noetic/setup.sh; . /Scout_mini_navigation/install/setup.sh; rostopic info /map 2>&1; timeout 6 rostopic hz /map 2>&1 || true"
echo '=== mapping topics ==='
docker exec "$C" sh -lc ". /opt/ros/noetic/setup.sh; . /Scout_mini_navigation/install/setup.sh; rostopic list 2>&1 | grep -E '^/(map|cloud|Odometry|livox|scan)' | sort || true"
echo '=== recent persistent map files ==='
find /var/lib/slamibot/scout-nav/maps/api_map -maxdepth 2 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null | sort -r | head -60
echo '=== fastlio output ==='
find /var/lib/slamibot/scout-nav/fastlio/PCD -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' 2>/dev/null | sort -r | head -20
echo '=== map api list tail ==='
curl -sS --max-time 8 http://127.0.0.1:5000/api/map/maps/list || true
echo
