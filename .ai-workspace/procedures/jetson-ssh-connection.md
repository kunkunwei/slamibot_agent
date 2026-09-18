# Jetson 可靠 SSH 连接方式

> 当前事实：2026-08-20 15:22:32 CST，Codex 从 Windows 通过 LAN 直连成功。  
> 返回：`host=ubuntu`、`user=jetson`。  
> 本文是新会话的 SSH 操作入口；状态变化后必须按绝对时间更新。

## 新板入口：ROS2 部署候选（2026-09-01）

```text
host: 192.168.31.35
port: 22
user: jetson
os: Ubuntu 22.04.5 LTS（CONFIRMED_READ_ONLY）
platform: arm64 / L4T R36.5
status: CONFIRMED（2026-09-01 17:07:32 CST）
```

新板沿用旧板用户名和密码，但密码不得写入工作台。现有公钥已安装并通过 `BatchMode=yes` 验证；Git Bash 首次安装命令为：

```bash
ssh-copy-id -F /dev/null -i /c/Users/kun/.ssh/id_rsa.pub jetson@192.168.31.35
```

公钥完成后使用：

```bash
ssh -F /dev/null -i /c/Users/kun/.ssh/id_rsa -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes jetson@192.168.31.35
```

该目标当前仅允许 READ_ONLY。已确认仓库为 `dev_ros2`@`27325c45`，但 `/opt/ros`、`ros2` 和 `colcon` 均不存在；原生/容器部署方式仍待决定。不得覆盖下面旧板 ROS1 CURRENT 的连接记录。

## 旧板首选入口：局域网

```text
host: 192.168.31.135
port: 22
user: jetson
private key: C:\Users\kun\.ssh\id_rsa
status: CONFIRMED
```

交互登录：

```powershell
ssh -F NUL -i "C:\Users\kun\.ssh\id_rsa" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 jetson@192.168.31.135
```

最小只读验证：

```powershell
ssh -F NUL -i "C:\Users\kun\.ssh\id_rsa" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 jetson@192.168.31.135 "printf 'host='; hostname; printf 'user='; whoami; date"
```

`-F NUL` 必须保留，用于绕过 Windows 用户 SSH config 中可能存在的旧 Host、代理或公网映射配置。`BatchMode=yes` 表示只使用已有密钥，不等待密码交互。

## Codex 新会话执行规则

1. 用户已明确告知 Jetson 开机时，优先使用上述 LAN 命令，不得被旧交接中的“已关机”状态覆盖。
2. Claude Code `jetson_read_only` 或 `jetson-readonly.cjs` 若因本地进程执行权限失败，这只是本地助手失败，不是 Jetson 离线证据。
3. 当前任务已有 SSH 授权时，Codex 可通过 `functions.exec_command` 使用上述固定 SSH 前缀；沙箱要求时设置 `require_escalated`。
4. 默认只执行 READ_ONLY 命令。BUILD、DEPLOY 和 DANGEROUS 仍按工作台权限规则单独授权。
5. 不要因为公网入口超时停止排查；先检查 LAN。

推荐允许的固定前缀：

```text
ssh -F NUL
```

## 公网入口：当前不可作为首选

```text
host: 116.148.216.66
port: 30046
user: root
status: UNREACHABLE_2026_08_20
```

2026-08-20 的现象是连续连接超时，尚未进入 SSH 握手。该结果仅表示公网映射不可达，不能推出 Jetson 已关机或 LAN 不可达。

如未来明确需要验证公网入口，命令为：

```powershell
ssh -F NUL -o BatchMode=yes -o ConnectTimeout=8 -p 30046 root@116.148.216.66
```

## Jetson 热点入口

```text
host: 192.168.117.6
port: 22
user: jetson
status: NEEDS_CONFIRMATION
```

只有电脑已连接 Jetson 热点时才尝试：

```powershell
ssh -F NUL -i "C:\Users\kun\.ssh\id_rsa" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 jetson@192.168.117.6
```

## D360 保持热点时通过网线 IPv6 SSH（2026-09-03 实测）

适用于电脑只有一个无线网卡、需要继续连接公司 Wi-Fi 使用本地 AI，同时要求 D360 的 `wlan0` 保持 `Hotspot` 模式的场景。电脑 WLAN 继续联网，电脑有线网卡直连 D360 的空闲有线口；不修改热点、雷达 IPv4 或默认路由。

### 1. 在 D360 桌面确认热点

```bash
nmcli -f DEVICE,TYPE,STATE,CONNECTION device status
ip -4 -br addr show wlan0
ip -6 -br addr show eth1
```

应确认：

- `wlan0` 显示 `connected: Hotspot`，热点地址为 `192.168.117.6/24`；
- `eth0` 是雷达专用口，不修改；
- `eth1` 有 `fe80::.../64` IPv6 链路本地地址。复制地址时去掉末尾 `/64`。

`p2p-dev-wlan0` 是 Wi-Fi Direct 虚拟接口，未连接不影响热点；`docker0` 是 Docker 虚拟网桥，均不用于本次 SSH。

### 2. 在 Windows 查找有线网卡编号

```powershell
Get-NetAdapter
```

找到状态为 `Up` 的 Realtek 有线网卡并记录 `ifIndex`。2026-09-03 本机实测为 `15`；换电脑、重装驱动或接口变化后必须重新确认。IPv6 链路本地地址连接时用 `%<ifIndex>` 指定出口，例如 `%15`。

可先验证：

```powershell
ping -6 fe80::4ebb:47ff:fe51:6ab2%15
Test-NetConnection "fe80::4ebb:47ff:fe51:6ab2%15" -Port 22
```

### 3. SSH 登录

PowerShell 中整行执行，不能在单独的 `-o` 后换行：

```powershell
ssh -6 -F F:\slamibot_agent\.ssh-empty-config -i C:\Users\kun\.ssh\id_rsa -o IdentitiesOnly=yes -o HostKeyAlias=d360-e21b5e-eth1 -o StrictHostKeyChecking=accept-new jetson@fe80::4ebb:47ff:fe51:6ab2%15
```

该命令已由用户在 D360 `slamibote21b5e` 上确认可用。参数说明：

- `-6`：强制 IPv6；
- `-F F:\slamibot_agent\.ssh-empty-config`：绕过本机旧 SSH config；当前 Git for Windows SSH 不使用 `-F NUL`；
- `HostKeyAlias=d360-e21b5e-eth1`：为该设备保存独立主机密钥，避免多台 D360 共用热点 IPv4 时冲突；
- `StrictHostKeyChecking=accept-new`：仅首次自动接受新别名的主机密钥，后续密钥变化仍会拒绝。

### 4. 更换 D360 后重新发现

不同设备的 `fe80::` 地址可能不同。优先在设备桌面执行 `ip -6 -br addr show eth1`；无法查看桌面时，可在 Windows 通过以下命令查看直连有线口邻居：

```powershell
Get-NetNeighbor -InterfaceIndex 15 -AddressFamily IPv6
```

选择状态为 `Reachable` 的 `fe80::` 地址，并同时替换 SSH 命令中的地址和设备专属 `HostKeyAlias`。`192.168.144.87` 是 BOX 图传链路地址，不作为电脑直连 D360 的 SSH 地址。

## 常用只读检查

```powershell
# 身份和时间
ssh -F NUL -o BatchMode=yes jetson@192.168.31.135 "hostname; whoami; date"

# 容器状态
ssh -F NUL -o BatchMode=yes jetson@192.168.31.135 "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'"

# FastAPI 健康状态
ssh -F NUL -o BatchMode=yes jetson@192.168.31.135 "curl -sS http://127.0.0.1:5000/health"

# 底盘模式
ssh -F NUL -o BatchMode=yes jetson@192.168.31.135 "curl -sS http://127.0.0.1:5000/api/base_mode/status"

# 导航 launch 状态
ssh -F NUL -o BatchMode=yes jetson@192.168.31.135 "curl -sS http://127.0.0.1:5000/api/launch/status"
```
