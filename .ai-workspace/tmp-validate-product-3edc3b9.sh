set +e
C=scout-nav-product-3edc3b9-test-20260903
echo '=== container ==='
docker inspect "$C" --format 'status={{.State.Status}} running={{.State.Running}} restart={{.RestartCount}} oom={{.State.OOMKilled}} image={{.Image}} started={{.State.StartedAt}}'
echo '=== env/workspace ==='
docker exec "$C" bash -lc 'echo SCOUT_NAV_WS=$SCOUT_NAV_WS; pwd; test -f /Scout_mini_navigation/install/setup.bash && echo INSTALL_OK; test ! -d /Scout_mini_navigation/src && echo SOURCE_FREE_OK || echo SOURCE_PRESENT'
echo '=== HTTP ==='
for url in \
  http://127.0.0.1:5000/health \
  http://127.0.0.1:5000/api/status/ \
  http://127.0.0.1:5000/api/launch/status \
  http://127.0.0.1/app/ \
  http://127.0.0.1:5000/api/capture/list?limit=3; do
  echo "--- $url"
  curl -sS --max-time 8 -o /tmp/check.out -w 'HTTP=%{http_code} TYPE=%{content_type} SIZE=%{size_download}\n' "$url"
  head -c 500 /tmp/check.out; echo
done
echo '=== MJPEG headers ==='
curl -sS --max-time 8 -D - -o /dev/null http://127.0.0.1:5000/api/camera/stream.mjpeg | head -15
echo '=== persistence ==='
docker exec "$C" bash -lc 'echo maps=$(find /data/scout-nav/maps -type f 2>/dev/null | wc -l); echo pcd=$(find /data/scout-nav/fastlio/PCD -type f 2>/dev/null | wc -l); echo captures=$(find /data/scout-nav/db/captures -type f 2>/dev/null | wc -l); python3 - <<"PY"
import sqlite3
p="/data/scout-nav/db/nav_api.db"
c=sqlite3.connect(p)
print("db_integrity="+c.execute("pragma integrity_check").fetchone()[0])
print("tables="+",".join(r[0] for r in c.execute("select name from sqlite_master where type='table' order by name")))
PY'
echo '=== ROS ==='
docker exec "$C" bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; echo NODES; rosnode list 2>/dev/null | sort; echo CLOCK; timeout 5 rostopic echo -n1 /clock; echo ODOM; timeout 5 rostopic echo -n1 /odom/header || true; echo SCAN; timeout 5 rostopic echo -n1 /scan/header || true; echo AMCL; timeout 5 rostopic echo -n1 /amcl_pose/header || true; echo TF; timeout 5 rosrun tf tf_echo map base_link || true'
echo '=== logs errors ==='
docker logs "$C" 2>&1 | grep -Ei 'error|exception|traceback|failed|not found|no such' | tail -100 || true