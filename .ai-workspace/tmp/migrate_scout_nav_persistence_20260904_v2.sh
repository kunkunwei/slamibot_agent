#!/usr/bin/env bash
set -Eeuo pipefail
OLD_CONTAINER="scout-nav-product-9eebfd5-pre-persistence-20260904"
FAILED_CONTAINER="scout-nav-product-9eebfd5-empty-bootstrap-20260904"
NEW_CONTAINER="scout-nav-product-9eebfd5-persistent-20260904"
IMAGE="scout-nav:product-9eebfd5-arm64"
DATA="/var/lib/slamibot/scout-nav"
FAILED_DATA="/var/lib/slamibot/archive/scout-nav/20260904-empty-bootstrap-data"
ARCHIVE="/var/lib/slamibot/archive/scout-nav/20260904-pre-persistence"
OLD_MAPS="/home/jetson/Scout_mini_navigation/src/my_nav/maps"
OLD_PCD="/home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD"
OLD_DB="/home/jetson/Scout_mini_navigation/src/nav_api/db"
fail(){ echo "ERROR: $*" >&2; exit 1; }

docker container inspect "$OLD_CONTAINER" >/dev/null 2>&1 || fail "preserved original container missing"
docker container inspect "$FAILED_CONTAINER" >/dev/null 2>&1 || fail "failed bootstrap container missing"
! docker container inspect "$NEW_CONTAINER" >/dev/null 2>&1 || fail "target container name already exists"
[ -d "$DATA" ] || fail "expected empty-bootstrap data root missing"
[ ! -e "$FAILED_DATA" ] || fail "failed-data archive target already exists"
[ ! -e "$ARCHIVE" ] || fail "migration archive target already exists"
[ -d "$OLD_MAPS/api_map" ] || fail "original api_map missing"
[ -f "$OLD_DB/nav_api.db" ] || fail "original nav_api.db missing"
[ -d "$OLD_DB/captures" ] || fail "original captures missing"
[ -d "$OLD_DB/tts_cache" ] || fail "original tts_cache missing"
[ -d "$OLD_PCD" ] || fail "original PCD directory missing"
[ "$(stat -c %d "$OLD_MAPS")" = "$(stat -c %d /var/lib)" ] || fail "old and new roots are not on same filesystem"

echo V2_PRECHECK_OK
# -i is required: the migration program is supplied on stdin.
docker run --rm -i --network none --entrypoint /bin/bash -v /:/host "$IMAGE" -s <<'MIGRATE'
set -Eeuo pipefail
D=/host/var/lib/slamibot/scout-nav
FD=/host/var/lib/slamibot/archive/scout-nav/20260904-empty-bootstrap-data
A=/host/var/lib/slamibot/archive/scout-nav/20260904-pre-persistence
OM=/host/home/jetson/Scout_mini_navigation/src/my_nav/maps
OP=/host/home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD
ODB=/host/home/jetson/Scout_mini_navigation/src/nav_api/db
mkdir -p /host/var/lib/slamibot/archive/scout-nav
mv "$D" "$FD"
mkdir -p "$D/maps" "$D/fastlio" "$D/db" "$A/maps" "$A/db-backups" "$A/dev-artifacts"

mv "$OM/api_map" "$D/maps/api_map"
mv "$OM/slam2map" "$D/maps/slam2map"
[ ! -d "$OM/.quarantine" ] || mv "$OM/.quarantine" "$A/maps/quarantine"
[ ! -d "$OM/__pycache__" ] || mv "$OM/__pycache__" "$A/dev-artifacts/maps-pycache"
ln -s /var/lib/slamibot/scout-nav/maps/api_map "$OM/api_map"
ln -s /var/lib/slamibot/scout-nav/maps/slam2map "$OM/slam2map"

cp -an /Scout_mini_navigation/install/share/my_nav/maps/api_map/. "$D/maps/api_map/"
mkdir -p "$D/maps/pcd-only"
for n in dinggu7_7 map2604 map2605 map2701; do
  if [ -d "$D/maps/api_map/$n" ] && [ ! -f "$D/maps/api_map/$n/$n.yaml" ]; then mv "$D/maps/api_map/$n" "$D/maps/pcd-only/$n"; fi
done

mv "$OP" "$D/fastlio/PCD"
ln -s /var/lib/slamibot/scout-nav/fastlio/PCD "$OP"

mv "$ODB/nav_api.db" "$D/db/nav_api.db"
mv "$ODB/captures" "$D/db/captures"
mv "$ODB/tts_cache" "$D/db/tts_cache"
ln -s /var/lib/slamibot/scout-nav/db/nav_api.db "$ODB/nav_api.db"
ln -s /var/lib/slamibot/scout-nav/db/captures "$ODB/captures"
ln -s /var/lib/slamibot/scout-nav/db/tts_cache "$ODB/tts_cache"
for f in "$ODB"/*; do
  [ -f "$f" ] || continue
  [ "$(basename "$f")" = schema.sql ] && continue
  mv "$f" "$A/db-backups/"
done
cp -a "$D/db/nav_api.db" "$A/db-backups/nav_api.db.before-persistence-path-update.bak"

python3 - "$D/db/nav_api.db" "$D/maps/api_map" <<'PY'
import os,sqlite3,sys
p,root=sys.argv[1:]
con=sqlite3.connect(p)
for (name,) in con.execute('select mapName from Map').fetchall():
 d=os.path.join(root,name); y=os.path.join(d,name+'.yaml'); pc=os.path.join(d,name+'.pcd')
 if not os.path.isfile(y): raise SystemExit('DB map missing YAML after restore: '+name)
 con.execute("update Map set yamlFilePath=?,pcdFilePath=?,updatedTime=datetime('now','localtime') where mapName=?",('/var/lib/slamibot/scout-nav/maps/api_map/%s/%s.yaml'%(name,name),'/var/lib/slamibot/scout-nav/maps/api_map/%s/%s.pcd'%(name,name) if os.path.isfile(pc) else None,name))
con.commit()
if con.execute('pragma integrity_check').fetchone()[0] != 'ok': raise SystemExit('sqlite integrity failed')
con.close()
PY

chown -R 1000:1000 /host/var/lib/slamibot
find "$D" -xdev -type f -printf '%P|%s\n' | sort > "$A/data-inventory-path-size.txt"
{
 echo migration_date=2026-09-04
 echo data_root=/var/lib/slamibot/scout-nav
 echo archive_root=/var/lib/slamibot/archive/scout-nav/20260904-pre-persistence
 du -sh "$D/maps/api_map" "$D/maps/pcd-only" "$D/maps/slam2map" "$D/fastlio/PCD" "$D/db"
} > "$A/migration-summary.txt"
MIGRATE

echo V2_DATA_MOVED

docker run -d \
 --name "$NEW_CONTAINER" --restart unless-stopped --network host --privileged --security-opt label=disable \
 -e SCOUT_NAV_DATA_DIR="$DATA" -e SCOUT_NAV_DB_DIR="$DATA/db" -e SCOUT_NAV_MAPS_DIR="$DATA/maps" \
 -e NAV_API_DB_PATH="$DATA/db/nav_api.db" -e NAV_API_MAP_ROOT="$DATA/maps/api_map" \
 -e CAPTURE_DIR="$DATA/db/captures" -e TTS_PCM_CACHE_DIR="$DATA/db/tts_cache" \
 -e FAST_LIO_PCD_DIR="$DATA/fastlio/PCD" -e FASTLIO_PCD_DIR="$DATA/fastlio/PCD" \
 -e FASTLIO_PCD_FILE="$DATA/fastlio/PCD/scans.pcd" -e ROS_MASTER_WAIT_TIMEOUT_SEC=60 \
 -v "$DATA:$DATA" -v "$DATA/db:/data/scout-nav/db" -v "$DATA/db:/Scout_mini_navigation/src/nav_api/db" \
 -v "$DATA/fastlio/PCD:/data/scout-nav/fastlio/PCD" -v "$DATA/fastlio/PCD:/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD" \
 -v "$DATA/maps:/data/scout-nav/maps" -v "$DATA/maps:/Scout_mini_navigation/src/my_nav/maps" \
 "$IMAGE" >/dev/null
sleep 15
[ "$(docker inspect -f '{{.State.Status}}' "$NEW_CONTAINER")" = running ] || { docker logs --tail 160 "$NEW_CONTAINER" >&2 || true; docker start "$OLD_CONTAINER" >/dev/null || true; fail "new container failed; original restarted"; }
echo V2_NEW_CONTAINER_RUNNING
docker inspect "$NEW_CONTAINER" --format 'image={{.Config.Image}} status={{.State.Status}} restart={{.HostConfig.RestartPolicy.Name}} oom={{.State.OOMKilled}}'