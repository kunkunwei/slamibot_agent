"""Safety-critical coordination for manual takeover and mapping mode."""

import logging
import threading
from typing import Callable

from . import process_manager
from .control_ownership import (
    OWNER_MANUAL,
    OWNER_MANUAL_PENDING,
    OWNER_MAPPING,
    OWNER_MAPPING_PENDING,
    claim,
    snapshot,
)
from .models import ApiResponse, fail, ok
from .ros_client import ros_client
from .teleop import teleop_controller


LOGGER = logging.getLogger(__name__)
_transition_lock = threading.RLock()


def _attempt(name: str, action: Callable[[], tuple[bool, str]], result: dict) -> bool:
    try:
        success, message = action()
    except Exception as exc:
        success, message = False, str(exc)
    result["steps"][name] = {"success": bool(success), "message": str(message or "")}
    if not success:
        result["warnings"].append("%s: %s" % (name, message or "failed"))
    return bool(success)


def _cancel_navigation(result: dict) -> bool:
    service_ok = _attempt("navigationTaskCancelled", ros_client.cancel_nav, result)
    _attempt("moveBaseGoalsCancelled", ros_client.cancel_move_base_goals, result)

    stopped = service_ok
    if not stopped:
        try:
            nav_state = str(ros_client.get_nav_status().get("state") or "").upper()
        except Exception as exc:
            nav_state = ""
            result["warnings"].append("navigationStatusChecked: %s" % exc)
        idle = nav_state == "IDLE"
        result["steps"]["navigationStatusChecked"] = {
            "success": idle,
            "message": nav_state or "UNKNOWN",
        }
        if idle:
            stopped = True
        else:
            stopped = _attempt(
                "navigationProcessStopped",
                process_manager.stop_navigation,
                result,
            )

    result["navigationCancelled"] = stopped
    return stopped


def force_manual_takeover() -> ApiResponse:
    """Best-effort stop automatic navigation, then grant teleop ownership."""
    with _transition_lock:
        ownership = claim(OWNER_MANUAL_PENDING)
        result = {
            "targetMode": "manual",
            "ownership": ownership,
            "navigationCancelled": False,
            "zeroVelocityPublished": False,
            "teleopEnabled": False,
            "mappingStarted": False,
            "steps": {},
            "warnings": [],
        }
        _cancel_navigation(result)
        result["zeroVelocityPublished"] = _attempt(
            "zeroVelocityPublished",
            lambda: ros_client.publish_cmd_vel(0.0, 0.0),
            result,
        )
        try:
            response = teleop_controller.force_enable()
            enabled = bool(getattr(response, "success", False))
            message = str(getattr(response, "msg", "") or "")
        except Exception as exc:
            enabled, message = False, str(exc)
        result["steps"]["teleopEnabled"] = {"success": enabled, "message": message}
        result["teleopEnabled"] = enabled
        if not enabled:
            result["warnings"].append("teleopEnabled: %s" % (message or "failed"))
            result["ownership"] = snapshot()
            return fail("强制手动接管失败: %s" % (message or "teleop 未启用"), result)
        if not result["navigationCancelled"]:
            result["ownership"] = snapshot()
            return fail("强制手动接管未能确认自动导航已停止", result)
        result["ownership"] = claim(OWNER_MANUAL)
        message = "已强制切换到手动遥控"
        if result["warnings"]:
            message += "（自动导航停止存在警告）"
        return ok(result, message)


def force_mapping_mode() -> ApiResponse:
    """Stop all motion sources before switching the managed processes to mapping."""
    with _transition_lock:
        ownership = claim(OWNER_MAPPING_PENDING)
        result = {
            "targetMode": "mapping",
            "ownership": ownership,
            "navigationCancelled": False,
            "zeroVelocityPublished": False,
            "teleopEnabled": False,
            "mappingStarted": False,
            "steps": {},
            "warnings": [],
        }
        _cancel_navigation(result)
        result["zeroVelocityPublished"] = _attempt(
            "zeroVelocityPublished",
            lambda: ros_client.publish_cmd_vel(0.0, 0.0),
            result,
        )
        try:
            disable_response = teleop_controller.disable(
                resume_navigation=False,
                claim_auto=False,
            )
            disabled = bool(getattr(disable_response, "success", False))
            disable_message = str(getattr(disable_response, "msg", "") or "")
        except Exception as exc:
            disabled, disable_message = False, str(exc)
        result["steps"]["teleopDisabled"] = {
            "success": disabled,
            "message": disable_message,
        }
        if not disabled:
            result["warnings"].append("teleopDisabled: %s" % (disable_message or "failed"))

        mapping_ok = _attempt("mappingStarted", process_manager.switch_to_mapping, result)
        result["mappingStarted"] = mapping_ok
        result["launchStatus"] = process_manager.get_status()
        if not mapping_ok:
            result["ownership"] = snapshot()
            return fail("切换建图模式失败，导航已保持停止", result)
        result["ownership"] = claim(OWNER_MAPPING)
        message = "已强制切换到建图模式"
        if result["warnings"]:
            message += "（停止旧导航存在警告）"
        return ok(result, message)
