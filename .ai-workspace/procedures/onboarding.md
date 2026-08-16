# 流程：新成员交接（onboarding）

## 交接清单
1. 阅读本工作区 `.ai-workspace/README.md` 与顶层 `CLAUDE.md`。
2. 阅读 `facts/repos.yaml`（仓库清单）与 `facts/robot_profile.yaml`（机型）。
3. 阅读 `core/` 六份全局规范（工程/安全/测试/边界/技术栈隔离/生命周期/角色）。
4. 阅读 `facts/rosbridge_profile.yaml` 理解前后端与 ROS 的边界。
5. 了解三 Agent 角色与 Jetson 权限分级。

## 需要交接的“隐藏上下文”（务必落到文件）
- SSH 主机/端口、Docker 镜像与启动方式、rosbridge 地址、关键 Topic/TF、已知坑（`known-issues/`）。
- 任何尚未文件化的事实，先补进 `facts/`，再交接。
