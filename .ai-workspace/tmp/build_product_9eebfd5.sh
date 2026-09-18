#!/usr/bin/env bash
set -euo pipefail
SRC=/home/jetson/product_builds/scout-nav-9eebfd5
BRANCH=codex/product-f376a4c-release-20260903
COMMIT=9eebfd5b2fdaa4bb38ce01c3e5676ef137c7964c
IMAGE=scout-nav:product-9eebfd5-arm64
if [ -e "$SRC" ]; then
  echo "ERROR: build directory already exists: $SRC" >&2
  exit 2
fi
mkdir -p /home/jetson/product_builds
git clone --depth 1 --branch "$BRANCH" git@github.com:kunkunwei/Scout_mini_navigation.git "$SRC"
cd "$SRC"
ACTUAL=$(git rev-parse HEAD)
[ "$ACTUAL" = "$COMMIT" ] || { echo "ERROR: expected $COMMIT, got $ACTUAL" >&2; exit 3; }
echo "BUILD_SOURCE=$ACTUAL"
DOCKER_BUILDKIT=1 docker build --progress=plain -f Dockerfile.product -t "$IMAGE" .
docker image inspect -f 'BUILD_IMAGE={{.RepoTags}}|{{.Id}}|{{.Architecture}}|{{.Created}}' "$IMAGE"