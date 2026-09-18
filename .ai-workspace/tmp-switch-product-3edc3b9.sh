set -e
OLD=scout-nav-product-ec245a7-test-20260903
NEW=scout-nav-product-3edc3b9-test-20260903
IMAGE=scout-nav:product-3edc3b9-arm64
DBDIR=/home/jetson/Scout_mini_navigation/src/nav_api/db

echo 'Stopping old container...'
docker stop -t 20 "$OLD"
if [ -f "$DBDIR/nav_api.db" ]; then
  cp -p "$DBDIR/nav_api.db" "$DBDIR/nav_api.db.before-product-3edc3b9-test-20260903.bak"
fi

echo 'Starting new container...'
if ! docker run -d \
  --name "$NEW" \
  --network host \
  --privileged \
  --security-opt label=disable \
  -e SCOUT_NAV_DATA_DIR=/data/scout-nav \
  -e NAV_API_MAP_ROOT=/data/scout-nav/maps/api_map \
  -e NAV_API_DB_PATH=/data/scout-nav/db/nav_api.db \
  -e FASTLIO_PCD_DIR=/data/scout-nav/fastlio/PCD \
  -e FASTLIO_PCD_FILE=/data/scout-nav/fastlio/PCD/scans.pcd \
  -e SCOUT_NAV_MAPS_DIR=/data/scout-nav/maps \
  -e SCOUT_NAV_DB_DIR=/data/scout-nav/db \
  -e FAST_LIO_PCD_DIR=/data/scout-nav/fastlio/PCD \
  -e ROS_MASTER_WAIT_TIMEOUT_SEC=60 \
  -v /home/jetson/Scout_mini_navigation/src/nav_api/db:/Scout_mini_navigation/src/nav_api/db \
  -v /home/jetson/Scout_mini_navigation/src/nav_api/db:/data/scout-nav/db \
  -v /home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD:/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD \
  -v /home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD:/data/scout-nav/fastlio/PCD \
  -v /home/jetson/Scout_mini_navigation/src/my_nav/maps:/Scout_mini_navigation/src/my_nav/maps \
  -v /home/jetson/Scout_mini_navigation/src/my_nav/maps:/data/scout-nav/maps \
  "$IMAGE"; then
  echo 'New container failed to create; restoring old container.' >&2
  docker start "$OLD"
  exit 1
fi
sleep 12
if ! docker ps --format '{{.Names}}' | grep -qx "$NEW"; then
  echo 'New container exited; restoring old container.' >&2
  docker logs --tail 120 "$NEW" || true
  docker start "$OLD"
  exit 1
fi
echo '=== switched ==='
docker ps -a --filter name=scout-nav-product --format '{{.Names}}|{{.Image}}|{{.Status}}'
echo '=== new logs ==='
docker logs --tail 80 "$NEW"