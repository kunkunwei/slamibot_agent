# 任务日志：2D 导航一键安装脚本改为公开仓库分发

- 日期：2026-09-16（建立）
- 状态：**待执行** —— 等公开仓库就绪；脚本内容与文档旧链接的现状已记录在下方，可直接照单执行
- 关联：`.ai-workspace/tasks/branch-cleanup-2026-09-16.md`（同一轮工作的分支清理记录）、
  `D360装机流程.txt` §12、已知问题 `known-issues/product-image-ships-demo-maps-2026-09-16.md`

## 一、要解决的问题

`D360装机流程.txt` §12.2 的"一键安装"让装机人员执行：

```
curl -fsSL -o /tmp/install_2d_nav.sh \
  https://raw.githubusercontent.com/kunkunwei/Scout_mini_navigation/master/scripts/install_2d_nav.sh
```

但 `kunkunwei/Scout_mini_navigation` 是**私有仓库**，新设备上没有任何凭据，这一步必然 404。
即：2D 导航的"一键"捷径是断的；只有 §12.3 手写 compose 那条路能用。

## 二、为什么基础三容器的一键流程没这个问题（已实测取证）

基础三容器链路的分发渠道是**公开 Gitee + ACR**，与 GitHub 无关：

| 环节 | 事实 | 取证方式（2026-09-16） |
|---|---|---|
| 装机脚本 `setup_env.bash` | 位于公开 Gitee `gitee.com/electech6/d360_deploy` | 本机 `curl -sL -o /dev/null -w %{http_code}` → **200** |
| 三容器 compose 文件 | 由该脚本在设备上**就地写入** `/etc/slamibot/system/docker-compose.yml`，不从网上取 | 文档"四、脚本自动完成的 6 步"第 5 步 |
| 镜像 `slamibot/*` | ACR 命名空间**匿名可拉**，无需 docker login | 在**无任何 docker 凭据**的 164（`/root/.docker/config.json`、`~/.docker/config.json` 均不存在）上执行 `docker manifest inspect registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d:1.2.3` 与 `.../slamibot_d360_firmware:latest`，均 **OK** |
| GitHub 私有仓库 | 匿名不可达 | `api.github.com/repos/kunkunwei/Scout_mini_navigation` → 404；`raw.../master/README.md` → 404；同网络公开仓库 raw → 200 |

**踩过的坑（勿再误判）**：直接匿名访问 ACR 的 `/v2/<repo>/manifests/<tag>` 会 401，
`dockerauth.cn-shanghai.aliyuncs.com/auth?...` 返回的匿名 token 里 `access` 字段为空——
这是 ACR 的 API 行为，**不能**据此判定"仓库私有/需要登录"。判断可拉取性只认 docker 自己的流程
（`docker manifest inspect` / `docker pull`，且必须在**没有凭据的机器**上测）。

## 三、待执行清单（公开仓库就绪后）

1. **上传脚本**到公开仓库（Gitee 或 GitHub 公开仓库均可，建议与现有 `d360_deploy` 同一套路）。
   脚本来源：`Scout_mini_navigation@master`（`1ad7809`）里的 `scripts/install_2d_nav.sh`，
   默认镜像已是 `registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d:1.2.3`。
   内容校验：`bash -n` 通过；脚本内 `IMAGE=` 默认值为 1.2.3。
2. **匿名可达性验证**（必须先做）：在一台**没有任何代码托管凭据**的机器上
   `curl -fsSL -o /tmp/x.sh <新URL> && bash -n /tmp/x.sh`，并在浏览器无痕窗口打开同一 URL 复核。
3. **改文档 `D360装机流程.txt` §12.2**：把 curl 的 URL 换成新公开地址，并保留 `--dry-run` 那一步。
   注意：该文件是 **UTF-8 + CRLF**，编辑时勿改行尾；`Edit` 的多行匹配在混合行尾下会失败，
   建议按单行做替换。
4. **（建议同时做）把脚本打进导航镜像**，让离线/无托管访问也能装。做法：
   Dockerfile 里 `COPY scripts/install_2d_nav.sh /Scout_mini_navigation/scripts/`，出下个 tag；
   文档补一条备用取法：
   `docker run --rm --entrypoint cat <镜像> /Scout_mini_navigation/scripts/install_2d_nav.sh > /tmp/install_2d_nav.sh`
   （当前 1.2.3 镜像里 `ls /Scout_mini_navigation` 只有 `install/`，脚本不在里面。）
5. **在新设备上端到端演练一次**：从裸机按文档走完 §一～§十二，验收点用 §12.4
   （`/health` 返回 `rosbridgeConnected:true`、四端口在听、APP 能进、首启需先
   `GET /api/control/mode/navigation/ensure` 再建图）。
6. 演练通过后回来把本文状态改为 completed，并把新 URL 记录进 §12.1/§12.7 的引用处。

## 四、验收标准（完成定义）

- 在**没有 GitHub/Gitee 凭据、只有网络**的新设备上，§12.2 的文档命令能取到脚本并完成安装；
- 在**完全无外网**的设备上，§12.3 手写 compose（或镜像内自带脚本）也能完成安装；
- 文档里不再出现任何指向私有仓库的取脚本 URL。

## 五、本轮已完成、与本文相关的上下文（便于接手）

- 701（开发设备）导航容器升级到 1.2.2，误拷的开发地图已全部撤销：701 现为 27 套真实地图、0 断链。
- 镜像清理发布 **1.2.3**（`sha256:51c75fe4…`），剔除镜像内残留的开发地图文件。
- 源码 `Scout_mini_navigation` 远端**只剩 `master`＝`1ad7809`**（由 `140f049` 快进，无多余合并提交）；
  其余 7 个分支已删，提交点记录见 `tasks/branch-cleanup-2026-09-16.md`。
- 仍未决（不属本文范围）：701/164 是否切到 1.2.3；ACR 上坏的 `1.1` tag 是否删；
  701 上 12 个历史 stopped 测试容器是否清；164 相机不出图与无讯飞网关。
