import json
import os
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from d360_sensor_guard import (
    CLEANUP_COMMAND,
    HOST_SENSOR_PROCESS_COMMAND,
    INSPECT_COMMAND,
    NODE_LIST_COMMAND,
    NODE_PING_COMMANDS,
    SENSOR_NODE_NAMES,
    START_COMMAND,
    STOP_COMMAND,
    Guard,
    RunResult,
    contains_named_process,
    new_state,
    parse_config,
    parse_container_state,
    parse_process_lines,
)

PROBE_ARGV = [os.path.abspath("candidate-python"), os.path.abspath("health-probe.py")]
RUNNING_INSPECT = json.dumps(
    {
        "Status": "running",
        "Running": True,
        "Pid": 4321,
        "StartedAt": "2026-09-02T15:02:50+08:00",
    }
)
STOPPED_INSPECT = json.dumps(
    {
        "Status": "exited",
        "Running": False,
        "Pid": 0,
        "StartedAt": "2026-09-02T14:44:00+08:00",
    }
)


def healthy_sample():
    return {
        "ntp": "yes",
        "project_duration": 0.0,
        "core_processes": ["11 roscore", "12 system_monitor"],
        "container": {
            "running": True,
            "state": "running",
            "pid": 4321,
            "started_at": "2026-09-02T15:02:50+08:00",
        },
        "sensor_processes": [
            "21 /opt/ros/noetic/lib/livox_ros_driver2/livox_ros_driver2_node",
            "22 /opt/slam/bin/oak_hardware_trigger_ros",
            "23 /opt/slam/bin/oak_keyframe_stitcher",
        ],
        "sensor_processes_present": True,
        "oak_process_present": True,
        "usb_product": "f63b",
        "health": {
            "category": "healthy",
            "sensor_category": "healthy",
            "lidar_rate": 10.011,
            "point_num": 19968,
            "imu_rate": 199.863,
            "timeshare_changed": True,
            "camera_publishers": {"A": True, "B": True, "C": True},
            "camera_rates": {"A": 10.0, "B": 10.1, "C": 9.9},
            "keyframe_rate": 3.67,
            "camera_temperature_publisher": True,
            "xlink_indicator": False,
        },
        "led": {"led_control_alive": True, "system_monitor_alive": True},
        "errors": [],
    }


def stopped_sample():
    sample = healthy_sample()
    sample["container"] = {
        "running": False,
        "state": "exited",
        "pid": 0,
        "started_at": "2026-09-02T14:44:00+08:00",
    }
    sample["sensor_processes"] = []
    sample["sensor_processes_present"] = False
    sample["oak_process_present"] = False
    sample["health"]["category"] = "container_not_running"
    sample["health"]["sensor_category"] = "container_not_running"
    sample["health"]["lidar_rate"] = None
    sample["health"]["point_num"] = None
    sample["health"]["imu_rate"] = None
    sample["health"]["timeshare_changed"] = None
    sample["health"]["camera_publishers"] = {"A": None, "B": None, "C": None}
    sample["health"]["camera_rates"] = {"A": None, "B": None, "C": None}
    sample["health"]["keyframe_rate"] = None
    sample["health"]["camera_temperature_publisher"] = None
    return sample


def fault_sample(category="livox_packet_mode", *, active=False):
    sample = healthy_sample()
    sample["health"]["sensor_category"] = category
    sample["health"]["category"] = "active" if active else category
    if active:
        sample["project_duration"] = 10.0
    if category == "livox_packet_mode":
        sample["health"]["lidar_rate"] = 2083.0
        sample["health"]["point_num"] = 96
    elif category == "livox_no_data":
        sample["health"]["lidar_rate"] = None
    elif category == "timeshare_frozen":
        sample["health"]["timeshare_changed"] = False
    elif category == "oak_xlink_crash":
        sample["oak_process_present"] = False
        sample["usb_product"] = "f63c"
        sample["health"]["camera_publishers"] = {"A": False, "B": False, "C": False}
        sample["health"]["camera_rates"] = {"A": None, "B": None, "C": None}
        sample["health"]["keyframe_rate"] = None
        sample["health"]["xlink_indicator"] = True
    elif category == "camera_no_data":
        sample["health"]["camera_rates"]["B"] = None
    elif category == "keyframe_no_data":
        sample["health"]["keyframe_rate"] = None
    return sample


class ScriptedRunner:
    """Separates fixed probe/start/stop/inspect/process/cleanup/node commands."""

    def __init__(self, probes=None, commands=None):
        self.probes = list(probes or [])
        self.commands = {
            tuple(argv): list(values) if isinstance(values, list) else [values]
            for argv, values in (commands or {}).items()
        }
        self.indices = defaultdict(int)
        self.calls = []

    def run(self, argv: Sequence[str], timeout: int) -> RunResult:
        argv = list(argv)
        self.calls.append((argv, timeout))
        if argv == PROBE_ARGV:
            if not self.probes:
                return RunResult(98, "", "probe script exhausted")
            value = self.probes.pop(0)
            if isinstance(value, RunResult):
                return value
            if isinstance(value, str):
                return RunResult(0, value, "")
            return RunResult(0, json.dumps(value), "")
        key = tuple(argv)
        if key not in self.commands:
            return RunResult(99, "", "unexpected argv")
        values = self.commands[key]
        index = self.indices[key]
        self.indices[key] += 1
        value = values[min(index, len(values) - 1)]
        if isinstance(value, RunResult):
            return value
        if isinstance(value, int):
            return RunResult(value, "", "")
        return RunResult(0, value, "")


def startup_commands(**overrides):
    commands = {
        tuple(CLEANUP_COMMAND): 0,
        tuple(NODE_LIST_COMMAND): "\n",
        tuple(START_COMMAND): 0,
    }
    commands.update({tuple(argv): value for argv, value in overrides.items()})
    return commands


def manual_commands(**overrides):
    commands = {
        tuple(STOP_COMMAND): 0,
        tuple(INSPECT_COMMAND): STOPPED_INSPECT,
        tuple(HOST_SENSOR_PROCESS_COMMAND): "PID COMMAND\n55 unrelated\n",
        tuple(CLEANUP_COMMAND): 0,
        tuple(NODE_LIST_COMMAND): "\n",
        tuple(START_COMMAND): 0,
    }
    commands.update({tuple(argv): value for argv, value in overrides.items()})
    return commands


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = self.temp.name
        self.config = {
            "state_path": os.path.join(root, "state.json"),
            "log_path": os.path.join(root, "guard.jsonl"),
            "lock_path": os.path.join(root, "guard.lock"),
            "probe_command": list(PROBE_ARGV),
            "probe_timeout": 90,
            "action_timeout": 30,
            "startup_ntp_wait_seconds": 10,
            "startup_ntp_poll_seconds": 5,
            "livox_postcheck_seconds": 15,
            "oak_postcheck_seconds": 120,
            "dry_run": False,
            "allow_startup_start": True,
            "allow_manual_recovery": True,
        }
        self.sleeps = []
        self.now = 1000.0

    def make_guard(self, runner, **overrides):
        return Guard(
            {**self.config, **overrides},
            runner=runner,
            clock=lambda: self.now,
            sleeper=self.sleeps.append,
            lock_acquirer=lambda _: True,
        )

    def read_state(self):
        return json.loads(Path(self.config["state_path"]).read_text(encoding="utf-8"))

    def write_state(self, value):
        Path(self.config["state_path"]).write_text(json.dumps(value), encoding="utf-8")

    def successful_startup(self):
        runner = ScriptedRunner(
            [stopped_sample(), healthy_sample(), healthy_sample(), healthy_sample()],
            startup_commands(),
        )
        result = self.make_guard(runner).run("startup")
        return result, runner

    def successful_manual(self, commands=None, probes=None):
        runner = ScriptedRunner(
            probes or [fault_sample(), healthy_sample(), healthy_sample(), healthy_sample()],
            commands or manual_commands(),
        )
        result = self.make_guard(runner).run(
            "manual-recover", confirm_manual_recovery=True
        )
        return result, runner


class GuardParserConfigTests(GuardCase):
    def write_config(self, **overrides):
        values = {
            "state_path": os.path.abspath(self.config["state_path"]),
            "log_path": os.path.abspath(self.config["log_path"]),
            "lock_path": os.path.abspath(self.config["lock_path"]),
            "probe_command": json.dumps(PROBE_ARGV),
        }
        values.update(overrides)
        path = os.path.abspath(os.path.join(self.temp.name, "guard.ini"))
        Path(path).write_text(
            "[guard]\n" + "".join(f"{key}={value}\n" for key, value in values.items()),
            encoding="utf-8",
        )
        return path

    def test_config_defaults_are_safe(self):
        config = parse_config(self.write_config())
        self.assertTrue(config["dry_run"])
        self.assertFalse(config["allow_startup_start"])
        self.assertFalse(config["allow_manual_recovery"])
        self.assertEqual(config["livox_postcheck_seconds"], 15)
        self.assertEqual(config["oak_postcheck_seconds"], 120)

    def test_config_rejects_relative_config_path(self):
        with self.assertRaisesRegex(ValueError, "config path"):
            parse_config("guard.ini")

    def test_config_rejects_unknown_key(self):
        with self.assertRaisesRegex(ValueError, "unknown configuration"):
            parse_config(self.write_config(automatic_action="true"))

    def test_config_rejects_bad_boolean(self):
        with self.assertRaisesRegex(ValueError, "dry_run"):
            parse_config(self.write_config(dry_run="enabled"))

    def test_config_rejects_zero_timeout(self):
        with self.assertRaisesRegex(ValueError, "probe_timeout"):
            parse_config(self.write_config(probe_timeout="0"))

    def test_config_rejects_relative_state_path(self):
        with self.assertRaisesRegex(ValueError, "state_path"):
            parse_config(self.write_config(state_path="state.json"))

    def test_config_rejects_probe_shell_string(self):
        with self.assertRaisesRegex(ValueError, "probe_command"):
            parse_config(self.write_config(probe_command='"python probe.py"'))

    def test_config_rejects_relative_probe_script(self):
        command = json.dumps([PROBE_ARGV[0], "probe.py"])
        with self.assertRaisesRegex(ValueError, "absolute executable"):
            parse_config(self.write_config(probe_command=command))

    def test_config_rejects_oak_timeout_shorter_than_livox(self):
        with self.assertRaisesRegex(ValueError, "oak_postcheck"):
            parse_config(
                self.write_config(livox_postcheck_seconds="15", oak_postcheck_seconds="10")
            )

    def test_process_parser_and_named_match(self):
        lines = parse_process_lines("PID COMMAND\n22 livox_ros_driver2_node\n")
        self.assertEqual(lines, ["22 livox_ros_driver2_node"])
        self.assertTrue(contains_named_process(lines, ("livox_ros_driver2_node",)))

    def test_manual_cleanup_covers_exact_runtime_node_names(self):
        self.assertEqual(
            SENSOR_NODE_NAMES,
            (
                "/livox_lidar_publisher2",
                "/oak_hardware_trigger_ros",
                "/oak_keyframe_stitcher",
            ),
        )
        for name in SENSOR_NODE_NAMES:
            self.assertIn(name, NODE_PING_COMMANDS)
            self.assertIn(name, NODE_PING_COMMANDS[name][-1])

    def test_host_sensor_process_command_is_distinct_and_fixed(self):
        self.assertEqual(HOST_SENSOR_PROCESS_COMMAND, ["ps", "-eo", "pid,args"])

    def test_inspect_parser_requires_pid(self):
        self.assertIsNone(parse_container_state('{"Running":false,"Status":"exited"}'))

    def test_inspect_parser_reads_stopped_state(self):
        parsed = parse_container_state(STOPPED_INSPECT)
        self.assertFalse(parsed["running"])
        self.assertEqual(parsed["pid"], 0)


class MonitorTests(GuardCase):
    def test_monitor_healthy_is_probe_only(self):
        runner = ScriptedRunner([healthy_sample()])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["status"], "HEALTHY")
        self.assertFalse(result["manual_action_required"])
        self.assertEqual(runner.calls, [(PROBE_ARGV, 90)])

    def test_monitor_active_healthy_is_observation_only(self):
        sample = healthy_sample()
        sample["project_duration"] = 30.0
        sample["health"]["category"] = "active"
        runner = ScriptedRunner([sample])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["status"], "ACTIVE_MONITORING")
        self.assertFalse(result["manual_action_required"])

    def test_monitor_active_fault_alerts_without_action(self):
        runner = ScriptedRunner([fault_sample("livox_no_data", active=True)])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["status"], "MONITOR_ALERT")
        self.assertEqual(result["reason"], "active_livox_no_data")
        self.assertTrue(result["manual_action_required"])
        self.assertEqual(len(runner.calls), 1)

    def test_monitor_container_not_running_alerts(self):
        runner = ScriptedRunner([stopped_sample()])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["reason"], "container_not_running")
        self.assertTrue(result["manual_action_required"])

    def test_monitor_livox_packet_alerts(self):
        runner = ScriptedRunner([fault_sample("livox_packet_mode")])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["reason"], "livox_packet_mode")
        self.assertEqual(runner.calls, [(PROBE_ARGV, 90)])

    def test_monitor_oak_crash_alerts(self):
        runner = ScriptedRunner([fault_sample("oak_xlink_crash")])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["reason"], "oak_xlink_crash")
        self.assertTrue(result["manual_action_required"])

    def test_monitor_probe_command_failure_is_fail_closed(self):
        runner = ScriptedRunner([RunResult(2, "", "failed")])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["reason"], "probe_or_parse_failed")
        self.assertTrue(result["manual_action_required"])

    def test_monitor_malformed_json_is_fail_closed(self):
        runner = ScriptedRunner(["not-json"])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["status"], "MONITOR_ALERT")

    def test_monitor_invalid_shape_is_fail_closed(self):
        runner = ScriptedRunner([{"health": {"category": "healthy"}}])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["reason"], "probe_or_parse_failed")

    def test_corrupt_state_blocks_before_probe(self):
        Path(self.config["state_path"]).write_text("{broken", encoding="utf-8")
        runner = ScriptedRunner([])
        result = self.make_guard(runner).run("monitor")
        self.assertEqual(result["status"], "STATE_INVALID")
        self.assertEqual(runner.calls, [])
        self.assertTrue(result["manual_lock"])

    def test_lock_contention_blocks_before_probe(self):
        runner = ScriptedRunner([])
        guard = Guard(self.config, runner=runner, lock_acquirer=lambda _: False)
        result = guard.run("monitor")
        self.assertEqual(result["status"], "LOCKED")
        self.assertEqual(runner.calls, [])

    def test_monitor_log_is_strict_jsonl(self):
        runner = ScriptedRunner([healthy_sample()])
        self.make_guard(runner).run("monitor")
        lines = Path(self.config["log_path"]).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["mode"], "monitor")
        self.assertEqual(record["status"], "HEALTHY")


class StartupTests(GuardCase):
    def test_startup_waits_for_exact_ntp_yes(self):
        first = stopped_sample()
        first["ntp"] = "no"
        runner = ScriptedRunner(
            [first, stopped_sample(), healthy_sample(), healthy_sample(), healthy_sample()],
            startup_commands(),
        )
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["status"], "STARTED_HEALTHY")
        self.assertEqual(self.sleeps, [5, 15, 105])

    def test_startup_ntp_timeout_blocks_without_action(self):
        sample = stopped_sample()
        sample["ntp"] = "no"
        runner = ScriptedRunner([sample, sample, sample])
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["reason"], "ntp_wait_timeout")
        self.assertNotIn((START_COMMAND, 30), runner.calls)

    def test_startup_probe_failure_blocks(self):
        runner = ScriptedRunner([RunResult(1, "", "probe failed")])
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["reason"], "probe_or_parse_failed")

    def test_startup_project_duration_active_blocks(self):
        sample = stopped_sample()
        sample["project_duration"] = 1.0
        sample["health"]["category"] = "active"
        runner = ScriptedRunner([sample])
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["reason"], "project_or_acquisition_active")

    def test_startup_real_core_process_active_blocks(self):
        sample = stopped_sample()
        sample["core_processes"] = ["44 rosbag record -a"]
        sample["health"]["category"] = "active"
        runner = ScriptedRunner([sample])
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["status"], "STARTUP_BLOCKED")
        self.assertEqual(len(runner.calls), 1)

    def test_startup_already_running_never_stops(self):
        runner = ScriptedRunner([healthy_sample()])
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["status"], "ALREADY_RUNNING")
        self.assertEqual(runner.calls, [(PROBE_ARGV, 90)])

    def test_startup_already_running_fault_requests_manual_action(self):
        runner = ScriptedRunner([fault_sample("camera_no_data")])
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["status"], "ALREADY_RUNNING")
        self.assertTrue(result["manual_action_required"])

    def test_startup_stopped_but_sensor_process_present_blocks(self):
        sample = stopped_sample()
        sample["sensor_processes_present"] = True
        sample["sensor_processes"] = ["77 livox_ros_driver2_node"]
        runner = ScriptedRunner([sample])
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["reason"], "sensor_process_present")

    def test_startup_dry_run_blocks(self):
        runner = ScriptedRunner([stopped_sample()])
        result = self.make_guard(runner, dry_run=True).run("startup")
        self.assertEqual(result["reason"], "dry_run")
        self.assertEqual(len(runner.calls), 1)

    def test_startup_authorization_default_blocks(self):
        runner = ScriptedRunner([stopped_sample()])
        result = self.make_guard(runner, allow_startup_start=False).run("startup")
        self.assertEqual(result["reason"], "startup_start_not_authorized")

    def test_startup_does_not_run_host_residue_probe(self):
        result, runner = self.successful_startup()
        self.assertEqual(result["status"], "STARTED_HEALTHY")
        self.assertNotIn((HOST_SENSOR_PROCESS_COMMAND, 30), runner.calls)

    def test_startup_cleanup_failure_stops_before_start(self):
        commands = startup_commands()
        commands[tuple(CLEANUP_COMMAND)] = 1
        runner = ScriptedRunner([stopped_sample()], commands)
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["reason"], "cleanup_failed")
        self.assertNotIn((START_COMMAND, 30), runner.calls)

    def test_startup_reachable_stale_node_blocks(self):
        node = next(iter(NODE_PING_COMMANDS))
        commands = startup_commands()
        commands[tuple(NODE_LIST_COMMAND)] = node + "\n"
        commands[tuple(NODE_PING_COMMANDS[node])] = 0
        runner = ScriptedRunner([stopped_sample()], commands)
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["reason"], "sensor_node_reachable")

    def test_startup_start_failure_is_reported(self):
        commands = startup_commands()
        commands[tuple(START_COMMAND)] = 1
        runner = ScriptedRunner([stopped_sample()], commands)
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["reason"], "start_failed")

    def test_startup_livox_postcheck_failure(self):
        runner = ScriptedRunner(
            [stopped_sample(), fault_sample("livox_no_data")], startup_commands()
        )
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["reason"], "livox_postcheck_failed")
        self.assertEqual(self.sleeps, [15])

    def test_startup_oak_postcheck_failure(self):
        runner = ScriptedRunner(
            [stopped_sample(), healthy_sample(), fault_sample("camera_no_data")],
            startup_commands(),
        )
        result = self.make_guard(runner).run("startup")
        self.assertEqual(result["reason"], "oak_postcheck_failed")
        self.assertEqual(self.sleeps, [15, 105])

    def test_startup_success_runs_single_start_and_postchecks(self):
        result, runner = self.successful_startup()
        self.assertEqual(result["status"], "STARTED_HEALTHY")
        self.assertEqual(self.sleeps, [15, 105])
        self.assertEqual(sum(1 for argv, _ in runner.calls if argv == START_COMMAND), 1)
        self.assertNotIn((STOP_COMMAND, 30), runner.calls)


class ManualRecoveryTests(GuardCase):
    def test_manual_cli_confirmation_required(self):
        runner = ScriptedRunner([])
        result = self.make_guard(runner).run("manual-recover")
        self.assertEqual(result["reason"], "cli_confirmation_missing")
        self.assertEqual(runner.calls, [])

    def test_manual_config_authorization_required(self):
        runner = ScriptedRunner([])
        result = self.make_guard(runner, allow_manual_recovery=False).run(
            "manual-recover", confirm_manual_recovery=True
        )
        self.assertEqual(result["reason"], "config_authorization_missing")

    def test_manual_dry_run_refuses(self):
        runner = ScriptedRunner([])
        result = self.make_guard(runner, dry_run=True).run(
            "manual-recover", confirm_manual_recovery=True
        )
        self.assertEqual(result["reason"], "dry_run")

    def test_manual_ntp_no_sets_lock_without_stop(self):
        sample = fault_sample()
        sample["ntp"] = "no"
        runner = ScriptedRunner([sample])
        result = self.make_guard(runner).run(
            "manual-recover", confirm_manual_recovery=True
        )
        self.assertEqual(result["reason"], "ntp_not_synchronized")
        self.assertTrue(result["manual_lock"])
        self.assertNotIn((STOP_COMMAND, 30), runner.calls)

    def test_manual_active_project_sets_lock(self):
        runner = ScriptedRunner([fault_sample(active=True)])
        result = self.make_guard(runner).run(
            "manual-recover", confirm_manual_recovery=True
        )
        self.assertEqual(result["reason"], "project_or_acquisition_active")
        self.assertTrue(result["manual_lock"])

    def test_manual_container_not_running_sets_lock(self):
        runner = ScriptedRunner([stopped_sample()])
        result = self.make_guard(runner).run(
            "manual-recover", confirm_manual_recovery=True
        )
        self.assertEqual(result["reason"], "container_not_running")

    def test_manual_stop_failure_sets_lock(self):
        commands = manual_commands()
        commands[tuple(STOP_COMMAND)] = 1
        result, _ = self.successful_manual(commands=commands, probes=[fault_sample()])
        self.assertEqual(result["reason"], "stop_failed")
        self.assertTrue(result["manual_lock"])

    def test_manual_stop_uses_exact_20_second_argv(self):
        result, runner = self.successful_manual()
        self.assertEqual(result["status"], "MANUAL_RECOVERY_SUCCEEDED")
        self.assertIn((STOP_COMMAND, 30), runner.calls)
        self.assertEqual(STOP_COMMAND, ["docker", "stop", "-t", "20", "firmware-sensors"])

    def test_manual_inspect_running_state_fails(self):
        commands = manual_commands()
        commands[tuple(INSPECT_COMMAND)] = RUNNING_INSPECT
        result, _ = self.successful_manual(commands=commands, probes=[fault_sample()])
        self.assertEqual(result["reason"], "stop_inspect_failed")

    def test_manual_inspect_malformed_state_fails(self):
        commands = manual_commands()
        commands[tuple(INSPECT_COMMAND)] = "not-json"
        result, _ = self.successful_manual(commands=commands, probes=[fault_sample()])
        self.assertEqual(result["reason"], "stop_inspect_failed")

    def test_manual_host_sensor_process_query_failure(self):
        commands = manual_commands()
        commands[tuple(HOST_SENSOR_PROCESS_COMMAND)] = RunResult(1, "", "ps failed")
        result, _ = self.successful_manual(commands=commands, probes=[fault_sample()])
        self.assertEqual(result["reason"], "sensor_process_query_failed")

    def test_manual_host_sensor_process_remaining(self):
        commands = manual_commands()
        commands[tuple(HOST_SENSOR_PROCESS_COMMAND)] = (
            "PID COMMAND\n77 /opt/slam/bin/oak_hardware_trigger_ros\n"
        )
        result, _ = self.successful_manual(commands=commands, probes=[fault_sample()])
        self.assertEqual(result["reason"], "sensor_process_remaining")
        self.assertTrue(result["manual_lock"])

    def test_manual_cleanup_failure(self):
        commands = manual_commands()
        commands[tuple(CLEANUP_COMMAND)] = 1
        result, runner = self.successful_manual(commands=commands, probes=[fault_sample()])
        self.assertEqual(result["reason"], "cleanup_failed")
        self.assertNotIn((START_COMMAND, 30), runner.calls)

    def test_manual_node_list_failure(self):
        commands = manual_commands()
        commands[tuple(NODE_LIST_COMMAND)] = RunResult(1, "", "master unavailable")
        result, _ = self.successful_manual(commands=commands, probes=[fault_sample()])
        self.assertEqual(result["reason"], "node_list_failed")

    def test_manual_reachable_sensor_node_fails(self):
        node = next(iter(NODE_PING_COMMANDS))
        commands = manual_commands()
        commands[tuple(NODE_LIST_COMMAND)] = node + "\n"
        commands[tuple(NODE_PING_COMMANDS[node])] = 0
        result, _ = self.successful_manual(commands=commands, probes=[fault_sample()])
        self.assertEqual(result["reason"], "sensor_node_reachable")

    def test_manual_unreachable_stale_node_allows_sequence(self):
        node = next(iter(NODE_PING_COMMANDS))
        commands = manual_commands()
        commands[tuple(NODE_LIST_COMMAND)] = node + "\n"
        commands[tuple(NODE_PING_COMMANDS[node])] = 1
        result, runner = self.successful_manual(commands=commands)
        self.assertEqual(result["status"], "MANUAL_RECOVERY_SUCCEEDED")
        self.assertIn((NODE_PING_COMMANDS[node], 30), runner.calls)

    def test_manual_start_failure(self):
        commands = manual_commands()
        commands[tuple(START_COMMAND)] = 1
        result, _ = self.successful_manual(commands=commands, probes=[fault_sample()])
        self.assertEqual(result["reason"], "start_failed")
        self.assertTrue(result["manual_lock"])

    def test_manual_livox_postcheck_failure(self):
        result, _ = self.successful_manual(
            probes=[fault_sample(), fault_sample("livox_no_data")]
        )
        self.assertEqual(result["reason"], "livox_postcheck_failed")
        self.assertEqual(self.sleeps, [15])

    def test_manual_oak_postcheck_failure(self):
        result, _ = self.successful_manual(
            probes=[fault_sample(), healthy_sample(), fault_sample("oak_xlink_crash")]
        )
        self.assertEqual(result["reason"], "oak_postcheck_failed")
        self.assertEqual(self.sleeps, [15, 105])

    def test_manual_success_clears_existing_lock(self):
        state = new_state()
        state["manual_lock"] = True
        state["status"] = "MANUAL_RECOVERY_FAILED"
        state["reason"] = "prior_failure"
        self.write_state(state)
        result, _ = self.successful_manual()
        self.assertEqual(result["status"], "MANUAL_RECOVERY_SUCCEEDED")
        self.assertFalse(result["manual_lock"])
        self.assertFalse(result["manual_action_required"])

    def test_manual_success_exact_sequence(self):
        result, runner = self.successful_manual()
        self.assertEqual(result["status"], "MANUAL_RECOVERY_SUCCEEDED")
        action_calls = [argv for argv, _ in runner.calls if argv != PROBE_ARGV]
        self.assertEqual(
            action_calls,
            [
                STOP_COMMAND,
                INSPECT_COMMAND,
                HOST_SENSOR_PROCESS_COMMAND,
                CLEANUP_COMMAND,
                NODE_LIST_COMMAND,
                START_COMMAND,
            ],
        )
        self.assertEqual(self.sleeps, [15, 105])


class StaticSafetyTests(GuardCase):
    def test_all_runner_actions_exclude_forbidden_commands(self):
        _, startup_runner = self.successful_startup()
        self.sleeps.clear()
        _, manual_runner = self.successful_manual()
        flattened = [
            item
            for runner in (startup_runner, manual_runner)
            for argv, _ in runner.calls
            for item in argv
        ]
        forbidden = [
            "docker " + "restart",
            "p" + "kill",
            "/stm32" + "_cmd",
            "rgb" + "control",
            "rostopic pub",
        ]
        for token in forbidden:
            self.assertFalse(any(token in item for item in flattened), token)

    def test_monitor_service_executes_monitor_only(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / "d360-sensor-guard.service").read_text(encoding="utf-8")
        self.assertIn("d360_sensor_guard.py monitor /etc/", service)
        self.assertNotIn("manual-recover", service)
        self.assertNotIn(" startup ", service)

    def test_timer_targets_monitor_service_only(self):
        root = Path(__file__).resolve().parents[1]
        timer = (root / "d360-sensor-guard.timer").read_text(encoding="utf-8")
        self.assertIn("Unit=d360-sensor-guard.service", timer)
        self.assertNotIn("manual-recover", timer)
        self.assertNotIn("startup", timer)

    def test_startup_unit_is_installable_and_retries_failures(self):
        root = Path(__file__).resolve().parents[1]
        startup = (root / "d360-sensor-guard-startup.service").read_text(encoding="utf-8")
        self.assertIn("d360_sensor_guard.py startup /etc/", startup)
        self.assertIn("[Install]", startup)
        self.assertIn("WantedBy=multi-user.target", startup)
        self.assertIn("Restart=on-failure", startup)
        self.assertIn("RestartSec=10s", startup)

    def test_no_manual_recovery_unit_exists(self):
        root = Path(__file__).resolve().parents[1]
        unit_names = {path.name for path in root.glob("*.service")}
        self.assertNotIn("d360-sensor-guard-manual-recover.service", unit_names)


if __name__ == "__main__":
    unittest.main()
