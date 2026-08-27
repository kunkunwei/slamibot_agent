# 后端 API 补全：scout-nav-timefix-20260827 容器（2026-08-27）

## 背景
新版导航容器 `scout-nav-timefix-20260827`（镜像 `scout-nav:jetson0826-src-timefix-20260827`）
后端 API 未完整实现（底盘 API 与 APP 契约对不上）。用户指令：「修复完整当前容器的API实现，
不一定就要照抄旧容器」「现在APP是完全对齐旧容器的后端」。

## 补全内容（7 个文件，容器内 install + src 两处均已部署，md5 一致）
- `base_mode.py`：采用旧版完整状态机（1028 行），保留新版 `pub_tf:=true`（AMCL 导航需要 scout_base 广播 odom→base_link TF）。
  支持 status 完整字段（mode/modeLabel/control/policy/selectedBase/activeBase/detectedBase/bases/navState/ready/reason/teleopEnabled/managedScoutRunning）、
  switch 支持 GET+POST、AUTO/MANUAL 策略、managed scout roslaunch。
- `action.py`：7 路由（list/add/update/delete/toggle/execute/stop）+ 6 个默认动作。
- `control.py`：5 路由（mapping/navigation/navigation/ensure/default GET+POST）。
- `process_manager.py`：12 个函数 re-export（ensure_navigation 等）。
- `models.py`：追加 DefaultModeRequest + NavigationAction 系列请求模型。
- `app.py`：注册 action_router + lifespan 非致命 restore_default_mode。
- `schema.sql`：追加 NavigationAction 表 + SystemConfig 表。

## 验证结果（2026-08-27，容器重启后生效）
- `/api/base_mode/status`：完整字段，SCOUT detected/ready 均 true。
- `/api/base_mode/switch?mode=scout`：成功启动 managed scout（can0 配置 UP + roslaunch scout_mini_base.launch pub_tf:=true），mode=SCOUT ready=true。
- `/api/action/list`：返回 6 个默认动作。
- `/api/control/mode/navigation/ensure`、`/api/control/mode/default` GET/POST：通过。

## 关键坑（已查明，供后续会话）
1. **`INSERT OR IGNORE` 静默忽略 NOT NULL 冲突**：`action.py` DEFAULTS 里 `duration=None`，
   而 `NavigationAction.duration` 是 `NOT NULL DEFAULT 0` → 6 行默认动作全部被忽略，action/list 返回空。
   **旧容器同样有此 bug**（同样的 DEFAULTS + 同样 NOT NULL schema）。已修复：DEFAULTS 的 duration 改 `0`，
   `add_action` 的 `getattr(req,'duration',None)` 改 `getattr(req,'duration',0) or 0`。
2. **scout_base_node 是容器内进程，容器重启即丢失**：底盘驱动由 base_mode managed scout 管理。
   容器重启后需 `GET /api/base_mode/switch?mode=scout` 重新拉起（会串行检查 CAN→配 can0(bitrate 500000)→roslaunch→校验 /scout_status）。
   这是**预期行为**，不是 bug；重启后底盘不会自动恢复，必须手动 switch 或由上层流程调用。
3. **魔改 FastAPI `include_router` 生成懒加载 `_IncludedRouter`**：`app.routes` 不展开子路由，
   `getattr(r,'path')` 为空。**验证路由要用各模块 `router.routes` 遍历**，不能遍历 `app.routes`。
4. **容器内 src 与宿主机 src 不共享**：docker cp 只改容器内文件。宿主机 `/home/jetson/Scout_mini_navigation/src/`
   是 git 仓库（分支 `jetson/0826`），镜像构建用宿主机 `install/`（Dockerfile `COPY install/`）。
   持久化需将容器内修改同步回宿主机 src + install 并 git 提交（宿主机有大量用户未提交修改，须只动任务 scope 文件）。

## 持久化（已完成 2026-08-27）
- 以容器 install（运行时权威，uvicorn 实际加载）为源，同步 11 个文件到宿主机 `src/nav_api/` 与 `install/lib/python3/dist-packages/` 对应路径（md5 三侧一致）。
- 范围：`fastapi_service/action.py`(新增)、`app.py`、`base_mode.py`、`control.py`、`database.py`、`models.py`、`process_manager.py`；`scripts/launch_manager.py`、`db.py`、`nav_multi_node.py`；`db/schema.sql`。
- git 提交 `00aa4b1`（分支 `jetson/0826`）已 push 到云端 `github.com:kunkunwei/Scout_mini_navigation.git`。
- **未包含**：宿主机 git 既有的未提交修改（`audio.py`/`navigation.py`/`teleop.py` 等 M 文件、maps 删除、Dockerfile、docker-entrypoint.sh 等）——留给用户确认，勿夹带。
- 旧容器（installonly-lf `scout-nav:0cf1d78-installonly-lf-20260826`）是**要迭代的下一个版本**（用户确认），有 issue 先停用；本次补全以当前容器运行时验证为准。
