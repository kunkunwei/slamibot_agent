#!/usr/bin/env python3
"""Read-only D360 sensor health probe with fixed argv commands."""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

ROS_SETUP = "source /opt/ros/noetic/setup.bash"
FRAMEWORK_SETUP = "source /root/SLAMIBOT_D360_Framework/install/setup.bash"
SENSOR_SETUP = f"{ROS_SETUP} && {FRAMEWORK_SETUP}"
CORE_ROS = ["docker", "exec", "core", "/bin/bash", "-lc"]
SENSOR_ROS = ["docker", "exec", "firmware-sensors", "/bin/bash", "-lc"]

NTP_COMMAND = ["timedatectl", "show", "-p", "NTPSynchronized", "--value"]
PROJECT_DURATION_COMMAND = CORE_ROS + [
    f"{ROS_SETUP} && rostopic echo -n 1 /project_duration"
]
CORE_PROCESSES_COMMAND = ["docker", "top", "core", "-eo", "pid,args"]
CONTAINER_INSPECT_COMMAND = [
    "docker",
    "inspect",
    "--format",
    "{{json .State}}",
    "firmware-sensors",
]
SENSOR_PROCESSES_COMMAND = [
    "docker",
    "top",
    "firmware-sensors",
    "-eo",
    "pid,args",
]
LIDAR_RATE_COMMAND = SENSOR_ROS + [
    f"{SENSOR_SETUP} && timeout 6s rostopic hz -w 5 /livox/lidar"
]
POINT_NUM_COMMAND = SENSOR_ROS + [
    f"{SENSOR_SETUP} && rostopic echo -n 1 /livox/lidar/point_num"
]
IMU_RATE_COMMAND = SENSOR_ROS + [
    f"{SENSOR_SETUP} && timeout 6s rostopic hz -w 20 /livox/imu"
]
TIMESHARE_COMMAND = [
    "docker",
    "exec",
    "firmware-sensors",
    "/bin/bash",
    "-lc",
    "cat /dev/shm/timeshare | od -An -td8 -N16",
]
KEYFRAME_RATE_COMMAND = SENSOR_ROS + [
    f"{SENSOR_SETUP} && timeout 4s rostopic hz -w 5 /keyframe"
]
CAMERA_TEMPERATURE_INFO_COMMAND = SENSOR_ROS + [
    f"{SENSOR_SETUP} && rostopic info /camera_temperature"
]
USB_COMMAND = ["lsusb"]
LED_CONTROL_PING_COMMAND = CORE_ROS + [
    f"{ROS_SETUP} && rosnode ping -c 1 /led_control"
]
SYSTEM_MONITOR_PING_COMMAND = CORE_ROS + [
    f"{ROS_SETUP} && rosnode ping -c 1 /system_monitor"
]

CAMERA_TOPICS = {
    "A": "/SLB_CAM_A/compressed",
    "B": "/SLB_CAM_B/compressed",
    "C": "/SLB_CAM_C/compressed",
}
CORE_ACTIVITY_PROCESSES = (
    "record_node",
    "rosbag",
    "run_mapping_online",
    "lasermapping",
    "lidar_add_rgb",
)
LIVOX_PROCESS_NAMES = ("livox_ros_driver2_node",)
OAK_PROCESS_NAMES = ("oak_hardware_trigger_ros",)
STITCHER_PROCESS_NAMES = ("oak_keyframe_stitcher",)
SENSOR_PROCESS_NAMES = LIVOX_PROCESS_NAMES + OAK_PROCESS_NAMES + STITCHER_PROCESS_NAMES


def camera_info_command(camera: str) -> list[str]:
    return SENSOR_ROS + [f"{SENSOR_SETUP} && rostopic info {CAMERA_TOPICS[camera]}"]


def camera_rate_command(camera: str) -> list[str]:
    return SENSOR_ROS + [
        f"{SENSOR_SETUP} && timeout 4s rostopic hz -w 5 {CAMERA_TOPICS[camera]}"
    ]


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class RunnerProtocol(Protocol):
    def run(self, argv: Sequence[str], timeout: int) -> CommandResult:
        """Run a fixed argv command without a shell."""


class CommandRunner:
    def run(self, argv: Sequence[str], timeout: int) -> CommandResult:
        try:
            completed = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
            return CommandResult(completed.returncode, completed.stdout, completed.stderr)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout or ""
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr or ""
            return CommandResult(124, stdout, stderr, True)
        except OSError as exc:
            return CommandResult(127, "", str(exc))


def parse_ntp(text: str | None) -> str | None:
    if not isinstance(text, str):
        return None
    value = text.strip()
    return value if value in {"yes", "no"} else None


def parse_ros_data(text: str | None) -> float | None:
    if not isinstance(text, str):
        return None
    match = re.search(
        r"(?:^|\n)\s*(?:data:\s*)?([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:\n|$)",
        text,
    )
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_average_rate(text: str | None) -> float | None:
    if not isinstance(text, str) or "no new messages" in text.lower():
        return None
    matches = re.findall(r"average rate:\s*([0-9]+(?:\.[0-9]+)?)", text)
    return float(matches[-1]) if matches else None


def parse_point_num(text: str | None) -> int | None:
    if not isinstance(text, str):
        return None
    match = re.search(r"(?:point_num\s*:\s*|^\s*)(\d+)\s*(?:\n|$)", text)
    return int(match.group(1)) if match else None


def parse_publisher_presence(text: str | None) -> bool | None:
    if not isinstance(text, str):
        return None
    match = re.search(
        r"^Publishers:\s*(.*?)(?=^Subscribers:|^Services:|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return None
    body = match.group(1).strip()
    if not body or body.lower() == "none":
        return False
    return bool(re.search(r"(?:^|\n)\s*\*\s+", body))


def parse_process_lines(text: str | None) -> list[str] | None:
    if not isinstance(text, str):
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and re.match(r"^(?:PID\s+)?(?:COMMAND|ARGS)|^PID\s+", lines[0], re.I):
        lines = lines[1:]
    return lines


def parse_timeshare_pair(text: str | None) -> tuple[int, int] | None:
    if not isinstance(text, str):
        return None
    values = re.findall(r"[-+]?\d+", text)
    if len(values) != 2:
        return None
    try:
        return int(values[0]), int(values[1])
    except ValueError:
        return None


def parse_usb_products(text: str | None) -> list[str] | None:
    if not isinstance(text, str):
        return None
    return [item.lower() for item in re.findall(r"\b03e7:(f63[bc])\b", text, re.I)]


def parse_usb_product(text: str | None) -> str | None:
    products = parse_usb_products(text)
    if not products:
        return None
    return "f63b" if "f63b" in products else "f63c"


def parse_container_state(text: str | None) -> dict[str, Any] | None:
    if not isinstance(text, str):
        return None
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    running = raw.get("Running")
    status = raw.get("Status")
    pid = raw.get("Pid")
    started_at = raw.get("StartedAt")
    if (
        not isinstance(running, bool)
        or not isinstance(status, str)
        or not status
        or not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid < 0
        or not isinstance(started_at, str)
    ):
        return None
    return {
        "running": running,
        "state": status,
        "pid": pid,
        "started_at": started_at,
    }


def contains_process(lines: list[str] | None, names: Sequence[str]) -> bool | None:
    if lines is None:
        return None
    joined = "\n".join(lines).lower()
    return any(name.lower() in joined for name in names)


def sensor_processes_present(lines: list[str] | None) -> bool | None:
    return contains_process(lines, SENSOR_PROCESS_NAMES)


def acquisition_active(duration: float | None, core_processes: list[str] | None) -> bool | None:
    if duration is None or core_processes is None:
        return None
    joined = "\n".join(core_processes).lower()
    return duration != 0 or any(name in joined for name in CORE_ACTIVITY_PROCESSES)


def classify_sensor(
    *,
    container_running: bool,
    livox_process_present: bool | None,
    oak_process_present: bool | None,
    stitcher_process_present: bool | None,
    lidar_rate: float | None,
    point_num: int | None,
    imu_rate: float | None,
    timeshare_changed: bool | None,
    camera_publishers: Mapping[str, bool | None],
    camera_rates: Mapping[str, float | None],
    keyframe_rate: float | None,
    camera_temperature_publisher: bool | None,
    usb_product: str | None,
    xlink_indicator: bool,
) -> str:
    if not container_running:
        return "container_not_running"
    if livox_process_present is not True or stitcher_process_present is not True:
        return "sensor_process_missing"
    if lidar_rate is None or point_num is None or imu_rate is None:
        return "livox_no_data"
    if lidar_rate > 100 or point_num < 1000:
        return "livox_packet_mode"
    if timeshare_changed is not True:
        return "timeshare_frozen"

    no_camera_publishers = all(value is False for value in camera_publishers.values())
    if xlink_indicator or usb_product == "f63c":
        return "oak_xlink_crash"
    if oak_process_present is False and no_camera_publishers:
        return "oak_xlink_crash"
    if oak_process_present is not True:
        return "sensor_process_missing"
    if (
        any(value is not True for value in camera_publishers.values())
        or any(not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0
               for value in camera_rates.values())
        or camera_temperature_publisher is not True
    ):
        return "camera_no_data"
    if not isinstance(keyframe_rate, (int, float)) or isinstance(keyframe_rate, bool) or keyframe_rate <= 0:
        return "keyframe_no_data"
    return "healthy"


def classify(critical_errors: Sequence[str], active: bool | None, sensor_category: str) -> str:
    if critical_errors or active is None:
        return "query_failed"
    if active:
        return "active"
    return sensor_category


class HealthProbe:
    def __init__(
        self,
        runner: RunnerProtocol | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.runner = runner or CommandRunner()
        self.sleeper = sleeper or time.sleep
        self.errors: list[str] = []
        self.critical_errors: list[str] = []

    def _run(
        self,
        name: str,
        argv: Sequence[str],
        timeout: int,
        *,
        critical: bool = True,
        accepted_returncodes: Sequence[int] = (0,),
    ) -> CommandResult | None:
        result = self.runner.run(list(argv), timeout)
        if result.timed_out or result.returncode not in accepted_returncodes:
            detail = "timeout" if result.timed_out else f"exit_{result.returncode}"
            error = f"{name}:{detail}"
            self.errors.append(error)
            if critical:
                self.critical_errors.append(error)
            return None
        return result

    def _parse_required(self, name: str, value: Any) -> Any:
        if value is None:
            error = f"{name}:parse"
            self.errors.append(error)
            self.critical_errors.append(error)
        return value

    def collect(self) -> dict[str, Any]:
        ntp_result = self._run("ntp", NTP_COMMAND, 2)
        duration_result = self._run("project_duration", PROJECT_DURATION_COMMAND, 4)
        core_result = self._run("core_processes", CORE_PROCESSES_COMMAND, 3)
        inspect_result = self._run("container_inspect", CONTAINER_INSPECT_COMMAND, 3)

        ntp = self._parse_required("ntp", parse_ntp(ntp_result.stdout if ntp_result else None))
        duration = self._parse_required(
            "project_duration", parse_ros_data(duration_result.stdout if duration_result else None)
        )
        core_processes = self._parse_required(
            "core_processes", parse_process_lines(core_result.stdout if core_result else None)
        )
        container = self._parse_required(
            "container_inspect",
            parse_container_state(inspect_result.stdout if inspect_result else None),
        )
        container_running = bool(container and container["running"])
        if container_running:
            sensor_process_result = self._run(
                "sensor_processes", SENSOR_PROCESSES_COMMAND, 3
            )
            sensor_processes = self._parse_required(
                "sensor_processes",
                parse_process_lines(sensor_process_result.stdout if sensor_process_result else None),
            )
        else:
            sensor_processes = []

        defaults: dict[str, Any] = {
            "lidar_rate": None,
            "point_num": None,
            "imu_rate": None,
            "timeshare_changed": None,
            "camera_publishers": {camera: None for camera in CAMERA_TOPICS},
            "camera_rates": {camera: None for camera in CAMERA_TOPICS},
            "keyframe_rate": None,
            "camera_temperature_publisher": None,
        }
        xlink_indicator = False
        usb_result = self._run("usb", USB_COMMAND, 3, critical=False)
        usb_product = parse_usb_product(usb_result.stdout if usb_result else None)

        if container_running:
            expected_window_end = (0, 124)
            lidar_result = self._run(
                "lidar_rate", LIDAR_RATE_COMMAND, 10,
                accepted_returncodes=expected_window_end,
            )
            point_result = self._run("point_num", POINT_NUM_COMMAND, 6)
            imu_result = self._run(
                "imu_rate", IMU_RATE_COMMAND, 10,
                accepted_returncodes=expected_window_end,
            )
            timeshare_first = self._run("timeshare_first", TIMESHARE_COMMAND, 4)
            self.sleeper(0.5)
            timeshare_second = self._run("timeshare_second", TIMESHARE_COMMAND, 4)

            defaults["lidar_rate"] = parse_average_rate(lidar_result.stdout if lidar_result else None)
            defaults["point_num"] = parse_point_num(point_result.stdout if point_result else None)
            defaults["imu_rate"] = parse_average_rate(imu_result.stdout if imu_result else None)
            first_value = self._parse_required(
                "timeshare_first",
                parse_timeshare_pair(timeshare_first.stdout if timeshare_first else None),
            )
            second_value = self._parse_required(
                "timeshare_second",
                parse_timeshare_pair(timeshare_second.stdout if timeshare_second else None),
            )
            defaults["timeshare_changed"] = (
                first_value[1] != second_value[1]
                if first_value is not None and second_value is not None
                else None
            )

            for camera in CAMERA_TOPICS:
                info = self._run(f"camera_{camera}_info", camera_info_command(camera), 4)
                rate = self._run(
                    f"camera_{camera}_rate", camera_rate_command(camera), 8,
                    accepted_returncodes=expected_window_end,
                )
                defaults["camera_publishers"][camera] = parse_publisher_presence(
                    info.stdout if info else None
                )
                defaults["camera_rates"][camera] = parse_average_rate(rate.stdout if rate else None)

            keyframe_result = self._run(
                "keyframe_rate", KEYFRAME_RATE_COMMAND, 8,
                accepted_returncodes=expected_window_end,
            )
            temperature_result = self._run(
                "camera_temperature", CAMERA_TEMPERATURE_INFO_COMMAND, 4
            )
            defaults["keyframe_rate"] = parse_average_rate(
                keyframe_result.stdout if keyframe_result else None
            )
            defaults["camera_temperature_publisher"] = parse_publisher_presence(
                temperature_result.stdout if temperature_result else None
            )

        led_result = self._run("led_control_ping", LED_CONTROL_PING_COMMAND, 2, critical=False)
        monitor_result = self._run(
            "system_monitor_ping", SYSTEM_MONITOR_PING_COMMAND, 2, critical=False
        )

        livox_present = contains_process(sensor_processes, LIVOX_PROCESS_NAMES)
        oak_present = contains_process(sensor_processes, OAK_PROCESS_NAMES)
        stitcher_present = contains_process(sensor_processes, STITCHER_PROCESS_NAMES)
        active = acquisition_active(duration, core_processes)
        sensor_category = classify_sensor(
            container_running=container_running,
            livox_process_present=livox_present,
            oak_process_present=oak_present,
            stitcher_process_present=stitcher_present,
            lidar_rate=defaults["lidar_rate"],
            point_num=defaults["point_num"],
            imu_rate=defaults["imu_rate"],
            timeshare_changed=defaults["timeshare_changed"],
            camera_publishers=defaults["camera_publishers"],
            camera_rates=defaults["camera_rates"],
            keyframe_rate=defaults["keyframe_rate"],
            camera_temperature_publisher=defaults["camera_temperature_publisher"],
            usb_product=usb_product,
            xlink_indicator=xlink_indicator,
        )
        category = classify(self.critical_errors, active, sensor_category)

        return {
            "ntp": ntp,
            "project_duration": duration,
            "core_processes": core_processes,
            "container": container,
            "sensor_processes": sensor_processes,
            "sensor_processes_present": sensor_processes_present(sensor_processes),
            "oak_process_present": oak_present,
            "usb_product": usb_product,
            "health": {
                "category": category,
                "sensor_category": sensor_category,
                "lidar_rate": defaults["lidar_rate"],
                "point_num": defaults["point_num"],
                "imu_rate": defaults["imu_rate"],
                "timeshare_changed": defaults["timeshare_changed"],
                "camera_publishers": defaults["camera_publishers"],
                "camera_rates": defaults["camera_rates"],
                "keyframe_rate": defaults["keyframe_rate"],
                "camera_temperature_publisher": defaults["camera_temperature_publisher"],
                "xlink_indicator": xlink_indicator,
            },
            "led": {
                "led_control_alive": bool(
                    led_result
                    and any(
                        marker in led_result.stdout.lower()
                        for marker in ("pinged machine", "xmlrpc reply")
                    )
                ),
                "system_monitor_alive": bool(
                    monitor_result
                    and any(
                        marker in monitor_result.stdout.lower()
                        for marker in ("pinged machine", "xmlrpc reply")
                    )
                ),
            },
            "errors": self.errors,
        }


def probe(
    runner: RunnerProtocol | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    return HealthProbe(runner, sleeper=sleeper).collect()


def main() -> int:
    print(json.dumps(probe(), separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
