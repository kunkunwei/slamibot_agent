#!/usr/bin/env bash
set -Eeuo pipefail

CURRENT="scout-nav-product-9eebfd5-test-20260904"
OLD_NAME="scout-nav-product-9eebfd5-pre-persistence-20260904"
NEW_NAME="scout-nav-product-9eebfd5-persistent-20260904"
IMAGE="scout-nav:product-9eebfd5-arm64"
DATA="/var/lib/slamibot/scout-nav"
ARCHIVE="/var/lib/slamibot/archive/scout-nav/20260904-pre-persistence"
OLD_MAPS="/home/jetson/Scout_mini_navigation/src/my_nav/maps"
OLD_PCD="/home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD"
OLD_DB="/home/jetson/Scout_mini_navigation/src/nav_api/db"

fail() { echo "ERROR: $*" >&2; exit 1; }

docker container inspect "$CURRENT" >/dev/null 2>&1 || fail "current container missing: $CURRENT"
[ "$(docker inspect -f '{{.State.Status}}' "$CURRENT")" = running ] || fail "current container is not running"
docker image inspect "$IMAGE" >/dev/null 2>&1 || fail "image missing: $IMAGE"
! docker container inspect "$OLD_NAME" >/dev/null 2>&1 || fail "rollback name already exists: $OLD_NAME"
! docker container inspect "$NEW_NAME" >/dev/null 2>&1 || fail "new name already exists: $NEW_NAME"
[ ! -e "$DATA" ] || fail "target data root already exists: $DATA"
[ ! -e "$ARCHIVE" ] || fail "archive root already exists: $ARCHIVE"
[ -d "$OLD_MAPS/api_map" ] || fail "old api_map missing"
[ -f "$OLD_DB/nav_api.db" ] || fail "old nav_api.db missing"
[ -d "$OLD_DB/captures" ] || fail "old captures missing"
[ -d "$OLD_DB/tts_cache" ] || fail "old tts_cache missing"
[ -d "$OLD_PCD" ] || fail "old PCD directory missing"

printf 'PRECHECK_OK\n'
docker stop -t 20 "$CURRENT" >/dev/null
printf 'STOPPED=%s\n' "$CURRENT"

# Root-owned host migration. / is mounted once so mv remains an atomic same-filesystem rename.
docker run --rm --network none --entrypoint /bin/bash -v /:/host "$IMAGE" -s <<'MIGRATE'
set -Eeuo pipefail
D=/host/var/lib/slamibot/scout-nav
A=/host/var/lib/slamibot/archive/scout-nav/20260904-pre-persistence
OM=/host/home/jetson/Scout_mini_navigation/src/my_nav/maps
OP=/host/home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD
ODB=/host/home/jetson/Scout_mini_navigation/src/nav_api/db

mkdir -p "$D/maps" "$D/fastlio" "$D/db" "$A/maps" "$A/db-backups" "$A/dev-artifacts"

# Active map data.
mv "$OM/api_map" "$D/maps/api_map"
mv "$OM/slam2map" "$D/maps/slam2map"
if [ -d "$OM/.quarantine" ]; then mv "$OM/.quarantine" "$A/maps/quarantine"; fi
if [ -d "$OM/__pycache__" ]; then mv "$OM/__pycache__" "$A/dev-artifacts/maps-pycache"; fi
ln -s /var/lib/slamibot/scout-nav/maps/api_map "$OM/api_map"
ln -s /var/lib/slamibot/scout-nav/maps/slam2map "$OM/slam2map"

# Restore 2D maps that only existed in the immutable image. Never overwrite newer host files.
cp -an /Scout_mini_navigation/install/share/my_nav/maps/api_map/. "$D/maps/api_map/"

# Keep PCD-only results, but separate them from loadable 2D maps.
mkdir -p "$D/maps/pcd-only"
for n in dinggu7_7 map2604 map2605 map2701; do
  if [ -d "$D/maps/api_map/$n" ] && [ ! -f "$D/maps/api_map/$n/$n.yaml" ]; then
    mv "$D/maps/api_map/$n" "$D/maps/pcd-only/$n"
  fi
done

# FAST-LIO working output.
mv "$OP" "$D/fastlio/PCD"
ln -s /var/lib/slamibot/scout-nav/fastlio/PCD "$OP"

# Active database/media/cache. Historical backup files stay available in a separate archive.
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

# Normalize all valid DB map paths to the host-owned, same-path mount.
python3 - "$D/db/nav_api.db" "$D/maps/api_map" <<'PY'
import os, sqlite3, sys
p, root = sys.argv[1:]
con = sqlite3.connect(p)
rows = con.execute('SELECT mapName FROM Map').fetchall()
for (name,) in rows:
    d = os.path.join(root, name)
    yaml = os.path.join(d, name + '.yaml')
    pcd = os.path.join(d, name + '.pcd')
    if not os.path.isfile(yaml):
        raise SystemExit('DB map still missing YAML after image restore: ' + name)
    con.execute(
        "UPDATE Map SET yamlFilePath=?, pcdFilePath=?, updatedTime=datetime('now','localtime') WHERE mapName=?",
        ('/var/lib/slamibot/scout-nav/maps/api_map/%s/%s.yaml' % (name, name),
         '/var/lib/slamibot/scout-nav/maps/api_map/%s/%s.pcd' % (name, name) if os.path.isfile(pcd) else None,
         name),
    )
con.commit()
assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
con.close()
PY

# Ownership and an auditable inventory. No user data is deleted.
chown -R 1000:1000 /host/var/lib/slamibot
find "$D" -xdev -type f -printf '%P|%s\n' | sort > "$A/data-inventory-path-size.txt"
{
  echo "migration_date=2026-09-04"
  echo "data_root=/var/lib/slamibot/scout-nav"
  echo "archive_root=/var/lib/slamibot/archive/scout-nav/20260904-pre-persistence"
  du -sh "$D/maps/api_map" "$D/maps/pcd-only" "$D/maps/slam2map" "$D/fastlio/PCD" "$D/db"
} > "$A/migration-summary.txt"
MIGRATE

printf 'DATA_MOVED\n'
docker rename "$CURRENT" "$OLD_NAME"

docker run -d \
  --name "$NEW_NAME" \
  --restart unless-stopped \
  --network host \
  --privileged \
  --security-opt label=disable \
  -e SCOUT_NAV_DATA_DIR="$DATA" \
  -e SCOUT_NAV_DB_DIR="$DATA/db" \
  -e SCOUT_NAV_MAPS_DIR="$DATA/maps" \
  -e NAV_API_DB_PATH="$DATA/db/nav_api.db" \
  -e NAV_API_MAP_ROOT="$DATA/maps/api_map" \
  -e CAPTURE_DIR="$DATA/db/captures" \
  -e TTS_PCM_CACHE_DIR="$DATA/db/tts_cache" \
  -e FAST_LIO_PCD_DIR="$DATA/fastlio/PCD" \
  -e FASTLIO_PCD_DIR="$DATA/fastlio/PCD" \
  -e FASTLIO_PCD_FILE="$DATA/fastlio/PCD/scans.pcd" \
  -e ROS_MASTER_WAIT_TIMEOUT_SEC=60 \
  -v "$DATA:$DATA" \
  -v "$DATA/db:/data/scout-nav/db" \
  -v "$DATA/db:/Scout_mini_navigation/src/nav_api/db" \
  -v "$DATA/fastlio/PCD:/data/scout-nav/fastlio/PCD" \
  -v "$DATA/fastlio/PCD:/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD" \
  -v "$DATA/maps:/data/scout-nav/maps" \
  -v "$DATA/maps:/Scout_mini_navigation/src/my_nav/maps" \
  "$IMAGE" >/dev/null

sleep 15
STATUS="$(docker inspect -f '{{.State.Status}}' "$NEW_NAME")"
[ "$STATUS" = running ] || {
  echo "NEW_CONTAINER_FAILED; starting preserved rollback container" >&2
  docker logs --tail 160 "$NEW_NAME" >&2 || true
  docker start "$OLD_NAME" >/dev/null || true
  exit 1
}

printf 'NEW_CONTAINER_RUNNING=%s\n' "$NEW_NAME"
docker inspect "$NEW_NAME" --format 'image={{.Config.Image}} status={{.State.Status}} restart={{.HostConfig.RestartPolicy.Name}} oom={{.State.OOMKilled}}'
docker inspect "$NEW_NAME" --format '{{range .Mounts}}{{println .Source " -> " .Destination}}{{end}}'
docker exec "$NEW_NAME" python3 - <<'PY'
import os, sqlite3
root='/var/lib/slamibot/scout-nav'
con=sqlite3.connect(root+'/db/nav_api.db')
print('integrity='+con.execute('pragma integrity_check').fetchone()[0])
print('maps_db='+str(con.execute('select count(*) from Map').fetchone()[0]))
print('captures_db='+str(con.execute('select count(*) from Captures').fetchone()[0]))
print('maps_dirs='+str(len([x for x in os.listdir(root+'/maps/api_map') if os.path.isdir(root+'/maps/api_map/'+x)])))
print('captures_files='+str(len([x for x in os.listdir(root+'/db/captures') if os.path.isfile(root+'/db/captures/'+x)])))
print('tts_files='+str(len([x for x in os.listdir(root+'/db/tts_cache') if os.path.isfile(root+'/db/tts_cache/'+x)])))
PY

docker logs --tail 100 "$NEW_NAME" 2>&1