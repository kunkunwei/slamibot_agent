#!/usr/bin/env python3
"""Fail-closed local candidate for D360 monitor, startup, and manual recovery."""

from __future__ import annotations

import argparse
import configparser
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence, TextIO

try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    fcntl = None

CONTAINER_NAME = "firmware-sensors"
START_COMMAND = ["docker", "start", CONTAINER_NAME]
STOP_COMMAND = ["docker", "stop", "-t", "20", CONTAINER_NAME]
INSPECT_COMMAND = [
    "docker",
    "inspect",
    "--format",
    "{{json .State}}",
    CONTAINER_NAME,
]
HOST_SENSOR_PROCESS_COMMAND = ["ps", "-eo", "pid,args"]
ROS_SETUP = "source /opt/ros/noetic/setup.bash"
CORE_ROS = ["docker", "exec", "core", "/bin/bash", "-lc"]
CLEANUP_COMMAND = CORE_ROS + [f"{ROS_SETUP} && printf 'y\\n' | rosnode cleanup"]
NODE_LIST_COMMAND = CORE_ROS + [f"{ROS_SETUP} && rosnode list"]
SENSOR_NODE_NAMES = (
    "/livox_lidar_publisher2",
    "/oak_hardware_trigger_ros",
    "/oak_keyframe_stitcher",
)
NODE_PING_COMMANDS = {
    name: CORE_ROS + [f"{ROS_SETUP} && rosnode ping -c 1 {name}"]
    for name in SENSOR_NODE_NAMES
}
CORE_ACTIVITY_PROCESSES = (
    "record_node",
    "rosbag",
    "run_mapping_online",
    "lasermapping",
    "lidar_add_rgb",
)
SENSOR_PROCESS_NAMES = (
    "livox_ros_driver2_node",
    "oak_hardware_trigger_ros",
    "oak_keyframe_stitcher",
)
CATEGORIES = {
    "active",
    "query_failed",
    "container_not_running",
    "sensor_process_missing",
    "livox_no_data",
    "livox_packet_mode",
    "timeshare_frozen",
    "oak_xlink_crash",
    "camera_no_data",
    "keyframe_no_data",
    "healthy",
}
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class RunnerProtocol(Protocol):
    def run(self, argv: Sequence[str], timeout: int) -> RunResult:
        """Run one fixed argv command with shell disabled."""


class Runner:
    def run(self, argv: Sequence[str], timeout: int) -> RunResult:
        try:
            completed = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=False,
            )
            return RunResult(completed.returncode, completed.stdout, completed.stderr)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout or ""
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr or ""
            return RunResult(124, stdout, stderr, True)
        except OSError as exc:
            return RunResult(127, "", str(exc))


DEFAULTS: dict[str, Any] = {
    "dry_run": True,
    "allow_startup_start": False,
    "allow_manual_recovery": False,
    "probe_timeout": 90,
    "action_timeout": 30,
    "startup_ntp_wait_seconds": 120,
    "startup_ntp_poll_seconds": 5,
    "livox_postcheck_seconds": 15,
    "oak_postcheck_seconds": 120,
}
REQUIRED_CONFIG_KEYS = {"state_path", "log_path", "lock_path", "probe_command"}
ALLOWED_CONFIG_KEYS = set(DEFAULTS) | REQUIRED_CONFIG_KEYS
BOOLEAN_KEYS = {"dry_run", "allow_startup_start", "allow_manual_recovery"}
INTEGER_KEYS = {
    "probe_timeout",
    "action_timeout",
    "startup_ntp_wait_seconds",
    "startup_ntp_poll_seconds",
    "livox_postcheck_seconds",
    "oak_postcheck_seconds",
}
PATH_KEYS = {"state_path", "log_path", "lock_path"}


def parse_bool(name: str, value: str) -> bool:
    lowered = value.strip().lower()
    if lowered not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return lowered == "true"


def parse_positive_int(name: str, value: str | int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def parse_config(path: str) -> dict[str, Any]:
    if not os.path.isabs(path):
        raise ValueError("config path must be absolute")
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(path, encoding="utf-8") or "guard" not in parser:
        raise ValueError("missing [guard] configuration")
    raw = dict(parser["guard"])
    unknown = set(raw) - ALLOWED_CONFIG_KEYS
    if unknown:
        raise ValueError(f"unknown configuration keys: {', '.join(sorted(unknown))}")
    missing = REQUIRED_CONFIG_KEYS - set(raw)
    if missing:
        raise ValueError(f"missing configuration keys: {', '.join(sorted(missing))}")

    config = dict(DEFAULTS)
    config.update(raw)
    for name in BOOLEAN_KEYS:
        value = config[name]
        config[name] = value if isinstance(value, bool) else parse_bool(name, value)
    for name in INTEGER_KEYS:
        config[name] = parse_positive_int(name, config[name])
    if config["oak_postcheck_seconds"] < config["livox_postcheck_seconds"]:
        raise ValueError("oak_postcheck_seconds must be >= livox_postcheck_seconds")
    for name in PATH_KEYS:
        value = config[name]
        if not isinstance(value, str) or not value or not os.path.isabs(value):
            raise ValueError(f"{name} must be an absolute path")
        config[name] = os.path.normpath(value)

    try:
        probe_command = json.loads(raw["probe_command"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("probe_command must be a JSON argv list") from exc
    if (
        not isinstance(probe_command, list)
        or not probe_command
        or not all(isinstance(item, str) and item for item in probe_command)
        or not os.path.isabs(probe_command[0])
        or (len(probe_command) > 1 and not os.path.isabs(probe_command[1]))
    ):
        raise ValueError("probe_command must contain absolute executable/script paths")
    config["probe_command"] = probe_command
    return config


def parse_process_lines(text: str | None) -> list[str] | None:
    if not isinstance(text, str):
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and lines[0].upper().startswith("PID "):
        lines = lines[1:]
    return lines


def contains_named_process(lines: Sequence[str], names: Sequence[str]) -> bool:
    joined = "\n".join(lines).lower()
    return any(name.lower() in joined for name in names)


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
    return {"running": running, "state": status, "pid": pid, "started_at": started_at}


def default_lock_acquirer(file_object: TextIO) -> bool:
    if fcntl is not None:
        try:
            fcntl.flock(file_object.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False
    import msvcrt  # pragma: no cover

    try:  # pragma: no cover
        file_object.seek(0)
        if file_object.read(1) == "":
            file_object.write("0")
            file_object.flush()
        file_object.seek(0)
        msvcrt.locking(file_object.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def new_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": None,
        "status": "INIT",
        "reason": "initialized",
        "category": None,
        "sensor_category": None,
        "manual_action_required": False,
        "manual_lock": False,
        "updated_at": None,
    }


def state_is_valid(state: Any) -> bool:
    return (
        isinstance(state, dict)
        and state.get("schema_version") == SCHEMA_VERSION
        and isinstance(state.get("status"), str)
        and isinstance(state.get("reason"), str)
        and isinstance(state.get("manual_action_required"), bool)
        and isinstance(state.get("manual_lock"), bool)
    )


class Guard:
    def __init__(
        self,
        config: Mapping[str, Any],
        runner: RunnerProtocol | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        lock_acquirer: Callable[[TextIO], bool] | None = None,
    ) -> None:
        self.config = {**DEFAULTS, **dict(config)}
        self.runner = runner or Runner()
        self.clock = clock or time.time
        self.sleeper = sleeper or time.sleep
        self.lock_acquirer = lock_acquirer or default_lock_acquirer
        self.state = new_state()

    def _load_state(self) -> bool:
        try:
            with open(self.config["state_path"], encoding="utf-8") as handle:
                loaded = json.load(handle)
        except FileNotFoundError:
            self.state = new_state()
            return True
        except (OSError, json.JSONDecodeError):
            self.state = new_state()
            self.state["manual_lock"] = True
            return False
        if not state_is_valid(loaded):
            self.state = new_state()
            self.state["manual_lock"] = True
            return False
        self.state = loaded
        return True

    def _save_state(self) -> None:
        path = self.config["state_path"]
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(prefix=".state-", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(self.state, handle, separators=(",", ":"), sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except Exception:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            raise

    def _log(self) -> None:
        path = self.config["log_path"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(self.state, separators=(",", ":"), sort_keys=True) + "\n")

    def _finish(
        self,
        mode: str,
        status: str,
        reason: str,
        *,
        sample: Mapping[str, Any] | None = None,
        manual: bool = False,
        lock: bool | None = None,
    ) -> dict[str, Any]:
        self.state.update(
            {
                "mode": mode,
                "status": status,
                "reason": reason,
                "manual_action_required": manual,
                "updated_at": self.clock(),
            }
        )
        if lock is not None:
            self.state["manual_lock"] = lock
        if sample is not None:
            health = sample.get("health")
            self.state["category"] = health.get("category") if isinstance(health, Mapping) else None
            self.state["sensor_category"] = (
                health.get("sensor_category") if isinstance(health, Mapping) else None
            )
        self._save_state()
        self._log()
        return dict(self.state)

    def _manual_fail(self, reason: str, sample: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return self._finish(
            "manual-recover",
            "MANUAL_RECOVERY_FAILED",
            reason,
            sample=sample,
            manual=True,
            lock=True,
        )

    def _run_command(self, argv: Sequence[str]) -> RunResult:
        return self.runner.run(list(argv), int(self.config["action_timeout"]))

    @staticmethod
    def _valid_sample(sample: Any) -> bool:
        if not isinstance(sample, dict):
            return False
        health = sample.get("health")
        container = sample.get("container")
        duration = sample.get("project_duration")
        return (
            sample.get("ntp") in {"yes", "no"}
            and isinstance(duration, (int, float))
            and not isinstance(duration, bool)
            and isinstance(sample.get("core_processes"), list)
            and all(isinstance(item, str) for item in sample["core_processes"])
            and isinstance(sample.get("sensor_processes"), list)
            and all(isinstance(item, str) for item in sample["sensor_processes"])
            and isinstance(sample.get("sensor_processes_present"), bool)
            and isinstance(container, Mapping)
            and isinstance(container.get("running"), bool)
            and isinstance(container.get("state"), str)
            and isinstance(container.get("pid"), int)
            and not isinstance(container.get("pid"), bool)
            and isinstance(container.get("started_at"), str)
            and isinstance(health, Mapping)
            and health.get("category") in CATEGORIES
            and health.get("sensor_category") in CATEGORIES - {"active", "query_failed"}
        )

    def _sample(self) -> dict[str, Any] | None:
        command = self.config.get("probe_command")
        if not isinstance(command, list) or not command:
            return None
        result = self.runner.run(command, int(self.config["probe_timeout"]))
        if result.returncode != 0:
            return None
        try:
            sample = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError):
            return None
        return sample if self._valid_sample(sample) else None

    @staticmethod
    def _idle(sample: Mapping[str, Any]) -> bool:
        duration = sample.get("project_duration")
        processes = sample.get("core_processes")
        if duration != 0 or not isinstance(processes, list):
            return False
        return not contains_named_process(processes, CORE_ACTIVITY_PROCESSES)

    @staticmethod
    def _container_running(sample: Mapping[str, Any]) -> bool:
        container = sample.get("container")
        return bool(isinstance(container, Mapping) and container.get("running") is True)

    @staticmethod
    def _livox_postcheck_good(sample: Mapping[str, Any]) -> bool:
        if sample.get("ntp") != "yes" or not Guard._idle(sample) or not Guard._container_running(sample):
            return False
        if sample.get("sensor_processes_present") is not True:
            return False
        health = sample.get("health")
        if not isinstance(health, Mapping):
            return False
        lidar = health.get("lidar_rate")
        points = health.get("point_num")
        imu = health.get("imu_rate")
        return (
            isinstance(lidar, (int, float))
            and not isinstance(lidar, bool)
            and 5 <= lidar <= 20
            and isinstance(points, int)
            and not isinstance(points, bool)
            and points >= 1000
            and isinstance(imu, (int, float))
            and not isinstance(imu, bool)
            and imu > 0
            and health.get("timeshare_changed") is True
        )

    @staticmethod
    def _oak_postcheck_good(sample: Mapping[str, Any]) -> bool:
        if not Guard._livox_postcheck_good(sample):
            return False
        if sample.get("oak_process_present") is not True or sample.get("usb_product") != "f63b":
            return False
        health = sample.get("health")
        if not isinstance(health, Mapping) or health.get("sensor_category") != "healthy":
            return False
        publishers = health.get("camera_publishers")
        rates = health.get("camera_rates")
        keyframe = health.get("keyframe_rate")
        return (
            isinstance(publishers, Mapping)
            and all(publishers.get(camera) is True for camera in "ABC")
            and isinstance(rates, Mapping)
            and all(
                isinstance(rates.get(camera), (int, float))
                and not isinstance(rates.get(camera), bool)
                and rates[camera] > 0
                for camera in "ABC"
            )
            and isinstance(keyframe, (int, float))
            and not isinstance(keyframe, bool)
            and keyframe > 0
            and health.get("camera_temperature_publisher") is True
        )

    def _postcheck(self, manual: bool) -> dict[str, Any] | None:
        self.sleeper(int(self.config["livox_postcheck_seconds"]))
        livox_sample = self._sample()
        if livox_sample is None or not self._livox_postcheck_good(livox_sample):
            return self._manual_fail("livox_postcheck_failed", livox_sample) if manual else self._finish(
                "startup", "STARTUP_FAILED", "livox_postcheck_failed", sample=livox_sample, manual=True
            )
        remaining = int(self.config["oak_postcheck_seconds"]) - int(
            self.config["livox_postcheck_seconds"]
        )
        if remaining:
            self.sleeper(remaining)
        oak_sample = self._sample()
        if oak_sample is None or not self._oak_postcheck_good(oak_sample):
            return self._manual_fail("oak_postcheck_failed", oak_sample) if manual else self._finish(
                "startup", "STARTUP_FAILED", "oak_postcheck_failed", sample=oak_sample, manual=True
            )
        return None

    def monitor(self) -> dict[str, Any]:
        sample = self._sample()
        if sample is None:
            return self._finish(
                "monitor", "MONITOR_ALERT", "probe_or_parse_failed", manual=True
            )
        health = sample["health"]
        category = health["category"]
        sensor_category = health["sensor_category"]
        if category == "healthy":
            return self._finish("monitor", "HEALTHY", "healthy", sample=sample, manual=False)
        if category == "active" and sensor_category == "healthy":
            return self._finish(
                "monitor", "ACTIVE_MONITORING", "acquisition_active", sample=sample, manual=False
            )
        reason = f"active_{sensor_category}" if category == "active" else category
        return self._finish(
            "monitor", "MONITOR_ALERT", reason, sample=sample, manual=True
        )

    def _wait_for_ntp(self) -> tuple[dict[str, Any] | None, str | None]:
        elapsed = 0
        limit = int(self.config["startup_ntp_wait_seconds"])
        interval = int(self.config["startup_ntp_poll_seconds"])
        while True:
            sample = self._sample()
            if sample is None:
                return None, "probe_or_parse_failed"
            if sample["ntp"] == "yes":
                return sample, None
            if elapsed >= limit:
                return sample, "ntp_wait_timeout"
            delay = min(interval, limit - elapsed)
            if delay <= 0:
                return sample, "ntp_wait_timeout"
            self.sleeper(delay)
            elapsed += delay

    def _host_sensor_processes_absent(self) -> bool | None:
        result = self._run_command(HOST_SENSOR_PROCESS_COMMAND)
        if result.returncode != 0:
            return None
        lines = parse_process_lines(result.stdout)
        if lines is None:
            return None
        return not contains_named_process(lines, SENSOR_PROCESS_NAMES)

    def _cleanup_and_verify_nodes(self) -> str | None:
        cleanup = self._run_command(CLEANUP_COMMAND)
        if cleanup.returncode != 0:
            return "cleanup_failed"
        listed = self._run_command(NODE_LIST_COMMAND)
        if listed.returncode != 0:
            return "node_list_failed"
        nodes = {line.strip() for line in listed.stdout.splitlines() if line.strip()}
        for name in SENSOR_NODE_NAMES:
            if name not in nodes:
                continue
            ping = self._run_command(NODE_PING_COMMANDS[name])
            if ping.returncode == 0:
                return "sensor_node_reachable"
        return None

    def startup(self) -> dict[str, Any]:
        sample, error = self._wait_for_ntp()
        if error:
            return self._finish("startup", "STARTUP_BLOCKED", error, sample=sample, manual=True)
        assert sample is not None
        if not self._idle(sample):
            return self._finish(
                "startup", "STARTUP_BLOCKED", "project_or_acquisition_active", sample=sample, manual=True
            )
        if self._container_running(sample):
            return self._finish(
                "startup", "ALREADY_RUNNING", "container_already_running_monitor_only", sample=sample,
                manual=sample["health"]["sensor_category"] != "healthy"
            )
        if sample.get("sensor_processes_present") is not False:
            return self._finish(
                "startup", "STARTUP_BLOCKED", "sensor_process_present", sample=sample, manual=True
            )
        if bool(self.config["dry_run"]):
            return self._finish("startup", "STARTUP_BLOCKED", "dry_run", sample=sample, manual=True)
        if not bool(self.config["allow_startup_start"]):
            return self._finish(
                "startup", "STARTUP_BLOCKED", "startup_start_not_authorized", sample=sample, manual=True
            )
        node_error = self._cleanup_and_verify_nodes()
        if node_error:
            return self._finish("startup", "STARTUP_FAILED", node_error, sample=sample, manual=True)
        started = self._run_command(START_COMMAND)
        if started.returncode != 0:
            return self._finish("startup", "STARTUP_FAILED", "start_failed", sample=sample, manual=True)
        postcheck_failure = self._postcheck(manual=False)
        if postcheck_failure is not None:
            return postcheck_failure
        final_sample = self._sample()
        if final_sample is None or not self._oak_postcheck_good(final_sample):
            return self._finish(
                "startup", "STARTUP_FAILED", "final_postcheck_failed", sample=final_sample, manual=True
            )
        return self._finish(
            "startup", "STARTED_HEALTHY", "single_start_verified", sample=final_sample, manual=False
        )

    def manual_recover(self, confirm: bool) -> dict[str, Any]:
        if not confirm:
            return self._finish(
                "manual-recover", "MANUAL_RECOVERY_REFUSED", "cli_confirmation_missing", manual=True
            )
        if not bool(self.config["allow_manual_recovery"]):
            return self._finish(
                "manual-recover", "MANUAL_RECOVERY_REFUSED", "config_authorization_missing", manual=True
            )
        if bool(self.config["dry_run"]):
            return self._finish(
                "manual-recover", "MANUAL_RECOVERY_REFUSED", "dry_run", manual=True
            )

        sample = self._sample()
        if sample is None:
            return self._manual_fail("preflight_probe_failed")
        if sample["ntp"] != "yes":
            return self._manual_fail("ntp_not_synchronized", sample)
        if not self._idle(sample):
            return self._manual_fail("project_or_acquisition_active", sample)
        if not self._container_running(sample):
            return self._manual_fail("container_not_running", sample)

        stopped = self._run_command(STOP_COMMAND)
        if stopped.returncode != 0:
            return self._manual_fail("stop_failed", sample)
        inspected = self._run_command(INSPECT_COMMAND)
        container = parse_container_state(inspected.stdout) if inspected.returncode == 0 else None
        if container is None or container["running"] or container["pid"] != 0:
            return self._manual_fail("stop_inspect_failed", sample)
        absent = self._host_sensor_processes_absent()
        if absent is not True:
            reason = "sensor_process_query_failed" if absent is None else "sensor_process_remaining"
            return self._manual_fail(reason, sample)
        node_error = self._cleanup_and_verify_nodes()
        if node_error:
            return self._manual_fail(node_error, sample)
        started = self._run_command(START_COMMAND)
        if started.returncode != 0:
            return self._manual_fail("start_failed", sample)
        postcheck_failure = self._postcheck(manual=True)
        if postcheck_failure is not None:
            return postcheck_failure
        final_sample = self._sample()
        if final_sample is None or not self._oak_postcheck_good(final_sample):
            return self._manual_fail("final_postcheck_failed", final_sample)
        return self._finish(
            "manual-recover",
            "MANUAL_RECOVERY_SUCCEEDED",
            "manual_sequence_verified",
            sample=final_sample,
            manual=False,
            lock=False,
        )

    def run(self, mode: str, *, confirm_manual_recovery: bool = False) -> dict[str, Any]:
        lock_path = self.config["lock_path"]
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        try:
            with open(lock_path, "a+", encoding="utf-8") as lock_file:
                if not self.lock_acquirer(lock_file):
                    self.state = new_state()
                    return self._finish(mode, "LOCKED", "lock_busy", manual=True)
                if not self._load_state():
                    return self._finish(mode, "STATE_INVALID", "state_corruption", manual=True, lock=True)
                if mode == "monitor":
                    return self.monitor()
                if mode == "startup":
                    return self.startup()
                if mode == "manual-recover":
                    return self.manual_recover(confirm_manual_recovery)
                return self._finish(mode, "INVALID_MODE", "unsupported_mode", manual=True)
        except OSError:
            return {
                **new_state(),
                "mode": mode,
                "status": "IO_ERROR",
                "reason": "lock_or_state_io_error",
                "manual_action_required": True,
            }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("monitor", "startup", "manual-recover"))
    parser.add_argument("config", help="absolute path to the guard INI file")
    parser.add_argument("--confirm-manual-recovery", action="store_true")
    arguments = parser.parse_args()
    try:
        config = parse_config(arguments.config)
        result = Guard(config).run(
            arguments.mode,
            confirm_manual_recovery=arguments.confirm_manual_recovery,
        )
    except ValueError as exc:
        result = {
            "mode": arguments.mode,
            "status": "CONFIG_ERROR",
            "reason": str(exc),
            "manual_action_required": True,
        }
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    successful_statuses = {
        "HEALTHY",
        "ACTIVE_MONITORING",
        "MONITOR_ALERT",
        "ALREADY_RUNNING",
        "STARTED_HEALTHY",
        "MANUAL_RECOVERY_SUCCEEDED",
    }
    return 0 if result["status"] in successful_statuses else 1


if __name__ == "__main__":
    raise SystemExit(main())
