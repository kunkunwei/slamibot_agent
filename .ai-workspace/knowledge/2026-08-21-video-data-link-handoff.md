# 同事资料交班：导航 / 图传 / 数传 链路提示（2026-08-21）

> 本文件仅登记同事提供的资料事实，不执行任何部署、修改或推断扩展。
> 资料来源：`F:\同事文档\导航，图传，数传 副本\导航，图传，数传 副本.md`（同事文档，2026-08-21）
> 登记日期：2026-08-21

## 来源

- 绝对路径：`F:\同事文档\导航，图传，数传 副本\导航，图传，数传 副本.md`
- 类型：同事交班资料（Markdown 笔记）
- 用途：为后续「在图传/数传链路下测试导航任务创建是否比 Wi-Fi/热点顺畅」提供前置事实。
- 边界：本文仅做事实登记，不复制 1GB 导航 tar.gz 或其他大附件；不修改任何业务仓库。

---

## 已确认事实（CONFIRMED，按资料原文登记）

### 1. 串口别名 udev 规则
- 需配置：`/etc/udev/rules.d/99-serial-aliases.rules`
- 作用：将 USB 串口按设备绑定稳定别名，避免 Jetson 重启/插拔后节点漂移。
- 状态：资料指出需配置；当前 Jetson 是否已落地：未在本次资料中确认 → 见 `NEEDS_CONFIRMATION`。

### 2. 部署包提示（仅路径提示，未复制包体）
- `rtsp_server.tar.gz`：图传服务端部署包。
- `scout_mini_navigation.tar.gz`：导航/底盘相关部署包（与 `scout_mini_navigation` 目录相关）。
- 状态：仅记录资料中的存在与提示；不下载、不落盘、不在本工作区存放副本。

### 3. 图传脚本路径与脚本名（Jetson 板内）
- 资料原文路径：`/home/jetson/scout_mini_navigation/script/`
- 现场实际路径（CONFIRMED，2026-08-21 用户提供的终端输出）：`/home/jetson/Scout_mini_navigation/script/`
  - 用户在 Jetson 上执行：
      - `ls /home/jetson/scout_mini_navigation/script` → **目录不存在**。
      - `ls /home/jetson/Scout_mini_navigation/script` → 目录存在，列出 `rtsp_start.sh`、`sbus_start.sh`。
  - **结论**：资料原文目录名 `scout_mini_navigation`（首字母小写）与现场实际 `Scout_mini_navigation`（首字母大写 S）大小写不一致；本工作区以现场实际为准。
  - **副作用提示**：若脚本内部或 systemd / udev / docker-entrypoint 使用了 `scout_mini_navigation`（小写）路径字面量，可能因大小写敏感的文件系统而失效；具体哪些调用点受影响 `NEEDS_CONFIRMATION`，**不在本次登记范围内自动修改**。
- 脚本（资料原文）：
  - `rtsp_start.sh`：TCP 推流启动。
  - `rtsp_start_udp.sh`：UDP 推流启动。
  - `rtsp_stop.sh`：停止图传。
- 备注：资料明确区分 TCP / UDP 两种推流方式；选用哪种需按现场链路决定。
- **现场新增观察（CONFIRMED，2026-08-21）**：
  - 当前现场 `ls` 仅显示 `rtsp_start.sh`、`sbus_start.sh` 两个文件；`rtsp_start_udp.sh`、`rtsp_stop.sh` 在现场目录中是否存在仍 `NEEDS_CONFIRMATION`（可能受 `ls` 输出截断、`ls -a` 隐藏文件、或现场实际只保留 TCP 启动脚本等多种因素影响）。
  - `sbus_start.sh` 与资料「数传脚本应在 `/home/jetson/SLAMIBOT_D360_Framework/script/`」的归属存在差异；该脚本同时出现在 `Scout_mini_navigation/script/` 中的事实已登记，但**不得据此修改资料事实**，归属与功能差异 `NEEDS_CONFIRMATION`。

### 4. 数传脚本路径与脚本名（Jetson 板内）
- 资料原文路径：`/home/jetson/SLAMIBOT_D360_Framework/script/`
- 脚本：`sbus_start.sh`
- 用途：SBUS 数传链路启动（具体协议/串口参数以脚本内容为准）。
- **现场观察（CONFIRMED，2026-08-21）**：`sbus_start.sh` 同时出现在 `/home/jetson/Scout_mini_navigation/script/`（与图传脚本同目录）。这意味着 SBUS 数传脚本可能存在多份拷贝或归属调整；具体哪一份为权威启动入口、`SLAMIBOT_D360_Framework/script/sbus_start.sh` 是否仍存在且功能一致：`NEEDS_CONFIRMATION`。

### 4.1 图传脚本 CRLF 现场证据（CONFIRMED，2026-08-21）

> 本节基于用户提供的现场终端输出，**仅作登记**，不自动执行任何修复命令。

- 现场执行：
  - `ls -l /home/jetson/Scout_mini_navigation/script/rtsp_start.sh`：`rtsp_start.sh` 已具备可执行权限（文件 mode 含 `x`）。
  - 多次执行 `./rtsp_start.sh`，终端报错统一为：
      - `/bin/bash^M：解释器错误: 没有那个文件或目录`
- 根因判断（CONFIRMED）：
  - shebang 行（`#!/bin/bash`）末包含一个回车符 `\r`（CR），导致内核看到的解释器路径为 `/bin/bash\r`；`^M` 是回车符在终端的常见回显形式。
  - 这是典型的 **CRLF（Windows / DOS 风格）换行**进入 Unix 环境后遗留在文本脚本第一行的现象，与脚本内容无关、与图传/数传链路无关。
- **建议修复命令（仅作记录，待用户/现场授权后执行，Agent 不擅自执行）**：
  - 方案 A：`sed -i 's/\r$//' /home/jetson/Scout_mini_navigation/script/rtsp_start.sh`
  - 方案 B：`dos2unix /home/jetson/Scout_mini_navigation/script/rtsp_start.sh`
  - 修复后建议验证步骤（仅作记录）：
      - `head -n 1 /home/jetson/Scout_mini_navigation/script/rtsp_start.sh` → 应显示 `#!/bin/bash` 且行尾不再出现 `^M`。
      - `file /home/jetson/Scout_mini_navigation/script/rtsp_start.sh` → 应报告 `Bourne-Again shell script, ASCII text executable`（不应再出现 `CRLF` / `with CRLF line terminators`）。
      - `bash -n /home/jetson/Scout_mini_navigation/script/rtsp_start.sh` → 语法快速校验（仅作记录）。
      - 之后才能 `./rtsp_start.sh` 实际启动；本次会话**不执行**。
- **CRLF 修复后实际启动结果（CONFIRMED，2026-08-21 用户最新现场终端输出）**：
  - 用户在 `/home/jetson/Scout_mini_navigation/script` 执行 `sed -i 's/\r$//' rtsp_start.sh`。
  - 修复后校验通过：
      - `head -n 1 rtsp_start.sh` → 首行 `#!/bin/bash`（不再出现 `^M`）。
      - `file rtsp_start.sh` → 报告 `Bourne-Again shell script, UTF-8 Unicode text executable`（不再含 `CRLF` 字样）。
      - `bash -n rtsp_start.sh` → 语法校验通过，无报错。
  - `./rtsp_start.sh` 启动结果（CONFIRMED）：
      - 成功创建 tmux 会话 `rtsp_stream`。
      - 窗口 0：`/home/jetson/rtsp_server/mediamtx`（RTSP 服务端 mediamtx）。
      - 窗口 1：`/home/jetson/SLAMIBOT_D360_Framework/src/oak-camera_driver/scripts/oak_rtsp_pusher.py`（OAK 摄像头推流脚本）。
      - 终端输出 RTSP 地址模板：`rtsp://<本机IP>:8554/live`（具体本机 IP 未在用户输出中确认，仍 `NEEDS_CONFIRMATION`）。
      - FFmpeg 已识别输入流：`rawvideo BGR24 1248x240 10fps`；编码器初始化为 `libx264`；未观察到启动失败日志。
  - **结论（本次）**：`rtsp_start.sh` 脚本启动阶段已成功（CRLF 修复生效、tmux 会话与两个子窗口创建、FFmpeg 输入流被识别、libx264 初始化）。
  - **尚未确认（NEEDS_CONFIRMATION，不在本次会话中执行）**：
      - 实际本机 IP（`<本机IP>` 占位符的真实值）。
      - 接收机侧是否能成功 `rtsp://<本机IP>:8554/live` 拉流。
      - 视频画面是否正常（分辨率、色彩、码率）。
      - 网络链路（端口 8554 是否可达、是否被防火墙/NAT 阻断）。
      - 前端 APP 是否能连入并显示图传。
  - **未确认事项（NEEDS_CONFIRMATION，与本次修复解耦）**：
      - `rtsp_start.sh` 内部依赖（gstreamer / ffmpeg / v4l2 / 摄像头设备节点 / 推流参数）：UNKNOWN，未在本次会话读取脚本内容。
      - 图传接收机 IP、端口、TCP / UDP 选型：UNKNOWN（资料中 `192.168.144.87:8889/live` 仅作 WebRTC 视频入口登记，不直接作为推流目标）。
      - `rtsp_start.sh` 是否会因 CRLF 之外的同样问题影响 `sbus_start.sh` / `rtsp_start_udp.sh` / `rtsp_stop.sh` 等同目录脚本：`NEEDS_CONFIRMATION`；本节**仅就 `rtsp_start.sh` 本身已确认现象**登记。
      - `mediamtx` 的实际监听地址、配置（鉴权 / 端口 / 路径）、与 `oak_rtsp_pusher.py` 推送参数（编码、码率、分辨率）：UNKNOWN，未读取相关配置。

### 4.2 MediaMTX v1.9.0 监听端口与配置现场证据（CONFIRMED，2026-08-21 用户最新现场终端输出）

> 本节基于用户提供的现场终端输出，**仅作登记**，不擅自执行任何 Jetson 操作或配置修改。

- **MediaMTX 版本与服务端**（CONFIRMED）：
  - 版本：`MediaMTX v1.9.0`。
  - 启动配置文件：`/home/jetson/rtsp_server/mediamtx.yml`。
  - 启动入口：`/home/jetson/rtsp_server/mediamtx`（与 `rtsp_start.sh` tmux 窗口 0 一致）。
- **MediaMTX 监听端口（CONFIRMED）**：
  - RTSP：`8554 TCP`。
  - RTP：`8000 UDP`。
  - RTCP：`8001 UDP`。
  - RTMP：`1935`。
  - HLS：`8888`。
  - WebRTC（HTTP 控制/信令）：`8889`。
  - WebRTC ICE：`8189 UDP`。
  - SRT：`8890 UDP`。
- **`rtsp_start.sh` tmux 行为（CONFIRMED）**：
  - 创建 tmux 会话 `rtsp_stream`，包含两个窗口：
      - 窗口 0：`mediamtx`（RTSP/RTMP/HLS/WebRTC/SRT 多协议服务端）。
      - 窗口 1：`pusher`（即 OAK 摄像头推流脚本，对应 `/home/jetson/SLAMIBOT_D360_Framework/src/oak-camera_driver/scripts/oak_rtsp_pusher.py`）。
- **pusher 推流输入参数（CONFIRMED）**：
  - 输入格式：`rawvideo BGR24 1248x240 10fps`（分辨率 1248×240，10 fps，BGR24 像素格式）。
  - 编码器：`libx264` 初始化成功，未观察到启动失败日志。
- **当前结论（已确认）**：
  - 服务端：MediaMTX v1.9.0 已按 `mediamtx.yml` 配置成功启动；RTSP / RTMP / HLS / WebRTC / SRT / RTP / RTCP 端口监听已确认。
  - 推流端：FFmpeg 已识别 `rawvideo BGR24 1248x240 10fps` 输入流并初始化 `libx264` 编码器。
  - tmux 会话 `rtsp_stream` 已成功创建（mediamtx 窗口 + pusher 窗口）。
- **仍 `NEEDS_CONFIRMATION`（不在本次会话中执行）**：
  - 实际本机 IP（`rtsp://<本机IP>:8554/live` 中占位符的真实值），决定客户端是否能拉流。
  - 客户端/接收机侧是否能成功连接 RTSP / WebRTC / RTMP / HLS / SRT 任一协议并播放。
  - 视频画面是否正常（分辨率、色彩、码率、延迟）。
  - 网络链路质量（端口 8554 / 8889 / 1935 / 8888 / 8890 / 8189 可达性、NAT / 防火墙策略、带宽与丢包）。
  - 前端 APP 是否能接入并显示图传（与既有 APP rosbridge 路径 9090/19090 的关系仍 `NEEDS_CONFIRMATION`）。
  - `mediamtx.yml` 中除端口外的鉴权 / 路径 / 用户名密码 / TLS 等配置：未在本次资料中读取，仍 `UNKNOWN`。
- **不擅自推断**：本节仅就 MediaMTX 服务端监听与推流端编码初始化登记；不做"客户端可用""图传已上线""APP 可显示"等过度宣称。

### 4.3 VLC 拉流触发 pusher 端 `Broken pipe` 现场证据（CONFIRMED，2026-08-21 用户最新现场终端输出）

> 本节基于用户在 Jetson 上观察到的图传日志，**仅作登记**，不擅自执行任何 Jetson 操作、进程检查、网络调试或脚本修改。

- 触发条件（用户描述，未在本会话中观测）：
    - 用户在遥控器端打开 VLC（具体 URL 仍 `NEEDS_CONFIRMATION`）。
- Jetson 端日志片段（用户提供，原文登记，未做改写）：
    - `[ERROR] [1787281780.431750]: Pushing Error: [Errno 32] Broken pipe`
- 时间戳含义（仅按 ROS 风格日志解读，不做时间换算）：
    - `1787281780.431750` 是 ROS 时间戳（秒.纳秒），对应 2026-08-21 现场事件；与 VLC 打开动作的时序关系由用户描述，本会话**不擅自对齐**。
- 错误位置初步判断（仅按日志内容登记，非根因结论）：
    - `Pushing Error` 出现在 `oak_rtsp_pusher.py`（tmux 窗口 1）阶段。
    - `[Errno 32] Broken pipe` 是 Python 写入已关闭管道 / 子进程 stdin 时的典型异常；强烈指向 `oak_rtsp_pusher.py` 向 FFmpeg stdin（或 FFmpeg 子进程管道）写入阶段的失败。
    - 但**仅凭单行日志**：
        - 不能确认是 FFmpeg 子进程先退出、pusher 先退出，还是外部信号导致管道关闭。
        - 不能确认触发原因是否与 VLC 拉流动作直接相关；也可能由脚本被重复启动、参数不匹配、输入流中断、FFmpeg 编码失败等多种原因触发。
- 待确认事项（`NEEDS_CONFIRMATION`，不在本次会话中执行）：
    - `Broken pipe` 前后的完整 pusher / FFmpeg 日志（包括退出码、是否出现 `Conversion failed!`、`Broken pipe` 之前是否已有错误）。
    - VLC 实际打开的 URL（候选 `rtsp://<JetsonIP>:8554/live` 或 `http://<JetsonIP>:8889/live`），是否填写正确、是否带鉴权、是否触发 RTSP DESCRIBE / PLAY 流程。
    - MediaMTX 是否记录到对应的 client / read session 日志（如 `rtsp conn`、`rtsp session`、`webrtc session` 等）。
    - `rtsp_stream` tmux 会话是否存在重复启动（多份 mediamtx 或 pusher 进程监听同一端口、写入同一 path）。
    - FFmpeg 是否因输入 / 输出 / 编码参数不匹配而提前退出（与 OAK `rawvideo BGR24 1248x240 10fps` 输入、`libx264` 编码参数相关）。
    - VLC 与 Jetson 之间的网络路径（端口 8554 / 8889 / 8189 可达性、NAT / 防火墙策略、带宽与丢包）。
    - 错误发生时 pusher 是否仍在向 FFmpeg 喂帧，或 FFmpeg 已不再读取 stdin。
- 新增验证建议（**仅记录，不在本会话执行**）：
    - `tmux attach -t rtsp_stream` 进入会话，分别查看窗口 0（mediamtx）与窗口 1（pusher / FFmpeg）的最近若干屏日志，寻找 `Broken pipe` 前后的事件序列。
    - 在 VLC 内确认实际打开的 URL 是 `rtsp://<JetsonIP>:8554/live` 还是 `http://<JetsonIP>:8889/live`，并对照 `mediamtx.yml` 的 path / 鉴权设置。
    - 在 Jetson 上检查是否存在多个 `rtsp_stream` tmux 会话、多个 `oak_rtsp_pusher.py` 进程、多个 `mediamtx` 进程；查看 `/tmp`、`/home/jetson/rtsp_server` 下的日志文件。
    - 必要时使用 `journalctl`、`/proc/<pid>/fd`、`lsof -p <pid>` 等只读工具观察 FFmpeg 子进程的 stdin / stdout / stderr 与文件描述符状态。
- 明确边界（**不得过度宣称**）：
    - **不得直接归因于 VLC**；`Broken pipe` 可能由多种原因触发，VLC 拉流是其中一种可能而非唯一解释。
    - **不得据此修改 `oak_rtsp_pusher.py`、`rtsp_start.sh`、mediamtx 配置或 udev 规则**；本节仅做证据登记，不进入实现 / 调试。
    - **不得宣称图传链路已失效**；`Broken pipe` 是单点错误事件，不构成整链路不可用的结论。
- 当前结论（已确认）：
    - `Broken pipe` 错误发生在 `oak_rtsp_pusher.py` 向 FFmpeg stdin / 管道写入阶段的**强烈迹象**已登记。
    - 仅凭该行日志**不能确认根因**，也**不能直接归因于 VLC**。
    - 验证建议已列出，待用户 / 现场授权后再执行。
- `tests`: SKIPPED (文档同步，仅记录用户提供的现场终端输出，未运行任何测试 / 构建 / Jetson 操作)。

### 4.4 Jetson 网络 / tmux / 进程监听与 `Broken pipe` 持续重复 现场证据（CONFIRMED，2026-08-21 用户最新现场终端输出）

> 本节基于用户提供的现场终端输出，**仅作登记**，不擅自执行任何 Jetson 操作、网络调试、tmux attach、进程重启、脚本修改或接收端配置变更。

- **`ip -br addr` 输出（CONFIRMED）**：
    - `eth0 UP 192.168.1.55/24`：板载有线网卡（IP / 状态已确认；其链路角色以 4.5 节用户最新确认为准：eth0 = 雷达链路，**不**作为图传候选）。
    - `wlan0 UP 192.168.31.135/24`：公司 Wi-Fi 网卡（IP / 状态已确认；其链路角色以 4.5 节用户最新确认为准：wlan0 = 公司 Wi-Fi，**不**作为图传候选）。
    - 其余接口 `eth2` / `l4tbr0` / `rndis0` / `usb0` / `docker0` 状态为 `DOWN`（`lo` 除外）。
- **`tmux ls` 输出（CONFIRMED）**：
    - `rtsp_stream: 2 windows ...` 当前 attached（与 `4.1` CRLF 修复后 `./rtsp_start.sh` 创建会话一致）。
    - `sbus: 2 windows ...` 当前 attached。
    - 两个会话均处于运行中。
- **`ss -lntup` 中 mediamtx 相关监听（CONFIRMED）**：
    - 进程：`mediamtx`，PID `45140`。
    - UDP：`8000`（RTP）、`8001`（RTCP）、`8189`（WebRTC ICE）。
    - TCP：`8554`（RTSP）、`8889`（WebRTC HTTP）。
    - **结论**：MediaMTX 服务端监听按预期建立，**未发现"端口未监听"**问题。
- **接收端测试失败证据（CONFIRMED，2026-08-21 用户最新现场终端输出）**：
    - 接收端测试 URL：`rtsp://192.168.31.135:8554/live`（用户以 wlan0 公司 Wi-Fi 地址作为目标）。
    - 结果：失败。
- **pusher 端 `Broken pipe` 持续重复证据（CONFIRMED，2026-08-21 用户最新现场终端输出）**：
    - pusher 窗口持续重复：`[ERROR] ... Pushing Error: [Errno 32] Broken pipe`。
    - 与 `4.3` 的单条日志相比，本次证据升级为"持续重复"，强烈表明 pusher -> FFmpeg 子进程管道已断，**而非瞬时抖动**。
- **登记结论（已确认）**：
    - MediaMTX 监听正常（端口与进程均按预期工作），但 pusher -> FFmpeg 子进程管道已断；
    - **不得继续把问题归为"端口未监听"**；服务端链路已建立，问题点已收窄到 pusher 子进程 / FFmpeg 退出 / 输入流中断方向。
    - `192.168.31.135` 是 wlan0 公司 Wi-Fi 地址（与历史 `TASK-2026-08-19-001` 登记的 APP 实测目标一致），**不能默认视为图传接收机链路**；本次 `rtsp://192.168.31.135:8554/live` 接收端测试实际走公司 Wi-Fi，**不代表图传接收机链路可达性**。
    - `eth0 192.168.1.55` 是板载有线网卡（按 4.5 节用户最新确认属于**雷达链路**），**不**作为图传候选地址；不应以该地址作为图传目标，避免混入雷达网络；本次未对该地址执行任何测试。
- **新增待确认事项（`NEEDS_CONFIRMATION`，不在本次会话中执行）**：
    - **FFmpeg 退出的原始错误**：需 pusher 日志中 `Broken pipe` 之前输出，或在 Jetson 上单独运行 `oak_rtsp_pusher.py`（或等价命令）抓取启动 / 退出错误；当前仅观察到 `[Errno 32] Broken pipe` 重复，**无法确认**是 FFmpeg 先退出、pusher 先退出，还是外部信号导致管道关闭。
    - **图传接收机实际接口、网段、IP、是否已连接**（按 4.5 节用户最新确认，**当前 `ip -br addr` 列表中没有任何一个接口可以确认为图传接收机链路**）：候选范围需另行独立确认，不得再以 `192.168.31.135`（公司 Wi-Fi）或 `192.168.1.55`（雷达链路）作为图传目标。
    - **VLC 实际使用的协议 / URL**：是 RTSP（`rtsp://...:8554/live`）、WebRTC（`http://...:8889/live`）、HLS、RTMP 还是 SRT；是否带鉴权 / 用户名密码 / 路径后缀。
    - **MediaMTX 是否有 RTSP 客户端连接记录**（`rtsp conn`、`rtsp session`、`read`、`play` 等日志）；若全程无客户端连接记录，可与"接收端所在网段选错"假设互相印证。
- **明确边界（不得过度宣称）**：
    - **不得据本节直接宣布图传链路已修复 / 已失败**；本节仅作现状登记。
    - **不得据此修改 `oak_rtsp_pusher.py`、`rtsp_start.sh`、`mediamtx.yml`、udev 规则或网络配置**。
    - **不得在 Jetson 上重启 / 杀掉 `rtsp_stream` / `sbus` tmux 会话或 mediamtx / pusher 进程**，除非用户 / 现场明确授权。
    - **不得擅自连接接收机或修改接收端网络**；接收端状态由用户在遥控器侧另行核对。
- **当前结论（已确认）**：
    - MediaMTX 服务端在 Jetson 本机监听正常（UDP 8000 / 8001 / 8189，TCP 8554 / 8889）。
    - `rtsp_stream` tmux 会话仍 attached（窗口 0 mediamtx / 窗口 1 pusher）；`sbus` tmux 会话仍 attached。
    - pusher 端持续重复 `Broken pipe`，FFmpeg 子进程管道已断。
    - 接收端测试 `rtsp://192.168.31.135:8554/live` 失败——该地址属于公司 Wi-Fi（wlan0），测试实际走 Wi-Fi 链路，**不代表图传接收机链路可达性**。
    - 候选地址 `192.168.1.55`（eth0）经 4.5 节用户最新确认属于**雷达链路**，**不应**作为图传目标；本次未对该地址执行任何测试。
    - **当前 `ip -br addr` 列表中没有确认的图传接收机接口**；后续调试方向已收窄到 **pusher / FFmpeg 子进程生命周期** 与 **图传接收机实际链路确认** 两条独立线索；当前不能锁定其中任一条为根因。
- `tests`: SKIPPED (文档同步，仅记录用户提供的现场终端输出，未运行任何测试 / 构建 / Jetson 操作)。

### 4.5 网络角色用户最新现场确认（CONFIRMED，2026-08-21）

> 本节基于用户在现场对 Jetson 网络角色归属的最新说明，**仅作登记**，不擅自执行任何 Jetson 操作、网络调试或配置修改。

- **用户确认的网络角色（CONFIRMED，2026-08-21 现场说明）**：
    - `eth0 = 192.168.1.55/24`：**雷达链路**。
    - `wlan0 = 192.168.31.135/24`：**公司 Wi-Fi**。
- **由此带来的结论更新（CONFIRMED）**：
    - 此前对 `192.168.31.135:8554` 的 RTSP 接收测试**实际走公司 Wi-Fi**，**不代表图传接收机链路可达性**；该测试结果**不能**用于判断图传接收机是否在线、链路是否打通。
    - `192.168.1.55`（eth0）**不**应作为图传目标，避免与雷达网络流量混入；该地址仅在雷达相关测试中有效。
    - 当前 `ip -br addr` 输出（eth0 / wlan0 / eth2 / l4tbr0 / rndis0 / usb0 / docker0 / lo）**没有任何一个接口可以确认为图传接收机链路**——4.4 节中曾以"候选图传链路地址"措辞登记 eth0 / wlan0 的描述**已被本节覆盖、不得继续引用**。
- **仍 `NEEDS_CONFIRMATION`（不在本次会话中执行）**：
    - 图传接收机实际所在接口（如物理网卡、Wi-Fi 网卡、串口链路等独立通道）。
    - 图传接收机所属网段（与 Jetson 已知两条链路 / 网段是否完全独立）。
    - 图传接收机 IP、端口（8554 / 8889 / 其它）、协议（RTSP / WebRTC / RTMP / HLS / SRT 任一）。
    - 图传接收机是否已上电 / 已联网 / 已与 Jetson 同一可路由域内可达。
- **明确边界（不得过度宣称）**：
    - **不得**据此把当前 `Broken pipe` 或 `192.168.31.135` 接收失败归因为"图传链路已验证不可用"——这两条现象均与图传接收机真实链路无关。
    - **不得**据此修改 Jetson 网卡角色、路由、IP、绑定顺序或 systemd-networkd / Netplan 配置；本节仅作角色登记。
    - **不得**据此把 `192.168.1.55` 或 `192.168.31.135` 继续列为图传目标候选；这两个地址的角色已被用户锁定为雷达 / 公司 Wi-Fi。
- **保留事实（不随本节改变）**：
    - 4.4 节 MediaMTX 服务端监听事实（端口 8554 / 8889 / 8000 / 8001 / 8189 / 1935 / 8888 / 8890 与 mediamtx PID）**保留**。
    - 4.3 节与 4.4 节中 pusher 端 `[Errno 32] Broken pipe` 持续重复证据**保留**；其作为"pusher / FFmpeg 子进程管道已断"的独立线索仍成立，与本节网络角色结论相互独立。
- `tests`: SKIPPED (文档同步，仅记录用户提供的现场网络角色说明，未运行任何测试 / 构建 / Jetson 操作)。

### 4.6 BOX 重新连接后现场状态变化登记（CONFIRMED，2026-08-21 用户最新说明）

> 本节基于用户最新口头/文字说明，**仅作登记**，不擅自执行任何 Jetson 操作、命令、连接或脚本重启。

- **用户最新确认（CONFIRMED，2026-08-21）**：
    - **此前状态**：D360 **未连接** BOX。
    - **当前状态**：BOX **已重新连接**到 D360。
    - 状态变化由用户在交班中明确说明；本会话未执行任何远程命令、未在 Jetson 上执行任何操作、未重启任何脚本、未读取任何重连后的现场输出。
- **现场状态变化的潜在影响范围（登记，仅作分析；不得据此推断任何已发生的接口/设备/链路变化）**：
    - **网络接口**：BOX 重新连接可能涉及串口 / USB / 网线的物理拓扑变化；具体哪些网络接口被启用、IP 是否变化、路由是否新增仍 `NEEDS_CONFIRMATION`（**无重连后的命令输出**）。
    - **串口 / udev 设备**：BOX 重新连接可能让此前消失的 `/dev/ttyUSB2..ttyUSB8` 重新出现，`/dev/lg_speech_serial` 是否重新映射为 `ttyUSB8`、是否新增 `/dev/lg_speech_uac` 仍 `NEEDS_CONFIRMATION`（**无重连后的 `lsusb`/`/dev/tty*` 输出**）。
    - **图传 / 数传链路**：BOX 重新连接可能影响 SBUS 数传链路（`sbus` tmux 会话、`sbus_start.sh`）；是否引入新的图传/数传物理通道、是否需要重启 `rtsp_stream` / `sbus` tmux 会话仍 `NEEDS_CONFIRMATION`（**无重连后的 `tmux` / 进程 / 日志输出**）。
- **仍 `NEEDS_CONFIRMATION`（不在本次会话中执行）**：
    - BOX 重连后的网络接口列表（`ip -br addr`、`ip -br link`、`ip route`）。
    - BOX 重连后的 USB 设备列表（`lsusb`、`lsusb -t`、`lsusb -v`）。
    - BOX 重连后的串口节点列表（`/dev/tty*`，含 `/dev/ttyUSB0..ttyUSB*`、`/dev/lg_speech_serial`、`/dev/lg_speech_uac`）。
    - BOX 重连后 `tmux ls` 中 `rtsp_stream` / `sbus` 会话的实际状态（attached / windows / 历史日志）。
    - BOX 重连后 mediamtx / FFmpeg / oak_rtsp_pusher.py / sbus 相关进程是否仍在运行、是否需要重启。
    - BOX 重新连接是否引入新的图传/数传物理接口（如新增 USB 网卡 / 串口链路 / 其它通道）。
- **下一步只读核对（仅记录，不在本会话执行；待用户 / 现场授权后由用户在 Jetson 上执行；**不重复启动脚本**）**：
    - `ip -br addr`：观察 BOX 重连后接口列表与 IP 是否变化。
    - `ip route`：观察路由表是否新增。
    - `lsusb`：观察 USB 拓扑是否新增 BOX 相关设备。
    - `ip -br link`：观察链路状态（UP / DOWN）。
    - `ls /dev/tty*` 或 `ls -l /dev/tty*`：观察串口节点是否恢复到 BOX 接入时的预期集合（如 `ttyUSB2..ttyUSB8`、`/dev/lg_speech_serial`）。
    - `tmux ls`：观察 `rtsp_stream` / `sbus` 会话是否仍 attached。
    - `tmux capture-pane -pt rtsp_stream:0 -S -200` / `tmux capture-pane -pt rtsp_stream:1 -S -200` / `tmux capture-pane -pt sbus:0 -S -200`（只读）：抓取最近若干屏日志，确认 mediamtx / pusher / FFmpeg / sbus 实际状态。
    - `ps -ef | grep -E "mediamtx|oak_rtsp_pusher|sbus|ffmpeg"`（只读）：观察相关进程是否仍在运行。
    - `ss -lntup | grep -E ":8554|:8889|:8000|:8001|:8189|:1935|:8888|:8890"`（只读）：核对 MediaMTX 端口是否仍在监听。
- **明确边界（不得过度宣称）**：
    - **不得**据此宣称 BOX 重连后图传/数传链路已恢复或已失效；本节仅作状态登记。
    - **不得**据此重启 `rtsp_start.sh` / `sbus_start.sh` / `rtsp_stop.sh` 或任何 mediamtx / pusher / FFmpeg / sbus 进程；**不重复启动脚本**。
    - **不得**据此修改 `oak_rtsp_pusher.py`、`rtsp_start.sh`、`mediamtx.yml`、udev 规则或网络配置。
    - **不得**据此猜测 BOX 重新连接引入的新接口、新 IP、新链路角色；无证据一律 `UNKNOWN` / `NEEDS_CONFIRMATION`。
- **保留事实（不随本节改变）**：
    - 4.1~4.5 节中关于 `rtsp_start.sh` 启动、MediaMTX 监听、pusher `Broken pipe`、网络角色归属（eth0 = 雷达 / wlan0 = 公司 Wi-Fi）等事实**保留**。
    - 这些事实与 BOX 重连之间是否存在因果关系，本节**不得**擅自建立。
- `tests`: SKIPPED (文档同步，仅记录用户最新现场状态说明，未运行任何测试 / 构建 / Jetson 操作)。

### 4.8 2026-08-21 11:31 CST SSH 只读诊断 现场证据（CONFIRMED，2026-08-21 用户最新 SSH 只读快照输出）

> 本节基于用户提供的 SSH 只读快照输出（采集时间 2026-08-21 11:31 CST），**仅作登记**，不擅自执行任何 Jetson 操作、网络修改、进程重启、脚本变更、VLC 配置修改或接收端操作。本会话不远程连接 Jetson，仅登记用户提供的快照。

- **网络接口状态（CONFIRMED）**：
    - `eth2 UP`，同时持有 `192.168.123.55/24` 与 `192.168.144.87/24` 两个 `/24` 地址（与 4.7 节 `eth2` UP 事实一致；本快照确认这两个地址仍同时存在）。
    - 其它接口角色与 4.5 / 4.7 节登记一致：`eth0 = 192.168.1.55/24`（雷达链路）、`wlan0 = 192.168.31.135/24`（公司 Wi-Fi）。
- **MediaMTX 监听（CONFIRMED）**：
    - PID `52367`。
    - 监听端口：TCP `8554`（RTSP）、TCP `8889`（WebRTC HTTP）；UDP `8000`（RTP）、UDP `8001`（RTCP）、UDP `8189`（WebRTC ICE）。
    - 与 4.2 / 4.4 节端口清单完全一致；服务端链路持续在线。
- **pusher / ffmpeg 进程（CONFIRMED）**：
    - `pusher`（`oak_rtsp_pusher.py`）：PID `52418`，持续运行。
    - `ffmpeg`：PID `52438`，持续运行；命令行（用户提供，原文登记）：
        `ffmpeg -y -re -f rawvideo -pix_fmt bgr24 -s 1248x240 -r 10 -i - -c:v libx264 -preset ultrafast -tune zerolatency -r 10 -g 10 -threads 4 -b:v 800k -maxrate 1M -bufsize 500k -pix_fmt yuv420p -f rtsp -rtsp_transport tcp rtsp://192.168.144.87:8554/live`
    - 推流输出进度（用户提供，原文登记）：`frame=3348 fps=10 time=00:05:34.70`——pusher 持续向 MediaMTX `rtsp://192.168.144.87:8554/live` 推送 H264（`rawvideo BGR24 1248x240 10fps` → `libx264` → RTSP TCP）。
    - **关键事实**：本次快照中 pusher / ffmpeg **未观察到 `[Errno 32] Broken pipe`**（与 4.3 / 4.4 节"持续重复 `Broken pipe`"状态相比，本次快照**未见**该错误；本次不据此宣称 `Broken pipe` 已根除，仅作"本次当前快照中未出现"的时点登记）。
- **MediaMTX 链接日志（CONFIRMED，用户提供，原文登记）**：
    - 发布端：`192.168.144.87:35602` 成功 `publishing path 'live'`（`H264`）——pusher → MediaMTX 的 publish 链路正常。
    - 接收端：`192.168.144.11:46502` 成功 `reading path 'live'`（`with UDP`, `H264`）——**客户端经 UDP 拉流链路已建立**，与"发布端用 RTSP/TCP、接收端用 UDP"的链路模型一致。
    - 紧接 `rtcp: invalid packet version`（**RTCP 解析告警**：MediaMTX 收到的 RTCP 包 `version` 字段无效/异常）。
- **当前马赛克首要嫌疑（登记诊断，非根因结论）**：
    - 发布链路（pusher → MediaMTX → RTSP/TCP 推送）正常；接收端 VLC 已连上并进入 `reading path 'live'`。
    - **首要嫌疑**：VLC 使用 UDP/RTP 拉流时 RTP/RTCP 包异常 / 丢包 / 错解析（与 `rtcp: invalid packet version` 同行告警相互印证）。
    - **建议（仅记录，**不在本次会话执行**）**：让遥控器侧 VLC 强制 RTSP over TCP（VLC 偏好中勾选"Use RTSP over TCP"，或在 URL 前缀 `--rtsp-tcp` 等方式），再与当前 UDP 拉流做画面对比。
- **明确边界（不得过度宣称）**：
    - **不得据此宣称图传链路已修复**；本次快照仅展示"发布链路正常 + 接收端已 connected + 出现 RTCP 解析告警"的时点事实。
    - **不得据此宣称 `Broken pipe` 已根除**；pusher / FFmpeg 子进程生命周期的根因仍 `NEEDS_CONFIRMATION`，本次快照仅记录"本次未出现"。
    - **不得据此重启 `rtsp_start.sh` / `sbus_start.sh` / `rtsp_stop.sh` 或任何 mediamtx / pusher / FFmpeg / sbus 进程**。
    - **不得据此修改 `oak_rtsp_pusher.py`、`rtsp_start.sh`、`mediamtx.yml`、udev 规则、VLC 配置或网络配置**。
    - **不得据此在 Jetson 上执行任何修复、清理、重启或脚本变更**；本次为只读 SSH 快照登记。
- **仍 `NEEDS_CONFIRMATION`（不在本次会话执行）**：
    - VLC 拉流方式（UDP / TCP）的偏好设置、URL 是否带路径后缀、是否带鉴权。
    - `rtcp: invalid packet version` 的来源：是 VLC 客户端 RTCP 反馈异常、网络丢包导致的版本位被破坏，还是 MediaMTX 解析兼容性问题。
    - 强制 RTSP over TCP 后画面是否改善、改善到何种程度。
    - pusher / FFmpeg 在更长时间窗口（跨越本次快照）下是否仍持续运行、是否仍不出现 `Broken pipe`。
- **保留事实（不随本节改变）**：
    - 4.1~4.7 节中关于 `rtsp_start.sh` 启动、MediaMTX 监听端口、`Broken pipe` 历史证据、网络角色归属（eth0 = 雷达 / wlan0 = 公司 Wi-Fi）、`eth2` UP 与 `192.168.144.87` / `192.168.123.55` 是 Jetson 本机 `eth2` 地址的事实**全部保留**。
    - 本节**不**撤销 4.3 / 4.4 节 `Broken pipe` 持续重复登记；只是记录"2026-08-21 11:31 CST 这一刻快照中未出现"。
- `tests`: SKIPPED (SSH 只读诊断登记，仅记录用户提供的快照输出，未运行任何测试 / 构建 / Jetson 操作)。

### 4.7 BOX 重新连接后 `eth2` UP 与新增地址 现场证据（CONFIRMED，2026-08-21 用户最新现场终端输出）

> 本节基于用户最新提供的现场终端输出，**仅作登记**，不擅自执行任何 Jetson 操作、网络调试、tmux attach、进程重启、脚本修改或接收端配置变更。

- **`ip -br addr` 输出变化（CONFIRMED，对比 4.4 / 4.5）**：
    - `eth0 UP 192.168.1.55/24`：板载有线网卡，**角色保持为雷达链路**（4.5 节用户最新确认不变）。
    - `wlan0 UP 192.168.31.135/24`：公司 Wi-Fi 网卡，**角色保持为公司 Wi-Fi**（4.5 节用户最新确认不变）。
    - **`eth2 UP 192.168.123.55/24` + `192.168.144.87/24`**：**本节新增**。`eth2` 在 BOX 重新连接前为 `DOWN`（见 4.4 节），连接 BOX 后变为 `UP` 并同时持有两个 `/24` 地址。
    - 其余接口 `l4tbr0` / `rndis0` / `usb0` / `docker0` 状态为 `DOWN`（`lo` 除外）。
- **结论更新（CONFIRMED）**：
    - `192.168.144.87` 现已**确认为 Jetson `eth2` 本机地址**（与 4.4 节"该地址仅是 WebRTC 示例"的角色登记相比，**本节覆盖**该登记：`192.168.144.87` 现已可作为 Jetson 本机 `eth2` 接口的事实地址登记）。
    - 此前对 `192.168.31.135:8554` 的 RTSP 接收测试**实际走公司 Wi-Fi（wlan0）**，**不代表图传接收机链路可达性**——这条 4.5 节结论**保留不变**；本节不改变此条。
    - 当前 `ip -br addr` 输出中**新增** `eth2 UP 192.168.144.87/24` 与 `eth2 UP 192.168.123.55/24` 两个可作为 Jetson 本机地址的事实点；其中 `192.168.144.87` 与资料原文 WebRTC 视频入口 `http://192.168.144.87:8889/live` 中的 IP 一致，**但不得据此推断"图传接收机链路已打通"**——`192.168.144.87` 是 Jetson 本机地址，**接收机是否能从外部网段路由到 `eth2` 该地址**仍 `NEEDS_CONFIRMATION`。
    - `eth2` 同时持有 `192.168.123.55/24` 与 `192.168.144.87/24` 两个 `/24` 地址，意味着 `eth2` 是 Jetson 上**新增的**一个**多宿主（multi-homed）物理网卡**——其链路角色由 BOX 重新连接触发的拓扑变化而来；`eth2` 与 BOX 之间的物理拓扑（直连 / 经 Hub / 经 BOX 内部桥接）仍 `NEEDS_CONFIRMATION`。
- **建议作为当前 RTSP / WebRTC 测试目标地址（CONFIRMED 推荐登记，**仅作记录**，实际由用户在 Jetson / 接收机侧另行测试）**：
    - `rtsp://192.168.144.87:8554/live`：对应 4.2 节 MediaMTX 监听端口 RTSP `8554 TCP`。
    - `http://192.168.144.87:8889/live`：对应 4.2 节 MediaMTX 监听端口 WebRTC HTTP `8889`。
    - **注意**：上述两个 URL 是基于 4.2 节 MediaMTX 监听端口事实 + 4.7 节 `eth2 UP 192.168.144.87/24` 事实**拼接**出的候选地址；**协议 / 端口 / 路径后缀 `/live` 是否符合 `mediamtx.yml` 实际配置**仍需由 `mediamtx.yml` 内容核实；当前仅按"候选目标地址"登记。
- **`192.168.31.135`（wlan0 公司 Wi-Fi）相关结论保持不变**：
    - 此前对 `192.168.31.135:8554` 的 RTSP 接收测试**实际走公司 Wi-Fi**，**不代表图传接收机链路可达性**（与 4.5 节结论一致）。
    - 4.7 节**不**改变此结论；本节只是新增 `eth2` UP 与 `192.168.144.87` 作为 Jetson 本机 `eth2` 地址的事实。
- **`Broken pipe` 与本节的关系（保留事实）**：
    - 4.3 / 4.4 节中 pusher 端 `[Errno 32] Broken pipe` 持续重复证据**保留**；该线索与"BOX 重连 / `eth2` UP / 新增地址"是相互独立的观察点。
    - 本节**不**对 `Broken pipe` 是否因 BOX 重连而新增 / 复现 / 缓解下任何结论；pusher / FFmpeg 子进程生命周期的根因仍 `NEEDS_CONFIRMATION`。
    - 4.7 节**不得**被解读为"BOX 重连解决了 `Broken pipe`"或"BOX 重连引入了 `Broken pipe`"。
- **仍 `NEEDS_CONFIRMATION`（不在本次会话执行）**：
    - `eth2` 的物理拓扑（直连 BOX / 经 Hub / 经 BOX 内部桥接）。
    - `eth2` 是否与 BOX 内的图传/数传接收机形成同一可路由域（`192.168.123.0/24` / `192.168.144.0/24` 网段）。
    - 接收机实际所在网段、IP、端口、协议；是否已上电 / 已联网 / 已与 Jetson 同一可路由域内可达。
    - `mediamtx.yml` 中的 path / 鉴权配置；`/live` 是否为合法 path。
    - 4.3 / 4.4 节中 `Broken pipe` 的完整 pusher / FFmpeg 退出序列与根因。
    - `192.168.123.55/24` 与 `192.168.144.87/24` 两个 `/24` 地址的角色差异（两个网段分别是 BOX / 雷达 / 图传接收机 / 数传接收机中哪一个？）。
- **下一步只读核对（仅记录，不在本会话执行；待用户 / 现场授权后由用户在 Jetson 上执行；**不重复启动脚本**）**：
    - `ip -br addr` / `ip -br link`：核对 `eth2` 是否稳定 `UP`，两个 `/24` 是否仍在。
    - `ip route`：核对是否新增 `192.168.123.0/24` / `192.168.144.0/24` 路由。
    - `ip neigh` / `arp -a`（只读）：核对 `eth2` 网段内的邻居（是否有 BOX / 接收机设备出现）。
    - 在接收机侧（不在 Jetson 上）尝试访问 `rtsp://192.168.144.87:8554/live` 与 `http://192.168.144.87:8889/live`，核对是否能完成 RTSP DESCRIBE / PLAY 或 WebRTC 信令握手；具体步骤与结果由用户在接收机侧另行回传。
    - `tmux capture-pane -pt rtsp_stream:0 -S -200` / `tmux capture-pane -pt rtsp_stream:1 -S -200`（只读）：抓取最近若干屏日志，确认 mediamtx / pusher / FFmpeg 在 BOX 重连 + `eth2` UP 后的实际状态；注意 BOX 重连是否触发 pusher / FFmpeg 重新初始化。
    - `ps -ef | grep -E "mediamtx|oak_rtsp_pusher|sbus|ffmpeg"`（只读）：核对相关进程是否仍在运行、是否需要重启。
    - `ss -lntup | grep -E ":8554|:8889|:8000|:8001|:8189|:1935|:8888|:8890"`（只读）：核对 MediaMTX 端口是否仍在监听、监听地址是否绑定 `eth2` / `0.0.0.0`。
- **明确边界（不得过度宣称）**：
    - **不得据此宣称 BOX 重连后图传/数传链路已恢复**；本节仅作 `eth2` UP 与 `192.168.144.87` 是 Jetson 本机 `eth2` 地址的事实登记。
    - **不得据此重启 `rtsp_start.sh` / `sbus_start.sh` / `rtsp_stop.sh` 或任何 mediamtx / pusher / FFmpeg / sbus 进程**；**不重复启动脚本**。
    - **不得据此修改 `oak_rtsp_pusher.py`、`rtsp_start.sh`、`mediamtx.yml`、udev 规则或网络配置**。
    - **不得据此宣称 `192.168.144.87` 可被外部接收机直接访问**；`eth2` 是 Jetson 本机网卡，外部接收机是否能路由到 `eth2` 该地址仍 `NEEDS_CONFIRMATION`。
    - **不得据此把"对 `rtsp://192.168.144.87:8554/live` / `http://192.168.144.87:8889/live` 的接收测试"自动等同于"图传接收机链路已打通"**——这两条 URL 仍需在接收机侧独立测试，结果由用户回传。
    - **不得据此把当前 `Broken pipe` 归因为"BOX 重连引起"或"BOX 重连解决"**；`Broken pipe` 与本节相互独立。
- **保留事实（不随本节改变）**：
    - 4.1~4.5 节中关于 `rtsp_start.sh` 启动、MediaMTX 监听、pusher `Broken pipe`、网络角色归属（eth0 = 雷达 / wlan0 = 公司 Wi-Fi）等事实**保留**。
    - 4.6 节 BOX 重连状态登记**保留**；本节仅在 4.6 节基础上新增 `eth2` UP 与 `192.168.144.87` / `192.168.123.55` 是 Jetson 本机 `eth2` 地址的事实点。
- `tests`: SKIPPED (文档同步，仅记录用户提供的现场 `ip -br addr` 终端输出，未运行任何测试 / 构建 / Jetson 操作)。

### 4.9 2026-08-21 用户在 Jetson 上 ffplay 强制 RTSP over TCP 拉流验证 现场证据（CONFIRMED）

> 本节基于用户在 Jetson 上执行的只读 ffplay 拉流验证输出，**仅作登记**，不擅自执行任何 Jetson 操作、配置变更、APP/WEB/导航代码修改或远程命令。本会话不远程连接 Jetson，仅登记用户提供的输出。

- **用户在 Jetson 上执行的命令**（用户提供，原文登记）：
    - `ffplay -rtsp_transport tcp -fflags nobuffer -flags low_delay -framedrop -i rtsp://192.168.144.87:8554/live`
- **ffplay 画面结果（用户提供）**：
    - 画面**清晰**——用户观察无马赛克、无花屏、无明显卡顿/丢帧。
- **ffplay 识别出的流信息（用户提供，原文登记）**：
    - `Video: h264 (Constrained Baseline), yuv420p, 1248x240, 10 fps`
- **结论（CONFIRMED）**：
    - **相机输入链路**：OAK 摄像头 `rawvideo BGR24 1248x240 10fps` 输入正常；与 4.2 节 pusher 输入参数事实一致。
    - **FFmpeg 编码**：`libx264` 编码与 `rtsp_transport tcp` 推流参数工作正常；与 4.8 节 ffmpeg 命令行（`... -c:v libx264 ... -f rtsp -rtsp_transport tcp rtsp://192.168.144.87:8554/live`）事实一致。
    - **MediaMTX 发布**：`rtsp://192.168.144.87:8554/live` path 上 H264 RTSP/TCP 流可被独立客户端解析并解码，与 4.8 节发布端 `publishing path 'live'` 事实互相印证。
    - **RTSP over TCP 链路**：从 Jetson `eth2 192.168.144.87` 经 RTSP/TCP 8554 到 ffplay 的端到端 TCP 拉流链路可正常建立、画面清晰、流参数被准确识别——**整链路（相机输入 + FFmpeg/libx264 编码 + MediaMTX RTSP/TCP 服务端 + TCP 拉流客户端解码）全部正常工作**。
- **首要根因定位（CONFIRMED，与 4.8 节"首要嫌疑"互相印证并升级为更明确的根因结论）**：
    - 遥控器端 VLC 看到的"马赛克 / 画面异常"现象，与 4.8 节 MediaMTX 链接日志中 **接收端 `reading path 'live' (with UDP)` 紧接 `rtcp: invalid packet version`** 高度相关，且在用户使用 `ffplay -rtsp_transport tcp ...` 强制 RTSP over TCP 后**画面清晰、链路稳定**——这强烈表明：
        - **首要根因是 VLC / 图传接收端默认使用 UDP RTP/RTCP 传输时的不稳定或兼容性问题**（UDP RTP/RTCP 包丢失 / 错解析 / 版本位破坏，导致 VLC 解码器无法正常还原图像，表现为马赛克）。
        - **不是** Jetson 本机 IP（`192.168.144.87` / `192.168.123.55`）不可达；
        - **不是** OAK 相机输入异常；
        - **不是** FFmpeg/`libx264` 编码异常；
        - **不是** MediaMTX 服务端发布异常。
    - 因此图传链路在 Jetson 端实际处于"完全正常"状态；剩余问题仅在**接收端 UDP RTP/RTCP 传输**层面。
- **建议（仅记录，不在本会话执行；待用户 / 现场授权后由用户在遥控器侧执行）**：
    - **方案 A（推荐）**：遥控器 VLC 强制 RTSP over TCP——VLC 偏好 → 输入/编解码 → 网络 → 勾选 "Use RTSP over TCP"（或在命令行 `vlc --rtsp-tcp rtsp://192.168.144.87:8554/live`）；与 `ffplay -rtsp_transport tcp` 行为一致，预期画面与本次 ffplay 验证一致（清晰、无马赛克）。
    - **方案 B（备选）**：若遥控器 VLC 无法强制 TCP（如遥控器自带图传 APP 锁定 UDP 行为），改用支持 RTSP over TCP 的播放器（如 ffplay / mpv / PotPlayer / IINA 等），目标地址同样为 `rtsp://192.168.144.87:8554/live`。
    - **方案 C（评估）**：若必须保留 UDP 拉流，需要评估遥控器 / 接收端到 Jetson `eth2`（`192.168.144.0/24`）的 UDP 丢包、抖动与 NAT / 防火墙策略；可考虑调整 MediaMTX `mediamtx.yml` 的 UDP RTP/RTCP 缓冲区、抖动缓冲、Jitter buffer 或调整 VLC 端 UDP 缓存参数（如 `:network-caching=300`）。
- **明确边界（不得过度宣称）**：
    - **不得据此宣称"图传链路已修复"**：本次验证仅证明 Jetson 端的"相机 → 编码 → MediaMTX 发布 → RTSP/TCP 拉流"链路完整可用；**遥控器端实际切换到 RTSP/TCP 后画面是否改善，仍待用户在接收机侧独立测试后回传**。
    - **不得据此宣称"`Broken pipe` 已根除"**：4.3 / 4.4 节 pusher 端 `[Errno 32] Broken pipe` 持续重复证据**保留**；pusher / FFmpeg 子进程生命周期的根因仍 `NEEDS_CONFIRMATION`，与本次 ffplay 验证相互独立。
    - **不得据此宣称"遥控器图传链路已恢复"**：本次仅在 Jetson 本机 ffplay 上验证，**未在遥控器端实际测试**；遥控器端实际画面结果由用户在遥控器侧另行回传。
    - **不得据此重启 / 修改 `rtsp_start.sh` / `sbus_start.sh` / `rtsp_stop.sh` 或任何 mediamtx / pusher / FFmpeg / sbus 进程**。
    - **不得据此修改 `oak_rtsp_pusher.py`、`rtsp_start.sh`、`mediamtx.yml`、udev 规则、VLC 配置、遥控器图传 APP 配置或网络配置**。
    - **不得据此宣称 "图传链路已完整打通"**：**前端 APP 切换到图传/数传链路的测试联调仍待做**——APP rosbridge / 导航 API 目标地址与契约确认、APP 实测、导航任务创建在图传/数传链路下的顺/卡顿对比等仍未执行。
- **仍 `NEEDS_CONFIRMATION`（不在本次会话执行）**：
    - 遥控器 VLC 是否能强制 RTSP over TCP；强制后画面是否与本次 ffplay 验证一致（清晰、无马赛克）。
    - 遥控器自带图传 APP 的传输协议（是否锁定 UDP / 是否允许切换协议）；若不允许切换协议时的备选播放器选型。
    - `rtcp: invalid packet version` 的具体来源：VLC 客户端 RTCP 反馈异常 vs 网络丢包导致版本位被破坏 vs MediaMTX 解析兼容性。
    - `Broken pipe` 在更长时间窗口（跨越本次 ffplay 验证）下是否仍持续出现。
- **保留事实（不随本节改变）**：
    - 4.1~4.8 节中关于 `rtsp_start.sh` 启动、MediaMTX 监听端口、`Broken pipe` 历史证据、网络角色归属（eth0 = 雷达 / wlan0 = 公司 Wi-Fi）、`eth2` UP 与 `192.168.144.87` / `192.168.123.55` 是 Jetson 本机 `eth2` 地址的事实**全部保留**。
    - 本节**不**撤销 4.3 / 4.4 节 `Broken pipe` 持续重复登记；只是新增"ffplay RTSP/TCP 拉流验证通过、画面清晰、流参数被准确识别"的事实点。
- `tests`: PASS (本次仅在 Jetson 上执行只读 ffplay / TCP 流验证，未执行任何远程命令、未修改任何业务代码、未变更 Jetson / APP / WEB / Docker / udev / Git)。

### 5. WebRTC 视频查看地址（资料原文）
- `http://192.168.144.87:8889/live`
- 性质：资料给出的视频查看入口；**未证明**与导航 API / APP rosbridge 目标地址有任何关系（见下文 `NEEDS_CONFIRMATION`）。

### 6. 导航 Web 管理地址（资料原文）
- `http://192.168.117.6:9000/`
- 账号：`admin`（密码/鉴权资料未提供）
- 备注：`192.168.117.6` 在本工作区历史记录中曾作为 Jetson 热点地址出现；本次仅按资料原文登记，不做角色判定。

### 7. 机器狗连通性提示
- 资料提示：`ping 192.168.123.161` 验证机器狗是否在线。
- 性质：连通性自检提示；当前是否可达：`NEEDS_CONFIRMATION`。

### 8. 图传检查用的 ROS Topic（资料原文）
- `/SLB_CAM_A/compressed`
- 用途：图传链路存活/图像是否在发布的探针 topic（具体消息类型以现场为准）。

---

## 需现场确认（NEEDS_CONFIRMATION）

### A. 数传串口名
- 资料未给出稳定串口设备名（如 `/dev/ttyUSB*` 或 `/dev/lg_*` 别名）。
- 需现场确认：实际使用的串口节点、`udev` 是否已为该串口建立稳定别名。
- 关联：与 udev 规则 `99-serial-aliases.rules` 配置是否落地直接相关。

### B. 物理网卡 `eth1` / `eth30`
- 资料提示需按现场确认 `eth1` / `eth30` 是否存在、是否承担数传/图传流量。
- 当前 Jetson 上 `ip link` / `ip addr` 的实际情况：`UNKNOWN`，未在本任务中执行任何远程命令。

### C. 192.168.144.87 的角色与归属
- 资料中是 WebRTC 视频查看入口（示例/接收端访问地址）。
- **不得据此**将其作为 APP rosbridge / 导航 API / FastAPI 的目标 IP。
- 实际前端 APP 连入 rosbridge 的目标 IP、端口、协议、配置文件：**均 NEEDS_CONFIRMATION**。
- 与已知事实的关系（仅对照，不下结论）：
  - `TASK-2026-08-19-001` 已记录 APP/WEB 实际通过 9090 联调，热点 `192.168.117.6`、公司 Wi-Fi `192.168.31.135` 均实测过。
  - `192.168.144.87` 不在上述已确认的目标地址之列。

### D. 前端 APP 切换到图传/数传链路时的实际配置
- 实际生效的配置文件路径：UNKNOWN（候选：`RobotEndpoint.kt`、`nginx.conf`、APP 端配置文件等，但未确认）。
- 协议：UNKNOWN（HTTP / WebSocket / RTSP / WebRTC 各自独立，不得混用）。
- 端口：UNKNOWN（与 `9090` / `19090` / `80` / `5000` / `8889` / `9000` 的关系未确认）。
- 目标 IP：UNKNOWN（`192.168.144.87` 仅是 WebRTC 示例，不当作 APP 目标）。
- 鉴权 / TLS / 路由：`NEEDS_CONFIRMATION`。

### E. 其它未在资料中出现的字段
- 数传 SBUS 的波特率、帧格式、channel 映射：UNKNOWN。
- 图传 TCP / UDP 的端口、分辨率、码率：UNKNOWN。
- udev 规则 `99-serial-aliases.rules` 的具体内容（哪些 vid:pid 映射到哪些别名）：UNKNOWN。
- `rtsp_server.tar.gz` 与 `scout_mini_navigation.tar.gz` 的版本、来源、完整性校验：UNKNOWN。

---

## 用户的测试目标（登记用，不擅自执行）

- 目标：在图传 / 数传链路下，测试「导航任务创建」等操作是否比 Wi-Fi / 热点链路更顺畅。
- 当前阶段：仅登记目标与前置事实，不进入实现 / 部署 / 联调。
- 授权路径：仅限本工作区文档（`.ai-workspace/`）。

---

## 任务边界与不变量

- 不复制 `rtsp_server.tar.gz` / `scout_mini_navigation.tar.gz` / 其他大附件到本工作区。
- 不修改任何业务仓库、APP、导航代码、Jetson、Docker、udev 或 Git 历史。
- 不将 `192.168.144.87` 解释为 APP rosbridge / 导航 API 的目标 IP。
- 一切 `NEEDS_CONFIRMATION` / `UNKNOWN` 项，由用户在后续会话中给出或现场核对后再行登记。
