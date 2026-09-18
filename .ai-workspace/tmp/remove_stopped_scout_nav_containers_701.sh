#!/usr/bin/env bash
set -Eeuo pipefail
KEEP='scout-nav-video-link-5ad6000-test-20260904'
[ "$(docker inspect -f '{{.State.Status}}' "$KEEP")" = running ] || { echo "ABORT: current container is not running" >&2; exit 1; }
mapfile -t ids < <(docker ps -aq --filter 'name=scout-nav')
delete_ids=()
echo '=== DELETE CANDIDATES ==='
for id in "${ids[@]}"; do
  name=$(docker inspect -f '{{.Name}}' "$id" | sed 's#^/##')
  state=$(docker inspect -f '{{.State.Status}}' "$id")
  if [ "$name" = "$KEEP" ]; then
    echo "KEEP running $name"
  elif [ "$state" = running ]; then
    echo "KEEP other-running $name"
  else
    echo "DELETE $state $name"
    delete_ids+=("$id")
  fi
done
if [ "${#delete_ids[@]}" -gt 0 ]; then
  docker rm "${delete_ids[@]}"
fi
echo '=== AFTER ==='
docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}'
df -h /
docker system df
