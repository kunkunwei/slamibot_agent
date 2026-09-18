# D360 网线直连 IPv6 SSH 手动操作指南

## 适用场景

电脑只有一个无线网卡，需要同时满足：

- 电脑 WLAN 继续连接公司 Wi-Fi，保证本地 AI 可以联网；
- D360 的 `wlan0` 保持 `Hotspot` 模式和 `192.168.117.6/24`；
- 电脑通过网线直连 D360 `eth1`，使用 IPv6 link-local 地址 SSH；
- 不修改 `eth0` 雷达地址，不依赖 BOX 图传网络。

推荐连接关系：

```text
电脑 WLAN ── 公司 Wi-Fi ── 互联网 / 本地 AI
电脑 Realtek 有线网卡 ── 网线 ── D360 eth1 ── SSH
D360 wlan0 ── Hotspot（192.168.117.6/24）
D360 eth0 ── 雷达专用
```

## 一、在 D360 桌面手动查询地址

打开 D360 桌面终端，确认热点仍在运行：

```bash
nmcli -f DEVICE,TYPE,STATE,CONNECTION device status
ip -4 -br addr show wlan0
```

正常状态应包含：

```text
wlan0  wifi  connected  Hotspot
```

并且 `wlan0` 地址为：

```text
192.168.117.6/24
```

查询网线接口 `eth1` 的 IPv6 link-local 地址：

```bash
ip -6 -br addr show eth1
```

示例输出：

```text
eth1  UP  fe80::4ebb:47ff:fe51:6ab2/64
```

记录 `fe80::` 开头的地址，SSH 时去掉末尾 `/64`。当前 `slamibote21b5e` 实测地址为：

```text
fe80::4ebb:47ff:fe51:6ab2
```

辅助检查网线载波：

```bash
cat /sys/class/net/eth1/carrier
```

- 输出 `1`：网线物理链路已建立；
- 输出 `0`：检查网线、电脑网口和 D360 `eth1` 端口。

## 二、在 Windows 查询有线网卡编号

PowerShell 执行：

```powershell
Get-NetAdapter
```

找到状态为 `Up` 的 `Realtek PCIe GbE Family Controller`，记录它的 `ifIndex`。当前电脑实测编号为：

```text
15
```

IPv6 link-local 地址必须带出口编号。格式为：

```text
<D360的fe80地址>%<Windows有线网卡ifIndex>
```

当前完整目标地址为：

```text
fe80::4ebb:47ff:fe51:6ab2%15
```

换电脑、重装驱动或更换网卡后，`ifIndex` 可能变化，必须重新执行 `Get-NetAdapter`。

## 三、连接前验证

测试 IPv6 链路：

```powershell
ping -6 fe80::4ebb:47ff:fe51:6ab2%15
```

测试 SSH 端口：

```powershell
Test-NetConnection "fe80::4ebb:47ff:fe51:6ab2%15" -Port 22
```

应看到：

```text
TcpTestSucceeded : True
```

## 四、SSH 登录

在 PowerShell 中复制完整一行，到末尾再按回车：

```powershell
ssh -6 -F F:\slamibot_agent\.ssh-empty-config -i C:\Users\kun\.ssh\id_rsa -o IdentitiesOnly=yes -o HostKeyAlias=d360-e21b5e-eth1 -o StrictHostKeyChecking=accept-new jetson@fe80::4ebb:47ff:fe51:6ab2%15
```

成功后进入：

```text
jetson@ubuntu:~$
```

新设备尚未安装本机公钥时，会提示输入 `jetson` 用户密码；这是正常的首次交互登录。参数说明：

- `-6`：强制使用 IPv6；
- `-F F:\slamibot_agent\.ssh-empty-config`：绕过本机旧 SSH config；
- `-i C:\Users\kun\.ssh\id_rsa`：优先尝试本机私钥；目标尚未授权该公钥时会回退到密码；
- `IdentitiesOnly=yes`：只尝试指定私钥；
- `HostKeyAlias=d360-e21b5e-eth1`：为该 D360 保存独立主机密钥；
- `StrictHostKeyChecking=accept-new`：首次接受该新别名，后续密钥变化仍会拒绝。

### 为本地 AI 安装公钥（每台新 D360 一次）

本地 AI 通常需要非交互 SSH。先在 Git Bash 执行以下命令，并按提示输入一次 D360 的 `jetson` 用户密码：

```bash
ssh-copy-id -F /dev/null -i /c/Users/kun/.ssh/id_rsa.pub -o AddressFamily=inet6 -o HostKeyAlias=d360-e21b5e-eth1 -o StrictHostKeyChecking=accept-new "jetson@fe80::4ebb:47ff:fe51:6ab2%15"
```

安装后在 PowerShell 验证免密连接：

```powershell
ssh -6 -F F:\slamibot_agent\.ssh-empty-config -i C:\Users\kun\.ssh\id_rsa -o IdentitiesOnly=yes -o BatchMode=yes -o HostKeyAlias=d360-e21b5e-eth1 jetson@fe80::4ebb:47ff:fe51:6ab2%15 "hostname; whoami"
```

如果返回 `ubuntu` 和 `jetson`，本地 AI 才能稳定使用该 SSH 入口。安装公钥只修改当前用户的 `~/.ssh/authorized_keys`，不改变热点、网卡、雷达或服务配置。

## 五、更换 D360 后如何重新查询

每台 D360 的 `fe80::` 地址可能不同。更换设备后：

1. 在新 D360 桌面执行：

   ```bash
   ip -6 -br addr show eth1
   ```

2. 去掉地址末尾 `/64`；
3. 在 Windows 执行 `Get-NetAdapter`，确认有线网卡 `ifIndex`；
4. 用 `<新fe80地址>%<ifIndex>` 执行 `ping -6` 和 `Test-NetConnection`；
5. 把 SSH 命令中的地址和 `HostKeyAlias` 一起换成新设备专属值。

无法查看 D360 桌面时，可以在 Windows 查询直连邻居：

```powershell
Get-NetNeighbor -InterfaceIndex 15 -AddressFamily IPv6
```

选择状态为 `Reachable`、地址以 `fe80::` 开头的邻居。不要使用旧设备残留的 `Stale` 或 `Unreachable` 项。

## 六、常见问题

### `option requires an argument -- o`

原因是在单独的 `-o` 后按了回车。SSH 命令必须整行执行，或者每个 `-o` 后面立即跟参数。

### `Host key verification failed`

新 D360 不要复用另一台设备的 `HostKeyAlias`。为新设备使用新的别名，例如：

```text
d360-<热点SSID后缀>-eth1
```

不要为了省事全局关闭主机密钥校验，也不要盲目删除旧设备记录。

### Windows 邻居显示 `Unreachable`

依次确认：

```text
D360 eth1 carrier=1
Windows Realtek 状态为 Up
SSH 地址使用了正确的 %ifIndex
网线接的是 D360 eth1，而不是 eth0 雷达口
```

### 与本次 SSH 无关的接口和地址

- `p2p-dev-wlan0`：Wi-Fi Direct 虚拟接口，未连接是正常状态；
- `docker0`：Docker 虚拟网桥，不用于电脑直连；
- `192.168.144.87`：BOX 图传链路地址，电脑直连 D360 时不使用；
- `eth0`：雷达专用接口，不修改其 IPv4 配置。
