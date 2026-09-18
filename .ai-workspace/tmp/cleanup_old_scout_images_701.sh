#!/usr/bin/env bash
set -Eeuo pipefail
CURRENT_CONTAINER='scout-nav-video-link-5ad6000-test-20260904'
KEEP_CURRENT='sha256:f28242cf05cdee6bf4c76b9a63c818fe6734f59633b452ac283d7ede13f3eda2'
KEEP_BASE='sha256:6f23af329d33bb7984c0242f0890a7db89e5b1e8c7812d901a24a475e8357c8b'
actual=$(docker inspect -f '{{.Image}}' "$CURRENT_CONTAINER")
state=$(docker inspect -f '{{.State.Status}}' "$CURRENT_CONTAINER")
[ "$actual" = "$KEEP_CURRENT" ] || { echo "ABORT: current image changed: $actual" >&2; exit 1; }
[ "$state" = 'running' ] || { echo "ABORT: current container state is $state" >&2; exit 1; }
mapfile -t running_ids < <(docker ps -q | xargs -r docker inspect -f '{{.Image}}' | sort -u)
is_running_id(){ local needle="$1"; printf '%s\n' "${running_ids[@]}" | grep -Fxq "$needle"; }
echo '=== REMOVE OLD SCOUT-NAV IMAGE TAGS ==='
while IFS='|' read -r tag full_id; do
  [ -n "$tag" ] || continue
  if [ "$full_id" = "$KEEP_CURRENT" ] || [ "$full_id" = "$KEEP_BASE" ]; then
    echo "KEEP $tag $full_id"
  elif is_running_id "$full_id"; then
    echo "KEEP_RUNNING $tag $full_id"
  else
    echo "REMOVE $tag $full_id"
    docker image rm "$tag"
  fi
done < <(docker image ls --no-trunc --format '{{.Repository}}:{{.Tag}}|{{.ID}}' | awk -F'|' '$1 ~ /^scout-nav:/ || $1 ~ /^ghcr\.io\/kunkunwei\/scout-nav:/')
echo '=== CLEAR BUILD CACHE ==='
docker builder prune -a -f
echo '=== VERIFY ==='
[ "$(docker inspect -f '{{.Image}}' "$CURRENT_CONTAINER")" = "$KEEP_CURRENT" ]
[ "$(docker inspect -f '{{.State.Status}}' "$CURRENT_CONTAINER")" = 'running' ]
docker image inspect "$KEEP_CURRENT" >/dev/null
docker image inspect "$KEEP_BASE" >/dev/null
df -h /
docker system df || true
echo '=== REMAINING SCOUT-NAV IMAGES ==='
docker image ls --no-trunc --format '{{.Repository}}:{{.Tag}}|{{.ID}}|{{.Size}}' | grep '^scout-nav:' || true
echo '=== RUNNING CONTAINERS ==='
docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}'