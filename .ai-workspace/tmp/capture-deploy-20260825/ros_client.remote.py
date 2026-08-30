"""ROS 1 access from Python 3.10+ through rosbridge/roslibpy."""

import logging
import os
import json
import threading
from typing import Any, Callable, Optional, Tuple

import roslibpy


LOGGER = logging.getLogger(__name__)


class RosbridgeClient:
    """Keep a rosbridge connection and cache the latest AMCL pose."""

    def __init__(self) -> None:
        self._ros = roslibpy.Ros(
            host=os.environ.get("ROSBRIDGE_HOST", "127.0.0.1"),
            port=int(os.environ.get("ROSBRIDGE_PORT", "19090")),
        )
        self._pose_topic: Optional[roslibpy.Topic] = None
        self._topics: list[roslibpy.Topic] = []
        self._transport_running = False
        self._latest_pose: Optional[dict[str, float]] = None
        self._latest_nav_status: dict[str, Any] = {}
        self._latest_scout_status: Optional[dict[str, Any]] = None
        self._latest_bms_status: Optional[dict[str, Any]] = None
        self._latest_battery: Optional[dict[str, Any]] = None
        self._cmd_vel_topic: Optional[roslibpy.Topic] = None
        self._teleop_topic: Optional[roslibpy.Topic] = None
        self._point_arrived_handler: Optional[Callable[[dict[str, Any]], None]] = None
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return bool(self._ros.is_connected)

    def start(self) -> None:
        """Connect without preventing HTTP startup when ROS is unavailable."""
        try:
            self._ros.run(timeout=3)
            self._transport_running = True
        except Exception as exc:
            LOGGER.warning("rosbridge unavailable; ROS endpoints start degraded: %s", exc)
            self._ros.terminate()
            return

        self._pose_topic = roslibpy.Topic(
            self._ros,
            "/amcl_pose",
            "geometry_msgs/PoseWithCovarianceStamped",
        )
        self._pose_topic.subscribe(self._on_pose)
        self._topics = [
            self._pose_topic,
            self._subscribe(
                "/nav_multi/status", "std_msgs/String", self._on_nav_status
            ),
            self._subscribe(
                "/scout_status", "scout_msgs/ScoutStatus", self._on_scout_status
            ),
            self._subscribe(
                "/BMS_status", "scout_msgs/ScoutBmsStatus", self._on_bms_status
            ),
            self._subscribe(
                "/battery", "sensor_msgs/BatteryState", self._on_battery
            ),
            self._subscribe(
                "/nav_multi/point_arrived", "std_msgs/String", self._on_point_arrived
            ),
        ]
        LOGGER.info("connected to rosbridge")

    def stop(self) -> None:
        for topic in self._topics:
            topic.unsubscribe()
        with self._lock:
            if self._teleop_topic is not None:
                try:
                    self._teleop_topic.unsubscribe()
                except Exception as exc:
                    LOGGER.warning("ros_client: 取消 teleop 订阅失败: %s", exc)
                self._teleop_topic = None
            self._cmd_vel_topic = None
        if self._transport_running:
            self._ros.terminate()
            self._transport_running = False

    def _on_pose(self, message: dict[str, Any]) -> None:
        pose = message["pose"]["pose"]
        position = pose["position"]
        orientation = pose["orientation"]
        value = {
            "positionX": float(position["x"]),
            "positionY": float(position["y"]),
            "positionZ": float(position["z"]),
            "orientationX": float(orientation["x"]),
            "orientationY": float(orientation["y"]),
            "orientationZ": float(orientation["z"]),
            "orientationW": float(orientation["w"]),
        }
        with self._lock:
            self._latest_pose = value

    def _subscribe(self, name: str, message_type: str, callback) -> roslibpy.Topic:
        topic = roslibpy.Topic(self._ros, name, message_type)
        topic.subscribe(callback)
        return topic

    def _on_nav_status(self, message: dict[str, Any]) -> None:
        try:
            value = json.loads(message["data"])
        except (KeyError, TypeError, ValueError):
            return
        with self._lock:
            self._latest_nav_status = value

    def _on_point_arrived(self, message: dict[str, Any]) -> None:
        try:
            event = json.loads(message["data"])
        except (KeyError, TypeError, ValueError):
            LOGGER.warning("invalid /nav_multi/point_arrived payload: %s", message)
            return
        if not isinstance(event, dict):
            LOGGER.warning("invalid /nav_multi/point_arrived event: %s", event)
            return
        with self._lock:
            handler = self._point_arrived_handler
        if handler is None:
            return
        try:
            handler(event)
        except Exception:
            LOGGER.exception("point-arrival handler failed: %s", event)

    def set_point_arrived_handler(
        self, handler: Optional[Callable[[dict[str, Any]], None]]
    ) -> None:
        with self._lock:
            self._point_arrived_handler = handler

    def _on_scout_status(self, message: dict[str, Any]) -> None:
        with self._lock:
            self._latest_scout_status = message

    def _on_bms_status(self, message: dict[str, Any]) -> None:
        with self._lock:
            self._latest_bms_status = message

    def _on_battery(self, message: dict[str, Any]) -> None:
        with self._lock:
            self._latest_battery = message

    def get_current_pose(self) -> Tuple[Optional[dict[str, float]], str]:
        if not self.is_connected:
            return None, "rosbridge 未连接"
        with self._lock:
            pose = dict(self._latest_pose) if self._latest_pose else None
        if pose is None:
            return None, "尚未收到 /amcl_pose"
        return pose, "success"

    def _call_service(
        self, name: str, service_type: str, values: Optional[dict] = None
    ) -> Tuple[bool, str]:
        if not self.is_connected:
            return False, "rosbridge 未连接"
        try:
            service = roslibpy.Service(self._ros, name, service_type)
            result = service.call(roslibpy.ServiceRequest(values or {}), timeout=3)
            if "success" in result:
                return bool(result["success"]), result.get("message", "")
            return True, "success"
        except Exception as exc:
            return False, "ROS service 调用失败: %s" % exc

    def set_initial_pose(
        self,
        x: float,
        y: float,
        z: float,
        qx: float,
        qy: float,
        qz: float,
        qw: float,
    ) -> Tuple[bool, str]:
        if not self.is_connected:
            return False, "rosbridge 未连接"
        topic = roslibpy.Topic(
            self._ros, "/initialpose", "geometry_msgs/PoseWithCovarianceStamped"
        )
        message = {
            "header": {"frame_id": "map"},
            "pose": {
                "pose": {
                    "position": {"x": x, "y": y, "z": z},
                    "orientation": {"x": qx, "y": qy, "z": qz, "w": qw},
                },
                "covariance": [
                    0.25, 0, 0, 0, 0, 0,
                    0, 0.25, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0.068,
                ],
            },
        }
        try:
            topic.publish(roslibpy.Message(message))
            return True, "设置初始位姿成功"
        except Exception as exc:
            return False, "发布初始位姿失败: %s" % exc

    def trigger_global_localization(self) -> Tuple[bool, str]:
        success, message = self._call_service(
            "/global_localization", "std_srvs/Empty"
        )
        if success:
            message = "重定位已触发,请移动机器人使粒子收敛"
        return success, message

    def start_nav_task(
        self, task_id: int, task_name: str, points: list[dict]
    ) -> Tuple[bool, str]:
        payload = json.dumps(
            {"taskId": task_id, "taskName": task_name, "points": points},
            ensure_ascii=False,
        )
        return self._call_service(
            "/nav_multi/execute", "nav_api/NavCommand", {"data": payload}
        )

    def pause_nav(self) -> Tuple[bool, str]:
        return self._call_service("/nav_multi/pause", "std_srvs/Trigger")

    def resume_nav(self) -> Tuple[bool, str]:
        return self._call_service("/nav_multi/resume", "std_srvs/Trigger")

    def cancel_nav(self) -> Tuple[bool, str]:
        return self._call_service("/nav_multi/cancel", "std_srvs/Trigger")

    def next_nav_point(self) -> Tuple[bool, str]:
        # 推进到下一站:约定 ROS 端 std_srvs/Trigger 服务 /nav_multi/next。
        # 当 ROS 包尚未实现该 service 时,会失败并返回错误信息,
        # 由 HTTP 层透传给前端(不再 404)。
        return self._call_service("/nav_multi/next", "std_srvs/Trigger")

    def end_nav(self) -> Tuple[bool, str]:
        # 结束当前导航任务:约定 ROS 端 std_srvs/Trigger 服务 /nav_multi/end。
        return self._call_service("/nav_multi/end", "std_srvs/Trigger")

    def passage_nav(self) -> Tuple[bool, str]:
        # 放行/通过当前关卡:约定 ROS 端 std_srvs/Trigger 服务 /nav_multi/passage。
        return self._call_service("/nav_multi/passage", "std_srvs/Trigger")

    def patch_pcd(self, map_name: str) -> Tuple[bool, str]:
        # 局部补图:约定 ROS 端 std_srvs/Trigger 服务 /map_patch,
        # 传 map_name 字段;ROS 端未实现时返回失败信息,由 HTTP 层透传。
        return self._call_service(
            "/map_patch", "std_srvs/Trigger",
            values={"map_name": map_name},
        )

    def subscribe_teleop(self, callback) -> Tuple[bool, str]:
        """Subscribe to APP ``/cmd_vel_web``; replaces any prior subscription."""
        if not self.is_connected:
            return False, "rosbridge 未连接"
        try:
            topic = roslibpy.Topic(self._ros, "/cmd_vel_web", "geometry_msgs/Twist")
            topic.subscribe(callback)
            with self._lock:
                if self._teleop_topic is not None:
                    try:
                        self._teleop_topic.unsubscribe()
                    except Exception as exc:
                        LOGGER.warning("ros_client: 旧 teleop 订阅取消失败: %s", exc)
                self._teleop_topic = topic
            return True, "success"
        except Exception as exc:
            return False, "订阅 /cmd_vel_web 失败: %s" % exc

    def unsubscribe_teleop(self) -> Tuple[bool, str]:
        """Tear down the current ``/cmd_vel_web`` subscription if any."""
        with self._lock:
            topic = self._teleop_topic
            self._teleop_topic = None
        if topic is None:
            return True, "success"
        if not self.is_connected:
            return True, "success"
        try:
            topic.unsubscribe()
            return True, "success"
        except Exception as exc:
            return False, "取消 /cmd_vel_web 订阅失败: %s" % exc

    def publish_cmd_vel(self, linear_x: float, angular_z: float) -> Tuple[bool, str]:
        """Publish a sanitised ``geometry_msgs/Twist`` to ``/cmd_vel``.

        ``linear.x`` 与 ``angular.z`` 之外的字段统一置零。
        """
        if not self.is_connected:
            return False, "rosbridge 未连接"
        message = {
            "linear": {"x": float(linear_x), "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": float(angular_z)},
        }
        with self._lock:
            topic = self._cmd_vel_topic
            if topic is None:
                try:
                    topic = roslibpy.Topic(self._ros, "/cmd_vel", "geometry_msgs/Twist")
                    self._cmd_vel_topic = topic
                except Exception as exc:
                    return False, "创建 /cmd_vel 发布器失败: %s" % exc
        try:
            topic.publish(roslibpy.Message(message))
            return True, "success"
        except Exception as exc:
            return False, "发布 /cmd_vel 失败: %s" % exc

    def get_nav_status(self) -> dict[str, Any]:
        with self._lock:
            value = dict(self._latest_nav_status)
        return value or {
            "state": "IDLE",
            "taskId": None,
            "taskName": "",
            "currentPointIndex": 0,
            "totalPoints": 0,
            "currentPointName": "",
            "error": "",
        }

    def get_chassis_status(self) -> dict[str, Any]:
        with self._lock:
            scout = dict(self._latest_scout_status or {})
            bms = dict(self._latest_bms_status or {})
        return {
            "velocity": {
                "linear": scout.get("linear_velocity"),
                "angular": scout.get("angular_velocity"),
                "lateral": scout.get("lateral_velocity"),
            },
            "battery": {
                "soc": bms.get("SOC"),
                "soh": bms.get("SOH"),
                "voltage": bms.get("battery_voltage"),
                "current": bms.get("battery_current"),
                "temperature": bms.get("battery_temperature"),
            },
            "chassis": {
                "baseState": scout.get("base_state"),
                "controlMode": scout.get("control_mode"),
                "faultCode": scout.get("fault_code"),
            },
        }

    def get_battery_state(self) -> dict[str, float]:
        with self._lock:
            battery = dict(self._latest_battery or {})
        percentage = battery.get("percentage") or 0
        return {
            "percent": float(percentage) * 100.0,
            "voltage": float(battery.get("voltage") or 0),
        }


ros_client = RosbridgeClient()
