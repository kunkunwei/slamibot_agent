# scout-nav Plan C：已保存 2D 地图在 APP 显示机制（2026-08-26 已验证）

- 适用对象：SLAMIBot D360、ROS1 Noetic、Jetson、`scout-nav` 容器
- 关联手册：`known-issues/app-2d-map-quick-triage-2026-08-24.md`（/map 无 Publisher 排查通用路径）
- 决策背景：用户 2026-08-26 明确「Plan C」——建图过程移除 gmapping，只保留 FAST-LIO 3D 点云；
  2D 栅格地图统一手动降采样后展示（不实时生成）。
- 状态：**已验证闭环（2026-08-26）**，用户确认 APP 上 2D 地图显示。

## 核心结论

1. **建图模式下 `/map` 无 Publisher 是预期状态，不是故障。**
   Plan C 移除 gmapping 后，建图 launch（`fastlio_mapping.launch`）不再包含 `slam_gmapping`，
   因此建图期间 `/map` 没有实时发布者，APP 显示「等待/map栅格」属正常。
2. **已保存的 2D 地图通过「激活地图 + 切导航模式」由 map_server 发布 `/map` 显示。**
   APP 的 2D 栅格走 `NativeOccupancyGridClient` 订阅 `/map`（`frontend_api.yaml` occupancy_grid 已确认）。
   要让已转换好的 2D 地图显示，需要 map_server 加载该地图的 yaml 发布 `/map`。
3. **降采样走 `pcd_utils.voxel_downsample` 内联路径，不依赖 `pcd_downsample.py`。**
   `map_api.py:248` `from scripts.pcd_utils import load_pcd, save_pcd_binary, voxel_downsample`；
   `/downsample` 接口直接用 `voxel_downsample(points, None, voxel_size=0.1)` 生成 `*_display.pcd`。
   容器里没有 `pcd_downsample.py` 但降采样成功，原因在此（此前假设必须拷入该文件是错的）。

## 已验证机制与证据（2026-08-26 实测）

### 保存（save_map）
- `map2602` 产物全部有效：`map2602.pcd`（2.35GB）、`map2602.pgm` + `map2602.yaml`、`map2602_display.pcd`（14206 点）。
- PGM 有效性实测：P5 格式 43467B，像素 43452，其中空闲（>127）40069、占用/未知 3383，是正常房间地图。
- 2D 栅格由 `pcd_to_map.py` 从 FAST-LIO PCD 投影生成（`_PCD_TO_MAP`，经 my_nav symlink 解析到 src）。

### 降采样（downsample）
- `/api/map/downsample` 返回「3D 预览生成任务已启动」，实际经 `pcd_utils.voxel_downsample` 生成 `*_display.pcd`。

### 激活（switch_map）
- `POST /api/map/switch {"mapName":"map2602"}` → 返回 success + yamlFilePath；
  同时 `_update_launch_map` 把 `my_nav_launch.launch:11` 的 `<arg name="map_file" ...>` 更新为
  `/Scout_mini_navigation/install/lib/python3/my_nav/maps/api_map/map2602/map2602.yaml`。

### 显示（导航模式）
- `GET /api/control/mode/navigation` → `current_mode=navigation, navigation_running=true, pcd_running=true`。
- 导航三节点启动：`/map_server`、`/amcl`、`/move_base`。
- `/map` 实测：Publishers=`/map_server`；`frame_id="map"`、`resolution=0.05`、`width=213`、`height=204`，
  与 map2602.yaml 完全一致。
- 用户确认：**APP 上 2D 地图显示**。

## 关键事实纠正

- **FastAPI 监听 `5000` 端口**（`/opt/python-api/bin/python3 -m uvicorn fastapi_service.app:app --port 5000`）。
  `19090` 是容器内部 rosbridge（`/scout_nav_rosbridge`），不是 API 端口。之前 curl 19090 拿到的是 WebSocket 握手页。
- `pcd_downsample.py` 不在容器内，不补拷；降采样正确路径是 `pcd_utils`（scripts.pcd_utils 在容器内已有）。
- 上一轮 hotfix 的 my_nav symlink 使 `_PCD_TO_MAP`/`_MAP_ROOT`/`_NAV_LAUNCH` 经
  `install/lib/python3/my_nav -> src/my_nav` 解析可用。

## 遗留事项

- 当前 `scout-nav` 处于导航模式；底盘（BOX）断开，`/amcl`、`/move_base` 可能不健康，
  **导航闭环（交接 Phase B）待底盘恢复后再验收**。
- 若用户期望建图模式下也能查看「已保存 2D 地图」，需在 Phase C 固化时评估：
  激活地图后是否常驻一个只读 map_server 发布 `/map`（当前设计是导航模式才起 map_server）。
- Phase C 代码固化：`map_api.py` 的 `../../` 相对路径、`current_mode` 与进程状态一致性、
  降采样/保存/激活生命周期、正式 Docker 固化 `ros-noetic-slam-gmapping` 的移除与 FAST-LIO 资源。
- 数据落点：地图/DB 需确认在宿主持久化挂载（`/home/jetson/Scout_mini_navigation/...`），
  不依赖容器可写层；当前容器可写层热修（symlink）在重建容器后会丢失。
