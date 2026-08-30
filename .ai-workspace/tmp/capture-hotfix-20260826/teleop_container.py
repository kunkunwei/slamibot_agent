** WARNING: connection is not using a post-quantum key exchange algorithm.
** This session may be vulnerable to "store now, decrypt later" attacks.
** The server may need to be upgraded. See https://openssh.com/pq.html
"""APP joystick safe-control link for ROS1 Noetic.

APP publishes ``/cmd_vel_web`` (``geometry_msgs/Twist``) at roughly
10 Hz; we forward the sanitised linear/angular components to
``/cmd_vel`` at a continuous ``outputHz`` (default 50 Hz, override via
``TELEOP_OUTPUT_HZ``; the rate is clamped to ``MIN_OUTPUT_HZ`` so we
never drop below the Scout ugv_sdk ``AgilexBase::SendMotionCommand``
requirement of >= 50 Hz). Forwarding is suppressed unless the HTTP
endpoint ``/api/teleop_key/enable?enabled=true`` has armed the link.

State machine:

* ``disabled`` (default): drop any non-zero input from ``/cmd_vel_web``;
  the publisher thread stays idle and never emits to ``/cmd_vel``.
* ``enabled``: a publisher thread re-emits the most recent valid
  non-zero command to ``/cmd_vel`` at ``outputHz`` as long as fresh
  input keeps arriving. A watchdog publishes a single zero ``Twist``
  (then latches ``_watchdog_triggered``) if no fresh command arrives
  within ``TELEOP_WATCHDOG_SECONDS``; the latch prevents flooding
  ``/cmd_vel`` with identical zeros on subsequent ticks. Explicit zero
  inputs clear ``active`` immediately and trigger a direct zero publish
  so the chassis receives the stop within callback latency.

When transitioning to ``enabled`` while navigation is non-IDLE, we
first call ``/nav_multi/pause``. We remember whether we did so and, on
``disable``, only call ``/nav_multi/resume`` if we were the ones who
paused it.

Contract with ``ros_client``:
``subscribe_teleop`` / ``unsubscribe_teleop`` / ``publish_cmd_vel`` all
return ``(bool, str)``. Every caller must inspect the success flag and
log a warning on failure — silently dropping the tuple is a bug.
"""

import logging
import math
import os
import threading
import time
from typing import Optional

from fastapi import APIRouter, Query

from .mcp_compat import MCPServer
from .models import ApiResponse, fail, ok
from .ros_client import ros_client


LOGGER = logging.getLogger(__name__)


TELEOP_INPUT_TOPIC = "/cmd_vel_web"
TELEOP_OUTPUT_TOPIC = "/cmd_vel"

DEFAULT_MAX_LINEAR = 0.5
DEFAULT_MAX_ANGULAR = 0.5
DEFAULT_WATCHDOG_SECONDS = 0.4
MIN_WATCHDOG_SECONDS = 0.05

# Scout ugv_sdk ``AgilexBase::SendMotionCommand`` 注释要求命令频率
# >= 50 Hz;为避免误配置导致 Scout 不执行,``outputHz`` 下限锁死在
# ``MIN_OUTPUT_HZ``,``TELEOP_OUTPUT_HZ`` 只允许上调。
DEFAULT_OUTPUT_HZ = 50.0
MIN_OUTPUT_HZ = 50.0


def _read_float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        LOGGER.warning("teleop: %s 无效,使用默认 %.3f", name, default)
        return default
    if not math.isfinite(value):
        LOGGER.warning("teleop: %s 非有限值,使用默认 %.3f", name, default)
        return default
    return value


class TeleopController:
    """Owns the enable state, watchdog and message-forwarding plumbing."""

    def __init__(self) -> None:
        self._enabled = False
        self._nav_was_paused = False
        self._last_msg_time: Optional[float] = None
        # 最近一次通过 NaN/Inf 与限速校验后的有效 Twist 分量;
        # publisher 线程据此持续以 ``outputHz`` 复发到 /cmd_vel。
        self._last_linear: float = 0.0
        self._last_angular: float = 0.0
        self._watchdog_triggered = False
        self._active = False
        self._attached = False
        self._lock = threading.RLock()
        # 限速/角速配置必须非负,负值通过 max(0, value) 收敛到 0,
        # 避免 clamp(min,max) 在 max<min 时反向翻转符号。
        self._max_linear = max(
            0.0, _read_float_env("TELEOP_MAX_LINEAR", DEFAULT_MAX_LINEAR)
        )
        self._max_angular = max(
            0.0, _read_float_env("TELEOP_MAX_ANGULAR", DEFAULT_MAX_ANGULAR)
        )
        watchdog_raw = _read_float_env(
            "TELEOP_WATCHDOG_SECONDS", DEFAULT_WATCHDOG_SECONDS
        )
        self._watchdog_seconds = max(MIN_WATCHDOG_SECONDS, watchdog_raw)
        output_hz_raw = _read_float_env(
            "TELEOP_OUTPUT_HZ", DEFAULT_OUTPUT_HZ
        )
        # 下限钳制:即便运维误把 ``TELEOP_OUTPUT_HZ`` 配成小于 50 Hz,
        # 也不能让 Scout 收不到足够频率的命令而拒绝执行。
        self._output_hz = max(MIN_OUTPUT_HZ, output_hz_raw)
        self._publisher_stop = threading.Event()
        self._publisher_thread: Optional[threading.Thread] = None

    # --- lifecycle -----------------------------------------------------

    def attach(self) -> None:
        """Subscribe to the APP command topic. Safe to call once at startup.

        重复 attach 不会产生重复订阅;订阅失败时仍可启动 publisher
        线程,但 ``_attached`` 保持 ``False`` 以便 status 反映真实状态。
        """
        with self._lock:
            if self._attached:
                LOGGER.debug("teleop: 已附着,跳过重复订阅")
            else:
                ok_sub, msg_sub = ros_client.subscribe_teleop(self._on_twist)
                if ok_sub:
                    self._attached = True
                    LOGGER.info(
                        "teleop: 已订阅 %s, 限速 linear=%.3f angular=%.3f "
                        "watchdog=%.3fs output=%.1fHz",
                        TELEOP_INPUT_TOPIC,
                        self._max_linear,
                        self._max_angular,
                        self._watchdog_seconds,
                        self._output_hz,
                    )
                else:
                    LOGGER.warning(
                        "teleop: 订阅 %s 失败: %s", TELEOP_INPUT_TOPIC, msg_sub
                    )

            # 订阅成败都启动 publisher 线程,确保 disabled→enabled 后
            # 周期转发与超时零速保护同时生效(订阅恢复后即可转发)。
            self._publisher_stop.clear()
            if self._publisher_thread is None or not self._publisher_thread.is_alive():
                self._publisher_thread = threading.Thread(
                    target=self._publisher_loop,
                    name="teleop-publisher",
                    daemon=True,
                )
                try:
                    self._publisher_thread.start()
                except Exception as exc:
                    LOGGER.warning("teleop: publisher 线程启动失败: %s", exc)

    def _publisher_loop(self) -> None:
        """以 ``outputHz`` 周期调用 ``_publisher_tick``。"""
        period = 1.0 / max(MIN_OUTPUT_HZ, self._output_hz)
        while not self._publisher_stop.wait(period):
            try:
                self._publisher_tick()
            except Exception as exc:
                LOGGER.warning("teleop: publisher tick 异常: %s" % exc)

    def shutdown(self) -> None:
        """Force-disable, publish zero, drop subscription.

        顺序:设置 stop event → 短暂 join publisher(避免自 join,安全捕获)
        → 标记 disabled → 发布零速(检查返回) → 取消订阅(检查返回)。
        """
        try:
            self._publisher_stop.set()
        except Exception:
            pass

        try:
            thread = self._publisher_thread
            current = threading.current_thread()
            if (
                thread is not None
                and thread.is_alive()
                and thread is not current
            ):
                thread.join(timeout=0.5)
        except Exception as exc:
            LOGGER.warning("teleop: shutdown join publisher 异常: %s" % exc)

        try:
            with self._lock:
                self._enabled = False
                self._last_msg_time = None
                self._last_linear = 0.0
                self._last_angular = 0.0
                self._watchdog_triggered = False
                self._active = False

            try:
                ok_zero, msg_zero = ros_client.publish_cmd_vel(0.0, 0.0)
                if not ok_zero:
                    LOGGER.warning(
                        "teleop: shutdown 发布零速失败: %s", msg_zero
                    )
            except Exception as exc:
                LOGGER.warning("teleop: shutdown 发布零速异常: %s" % exc)

            try:
                ok_unsub, msg_unsub = ros_client.unsubscribe_teleop()
                if not ok_unsub:
                    LOGGER.warning("teleop: 取消订阅失败: %s" % msg_unsub)
            except Exception as exc:
                LOGGER.warning("teleop: 取消订阅异常: %s" % exc)

            with self._lock:
                self._attached = False
                self._nav_was_paused = False
        except Exception as exc:
            LOGGER.warning("teleop: shutdown 异常: %s" % exc)

    # --- HTTP-facing actions ------------------------------------------

    def enable(self) -> ApiResponse:
        """Arm the link; auto-pause navigation if needed."""
        # 模式互斥守卫:必须在 rosbridge/nav pause/状态改变之前执行,
        # 且必须 lazy import,因为 base_mode 顶层已导入 teleop_controller,
        # 顶层 import 会形成循环依赖。
        from .base_mode import base_mode_manager
        try:
            allowed, reason = base_mode_manager.can_enable_teleop()
        except Exception as exc:
            LOGGER.warning("teleop: base_mode 守卫异常: %s" % exc)
            return fail("base_mode 守卫检查失败: %s" % exc)
        if not allowed:
            return fail("底盘模式不允许启用遥操作: %s" % reason)

        if not ros_client.is_connected:
            return fail("rosbridge 未连接,无法启用遥操作")
        with self._lock:
            if self._enabled:
                return ok(self._status_payload(), "teleop 已启用")

        nav_state = ""
        try:
            nav_state = str(ros_client.get_nav_status().get("state", "") or "")
        except Exception as exc:
            LOGGER.warning("teleop: 获取导航状态失败: %s" % exc)

        paused_by_us = False
        if nav_state and nav_state != "IDLE":
            try:
                ok_pause, msg_pause = ros_client.pause_nav()
            except Exception as exc:
                return fail("暂停导航失败: %s" % exc)
            if not ok_pause:
                return fail(
                    "无法暂停当前导航(%s),拒绝启用遥操作: %s"
                    % (nav_state, msg_pause)
                )
            paused_by_us = True

        try:
            with self._lock:
                self._enabled = True
                self._nav_was_paused = paused_by_us
                self._last_msg_time = None
                self._last_linear = 0.0
                self._last_angular = 0.0
                self._watchdog_triggered = False
                self._active = False
            return ok(self._status_payload(), "teleop 已启用")
        except Exception as exc:
            LOGGER.warning("teleop: 启用时异常: %s" % exc)
            return fail("启用 teleop 失败: %s" % exc)

    def disable(self) -> ApiResponse:
        """Disarm, send zero, resume navigation if we previously paused it.

        契约:即使当前已经 disabled,也必须尽力发布一次零 Twist;
        不允许提前 return 跳过零速发布。
        """
        need_resume = False
        try:
            with self._lock:
                # 注意:不要在已 disabled 时提前 return,否则会跳过零速。
                need_resume = self._nav_was_paused
                self._enabled = False
                self._nav_was_paused = False
                self._last_msg_time = None
                self._last_linear = 0.0
                self._last_angular = 0.0
                self._watchdog_triggered = False
                self._active = False
        except Exception as exc:
            LOGGER.warning("teleop: disable 状态切换异常: %s" % exc)

        try:
            ok_zero, msg_zero = ros_client.publish_cmd_vel(0.0, 0.0)
            if not ok_zero:
                LOGGER.warning("teleop: disable 发布零速失败: %s" % msg_zero)
        except Exception as exc:
            LOGGER.warning("teleop: disable 发布零速异常: %s" % exc)

        if need_resume:
            try:
                ok_resume, msg_resume = ros_client.resume_nav()
                if not ok_resume:
                    LOGGER.warning(
                        "teleop: 恢复导航失败: %s" % msg_resume
                    )
            except Exception as exc:
                LOGGER.warning("teleop: 恢复导航异常: %s" % exc)

        return ok(self._status_payload(), "teleop 已禁用")

    def status(self) -> ApiResponse:
        return ok(self._status_payload())

    def _status_payload(self) -> dict:
        with self._lock:
            return {
                "enabled": self._enabled,
                "active": self._active,
                "attached": self._attached,
                "rosbridgeConnected": ros_client.is_connected,
                "watchdogSeconds": self._watchdog_seconds,
                "maxLinear": self._max_linear,
                "maxAngular": self._max_angular,
                "outputHz": self._output_hz,
                "navPausedByTeleop": self._nav_was_paused,
            }

    # --- message handling --------------------------------------------

    def _on_twist(self, message: dict) -> None:
        """rosbridge callback for ``/cmd_vel_web``.

        仅做 NaN/Inf + 限速校验并缓存最近一次有效 Twist;
        周期发布与 watchdog 由 ``_publisher_tick`` 统一承担,避免
        callback 与输出线程在同一 tick 重复发竞争。显式零 Twist
        为了保证底盘尽快收到停机命令,仍在本回调直接 publish 一次
        零速并清空 ``_active``。
        """
        try:
            linear = float(message.get("linear", {}).get("x", 0.0) or 0.0)
        except (TypeError, ValueError):
            linear = 0.0
        try:
            angular = float(message.get("angular", {}).get("z", 0.0) or 0.0)
        except (TypeError, ValueError):
            angular = 0.0

        if not (math.isfinite(linear) and math.isfinite(angular)):
            LOGGER.debug(
                "teleop: 收到非法分量,已丢弃: linear=%s angular=%s",
                linear,
                angular,
            )
            return

        now = time.monotonic()
        with self._lock:
            enabled = self._enabled

        if not enabled:
            # Drop non-zero input while disabled; allow explicit zero
            # forwarding too (so a release can reset the chassis).
            if abs(linear) > 0.0 or abs(angular) > 0.0:
                LOGGER.debug("teleop: 禁用状态下丢弃非零输入")
                return
            # Even zero messages reset the watchdog bookkeeping so that
            # enabling right after a release behaves deterministically.
            with self._lock:
                self._last_msg_time = now
                self._last_linear = 0.0
                self._last_angular = 0.0
                self._watchdog_triggered = False
                self._active = False
            return

        clamped_linear = max(-self._max_linear, min(self._max_linear, linear))
        clamped_angular = max(-self._max_angular, min(self._max_angular, angular))

        is_nonzero = abs(clamped_linear) > 0.0 or abs(clamped_angular) > 0.0

        if not is_nonzero:
            # enabled 状态收到显式零 Twist:直接发布零速并清空 active。
            # publisher 线程本身不会复发零(避免 /cmd_vel 洪水),所以
            # 必须由 callback 兜底,保证底盘在 callback 延迟内收到停机。
            try:
                ok_pub, msg_pub = ros_client.publish_cmd_vel(0.0, 0.0)
            except Exception as exc:
                LOGGER.warning("teleop: 显式零速发布异常: %s", exc)
                ok_pub, msg_pub = False, str(exc)
            if not ok_pub:
                LOGGER.warning(
                    "teleop: 显式零速发布失败: %s", msg_pub
                )
            with self._lock:
                self._last_linear = clamped_linear
                self._last_angular = clamped_angular
                self._last_msg_time = now
                self._watchdog_triggered = False
                self._active = False
            return

        # 非零输入:缓存最新分量与时间戳,具体发布交给 publisher 线程,
        # 以保证 /cmd_vel 长期稳定 >= ``outputHz``,满足 Scout 的频率要求。
        # 线程安全:lock 仅保护状态读写,publisher 在锁外调用 ROS 客户端,
        # 避免 callback 与 publisher 互斥时阻塞 ROS 发送。
        with self._lock:
            self._last_linear = clamped_linear
            self._last_angular = clamped_angular
            self._last_msg_time = now
            self._watchdog_triggered = False
            self._active = True

    def _publisher_tick(self) -> None:
        """周期 tick:按状态决定是否复发或触发 watchdog 零速。

        语义矩阵:

        * disabled:直接 return,publisher 不发任何消息。
        * 尚未收到过任何 Twist(_last_msg_time 为 None):return。
        * 当前时间 - last_msg_time >= watchdog:发布一次零速并 latch
          ``_watchdog_triggered``/``_active=False``;后续 tick 因 latch
          不再发零,避免 /cmd_vel 洪水。
        * 仍有新鲜输入:若 latch 未清则清掉(超时之后再次有输入即可恢复
          正常转发);仅在最近命令非零时重新 publish,避免零速反复发。
        """
        now = time.monotonic()
        with self._lock:
            enabled = self._enabled
            last_time = self._last_msg_time
            last_linear = self._last_linear
            last_angular = self._last_angular
            timeout = self._watchdog_seconds
            already_triggered = self._watchdog_triggered

        if not enabled:
            return
        if last_time is None:
            # We never received anything yet; nothing to do.
            return

        if now - last_time >= timeout:
            if already_triggered:
                return
            try:
                ok_pub, msg_pub = ros_client.publish_cmd_vel(0.0, 0.0)
            except Exception as exc:
                LOGGER.warning("teleop: watchdog 零速发布异常: %s" % exc)
                return
            if not ok_pub:
                LOGGER.warning(
                    "teleop: watchdog 零速发布失败: %s", msg_pub
                )
                return

            with self._lock:
                # 防止我们在读取 last_time 与 publish 之间收到了新输入
                # 导致误把尚未真正超时的链路置为 inactive。
                if (
                    self._enabled
                    and self._last_msg_time is not None
                    and now - self._last_msg_time >= timeout
                    and not self._watchdog_triggered
                ):
                    self._watchdog_triggered = True
                    self._active = False
            return

        # 仍在 watchdog 窗口内:清掉陈旧的 watchdog latch,使 timeout
        # 之后再收到输入可以立即恢复转发。
        if already_triggered:
            with self._lock:
                if self._watchdog_triggered:
                    self._watchdog_triggered = False

        # 跳过零速复发:显式零已经在 callback 里直接发过,这里再发会
        # 把 /cmd_vel 灌满重复的零 Twist;非零命令则持续以 outputHz 转发。
        if abs(last_linear) > 0.0 or abs(last_angular) > 0.0:
            try:
                ok_pub, msg_pub = ros_client.publish_cmd_vel(
                    last_linear, last_angular
                )
            except Exception as exc:
                LOGGER.warning("teleop: 周期发布异常: %s", exc)
                return
            if not ok_pub:
                LOGGER.warning(
                    "teleop: 周期发布失败: %s", msg_pub
                )
                return


teleop_controller = TeleopController()


router = APIRouter(prefix="/api/teleop_key", tags=["遥操作"])


def register_mcp_tools(mcp: MCPServer) -> None:
    mcp.tool(name="teleop_enable")(enable)
    mcp.tool(name="teleop_disable")(disable)
    mcp.tool(name="teleop_status")(status)


def enable() -> ApiResponse:
    """MCP tool wrapper for teleop_controller.enable()."""
    return teleop_controller.enable()


def disable() -> ApiResponse:
    """MCP tool wrapper for teleop_controller.disable()."""
    return teleop_controller.disable()


def status() -> ApiResponse:
    """MCP tool wrapper for teleop_controller.status()."""
    return teleop_controller.status()


@router.get("/enable", response_model=ApiResponse)
def teleop_enable(
    enabled: str = Query("false", description="true | false")
) -> ApiResponse:
    """APP 在首次非零输入时异步调 ``enabled=true``;页面关闭时调 ``false``。"""
    flag = str(enabled).lower() in ("1", "true", "yes", "on")
    if flag:
        return teleop_controller.enable()
    return teleop_controller.disable()


@router.get("/status", response_model=ApiResponse)
def teleop_status() -> ApiResponse:
    return teleop_controller.status()
