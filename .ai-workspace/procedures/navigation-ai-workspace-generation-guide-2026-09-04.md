# 导航研发本地 AI 工作台生成与使用指南

> 交付对象：机器人导航研发同事  
> 版本：1.0  
> 日期：2026-09-04  
> 定位：一套独立于业务代码、文件化、可审计、可回滚、默认只读的本地 AI 开发工作台。

---

## 1. 这套工作台解决什么问题

导航研发的上下文通常散落在代码、机器人现场、Docker、ROS 参数、Topic/TF、聊天记录和个人经验中。AI 如果只依赖对话记忆，容易混淆 ROS1/ROS2、猜测接口、覆盖现场改动，或把诊断直接升级成部署操作。

本工作台把“规范、事实、任务、流程、知识、接口和决策”集中到一个独立 Git 目录中，使 AI 和工程师遵循同一组可检查文件。

核心目标：

- **业务仓库保持独立**：工作台不承载业务代码，不合并导航、前端、后端或固件仓库。
- **事实源文件化**：机器人型号、仓库、ROS、接口、设备与运行环境都有唯一事实源。
- **默认零破坏**：未明确授权时只读，不改代码、不部署、不改远端系统。
- **技术栈隔离**：ROS1 和 ROS2 的命令、launch、参数、Topic/Service/Action、依赖与生命周期分开管理。
- **全过程可审计**：任务有 scope、forbidden、validation、rollback；改前看 status，改后看 diff。
- **可恢复交接**：换账号、换模型、重启客户端后，先读短检查点即可恢复。

## 2. 适用边界

适合：

- ROS1/ROS2 导航、定位、建图、传感器接入、规划与控制问题；
- 多业务仓库协作但不能合并仓库的机器人项目；
- 本地开发 + Jetson/工控机远程运行的场景；
- 需要 AI 辅助分析、修改、验收、交接和问题沉淀的团队。

不适合直接放入工作台：

- 业务源码副本、完整构建产物、镜像包、数据集、地图、点云、录包；
- 密码、Token、私钥、客户隐私数据；
- 临时热修脚本、一次性抓取文件和大日志的长期堆积。

## 3. 推荐目录架构

```text
nav-ai-workspace/
├── AGENTS.md                         # Codex/通用 Agent 自动入口
├── CLAUDE.md                         # Claude Code 入口（使用时）
├── .gitignore
└── .ai-workspace/
    ├── README.md                     # 工作台总说明与快速开始
    ├── core/                         # 不随项目变化的强制规则
    │   ├── engineering-rules.md
    │   ├── git-safety.md
    │   ├── change-policy.md
    │   ├── tech-stack-isolation.md
    │   ├── system-lifecycle.md
    │   ├── testing-rules.md
    │   ├── agent-roles.md
    │   └── context-compaction.md
    ├── projects/                     # 每个业务仓库的边界说明
    │   ├── navigation-ros1/project.md
    │   └── navigation-ros2/project.md
    ├── facts/                        # 唯一可信事实源（YAML）
    │   ├── repos.yaml
    │   ├── robot_profile.yaml
    │   ├── navigation_ros1_profile.yaml
    │   ├── navigation_ros2_profile.yaml
    │   ├── rosbridge_profile.yaml
    │   └── compute_profile.yaml
    ├── interfaces/                   # 接口语义与兼容性边界
    │   ├── navigation/README.md
    │   └── rosbridge/README.md
    ├── tasks/                        # 当前状态与短恢复入口
    │   ├── context-checkpoint.md
    │   ├── current.md
    │   ├── backlog.md
    │   └── completed.md
    ├── procedures/                   # 标准操作流程
    │   ├── onboarding.md
    │   ├── new-feature.md
    │   ├── bug-fix.md
    │   ├── navigation-debug.md
    │   ├── ros1-development.md
    │   ├── ros2-development.md
    │   ├── ros1-to-ros2-migration.md
    │   ├── remote-read-only-check.md
    │   └── rollback.md
    ├── agents/                       # Explorer/Implementer/Validator
    ├── knowledge/                    # 稳定领域知识和交接资料
    ├── known-issues/                 # 每个已知问题一份文件
    ├── decisions/                    # ADR 架构决策记录
    ├── tmp/                          # 可删除的任务临时材料
    └── backups/                      # 仅危险操作的最小备份
```

### 各层职责

| 层 | 回答的问题 | 内容特征 |
|---|---|---|
| core | 所有任务永远要遵守什么 | 稳定、强制、项目不可放宽 |
| projects | 这个仓库允许改什么、保护什么 | 按仓库独立 |
| facts | 当前真实环境是什么 | YAML、带确认状态、禁止猜测 |
| interfaces | 外部依赖什么语义 | Topic/Service/Action/API/错误码/TF |
| tasks | 现在做什么、做到哪一步 | 短、可恢复、可归档 |
| procedures | 同类任务按什么步骤执行 | 可复制流程与模板 |
| knowledge | 为什么这样设计、历史背景是什么 | 稳定知识，不充当运行态事实 |
| known-issues | 已踩过什么坑 | 现象、根因、证据、修复、回滚 |
| decisions | 为什么选择某个架构 | ADR，保留备选方案和后果 |

## 4. 顶层强制规则

建议把以下内容写入顶层 `AGENTS.md`，并让各 AI 工具自动读取：

1. **零破坏**：默认只读。没有任务授权，不修改业务代码、远端系统、ROS/Docker 运行态或 Git 历史。
2. **稳定基线优先**：明确哪个技术栈是 CURRENT。普通修复不得自动触发迁移。
3. **ROS1/ROS2 隔离**：不得混用命令、launch、参数、消息模型、依赖和工作区。
4. **事实源唯一**：缺失值只能写 `UNKNOWN`、`NEEDS_CONFIRMATION` 或 `TODO`，不能猜。
5. **最小权限**：本地默认只读；远端设备默认只读；写入、构建、部署、危险操作分级授权。
6. **保留用户改动**：改前检查 `git status`，禁止覆盖已有未提交内容。
7. **可审计可回滚**：任务必须写允许范围、禁止范围、验证方式和回滚方法；改后检查 `git diff`。
8. **接口默认受保护**：Topic、Service、Action、TF、参数名、状态码和 rosbridge/API 语义未经授权不得改变。
9. **输出落盘**：关键事实、验证结果和未完成项不能只留在聊天里。
10. **不声称未做的验证**：跳过测试必须明确写 `tests: SKIPPED`。

## 5. 事实源设计

### 5.1 通用状态字段

所有事实建议附带状态：

- `CONFIRMED`：已由代码、配置或运行态证据确认；
- `CONFIRMED_READ_ONLY`：通过远端只读检查确认；
- `NEEDS_CONFIRMATION`：有线索但尚未核验；
- `UNKNOWN`：当前没有可靠信息；
- `TODO`：已知需要补充；
- `DEPRECATED`：历史事实，仅用于回溯。

### 5.2 仓库清单模板

```yaml
repositories:
  - id: navigation_ros1
    name: <仓库名>
    local_path: <本机绝对路径或 UNKNOWN>
    remote_url: <远端地址或 UNKNOWN>
    default_branch: <分支或 NEEDS_CONFIRMATION>
    stack: { os: ubuntu20.04, ros: ros1, distro: noetic }
    lifecycle: CURRENT
    write_policy: TASK_SCOPE_ONLY
    status: CONFIRMED
```

### 5.3 机器人型号模板

```yaml
robots:
  - model: <型号>
    chassis: <底盘>
    compute: <计算平台>
    lidar: <雷达>
    cameras: []
    imu: <型号或 UNKNOWN>
    network_interfaces: []
    can_interface: <can0 或 UNKNOWN>
    navigation_stack: navigation_ros1
    status: NEEDS_CONFIRMATION
```

### 5.4 ROS1 导航事实模板

```yaml
navigation_ros1:
  lifecycle: CURRENT
  os: ubuntu20.04
  distro: noetic
  build_tool: catkin_make
  workspace: <路径>
  localization: []
  mapping: []
  global_planner: UNKNOWN
  local_planner: UNKNOWN
  topics: []
  services: []
  actions: []
  tf_frames: []
  parameters: {}
  launch_entries: {}
  dependencies: []
  maps_path: UNKNOWN
  logs_path: UNKNOWN
  status: NEEDS_CONFIRMATION
```

### 5.5 ROS2 导航事实模板

ROS2 必须使用独立文件，至少记录：发行版、RMW、colcon 工作区、Nav2 插件、Lifecycle 节点、Action、QoS、TF、参数文件、地图格式和启动入口。禁止把 ROS1 的 `roslaunch/rosparam/rostopic` 写进 ROS2 流程。

## 6. 项目边界文件

每个业务仓库建立一个 `projects/<project>/project.md`：

```markdown
# 项目：navigation-ros1

- id: navigation-ros1
- lifecycle: CURRENT
- repo: <URL>
- local_path: <PATH>
- tech_stack: { ros: ros1, distro: noetic, os: ubuntu20.04 }

## allowed_paths
- 默认无全局写权限；每个任务精确声明文件。

## protected_paths
- docker/ 与部署基础设施
- ros2/ 目录
- 用户已有未提交文件

## protected_interfaces
- /cmd_vel 语义
- move_base action
- map/odom/base_link TF 关系
- rosbridge 对外协议

## validation
- 静态检查
- 构建（授权时）
- 仿真（授权时）
- 真机（单独授权）
```

项目规则只能比全局规则更严格，不能更宽松。

## 7. 任务模板与工作流

### 7.1 标准任务模板

```yaml
- id: TASK-YYYY-MM-DD-001
  goal: <一句话目标>
  project: navigation-ros1
  technology: ros1
  lifecycle: CURRENT
  mode: read_only            # read_only / edit / build / deploy
  migration: false
  scope:
    - <允许读取或修改的路径>
  forbidden:
    - ros2/
    - docker/
    - protected interfaces
    - unrelated repositories
  evidence:
    - <日志、截图、录包、提交、复现时间>
  assumptions: []
  validation:
    - git diff
    - <任务相关验证>
  rollback: <恢复方法>
  status: in_progress
  tests: SKIPPED
  notes: ''
```

### 7.2 推荐执行顺序

1. **恢复上下文**：先读 `tasks/context-checkpoint.md`，再按需读 current 与 facts。
2. **Explorer 只读定位**：确认仓库、栈、接口、证据和建议 scope，假设必须显式标注。
3. **建立任务**：写 goal、scope、forbidden、validation、rollback。
4. **Implementer 最小修改**：改前 status；只改 scope；不顺手重构。
5. **Validator 独立验收**：检查 diff，并执行与风险匹配的验证。
6. **沉淀结果**：更新事实源、接口、known issue 或 ADR。
7. **任务压缩**：完成后覆盖短检查点，current 移入 completed。

## 8. 三种 Agent 角色

| 角色 | 默认权限 | 主要产物 | 禁止事项 |
|---|---|---|---|
| Explorer | 只读 | 事实、证据、假设、建议 scope | 修改文件、部署、把猜测当事实 |
| Implementer | 任务范围内写入 | 最小补丁、diff 摘要 | 扩大 scope、顺手重构、改受保护接口 |
| Validator | 原则上只读 | 验证结果、风险、回滚检查 | 无限自动修复、隐瞒失败 |

一个模型可以依次承担三种角色，但每个阶段的权限和输出必须明确。复杂任务可并行分析，写入任务必须保证修改路径不重叠。

## 9. Git 与变更安全

每次修改前：

```bash
git status --short --branch
git diff -- <任务涉及路径>
```

每次修改后：

```bash
git status --short
git diff --check
git diff -- <任务涉及路径>
```

禁止默认执行：

- `git reset --hard`、`git clean -fd`、强制 checkout；
- force push、改写公共历史；
- 把用户未提交修改混入当前任务；
- 在远端或受保护分支直接试错。

普通改动建议使用独立安全分支；提交只包含本任务文件。上传远端不等于功能已验证。

## 10. 远端计算平台与 Jetson 权限分级

建议建立四级权限：

| 级别 | 示例 | 默认策略 |
|---|---|---|
| READ_ONLY | 系统状态、日志、节点、Topic 元数据、TF、docker ps/logs、git status/diff | 可按任务自动执行 |
| BUILD | 编译、构建镜像、生成安装空间 | 必须任务明确授权 |
| DEPLOY | 重启服务、替换容器、切换镜像、写远端文件 | 必须当前任务明确授权 |
| DANGEROUS | 删除、prune、改系统、刷固件、重启整机、磁盘清理 | 每次人工确认 |

额外原则：

- 远端设备不安装 Agent、RAG、向量库或额外 AI 常驻服务；
- SSH 主机别名可以文件化，密码、私钥和 Token 不进入工作台；
- 设备关机或未获开机确认时，不尝试连接；
- 只读诊断不能被当作部署授权。

## 11. ROS 导航专项隔离

### ROS1 基线

典型工具：`catkin_make`、`roslaunch`、`rostopic`、`rosparam`、move_base。所有 ROS1 事实只写入 ROS1 profile。

### ROS2 产品或目标栈

典型工具：`colcon`、`ros2 launch`、`ros2 topic`、`ros2 param`、Nav2、Lifecycle、DDS/RMW。所有 ROS2 事实只写入 ROS2 profile。

### ROS1 → ROS2 迁移

迁移必须同时满足：

- 任务显式 `migration: true`；
- 写明 from/to；
- 人工明确批准；
- 使用独立分支或独立工作区；
- 旧接口不被新接口说明覆盖；
- ROS1 CURRENT 在迁移期间保持可用。

## 12. 导航问题的证据清单

导航故障单建议至少记录：

- 机器人型号、软件版本、Git commit、容器/镜像标识；
- 发生日期与精确时间、地图、起点、目标点、运动模式；
- 复现步骤、期望、实际现象、安全影响；
- ROS 栈与发行版；
- 节点列表和关键 Topic 的频率/类型/发布订阅关系；
- `map -> odom -> base_link` TF 与传感器外参；
- 定位、全局规划、局部规划、代价地图、速度命令的关键日志；
- 参数快照和 launch 入口；
- 是否可安全复现、是否需要抬轮/空旷区域/急停人员；
- 已尝试操作及其结果；
- 回滚点。

不要把截图中的猜测直接写成根因；先写“现象”和“证据”，根因需要可复核链路。

## 13. 初始化步骤

### 阶段 A：创建空工作台

1. 新建独立目录并初始化 Git。
2. 创建本指南第 3 节的最小目录。
3. 写顶层 AGENTS.md 和 README.md。
4. 配置 .gitignore，排除 tmp、日志、录包、地图、点云、密钥和大构建产物。

### 阶段 B：接入第一个导航仓库

1. 只读检查仓库 `git status`、远端、分支和目录结构。
2. 在 `facts/repos.yaml` 登记，不复制源码。
3. 建立 `projects/navigation-ros1/project.md` 或 ROS2 对应文件。
4. 从代码、launch、参数和接口文档提取事实；不确定项保留 UNKNOWN。
5. 建立接口保护清单，尤其是 cmd_vel、导航 Action、TF、地图与状态协议。

### 阶段 C：接入机器人

1. 建立 robot profile 和 compute profile。
2. 先离线填写已知信息，再在授权后做远端只读核验。
3. 将 SSH、Docker、ROS 和设备状态分开记录，避免把一次运行态当永久事实。
4. 敏感凭据只存在系统密钥链、SSH agent 或人工输入中。

### 阶段 D：启用任务流程

1. 创建第一个只读盘点任务。
2. 用 Explorer → Implementer → Validator 完成一个低风险小任务。
3. 验证 status/diff/rollback 流程。
4. 完成后更新 completed 与 context-checkpoint。

## 14. 最小可用版本（MVP）

如果时间有限，先创建以下 15 个文件即可投入使用：

1. `AGENTS.md`
2. `.ai-workspace/README.md`
3. `core/engineering-rules.md`
4. `core/git-safety.md`
5. `core/change-policy.md`
6. `core/tech-stack-isolation.md`
7. `projects/navigation-ros1/project.md`
8. `facts/repos.yaml`
9. `facts/robot_profile.yaml`
10. `facts/navigation_ros1_profile.yaml`
11. `interfaces/navigation/README.md`
12. `tasks/context-checkpoint.md`
13. `tasks/current.md`
14. `procedures/bug-fix.md`
15. `procedures/navigation-debug.md`

ROS2 只有在确实存在 ROS2 产品或迁移任务时再加入，不要为“以后可能用”而提前混入 ROS1 当前任务。

## 15. 不应原样复制的内容

交付工作台骨架时，应复制“结构和规则”，不要复制当前项目现场数据：

- 具体 IP、端口映射、用户名、设备序列号和客户网络信息；
- 远端仓库私有地址与访问凭据；
- 当前机器人容器 ID、镜像 SHA、现场路径和临时回滚标签；
- 大量历史 current/completed 内容；
- tmp、backups、bundle、tar.gz、构建缓存、地图、PCD、bag、数据库；
- 一次性恢复脚本和未经审查的现场热补代码；
- 与同事职责无关的前端、后端、语音、售后任务事实。

这些内容应由同事在自己的环境中重新确认并填写。

## 16. .gitignore 建议

```gitignore
.ai-workspace/tmp/**
.ai-workspace/backups/**
*.log
*.bag
*.bag.active
*.pcd
*.ply
*.db
*.sqlite*
*.tar
*.tar.gz
*.bundle
build/
devel/
install/
log/
.env
*.pem
*.key
id_rsa*
known_hosts*
```

如果某个小型样例必须纳入 Git，应使用白名单例外并说明来源、用途和隐私检查结果。

## 17. 交付验收清单

- [ ] 工作台与业务仓库物理分离；
- [ ] 顶层 Agent 入口会自动加载核心规则；
- [ ] CURRENT 技术栈写清楚；
- [ ] ROS1/ROS2 facts、project 和 procedure 分离；
- [ ] 仓库和机器人事实源不存在猜测值；
- [ ] 受保护接口已列出；
- [ ] 远端权限按 READ_ONLY/BUILD/DEPLOY/DANGEROUS 分级；
- [ ] 第一个任务包含 scope、forbidden、validation、rollback；
- [ ] 修改前后能够生成 status 和 diff；
- [ ] 不包含密码、Token、私钥、地图、点云、bag 和大日志；
- [ ] context-checkpoint 能在 40 行内恢复当前状态；
- [ ] 已演练一次小任务和一次回滚；
- [ ] 测试跳过时会明确标注，而不是声称通过。

## 18. 给同事的建议使用方式

第一次使用时，先让 AI 执行以下指令：

> 只读读取 AGENTS.md、.ai-workspace/README.md、tasks/context-checkpoint.md、facts/repos.yaml、robot_profile.yaml 和当前导航 profile。先输出已确认事实、未知项、风险和建议的第一个只读盘点任务。不要修改文件，不要连接远端，不要猜测 UNKNOWN。

完成首轮盘点后，再逐项授权补充 facts。以后每个任务都从短检查点恢复，不要依赖历史聊天记忆。

---

## 附录 A：本指南提炼自当前工作台的设计要点

当前工作台采用“独立 Git 工作台 + 多业务仓库引用”的方式，已经覆盖 core、projects、facts、interfaces、tasks、procedures、agents、knowledge、known-issues 和 decisions 等层。导航部分为 ROS1 CURRENT 与独立 ROS2 项目分别建立 project/profile/procedure，并通过迁移专项阻止普通任务隐式跨栈。任务收尾使用短检查点进行逻辑压缩。

本指南只复用其架构思想和通用模板，已主动剔除现场 IP、账号、镜像、容器、客户设备、历史任务和临时热修内容。交付给同事后，应以其自己的代码、机器人和运行环境重新建立事实源。
