set -u
echo '--- API MAP LIST ---'
curl -s --max-time 5 http://127.0.0.1:5001/api/map/list || true
echo
echo '--- ENV/PATHS ---'
docker exec scout-nav-product-9eebfd5-persistent-20260904 bash -lc 'env | grep -E "MAP_ROOT|DB_|FASTLIO|PCD_" | sort; ps -ef | grep -E "pcd_map_publisher|map_server" | grep -v grep; find /var/lib/slamibot/maps -maxdepth 2 -type f 2>/dev/null | sort | tail -80'
