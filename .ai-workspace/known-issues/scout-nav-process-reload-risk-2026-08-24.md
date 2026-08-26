# scout-nav 进程拓扑与无重启热更新风险（2026-08-24）

## 适用范围
- Jetson 上运行中的 `scout-nav` 容器；ROS1 Noetic 基线。
- 目的：在缺少重建/整容器重启时间窗口时，避免为加载 Python 改动破坏现有导航与 rosbridge。

## 已确认事实
- 容器 PID 1：`/bin/bash /usr/local/bin/nav-api-entrypoint`。
- entrypoint 直接启动 rosbridge、`nav_multi`、Nginx、Uvicorn，并执行 `wait "$API_PID"` 等待 Uvicorn。
- Uvicorn 当前容器 PID 147；`/nav_multi` 当前容器 PID 109。
- 容器 RestartPolicy：`unless-stopped`。
- Uvicorn 还是当前导航 `roslaunch` / PCD 相关进程的父进程；它不是可随意单独重载的无状态 Web 服务。
- 8 个 Python 文件已热拷贝进容器，9 个目标文件哈希一致；但运行中的 Python/ROS 节点不会自动重新加载磁盘代码。
- 当前 `/nav_multi/point_arrived` 为 `Unknown topic`，说明 PID 109 仍运行旧内存代码。
- 用户已确认容器内 `espeak-ng` 可通过 USB 扬声器播放中文，TTS/ALSA/扬声器基础链路正常。

## 禁止操作
- 不执行 `docker restart scout-nav`、`docker stop/start`、删除或重建容器。
- 不直接结束 Uvicorn：它退出后 PID 1 会进入全量 cleanup 并退出，随后 `unless-stopped` 可能自动拉起整个容器。
- 不在导航运行期间全局 `rosnode cleanup`；不批量结束 ROS/导航进程。
- 不把“文件已 copy”误判为“运行时已生效”。

## 风险解释
- 已确认的直接风险是 entrypoint 生命周期耦合：Uvicorn 退出会连带清理并触发容器级重启路径。
- ROS Master 可能保留短时 stale registration，表现为同名节点、话题或 rosbridge 状态异常；现场曾见 PCD 旧节点注册残留。
- “宿主机收养容器内孤儿进程/端口未释放”属于用户提出的机理假设，当前没有证据证明是本次问题的主因；Docker 正常停止时通常会终止容器 PID namespace 内进程。排障以实际 PID、ROS node URI、topic publisher 和端口为准。

## 当前安全测试策略
1. 保持现有 Uvicorn、`nav_multi`、rosbridge、Nginx 和导航进程不动。
2. 需要验证到点 TTS 时，另启隔离的临时订阅进程，订阅测试 topic/事件并调用同一 TTS 逻辑。
3. 先手工发布事件验证 `ROS Topic -> 后端处理 -> espeak-ng -> USB 扬声器`，再设计 `nav_multi` 的受控单进程切换窗口。
4. 任何真实运动、部署、重启或容器生命周期变更继续单独授权。

## 验证状态
- 文档依据：2026-08-24 只读进程/入口脚本/ROS topic 检查与用户现场播放确认。
- tests: SKIPPED (documentation-only; no container/process change)
