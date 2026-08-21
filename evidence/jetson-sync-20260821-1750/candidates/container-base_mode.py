"""底盘模式切换: NONE / SCOUT (managed roslaunch) / GO2 (driver not configured).

提供 HTTP 接口切换底盘模式,所有外部命令 ``shell=False`` + ``timeout``,
默认关闭底盘控制 (``mode=NONE``, ``ready=True``)。``SCOUT`` 模式下独占启
动 ``scout_base`` roslaunch;``GO2`` 模式当前未配置驱动,只记录失败原因。
``shutdown`` 只清理本进程启动的子进程组,绝不越权 kill 外部 ROS 节点。

状态机语义:
* ``mode`` = 真实底盘模式: ``NONE``(未知/未确认) / ``SCOUT`` / ``GO2``。
  ``NONE`` 只表示"不知道当前是哪种底盘",**不再代表手动**。
* ``control`` = /cmd_vel 控制权来源: ``AUTO``(自动导航) / ``MANUAL``(遥操作)。
  独立维度,不映射到 ``mode=NONE``。
* ``modeLabel``: ``NONE``->'未知'; ``GO2``->'GO2'; ``SCOUT``+``AUTO``->'自动导航';
  ``SCOUT``+``MANUAL``->'手动遥控'。
* ``switch(mode=manual)``: 暂停当前导航任务(由 ``teleop.enable`` 内部完成),
  启用 teleop 让 /cmd_vel 由摇杆接管;``mode`` 保持真实模式(若 Scout 驱动
  存在则升级为 SCOUT),``control`` 转 ``MANUAL``。
* ``switch(mode=auto|scout)``: 禁用 teleop(零速),恢复/允许自动导航;
  若外部 ``/scout_base_node`` 已存在视为已存在的 SCOUT 驱动,**不报错**,
  **不重复启动**,``control`` 转 ``AUTO``。
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from typing import Any, Optional

from fastapi import APIRouter, Query

from .models import ApiResponse, fail, ok
from .ros_client import ros_client
from .teleop import teleop_controller


LOGGER = logging.getLogger(__name__)


# 模式枚举: 与前端 ``?mode=none|scout|go2`` 一一对应。
# ``NONE`` 现在只表示"未知/未确认",**不再代表手动遥控**。
MODE_NONE = "NONE"
MODE_SCOUT = "SCOUT"
MODE_GO2 = "GO2"
VALID_MODES = (MODE_NONE, MODE_SCOUT, MODE_GO2)
_MODE_LABELS = {MODE_NONE: "未知", MODE_SCOUT: "自动导航", MODE_GO2: "GO2"}

# /cmd_vel 控制权来源: ``AUTO`` = 自动导航, ``MANUAL`` = 摇杆遥操作。
# 独立维度,与 ``mode`` 正交:``MANUAL`` **不**映射到 ``mode=NONE``。
CONTROL_AUTO = "AUTO"
CONTROL_MANUAL = "MANUAL"

# 前端高层语义别名: ``auto`` -> SCOUT(自主导航); ``manual`` 不再映射
# 到 NONE,而是作为控制权切换进入 ``_switch_to_manual`` 特殊路径。
_MODE_ALIASES = {"AUTO": MODE_SCOUT}


def _compute_mode_label(mode: str, control: str) -> str:
    """根据 ``mode`` 与 ``control`` 计算前端展示用中文标签。

    * ``NONE`` -> '未知'
    * ``GO2``  -> 'GO2'
    * ``SCOUT`` + ``AUTO``   -> '自动导航'
    * ``SCOUT`` + ``MANUAL`` -> '手动遥控'
    * 未知 mode 回退到 mode 字符串本身,不抛异常。
    """
    if mode == MODE_NONE:
        return "未知"
    if mode == MODE_GO2:
        return "GO2"
    if mode == MODE_SCOUT:
        if control == CONTROL_MANUAL:
            return "手动遥控"
        return "自动导航"
    return mode

# SCOUT_BASE_LAUNCH_FILE: 容器内已确认唯一绝对路径,避免 roslaunch 命中 install
# 与 src 同名 launch 抛 RLException。非容器环境可通过 ``SCOUT_BASE_LAUNCH_FILE``
# 环境变量覆盖;参数数组仍 ``shell=False``,绝不引入注入风险。
DEFAULT_SCOUT_BASE_LAUNCH_FILE = (
    "/Scout_mini_navigation/install/share/scout_base/launch/scout_mini_base.launch"
)
SCOUT_BASE_LAUNCH_FILE = os.environ.get(
    "SCOUT_BASE_LAUNCH_FILE", DEFAULT_SCOUT_BASE_LAUNCH_FILE
)

# roslaunch 参数数组: 直接传绝对 launch 文件路径,端口名、车型、omni 标志、
# 模拟标志、是否广播 TF 维持原语义。
SCOUT_LAUNCH_ARGS = [
    "roslaunch",
    SCOUT_BASE_LAUNCH_FILE,
    "port_name:=can0",
    "is_scout_mini:=true",
    "is_scout_omni:=false",
    "simulated_robot:=false",
    "pub_tf:=true",
]

# rosnode / rostopic 命令参数数组,避免 shell=True 注入。
ROSNODE_LIST_ARGS = ["rosnode", "list"]
ROSTOPIC_SCOUT_STATUS_ARGS = ["rostopic", "echo", "-n", "1", "/scout_status"]

# CAN 网口相关 ip 命令参数数组;全部 shell=False。
IP_LINK_SHOW_ARGS = ["ip", "link", "show", "can0"]
IP_LINK_SET_UP_ARGS = [
    "ip", "link", "set", "can0", "up", "type", "can", "bitrate", "500000",
]

# ROS python3 dist-packages 路径: 必须前置注入 PYTHONPATH,否则 rosnode/rostopic
# 会抛 ``ModuleNotFoundError: No module named 'rosnode'``。
ROS_PYTHONPATH_ENTRY = "/opt/ros/noetic/lib/python3/dist-packages"

# Scout 工作空间 install 路径: ``scout_msgs`` 等自定义消息类生成位置,
# 必须位于 ``/opt/ros/noetic/...`` **之前**,否则 rostopic 会先命中旧版同名
# 消息或抛 ``Cannot load message class for [scout_msgs/ScoutStatus]``。
SCOUT_INSTALL_PYTHONPATH_ENTRY = (
    "/Scout_mini_navigation/install/lib/python3/dist-packages"
)

# sysfs RX packets 路径: 比 ``ip -s link show`` 的表格输出更稳定,
# 直接读整数即可,异常全部返回 None。
CAN0_RX_PACKETS_PATH = "/sys/class/net/can0/statistics/rx_packets"

# 各阶段超时(秒): CAN 起活 / roslaunch 启动 / status 解析,均为保守上限。
CAN_UP_TIMEOUT = 5.0
CAN_TRAFFIC_POLL_INTERVAL = 0.2
CAN_TRAFFIC_TIMEOUT = 3.0
ROSLAUNCH_STARTUP_GRACE = 1.0
SCOUT_STATUS_POLL_INTERVAL = 0.3
SCOUT_STATUS_TIMEOUT = 8.0
GENERIC_CMD_TIMEOUT = 5.0

LOG_FILE_PATH = "/tmp/scout_base_mode.log"


def _open_log_file():
    """打开日志文件;失败时回退到 DEVNULL。"""
    try:
        # ``/tmp`` 在 Linux 上存在;为兼容开发机,先尝试创建,失败即 DEVNULL。
        return open(LOG_FILE_PATH, "ab", buffering=0)
    except OSError as exc:
        LOGGER.warning("base_mode: 打开日志文件 %s 失败, 回退 DEVNULL: %s", LOG_FILE_PATH, exc)
        return subprocess.DEVNULL


def _ros_subprocess_env() -> dict:
    """为 ROS CLI 子进程构造独立 ``environment`` 副本。

    docker-entrypoint 在 ``source ROS`` 之后又
    ``export PYTHONPATH=/Scout_mini_navigation/src/nav_api``;FastAPI 子进程继承
    之后 ``/opt/ros/noetic/lib/python3/dist-packages`` 不再位于
    ``sys.path``,导致 ``rosnode list`` / ``rostopic echo`` 子进程抛
    ``ModuleNotFoundError: No module named 'rosnode'``;另外
    ``scout_msgs`` 等自定义消息类位于
    ``/Scout_mini_navigation/install/lib/python3/dist-packages``,
    若未前置注入会抛 ``Cannot load message class for [scout_msgs/ScoutStatus]``。

    这里复制 ``os.environ`` 后**前置**追加 Scout install 与 ROS python3
    dist-packages,并保留已有 PYTHONPATH 项;不修改全局 ``os.environ``。
    仅用于 ROS CLI 子进程, ``ip`` 等系统命令无需此 env。使用 ``os.pathsep``
    (POSIX 为 ``:``) 拼接,避免硬编码分隔符带来的可移植性风险。
    """
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    entries = [SCOUT_INSTALL_PYTHONPATH_ENTRY, ROS_PYTHONPATH_ENTRY]
    if existing:
        entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def _read_can0_rx_packets() -> Optional[int]:
    """从 sysfs 直接读 can0 RX 计数;任何异常都返回 None。

    ``ip -s link show`` 的输出表头在数字之上,正则几乎无法可靠解析;
    sysfs 数值文件始终是单行整数,首选此路径。
    """
    try:
        with open(CAN0_RX_PACKETS_PATH, "r", encoding="ascii", errors="replace") as fh:
            raw = fh.read().strip()
    except (OSError, ValueError):
        return None
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _is_can0_up_from_text(out: str) -> bool:
    """判断 ``ip link show can0`` 输出是否真的 ``UP`` 且 ``state UP``。

    真实样本::

        3: can0: <NOARP,UP,LOWER_UP,ECHO> mtu 16 qdisc fq_code
            state UP mode DEFAULT group default qlen 10

    flags 字段位于首行 angle-bracket 之中,state 字段可能跨行,
    因此分两步解析:首行 flags 含 ``UP``,再匹配 ``state UP``。
    """
    if not out:
        return False
    # 按 ``\n`` 切分,首行就是带 flags 的那行。
    lines = out.splitlines()
    if not lines:
        return False
    first_line = lines[0]
    flags_match = re.search(r"<([^>]+)>", first_line)
    if not flags_match:
        return False
    flags = flags_match.group(1)
    if not re.search(r"\bUP\b", flags):
        return False
    # state 字段允许跨行,但必须存在于整个输出中。
    if not re.search(r"\bstate\s+UP\b", out, re.IGNORECASE):
        return False
    return True


def _external_scout_running() -> bool:
    """检测外部 ``/scout_base_node`` 是否在 ROS 节点列表中。

    与 ``BaseModeManager._managed_scout``(本进程启动的 roslaunch)正交,
    用于在新语义下"采纳"已存在的外部驱动。ROS master 不可用、rosnode
    列表失败等异常一律收敛为 False,绝不抛异常,供锁内热路径使用。
    """
    try:
        rc, out, _err = _run_capture(
            ROSNODE_LIST_ARGS, GENERIC_CMD_TIMEOUT, _ros_subprocess_env()
        )
    except Exception as exc:
        LOGGER.warning("base_mode: 检测外部 Scout 异常: %s", exc)
        return False
    if rc != 0 or not out:
        return False
    nodes = [line.strip() for line in out.splitlines() if line.strip()]
    return "/scout_base_node" in nodes


def _teleop_enabled_safe() -> bool:
    """读 teleop 启用状态;绝不抛异常,失败时回退 False。"""
    try:
        resp = teleop_controller.status()
    except Exception as exc:
        LOGGER.warning("base_mode: 读取 teleop 状态异常: %s", exc)
        return False
    data: Any = getattr(resp, "data", None)
    if not isinstance(data, dict):
        return False
    return bool(data.get("enabled", False))


def _nav_state_safe() -> str:
    """读当前导航任务状态;绝不抛异常,失败时回退 ``IDLE``。"""
    try:
        status = ros_client.get_nav_status()
    except Exception as exc:
        LOGGER.warning("base_mode: 读取 nav 状态异常: %s", exc)
        return "IDLE"
    if not isinstance(status, dict):
        return "IDLE"
    state = status.get("state", "IDLE")
    return str(state) if state is not None else "IDLE"


def _external_scout_present() -> bool:
    rc, out, _ = _run_capture(ROSNODE_LIST_ARGS, GENERIC_CMD_TIMEOUT, _ros_subprocess_env())
    return rc == 0 and "/scout_base_node" in {line.strip() for line in out.splitlines()}


class _SubprocessRecord:
    """记录本管理器启动的子进程,shutdown 时只清理自己拥有的句柄。"""

    __slots__ = ("proc", "pgid")

    def __init__(self, proc: subprocess.Popen, pgid: int) -> None:
        self.proc = proc
        self.pgid = pgid


class BaseModeManager:
    """串行锁保护的状态机;只有本进程启动的 roslaunch 会被 shutdown。

    双维度状态:
    * ``_mode``: 真实底盘模式 (``NONE``/``SCOUT``/``GO2``)。
      ``NONE`` = 未知/未确认,不是手动。
    * ``_control``: /cmd_vel 控制权来源 (``AUTO``/``MANUAL``),与 ``_mode``
      正交,独立维度。

    默认: ``mode=NONE``, ``control=AUTO``, ``ready=True``。NONE 是安全可
    用状态:启动 API 后无需任何额外配置即可正常工作;切换到 SCOUT/GO2 失败
    会回滚到 ``mode=NONE`` 并标注 ``ready=False`` + ``reason``。
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._mode = MODE_NONE
        # NONE 是安全可用状态:无需外部依赖,直接 ready=True。
        self._ready = True
        self._reason = ""
        self._managed_scout: Optional[_SubprocessRecord] = None
        # 控制权来源: 启动时默认 AUTO(由 _switch_to_manual 显式切换)。
        self._control = CONTROL_AUTO

    # --- public API --------------------------------------------------

    def status(self) -> ApiResponse:
        with self._lock:
            mode = self._mode
            ready = self._ready
            reason = self._reason
            managed_running = self._managed_scout is not None and self._managed_scout.proc.poll() is None
            # roslaunch may have started Scout before this API process. In that
            # case the old implementation reported NONE/ready=false with
            # SCOUT_NODE_ALREADY_RUNNING, which is not the real chassis mode.
            # Treat the observed Scout node as the authoritative SCOUT state.
            if mode == MODE_NONE and reason == "SCOUT_NODE_ALREADY_RUNNING":
                mode = MODE_SCOUT
                ready = True
                reason = "SCOUT_NODE_EXTERNAL"
            teleop_enabled = _teleop_enabled_safe()
            payload = {
                "mode": mode,
                "modeLabel": "手动遥控" if teleop_enabled and mode == MODE_SCOUT else _MODE_LABELS.get(mode, mode),
                "ready": ready,
                "reason": reason,
                "navState": _nav_state_safe(),
                "teleopEnabled": teleop_enabled,
                "managedScoutRunning": managed_running,
            }
        return ok(payload)

    def ensure_auto(self) -> ApiResponse:
        """导航下发前确保底盘处于自动模式 (SCOUT) 且 ``ready``。

        复用 ``self.switch(MODE_SCOUT)``;``switch`` 内部对已就绪的 SCOUT
        状态会幂等短路并返回当前快照,不会重复启动 roslaunch。
        失败时直接返回 ``fail`` + ``reason``,由 ``_send_task`` 透传给前端,
        避免在底盘不可用时下发任务。

        调用频率:每个导航任务下发前一次,HTTP 请求粒度。
        """
        return self.switch(MODE_SCOUT)

    def can_enable_teleop(self) -> tuple[bool, str]:
        """Teleop enable guard: 模式互斥下的最严策略。

        只有同时满足以下全部条件才允许启用遥操作,任意一条不满足都拒
        绝并返回 ``reason``,``teleop.enable`` 会把 ``reason`` 透传给
        调用方:

        * ``mode == SCOUT``:避免 NONE/GO2 下经 rosbridge 误向 ROS1
          ``/cmd_vel`` 发指令,或经 bridge 错误触达 GO2。
        * ``ready == True``:驱动节点与 CAN 物理层自检已通过。
        * ``_managed_scout`` 句柄存在且进程仍在运行:进程一旦已退出
          (``proc.poll() is not None``),同步将 ``ready`` 翻转为
          ``False`` 并写入明确 ``reason``,由用户重新走一次
          ``/api/base_mode/switch`` 拉起新的 roslaunch。

        调用频率:HTTP 请求粒度,锁内快速返回,无副作用 IO。
        """
        with self._lock:
            if self._mode != MODE_SCOUT:
                if self._mode == MODE_NONE and _external_scout_present():
                    self._mode = MODE_SCOUT
                    self._ready = True
                    self._reason = "SCOUT_NODE_EXTERNAL"
                else:
                    return False, "BASE_MODE_NOT_SCOUT: %s" % self._mode
            record = self._managed_scout
            if record is None or record.proc.poll() is not None:
                if _external_scout_present():
                    self._ready = True
                    self._reason = "SCOUT_NODE_EXTERNAL"
                else:
                    self._ready = False
                    self._reason = "SCOUT_PROCESS_EXITED"
                    return False, self._reason
            if not self._ready:
                return False, self._reason or "BASE_NOT_READY"
            return True, ""

    def switch(self, mode: str) -> ApiResponse:
        """按 ``mode`` 切换底盘模式;任意阶段失败都先尽力 ``disable`` teleop。

        接受 ``none|scout|go2`` 或前端别名 ``auto|manual``;
        ``auto`` 映射到 SCOUT(自主导航), ``manual`` 映射到 NONE(手动遥操作)。
        返回 data 包含 ``mode/modeLabel/navState/teleopEnabled/ready`` 等字段。
        """
        requested = str(mode or "").strip().upper()
        manual_control = requested == "MANUAL"
        target = _MODE_ALIASES.get(requested, requested)
        if manual_control:
            # 手动是控制权，不是底盘模式；真实底盘仍保持 SCOUT/NONE。
            target = MODE_SCOUT
        if target not in VALID_MODES:
            return fail(
                "不支持的模式: %s, 允许 %s" % (mode, ",".join(m.lower() for m in VALID_MODES))
            )

        # 切换第一步:禁用 teleop 并发布零速;若失败直接拒绝切换,
        # 避免底盘同时收到 teleop 与 roslaunch 两路冲突命令。
        try:
            disable_resp = teleop_controller.disable()
        except Exception as exc:
            LOGGER.warning("base_mode: 切换前 disable teleop 异常: %s", exc)
            return fail("切换前禁用 teleop 失败: %s" % exc)
        if not getattr(disable_resp, "success", False):
            return fail("切换前禁用 teleop 失败: %s" % getattr(disable_resp, "msg", ""))

        if manual_control:
            with self._lock:
                if self._mode == MODE_NONE and _external_scout_present():
                    self._mode = MODE_SCOUT
                    self._ready = True
                    self._reason = "SCOUT_NODE_EXTERNAL"
            enable_resp = teleop_controller.enable()
            if not getattr(enable_resp, "success", False):
                return fail(getattr(enable_resp, "msg", "启用手动遥控失败"))
            payload = self._snapshot_locked()
            payload["control"] = "MANUAL"
            payload["modeLabel"] = "手动遥控"
            payload["teleopEnabled"] = True
            return ok(payload, "已切换到手动遥控")

        with self._lock:
            if target == MODE_NONE:
                return self._switch_to_none_locked()
            if target == MODE_GO2:
                return self._switch_to_go2_locked()
            return self._switch_to_scout_locked()

    def shutdown(self) -> None:
        """lifespan 退出时调用: 仅清理本管理器启动的进程,先 disable teleop。"""
        try:
            disable_resp = teleop_controller.disable()
            if not getattr(disable_resp, "success", False):
                LOGGER.warning(
                    "base_mode: shutdown disable teleop 未成功: %s",
                    getattr(disable_resp, "msg", ""),
                )
        except Exception as exc:
            LOGGER.warning("base_mode: shutdown disable teleop 异常: %s" % exc)

        record: Optional[_SubprocessRecord] = None
        with self._lock:
            record = self._managed_scout
            self._managed_scout = None
            if record is not None:
                self._mode = MODE_NONE
                self._ready = True
                self._reason = ""

        if record is None:
            return

        self._terminate_record(record)

    # --- internal: transitions --------------------------------------

    def _switch_to_none_locked(self) -> ApiResponse:
        # NONE: 只停止自己启动的 Scout roslaunch,不动 CAN 网口。
        record = self._managed_scout
        if record is not None:
            self._managed_scout = None
            self._terminate_record(record)

        self._mode = MODE_NONE
        self._ready = True
        self._reason = ""
        return ok(self._snapshot_locked(), "已切换到 NONE")

    def _switch_to_go2_locked(self) -> ApiResponse:
        # GO2: 先停 Scout。驱动未配置时保留用户已选择的 mode=GO2,
        # 但 ``ready=False`` 标注真实状态。语义上视为"已按用户意图
        # 选择了 GO2,但当前不可用",success=True 以反映选择生效。
        record = self._managed_scout
        if record is not None:
            self._managed_scout = None
            self._terminate_record(record)

        self._mode = MODE_GO2
        self._ready = False
        self._reason = "GO2_DRIVER_NOT_CONFIGURED"
        return ok(
            self._snapshot_locked(),
            "已选择 GO2, 但驱动未配置",
        )

    def _switch_to_scout_locked(self) -> ApiResponse:
        # SCOUT: 串行检查 CAN → 启动 roslaunch → 校验 /scout_status 状态字段。
        # 失败时必须回滚 managed_scout + reason,绝不泄漏半成品进程。
        existing = self._managed_scout

        # 幂等: 已存在 managed Scout 且进程仍在运行,且 mode 已经是 SCOUT,
        # 直接返回当前快照,避免用户重复点击触发额外启动。
        if existing is not None:
            if existing.proc.poll() is None and self._mode == MODE_SCOUT:
                self._ready = True
                self._reason = ""
                return ok(self._snapshot_locked(), "已处于 SCOUT")

            # 句柄还在但进程已退出:清理句柄并继续后续启动流程,
            # 让用户可以重启一个 roslaunch 而无需先 NONE。
            self._managed_scout = None
            LOGGER.info(
                "base_mode: managed Scout 句柄进程已退出,清理后重启"
            )

        # 1) 冲突检测: rosnode 列表里如果存在 /scout_base_node 且不是本进程
        #    启动的 roslaunch,直接拒绝以避免多驱动抢 CAN。
        rc, out, err = _run_capture(ROSNODE_LIST_ARGS, GENERIC_CMD_TIMEOUT, _ros_subprocess_env())
        if rc != 0:
            # rosnode 非 0 通常意味着 roscore 未启动或网络不通,
            # fail closed: 不进入后续启动流程,避免重复节点。
            self._mode = MODE_NONE
            self._ready = False
            self._reason = "ROS_MASTER_UNAVAILABLE"
            return fail(
                "ROS master 不可用 (rosnode list rc=%s): %s"
                % (rc, err.strip() or out.strip() or "unknown")
            )
        if out:
            nodes = [line.strip() for line in out.splitlines() if line.strip()]
            if "/scout_base_node" in nodes:
                self._mode = MODE_SCOUT
                self._ready = True
                self._reason = "SCOUT_NODE_EXTERNAL"
                payload = self._snapshot_locked()
                payload["control"] = "AUTO"
                payload["modeLabel"] = "自动导航"
                payload["teleopEnabled"] = False
                return ok(payload, "已切换到自动导航")

        # 2) CAN 网口 up 检查: 已经是 UP 就跳过 set up, 避免不必要的 ioctl。
        rc, out, _ = _run_capture(IP_LINK_SHOW_ARGS, CAN_UP_TIMEOUT)
        can_up = bool(out) and _is_can0_up_from_text(out)
        if not can_up:
            rc_set, out_set, _ = _run_capture(
                IP_LINK_SET_UP_ARGS, CAN_UP_TIMEOUT
            )
            if rc_set != 0:
                LOGGER.warning(
                    "base_mode: ip link set can0 up 失败 rc=%s out=%s",
                    rc_set, out_set,
                )
            rc2, out2, _ = _run_capture(IP_LINK_SHOW_ARGS, CAN_UP_TIMEOUT)
            can_up = bool(out2) and _is_can0_up_from_text(out2)

        if not can_up:
            self._mode = MODE_NONE
            self._ready = False
            self._reason = "CAN0_NOT_UP"
            return fail("can0 无法置为 UP")

        # 3) CAN 流量自检: RX packets 在短暂等待后必须增长, 否则说明物理层无数据。
        rx_before = _read_can0_rx_packets()
        deadline = time.monotonic() + CAN_TRAFFIC_TIMEOUT
        traffic_grew = False
        while time.monotonic() < deadline:
            time.sleep(CAN_TRAFFIC_POLL_INTERVAL)
            rx_after = _read_can0_rx_packets()
            if rx_before is not None and rx_after is not None and rx_after > rx_before:
                traffic_grew = True
                break
        if not traffic_grew:
            self._mode = MODE_NONE
            self._ready = False
            self._reason = "CAN0_NO_TRAFFIC"
            return fail("can0 RX packets 在等待窗口内未增长, 物理层可能无数据")

        # 4) 启动前预检: launch 文件存在性。绝对路径虽能避开 roslaunch
        #    多文件 RLException,但路径仍可能因环境差异缺失;若不预检,
        #    Popen 会立刻退出但 reason 模糊, 不利于诊断。
        if not os.path.isfile(SCOUT_BASE_LAUNCH_FILE):
            self._mode = MODE_NONE
            self._ready = False
            self._reason = "SCOUT_LAUNCH_FILE_NOT_FOUND"
            LOGGER.warning(
                "base_mode: SCOUT_BASE_LAUNCH_FILE 不存在: %s",
                SCOUT_BASE_LAUNCH_FILE,
            )
            return fail(
                "scout 启动文件不存在: %s (可通过 SCOUT_BASE_LAUNCH_FILE 环境变量覆盖)"
                % SCOUT_BASE_LAUNCH_FILE
            )

        # 5) 启动 roslaunch: start_new_session=True 形成独立进程组, 便于整组 kill。
        log_handle = _open_log_file()
        proc: Optional[subprocess.Popen] = None
        try:
            proc = subprocess.Popen(  # noqa: S603 - shell=False, 参数数组
                SCOUT_LAUNCH_ARGS,
                stdout=log_handle,
                stderr=log_handle,
                stdin=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
                close_fds=True,
                env=_ros_subprocess_env(),
            )
        except OSError as exc:
            self._mode = MODE_NONE
            self._ready = False
            self._reason = "ROSLAUNCH_SPAWN_FAILED"
            LOGGER.warning("base_mode: 启动 roslaunch 异常: %s", exc)
            return fail("启动 roslaunch 失败: %s" % exc)
        finally:
            try:
                if log_handle is not subprocess.DEVNULL:
                    log_handle.close()
            except Exception:
                pass

        # 必须能取到进程组 ID,否则无法整组清理。失败时显式终止
        # 进程避免泄漏,并返回明确失败。
        try:
            pgid = os.getpgid(proc.pid)
        except (OSError, ProcessLookupError) as exc:
            LOGGER.warning("base_mode: getpgid 异常, 终止新进程: %s", exc)
            self._safe_terminate_proc(proc)
            self._mode = MODE_NONE
            self._ready = False
            self._reason = "ROSLAUNCH_PGID_UNAVAILABLE"
            return fail("无法获取 roslaunch 进程组, 已终止: %s" % exc)

        record = _SubprocessRecord(proc=proc, pgid=pgid)
        self._managed_scout = record
        # 给 roslaunch 一个最小启动宽限, 防止 Popen 立刻退出被误判成功。
        time.sleep(ROSLAUNCH_STARTUP_GRACE)
        if proc.poll() is not None:
            self._managed_scout = None
            self._mode = MODE_NONE
            self._ready = False
            self._reason = "ROSLAUNCH_EXITED_EARLY"
            return fail("roslaunch 启动后立即退出, 请查看日志 %s" % LOG_FILE_PATH)

        # 5) 校验 /scout_status: control_mode 必须为 1, fault_code 必须为 0。
        ok_status, parsed_reason = self._wait_for_scout_status(proc)
        if not ok_status:
            self._managed_scout = None
            self._terminate_record(record)
            self._mode = MODE_NONE
            self._ready = False
            self._reason = parsed_reason
            return fail(parsed_reason)

        self._mode = MODE_SCOUT
        self._ready = True
        self._reason = ""
        return ok(self._snapshot_locked(), "已切换到 SCOUT")

    # --- helpers ----------------------------------------------------

    def _wait_for_scout_status(self, proc: subprocess.Popen) -> tuple[bool, str]:
        """轮询 ``/scout_status``, 解析 ``control_mode`` 和 ``fault_code``。"""
        deadline = time.monotonic() + SCOUT_STATUS_TIMEOUT
        last_reason = "SCOUT_STATUS_TIMEOUT"
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return False, "ROSLAUNCH_EXITED_DURING_STATUS_CHECK"
            rc, out, _ = _run_capture(
                ROSTOPIC_SCOUT_STATUS_ARGS, GENERIC_CMD_TIMEOUT, _ros_subprocess_env()
            )
            if rc == 0 and out:
                control_mode = _parse_field(out, "control_mode")
                fault_code = _parse_field(out, "fault_code")
                if control_mode is not None and fault_code is not None:
                    if control_mode == "1" and fault_code == "0":
                        return True, ""
                    last_reason = (
                        "SCOUT_STATUS_UNHEALTHY: control_mode=%s fault_code=%s"
                        % (control_mode, fault_code)
                    )
            time.sleep(SCOUT_STATUS_POLL_INTERVAL)
        return False, last_reason

    def _safe_terminate_proc(self, proc: subprocess.Popen) -> None:
        """尽力终止单个 Popen 句柄; 异常仅记录, 不抛出。"""
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.wait(timeout=1.0)
                    except Exception:
                        pass
        except Exception as exc:
            LOGGER.warning("base_mode: 终止单进程异常: %s", exc)

    def _terminate_record(self, record: _SubprocessRecord) -> None:
        """整组 kill 自己启动的进程; 异常仅记录, 不抛出。"""
        try:
            os.killpg(record.pgid, 15)  # SIGTERM
        except ProcessLookupError:
            pass
        except OSError as exc:
            LOGGER.warning("base_mode: killpg 异常: %s", exc)

        try:
            record.proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(record.pgid, 9)  # SIGKILL
            except ProcessLookupError:
                pass
            except OSError as exc:
                LOGGER.warning("base_mode: killpg -9 异常: %s", exc)
            try:
                record.proc.wait(timeout=2.0)
            except Exception as exc:
                LOGGER.warning("base_mode: wait 进程退出异常: %s", exc)
        except Exception as exc:
            LOGGER.warning("base_mode: wait 子进程异常: %s", exc)

    def _snapshot_locked(self) -> dict:
        return {
            "mode": self._mode,
            "modeLabel": _MODE_LABELS.get(self._mode, self._mode),
            "navState": _nav_state_safe(),
            "ready": self._ready,
            "reason": self._reason,
            "teleopEnabled": _teleop_enabled_safe(),
            "managedScoutRunning": self._managed_scout is not None
            and self._managed_scout.proc.poll() is None,
        }


# --- regex helpers ---------------------------------------------------------

_FIELD_RE = re.compile(
    r"(?:^|\s)(control_mode|fault_code)\s*[:=]\s*(-?\d+)", re.IGNORECASE
)


def _parse_field(out: str, name: str) -> Optional[str]:
    if not out:
        return None
    for key, value in _FIELD_RE.findall(out):
        if key.lower() == name.lower():
            return value
    return None


def _run_capture(args: list[str], timeout: float, env: Optional[dict] = None) -> tuple[int, str, str]:
    """``shell=False`` 执行命令并捕获输出; 统一异常收敛为 ``(rc, out, err)``。

    ``env`` 为可选环境变量字典;ROS CLI 调用应传入 ``_ros_subprocess_env()``
    以确保 ROS python3 dist-packages 位于 ``PYTHONPATH``。``ip`` 等系统命令
    无需特殊 env,保持 ``None`` 即可。
    """
    run_kwargs: dict = dict(
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
    )
    if env is not None:
        run_kwargs["env"] = env
    try:
        completed = subprocess.run(args, **run_kwargs)  # noqa: S603 - shell=False, 参数数组
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as exc:
        return 127, "", str(exc)
    except Exception as exc:
        return 1, "", str(exc)
    return (
        int(completed.returncode),
        str(completed.stdout or ""),
        str(completed.stderr or ""),
    )


# --- singletons / router ---------------------------------------------------

base_mode_manager = BaseModeManager()

router = APIRouter(prefix="/api/base_mode", tags=["底盘模式"])


@router.get("/status", response_model=ApiResponse)
def base_mode_status() -> ApiResponse:
    return base_mode_manager.status()


@router.api_route("/switch", methods=["GET", "POST"], response_model=ApiResponse)
def base_mode_switch(mode: str = Query(..., description="none | scout | go2")) -> ApiResponse:
    return base_mode_manager.switch(mode)
