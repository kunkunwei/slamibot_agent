# ROS1 产品导航镜像 `product-ec245a7` 真机测试记录（2026-09-03）

## 当前现场

- 产品测试容器：`scout-nav-product-ec245a7-test-20260903`
- 产品镜像：`scout-nav:product-ec245a7-arm64`
- image ID：`sha256:c411cf9d926b67a783e0892b4e7d783c4f655723da9a88372438ce6fbef726b9`
- 状态：running，RestartCount=0，restart policy=`no`（未验收前不设自动启动）
- 原同事容器：`scout-nav-timefix-20260827`，当前 stopped/exited，未删除
- 同事恢复镜像：`scout-nav:recovery-colleague-2d-scanfix-20260903-f46e11f1f857`
- 恢复 image ID：`sha256:f46e11f1f857b905b030adc69d112f859d183f24cc1acc450830a2856a0e2eaa`

完整产品容器 inspect：

`F:\slamibot_agent\.ai-workspace\procedures\artifacts-scout-nav-product-ec245a7-test-inspect-20260903.json`

## 本次切换

1. 删除的仅为 Docker build cache：`10.5 GB -> 0 B`；未执行 system/image/container/volume prune。
2. Jetson 根分区可用空间约 `16 GB -> 26 GB`。
3. 停止但保留同事容器。
4. 创建切换前数据库副本：

```text
/home/jetson/Scout_mini_navigation/src/nav_api/db/nav_api.db.before-product-ec245a7-test-20260903-130145.bak
```

5. 产品容器沿用宿主机 maps、DB、PCD 六个双路径挂载，并显式设置：

```text
NAV_API_MAP_ROOT=/data/scout-nav/maps/api_map
NAV_API_DB_PATH=/data/scout-nav/db/nav_api.db
FASTLIO_PCD_DIR=/data/scout-nav/fastlio/PCD
```

## 已通过的测试

### 静态镜像测试

- arm64、ROS1 Noetic：PASS
- 仅 install、没有 src/build/devel：PASS
- `install/setup.bash`：PASS
- nav_api、my_nav、amcl、move_base、FAST-LIO、Livox 等包：PASS
- Python FastAPI/MCP/roslibpy/open3d imports：PASS
- maps/DB/PCD 持久化默认配置：PASS
- stop mapping 不删除原 PCD：PASS

### 在线只读冒烟测试

- 容器持续 running、RestartCount=0、OOM=false：PASS
- Nginx `/app/` HTTP 200：PASS
- FastAPI `/docs`、`/openapi.json` HTTP 200：PASS
- SQLite `PRAGMA integrity_check=ok`：PASS
- 地图根目录识别 12 个地图目录：PASS
- `/api/map/maps/list` 和 `/api/map/list` HTTP 200，能返回既有地图：PASS
- 自动恢复加载 `map0901`：PASS
- map_server、move_base、AMCL、nav_multi、rosbridge、PCD publisher：PASS
- Scout CAN 驱动异步启动：PASS；CAN0 `ERROR-ACTIVE`
- API 底盘状态：SCOUT detected/ready/active=true：PASS
- `/clock`、`/scan`、`/map`、`/odom`、`/scout_status`、`/amcl_pose`：PASS
- `/scan` frame=`base_link`、`/odom` frame=`odom`、`/amcl_pose` frame=`map`：PASS
- 直接订阅 `/tf` 验证 `map -> odom -> base_link`：PASS

说明：启动初期底盘 API 曾短暂显示 `SCOUT_NOT_DETECTED`，随后后端成功异步启动 `scout_base_node` 并转为 ready。旧 `tf_echo` 单次缓存检查未见 map frame，但直接订阅 `/tf` 同时取得 `map->odom` 和 `odom->base_link`，实际 TF 发布链路通过。

数据库启动后由 81920 bytes 增长为 90112 bytes，SQLite 完整性正常；切换前副本已保留。

## 尚未执行的真机运动验收

为避免无人值守驱动车辆，本次没有发布 `/cmd_vel`、初始化位姿或导航目标。需要现场人工完成：

1. APP/WEB 地图显示和地图列表；
2. RViz 与 WEB 初始化位姿坐标一致性；
3. 初始化位姿后观察 AMCL 是否稳定；
4. 近距离直线目标能否自然到达并结束；
5. 空旷区域是否仍出现绕行、反复重规划；
6. 到点后 `/cmd_vel` 是否归零；
7. 建图保存是否继续落入宿主机目录并写入数据库。

## 一键回退同事容器

产品测试不通过或需要继续同事版本测试时：

```bash
docker stop -t 20 scout-nav-product-ec245a7-test-20260903
docker start scout-nav-timefix-20260827
```

随后验证：

```bash
docker inspect -f 'status={{.State.Status}} image={{.Image}} restarts={{.RestartCount}}' scout-nav-timefix-20260827
```

image ID 必须为：

```text
sha256:f46e11f1f857b905b030adc69d112f859d183f24cc1acc450830a2856a0e2eaa
```

禁止删除产品测试容器、同事容器、恢复 tag 或执行 `docker system prune`。
