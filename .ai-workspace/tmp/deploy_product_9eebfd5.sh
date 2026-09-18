#!/usr/bin/env bash
set -euo pipefail
NAME=scout-nav-product-9eebfd5-test-20260904
IMAGE=scout-nav:product-9eebfd5-arm64
if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "ERROR_CONTAINER_EXISTS=$NAME" >&2
  exit 2
fi
if docker ps --format '{{.Names}}' | grep -q '^scout-nav'; then
  echo "ERROR_RUNNING_SCOUT_NAV" >&2
  docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}' | grep '^scout-nav'
  exit 3
fi
DB=/home/jetson/Scout_mini_navigation/src/nav_api/db/nav_api.db
if [ -f "$DB" ]; then
  cp -a "$DB" "${DB}.pre-9eebfd5-20260904-$(date +%H%M%S)"
fi
docker run -d \
  --name "$NAME" \
  --restart unless-stopped \
  --network host \
  --privileged \
  --security-opt label=disable \
  -e SCOUT_NAV_DATA_DIR=/data/scout-nav \
  -e SCOUT_NAV_DB_DIR=/data/scout-nav/db \
  -e SCOUT_NAV_MAPS_DIR=/data/scout-nav/maps \
  -e NAV_API_DB_PATH=/data/scout-nav/db/nav_api.db \
  -e NAV_API_MAP_ROOT=/data/scout-nav/maps/api_map \
  -e FAST_LIO_PCD_DIR=/data/scout-nav/fastlio/PCD \
  -e FASTLIO_PCD_DIR=/data/scout-nav/fastlio/PCD \
  -e FASTLIO_PCD_FILE=/data/scout-nav/fastlio/PCD/scans.pcd \
  -e ROS_MASTER_WAIT_TIMEOUT_SEC=60 \
  -v /home/jetson/Scout_mini_navigation/src/nav_api/db:/Scout_mini_navigation/src/nav_api/db \
  -v /home/jetson/Scout_mini_navigation/src/nav_api/db:/data/scout-nav/db \
  -v /home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD:/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD \
  -v /home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD:/data/scout-nav/fastlio/PCD \
  -v /home/jetson/Scout_mini_navigation/src/my_nav/maps:/Scout_mini_navigation/src/my_nav/maps \
  -v /home/jetson/Scout_mini_navigation/src/my_nav/maps:/data/scout-nav/maps \
  "$IMAGE"
sleep 12
docker inspect -f 'name={{.Name}}|image={{.Config.Image}}|status={{.State.Status}}|restart={{.HostConfig.RestartPolicy.Name}}|oom={{.State.OOMKilled}}|started={{.State.StartedAt}}' "$NAME"
docker logs --tail 120 "$NAME" 2>&1