# Jetson 可靠 SSH 连接方式

> 当前事实：2026-08-20 15:22:32 CST，Codex 从 Windows 通过 LAN 直连成功。  
> 返回：`host=ubuntu`、`user=jetson`。  
> 本文是新会话的 SSH 操作入口；状态变化后必须按绝对时间更新。

## 首选入口：局域网

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
