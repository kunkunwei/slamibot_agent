# ROS1 2D 导航同事调试镜像恢复清单（2026-09-03）

## 目的与边界

只保障恢复同事尚未完成测试、尚未同步 GitHub 的 ROS1 2D 导航成果。本文不授权部署产品镜像，不停止、重启或替换当前运行容器，也不得删除地图、PCD、数据库或相关 Docker 镜像。

## 已固化事实

- Jetson：`jetson@192.168.31.135`，hostname `ubuntu`
- 当前容器：`scout-nav-timefix-20260827`
- 同事调试镜像原 tag：`scout-nav:scanfix-neargoal-test3-20260903`
- 固定恢复 tag：`scout-nav:recovery-colleague-2d-scanfix-20260903-f46e11f1f857`
- 完整 image ID：`sha256:f46e11f1f857b905b030adc69d112f859d183f24cc1acc450830a2856a0e2eaa`
- 镜像创建时间：`2026-09-03T02:03:50.509676564Z`
- 镜像大小：`5493299766` bytes
- ROS：ROS1 Noetic
- 启动配置：host network、privileged、restart `unless-stopped`
- Entrypoint：`/ros_entrypoint.sh`
- Cmd：`/usr/local/bin/nav-api-entrypoint`
- WorkingDir：`/Scout_mini_navigation`

2026-09-03 11:38 CST 执行过滤后的 `docker diff`，仅见 `/root`、`/tmp`、`/run`、`/run/nginx.pid` 等运行产物；未发现 `/Scout_mini_navigation/src`、`/Scout_mini_navigation/install`、`/usr/local/bin`、`/etc` 或 `/app` 的启动后业务修改。因此同事成果已经包含在上述 image ID 中，不需要也不应额外 `docker commit`。

增加恢复 tag 后复核：当前容器仍为 `running`，`StartedAt=2026-09-03T02:10:25.027905997Z`，`RestartCount=0`，image ID 未变化。

完整现场参数证据：

`F:\slamibot_agent\.ai-workspace\procedures\artifacts-scout-nav-timefix-20260827-inspect-20260903.json`

## 必须保留的宿主机数据挂载

```text
/home/jetson/Scout_mini_navigation/src/my_nav/maps
  -> /Scout_mini_navigation/src/my_nav/maps
  -> /data/scout-nav/maps

/home/jetson/Scout_mini_navigation/src/nav_api/db
  -> /Scout_mini_navigation/src/nav_api/db
  -> /data/scout-nav/db

/home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD
  -> /Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD
  -> /data/scout-nav/fastlio/PCD
```

恢复前必须确认以上三个宿主机目录存在且内容正常；禁止用容器内空目录覆盖它们。

## 恢复前核验

```bash
docker image inspect scout-nav:recovery-colleague-2d-scanfix-20260903-f46e11f1f857 \
  --format 'id={{.Id}} tags={{json .RepoTags}}'
```

输出的 ID 必须严格等于：

```text
sha256:f46e11f1f857b905b030adc69d112f859d183f24cc1acc450830a2856a0e2eaa
```

如果 tag 不在但 image ID 仍在，可重新绑定：

```bash
docker tag \
  sha256:f46e11f1f857b905b030adc69d112f859d183f24cc1acc450830a2856a0e2eaa \
  scout-nav:recovery-colleague-2d-scanfix-20260903-f46e11f1f857
```

## 需要恢复时的创建命令

仅在人工确认旧容器已经停止并且决定恢复时执行。不要在当前容器仍运行时照抄执行。

```bash
docker run -d \
  --name scout-nav-timefix-20260827 \
  --restart unless-stopped \
  --network host \
  --privileged \
  -e SCOUT_NAV_DB_DIR=/data/scout-nav/db \
  -e FAST_LIO_PCD_DIR=/data/scout-nav/fastlio/PCD \
  -e SCOUT_NAV_WS=/Scout_mini_navigation \
  -e SCOUT_NAV_DATA_DIR=/data/scout-nav \
  -e SCOUT_NAV_MAPS_DIR=/data/scout-nav/maps \
  -v /home/jetson/Scout_mini_navigation/src/my_nav/maps:/Scout_mini_navigation/src/my_nav/maps \
  -v /home/jetson/Scout_mini_navigation/src/my_nav/maps:/data/scout-nav/maps \
  -v /home/jetson/Scout_mini_navigation/src/nav_api/db:/Scout_mini_navigation/src/nav_api/db \
  -v /home/jetson/Scout_mini_navigation/src/nav_api/db:/data/scout-nav/db \
  -v /home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD:/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD \
  -v /home/jetson/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD:/data/scout-nav/fastlio/PCD \
  scout-nav:recovery-colleague-2d-scanfix-20260903-f46e11f1f857
```

若同名旧容器仍存在，不得删除它来“省事”；先人工决定改名保留还是使用新的容器名。

## 恢复后验收

```bash
docker inspect -f 'status={{.State.Status}} image={{.Image}} started={{.State.StartedAt}} restarts={{.RestartCount}}' scout-nav-timefix-20260827
docker logs --tail 200 scout-nav-timefix-20260827
```

随后人工验证：地图列表和数据库记录完整、已有栅格地图与 PCD 可加载、建图保存可写入宿主机路径、AMCL/重定位正常、RViz 与 WEB 坐标一致、近目标导航能正常结束。

## 禁止事项

- 禁止 `docker system prune`、`docker image prune -a` 或删除上述恢复 tag/image ID。
- 禁止把 `scout-nav:product-ec245a7-arm64` 覆盖到此恢复 tag。
- 禁止把 GitHub 当前版本当成同事本轮未同步修改的事实源。
- 禁止不带宿主机 maps/PCD/DB 挂载启动恢复容器。
- 恢复 tag 名虽按不可变约定管理，但 Docker tag 技术上可被覆盖；任何重新打同名 tag 前必须核对完整 image ID。
