# 流程：Jetson / SSH 验证（jetson-validation）

> Jetson 只作为远程目标。默认 **READ_ONLY**，逐级授权，DANGEROUS 永远人工确认。

## 权限四级
| 级别 | 允许 | 授权 |
|---|---|---|
| READ_ONLY | 查状态/日志、`rosnode`/`ros2 node`、`topic` 查询、`docker ps/logs`、`git status/diff` | 默认 |
| BUILD | 编译、构建 Docker 镜像、跑测试 | 任务授权 |
| DEPLOY | 启停导航服务、重部署指定容器 | 任务授权 |
| DANGEROUS | 删容器/网络、`docker system prune`、`rm`、改系统配置、重启、磁盘清理 | 永远人工确认 |

## 连接
- 事实见 `facts/jetson_profile.yaml`；SSH 目标在 `~/.ssh/config`（`116.148.216.66:30046`, root）。

## 验证步骤模板
1. 先 READ_ONLY 采集：`git status`、`docker ps`、关键日志、topic/node 状态。
2. 需要编译/部署时，明确请求授权（BUILD / DEPLOY），说明要跑的命令与影响。
3. 验证结果（成功/失败/日志摘要）写回任务条目或 `known-issues/`。

## 铁律
- 不在 Jetson 新增 Agent/RAG/向量库/AI 服务/后台进程/额外容器。
- 权限模型比提示词约束可靠：未授权即拒绝。
