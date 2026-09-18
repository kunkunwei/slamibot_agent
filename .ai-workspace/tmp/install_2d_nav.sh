#!/usr/bin/env bash
# D360 2D 导航一键安装 / 升级脚本（compose 管理，只管 scout-nav 服务）
#
# 用法：sudo ./install_2d_nav.sh [选项]
#   --image TAG          镜像，默认 registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d:1.2.1
#   --service NAME        compose 服务名，默认 scout-nav
#   --data-dir PATH       数据根，默认 /var/lib/slamibot/scout-nav
#   --compose PATH        compose 文件，默认 /etc/slamibot/system/docker-compose.yml
#   --no-pull             不联网拉镜像（只用本地）
#   --skip-sensor-check   跳过传感器前置检查
#   --wait-sec N          health 等待上限，默认 120
#   --dry-run             只打印将要写入的服务片段与 diff，不改任何文件
#
# 边界：只新增/更新 scout-nav 一个服务；不动 core / firmware-sensors / ota_web；不删镜像；不 prune；不删数据。
# 幂等：重复执行＝升级镜像 tag。改 compose 前自动备份，失败自动回滚。
set -euo pipefail

IMAGE="registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d:1.2.1"
SERVICE="scout-nav"
DATA_DIR="/var/lib/slamibot/scout-nav"
COMPOSE="/etc/slamibot/system/docker-compose.yml"
PULL=1
SENSOR_CHECK=1
WAIT_SEC=120
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --image) IMAGE="$2"; shift 2 ;;
    --service) SERVICE="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --compose) COMPOSE="$2"; shift 2 ;;
    --no-pull) PULL=0; shift ;;
    --skip-sensor-check) SENSOR_CHECK=0; shift ;;
    --wait-sec) WAIT_SEC="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf '[错误] %s\n' "$*" >&2; exit 1; }

# ---------- 0. 环境前置 ----------
[ "$(id -u)" = "0" ] || die "请用 sudo 执行（需要改 $COMPOSE 与管理 docker）"
command -v docker >/dev/null 2>&1 || die "未安装 docker"
docker info >/dev/null 2>&1 || die "docker 不可用"
docker compose version >/dev/null 2>&1 || die "缺少 docker compose (v2)"
[ -f "$COMPOSE" ] || die "compose 文件不存在：$COMPOSE（请先按《D360装机流程》完成基础三容器安装）"
docker ps --format '{{.Names}}' | grep -qx core \
  || die "core 容器未运行：ROS master(11311) 由 core 提供，导航容器必须等它先起来"

# ---------- 1. 镜像 ----------
if [ "$PULL" = "1" ]; then
  log "拉取 $IMAGE ..."
  docker pull "$IMAGE" || die "拉取失败：先执行 docker login registry.cn-shanghai.aliyuncs.com"
else
  docker image inspect "$IMAGE" >/dev/null 2>&1 || die "本地无镜像 $IMAGE（且指定了 --no-pull）"
fi

# ---------- 2. 传感器前置（导航/建图/相机硬同步的前提）----------
if [ "$SENSOR_CHECK" = "1" ] && docker ps --format '{{.Names}}' | grep -qx firmware-sensors; then
  if docker exec firmware-sensors bash -lc '
      source /opt/ros/noetic/setup.bash >/dev/null 2>&1
      timeout 8 rostopic hz /clock       | grep -m1 "average rate" >/dev/null || exit 1
      timeout 8 rostopic info /livox/lidar 2>/dev/null | sed -n "/Publishers:/,/Subscribers:/p" | grep -q "[*]" || exit 2
      a=$(od -An -td8 -N16 /dev/shm/timeshare 2>/dev/null | awk "{print \$2}")
      sleep 2
      b=$(od -An -td8 -N16 /dev/shm/timeshare 2>/dev/null | awk "{print \$2}")
      [ -n "$a" ] && [ "$a" != "$b" ] || exit 3
      exit 0'; then
    log "传感器前置检查通过（/clock、/livox/lidar、timeshare 均在更新）"
  else
    log "警告：/clock 或 /livox/lidar 无数据、或 timeshare 冻结 —— 导航/建图/相机时间戳可能不可用"
    log "      建议先修上游传感器；本脚本仍会继续安装。"
  fi
fi

# ---------- 3. 写入 compose（先备份；--dry-run 只打印）----------
mkdir -p "$DATA_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${COMPOSE}.bak-${STAMP}"
NEW_YAML="$(mktemp /tmp/scout-nav-service.XXXXXX.yaml)"

python3 - "$COMPOSE" "$SERVICE" "$IMAGE" "$DATA_DIR" "$NEW_YAML" <<'PY'
import re
import sys

compose_path, service, image, data_dir, out_path = sys.argv[1:6]
text = open(compose_path, encoding="utf-8").read()
lines = text.split("\n")

block = [
    "  %s:" % service,
    "    image: %s" % image,
    "    container_name: %s" % service,
    "    network_mode: host",
    "    privileged: true",
    "    shm_size: 64m",
    "    restart: unless-stopped",
    "    volumes:",
    "      - %s:%s" % (data_dir, data_dir),
    "    depends_on:",
    "      - core",
]

print("将要写入的服务块:")
for line in block:
    print("  " + line)

existing = re.search(r"^  %s:[ \t]*$" % re.escape(service), text, re.M)
if existing:
    start = text[:existing.start()].count("\n")
    out = list(lines)
    replaced = False
    for i in range(start + 1, len(out)):
        if re.match(r"^\S|^  \S", out[i]):
            break
        m = re.match(r"^(\s*)image:\s*\S+", out[i])
        if m:
            out[i] = "%simage: %s" % (m.group(1), image)
            replaced = True
            break
    if not replaced:
        out.insert(start + 1, "    image: %s" % image)
    print("服务 %s 已存在：只更新 image 行（不动其它内容）" % service)
    new_text = "\n".join(out)
else:
    top = [i for i, l in enumerate(lines) if re.match(r"^[A-Za-z]", l) and not l.startswith("services:")]
    if top:
        at = top[0]
        new_text = "\n".join(lines[:at] + block + [""] + lines[at:])
    else:
        at = len(lines)
        while at > 0 and lines[at - 1].strip() == "":
            at -= 1
        new_text = "\n".join(lines[:at] + [""] + block + lines[at:])
    print("新增服务 %s（文本最小插入，其它服务一字不动）" % service)

open(out_path, "w", encoding="utf-8").write(new_text)
PY

log "将要写入的差异（$COMPOSE）:"
diff -u "$COMPOSE" "$NEW_YAML" || true

if [ "$DRY_RUN" = "1" ]; then
  log "--dry-run：未修改任何文件，结束"
  rm -f "$NEW_YAML"
  exit 0
fi

cp -p "$COMPOSE" "$BACKUP"
log "已备份原 compose: $BACKUP"
cat "$NEW_YAML" > "$COMPOSE"   # 用重定向而非 cp -p：保留原文件权限/属主，避免带入 mktemp 的 0600
rm -f "$NEW_YAML"
docker compose -f "$COMPOSE" config >/dev/null || {
  cp -p "$BACKUP" "$COMPOSE"
  die "compose 校验失败，已还原 $COMPOSE"
}

# ---------- 4. 拉起服务 ----------
log "docker compose up -d $SERVICE ..."
docker compose -f "$COMPOSE" up -d "$SERVICE"

# ---------- 5. 等 health，失败自动回滚 ----------
ok=0; i=0
while [ "$i" -lt "$((WAIT_SEC / 5))" ]; do
  i=$((i + 1)); sleep 5
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:5000/health 2>/dev/null || echo 000)
  log "等待服务就绪: +$((i * 5))s health=$code"
  [ "$code" = "200" ] && { ok=1; break; }
done

if [ "$ok" != "1" ]; then
  log "health 未在 ${WAIT_SEC}s 内就绪，回滚 compose 并重建旧服务"
  docker compose -f "$COMPOSE" logs --tail 40 "$SERVICE" 2>&1 || true
  cp -p "$BACKUP" "$COMPOSE"
  docker compose -f "$COMPOSE" up -d "$SERVICE" || true
  die "安装失败，已还原 $COMPOSE（备份：$BACKUP）"
fi

# ---------- 6. 验收 ----------
log "验收："
curl -s --max-time 8 http://127.0.0.1:5000/health; echo
curl -s --max-time 8 http://127.0.0.1:5000/api/launch/status; echo
maps=$(curl -s --max-time 8 http://127.0.0.1:5000/api/map/list \
       | python3 -c 'import sys,json;print(len(json.load(sys.stdin).get("data") or []))' 2>/dev/null || echo "?")
log "地图数量: $maps"
ss -lntp 2>/dev/null | grep -E ':(80|5000|9090|19090)\b' | awk '{print "  监听 " $4}'

cat <<INFO

==================== 安装完成 ====================
WEB    http://<设备IP>/app/
API    http://<设备IP>:5000
rosbridge  ws://<设备IP>:9090

升级   改 --image 或直接编辑 $COMPOSE 里的 tag 后：
       docker compose -f $COMPOSE up -d $SERVICE
回滚   cp -p $BACKUP $COMPOSE && docker compose -f $COMPOSE up -d $SERVICE
日志   docker compose -f $COMPOSE logs -f --tail 100 $SERVICE
首次启动会自动建 db/ fastlio/ maps/ 并播种镜像自带的演示地图。
================================================
INFO
