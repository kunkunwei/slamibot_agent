import json
import os
import sys
import unittest
from collections import defaultdict
from typing import Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from d360_health_probe import (
    CAMERA_TEMPERATURE_INFO_COMMAND,
    CONTAINER_INSPECT_COMMAND,
    CORE_PROCESSES_COMMAND,
    IMU_RATE_COMMAND,
    KEYFRAME_RATE_COMMAND,
    LED_CONTROL_PING_COMMAND,
    LIDAR_RATE_COMMAND,
    NTP_COMMAND,
    POINT_NUM_COMMAND,
    PROJECT_DURATION_COMMAND,
    SENSOR_PROCESSES_COMMAND,
    SYSTEM_MONITOR_PING_COMMAND,
    TIMESHARE_COMMAND,
    USB_COMMAND,
    CommandResult,
    acquisition_active,
    camera_info_command,
    camera_rate_command,
    parse_average_rate,
    parse_container_state,
    parse_ntp,
    parse_point_num,
    parse_process_lines,
    parse_publisher_presence,
    parse_ros_data,
    parse_timeshare_pair,
    parse_usb_product,
    parse_usb_products,
    probe,
)

PUBLISHER = """Type: sensor_msgs/CompressedImage
Publishers:
 * /oak_driver (http://firmware-sensors:12345/)
Subscribers: None
"""
NO_PUBLISHER = """Type: sensor_msgs/CompressedImage
Publishers: None
Subscribers: None
"""
RATE_10 = "subscribed to [/topic]\naverage rate: 10.043\n"
RUNNING = json.dumps(
    {
        "Status": "running",
        "Running": True,
        "Pid": 4321,
        "StartedAt": "2026-09-02T15:02:50.123456789+08:00",
    }
)
STOPPED = json.dumps(
    {
        "Status": "exited",
        "Running": False,
        "Pid": 0,
        "StartedAt": "2026-09-02T14:44:00.000000000+08:00",
    }
)


class MappingRunner:
    def __init__(self, mapping):
        self.mapping = {}
        for argv, values in mapping.items():
            self.mapping[tuple(argv)] = list(values) if isinstance(values, list) else [values]
        self.indices = defaultdict(int)
        self.calls = []

    def run(self, argv: Sequence[str], timeout: int) -> CommandResult:
        key = tuple(argv)
        self.calls.append((list(argv), timeout))
        if key not in self.mapping:
            return CommandResult(127, "", "unscripted command")
        index = self.indices[key]
        self.indices[key] += 1
        values = self.mapping[key]
        value = values[min(index, len(values) - 1)]
        if isinstance(value, CommandResult):
            return value
        return CommandResult(0, value, "")


def healthy_mapping():
    mapping = {
        tuple(NTP_COMMAND): "yes\n",
        tuple(PROJECT_DURATION_COMMAND): "data: 0.0\n---\n",
        tuple(CORE_PROCESSES_COMMAND): "PID COMMAND\n11 roscore\n12 system_monitor\n",
        tuple(CONTAINER_INSPECT_COMMAND): RUNNING,
        tuple(SENSOR_PROCESSES_COMMAND): (
            "PID COMMAND\n"
            "21 /opt/ros/noetic/lib/livox_ros_driver2/livox_ros_driver2_node "
            "__name:=livox_lidar_publisher2\n"
            "22 /opt/slam/bin/oak_hardware_trigger_ros "
            "__name:=oak_hardware_trigger_ros\n"
            "23 /opt/slam/bin/oak_keyframe_stitcher "
            "__name:=oak_keyframe_stitcher\n"
        ),
        tuple(USB_COMMAND): "Bus 002 Device 005: ID 03e7:f63b Intel Movidius MyriadX\n",
        tuple(LIDAR_RATE_COMMAND): "average rate: 10.011\n",
        tuple(POINT_NUM_COMMAND): "point_num: 19968\n",
        tuple(IMU_RATE_COMMAND): "average rate: 199.863\n",
        tuple(TIMESHARE_COMMAND): [
            " 1772675917 124520000\n",
            " 1772675917 624520000\n",
        ],
        tuple(KEYFRAME_RATE_COMMAND): "average rate: 3.67\n",
        tuple(CAMERA_TEMPERATURE_INFO_COMMAND): PUBLISHER,
        tuple(LED_CONTROL_PING_COMMAND): "pinged machine of node successfully\n",
        tuple(SYSTEM_MONITOR_PING_COMMAND): "pinged machine of node successfully\n",
    }
    for camera in "ABC":
        mapping[tuple(camera_info_command(camera))] = PUBLISHER
        mapping[tuple(camera_rate_command(camera))] = RATE_10
    return mapping


def collect_with(mutator=None):
    mapping = healthy_mapping()
    if mutator:
        mutator(mapping)
    runner = MappingRunner(mapping)
    return probe(runner, sleeper=lambda _: None), runner


class ProbeParserTests(unittest.TestCase):
    def test_ntp_accepts_exact_yes(self):
        self.assertEqual(parse_ntp("yes\n"), "yes")

    def test_ntp_rejects_uppercase(self):
        self.assertIsNone(parse_ntp("YES\n"))

    def test_ntp_accepts_exact_no(self):
        self.assertEqual(parse_ntp("no"), "no")

    def test_ros_data_parses_wrapper(self):
        self.assertEqual(parse_ros_data("data: 4.25\n---\n"), 4.25)

    def test_ros_data_rejects_malformed(self):
        self.assertIsNone(parse_ros_data("data: waiting\n"))

    def test_average_rate_uses_last_window(self):
        self.assertEqual(parse_average_rate("average rate: 9.8\naverage rate: 10.2\n"), 10.2)

    def test_average_rate_rejects_no_messages(self):
        self.assertIsNone(parse_average_rate("WARNING: no new messages\n"))

    def test_point_num_parses_field(self):
        self.assertEqual(parse_point_num("point_num: 20064\n"), 20064)

    def test_point_num_parses_scalar(self):
        self.assertEqual(parse_point_num("96\n"), 96)

    def test_publisher_present(self):
        self.assertIs(parse_publisher_presence(PUBLISHER), True)

    def test_publisher_absent(self):
        self.assertIs(parse_publisher_presence(NO_PUBLISHER), False)

    def test_publisher_malformed_is_unknown(self):
        self.assertIsNone(parse_publisher_presence("Type: std_msgs/String\n"))

    def test_process_parser_removes_header(self):
        self.assertEqual(parse_process_lines("PID COMMAND\n8 roscore\n"), ["8 roscore"])

    def test_process_parser_accepts_empty_body(self):
        self.assertEqual(parse_process_lines("PID COMMAND\n"), [])

    def test_timeshare_parses_real_od_text(self):
        self.assertEqual(
            parse_timeshare_pair(" 1772675917 124520000\n"),
            (1772675917, 124520000),
        )

    def test_timeshare_parser_requires_two_int64_fields(self):
        self.assertIsNone(parse_timeshare_pair("1772675917\n"))
        self.assertIsNone(parse_timeshare_pair("1 2 3\n"))

    def test_timeshare_command_reads_real_file_with_fixed_argv(self):
        self.assertEqual(TIMESHARE_COMMAND[:3], ["docker", "exec", "firmware-sensors"])
        self.assertEqual(
            TIMESHARE_COMMAND[-1],
            "cat /dev/shm/timeshare | od -An -td8 -N16",
        )

    def test_usb_prefers_f63b_if_both_seen(self):
        self.assertEqual(parse_usb_product("ID 03e7:f63c\nID 03e7:f63b\n"), "f63b")

    def test_usb_products_preserve_observations(self):
        self.assertEqual(parse_usb_products("ID 03e7:f63c\nID 03e7:f63b\n"), ["f63c", "f63b"])

    def test_container_state_parses_real_inspect_json(self):
        parsed = parse_container_state(RUNNING)
        self.assertEqual(parsed["state"], "running")
        self.assertEqual(parsed["pid"], 4321)
        self.assertTrue(parsed["running"])

    def test_container_state_rejects_missing_pid(self):
        self.assertIsNone(parse_container_state('{"Status":"running","Running":true}'))

    def test_activity_uses_project_duration(self):
        self.assertIs(acquisition_active(1.0, ["11 roscore"]), True)

    def test_activity_uses_real_core_process(self):
        self.assertIs(acquisition_active(0.0, ["44 rosbag record -a"]), True)

    def test_activity_ignores_unrelated_core_process(self):
        self.assertIs(acquisition_active(0.0, ["11 roscore", "12 system_monitor"]), False)


class ProbeClassificationTests(unittest.TestCase):
    def test_healthy_shape_and_values(self):
        result, _ = collect_with()
        self.assertEqual(result["health"]["category"], "healthy")
        self.assertEqual(result["health"]["sensor_category"], "healthy")
        self.assertAlmostEqual(result["health"]["lidar_rate"], 10.011)
        self.assertEqual(result["health"]["point_num"], 19968)
        self.assertEqual(result["container"]["started_at"], "2026-09-02T15:02:50.123456789+08:00")
        joined = "\n".join(result["sensor_processes"])
        self.assertIn("livox_ros_driver2_node", joined)
        self.assertIn("oak_hardware_trigger_ros", joined)
        self.assertIn("oak_keyframe_stitcher", joined)
        json.dumps(result)

    def test_active_category_with_healthy_sensor(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(tuple(PROJECT_DURATION_COMMAND), "data: 22.0\n")
        )
        self.assertEqual(result["health"]["category"], "active")
        self.assertEqual(result["health"]["sensor_category"], "healthy")

    def test_active_keeps_underlying_livox_fault(self):
        def mutate(mapping):
            mapping[tuple(CORE_PROCESSES_COMMAND)] = "PID COMMAND\n44 run_mapping_online\n"
            mapping[tuple(LIDAR_RATE_COMMAND)] = "no new messages\n"

        result, _ = collect_with(mutate)
        self.assertEqual(result["health"]["category"], "active")
        self.assertEqual(result["health"]["sensor_category"], "livox_no_data")

    def test_query_failed_for_command_error(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(
                tuple(CORE_PROCESSES_COMMAND), CommandResult(1, "", "container absent")
            )
        )
        self.assertEqual(result["health"]["category"], "query_failed")
        self.assertIn("core_processes:exit_1", result["errors"])

    def test_query_failed_for_ntp_parse_error(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(tuple(NTP_COMMAND), "YES\n")
        )
        self.assertEqual(result["health"]["category"], "query_failed")
        self.assertIn("ntp:parse", result["errors"])

    def test_query_failed_for_container_parse_error(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(tuple(CONTAINER_INSPECT_COMMAND), "not-json\n")
        )
        self.assertEqual(result["health"]["category"], "query_failed")

    def test_container_not_running_skips_sensor_docker_top(self):
        result, runner = collect_with(
            lambda mapping: mapping.__setitem__(tuple(CONTAINER_INSPECT_COMMAND), STOPPED)
        )
        called = [argv for argv, _ in runner.calls]
        self.assertEqual(result["health"]["category"], "container_not_running")
        self.assertFalse(result["container"]["running"])
        self.assertEqual(result["sensor_processes"], [])
        self.assertFalse(result["sensor_processes_present"])
        self.assertNotIn(SENSOR_PROCESSES_COMMAND, called)
        self.assertNotIn(LIDAR_RATE_COMMAND, called)
        self.assertNotIn("sensor_processes:exit_1", result["errors"])

    def test_sensor_process_missing_livox(self):
        def mutate(mapping):
            mapping[tuple(SENSOR_PROCESSES_COMMAND)] = (
                "PID COMMAND\n22 oak_hardware_trigger_ros\n"
                "23 oak_keyframe_stitcher\n"
            )

        result, _ = collect_with(mutate)
        self.assertEqual(result["health"]["category"], "sensor_process_missing")

    def test_sensor_process_missing_stitcher(self):
        def mutate(mapping):
            mapping[tuple(SENSOR_PROCESSES_COMMAND)] = (
                "PID COMMAND\n21 livox_ros_driver2_node\n"
                "22 oak_hardware_trigger_ros\n"
            )

        result, _ = collect_with(mutate)
        self.assertEqual(result["health"]["category"], "sensor_process_missing")

    def test_livox_no_data(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(tuple(LIDAR_RATE_COMMAND), "no new messages\n")
        )
        self.assertEqual(result["health"]["category"], "livox_no_data")

    def test_inner_observation_timeout_with_rate_is_accepted(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(
                tuple(LIDAR_RATE_COMMAND), CommandResult(124, "average rate: 10.012\n", "")
            )
        )
        self.assertEqual(result["health"]["category"], "healthy")
        self.assertAlmostEqual(result["health"]["lidar_rate"], 10.012)

    def test_inner_observation_timeout_without_messages_is_no_data(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(
                tuple(LIDAR_RATE_COMMAND), CommandResult(124, "no new messages\n", "")
            )
        )
        self.assertEqual(result["health"]["category"], "livox_no_data")
        self.assertNotIn("lidar_rate:exit_124", result["errors"])

    def test_outer_subprocess_timeout_is_query_failed(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(
                tuple(LIDAR_RATE_COMMAND), CommandResult(124, "average rate: 10.0\n", "", True)
            )
        )
        self.assertEqual(result["health"]["category"], "query_failed")
        self.assertIn("lidar_rate:timeout", result["errors"])

    def test_livox_packet_mode_2083_96(self):
        def mutate(mapping):
            mapping[tuple(LIDAR_RATE_COMMAND)] = "average rate: 2083.33\n"
            mapping[tuple(POINT_NUM_COMMAND)] = "point_num: 96\n"

        result, _ = collect_with(mutate)
        self.assertEqual(result["health"]["category"], "livox_packet_mode")

    def test_timeshare_low_field_change_is_healthy(self):
        result, _ = collect_with()
        self.assertTrue(result["health"]["timeshare_changed"])
        self.assertEqual(result["health"]["category"], "healthy")

    def test_timeshare_low_field_frozen_ignores_high_change(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(
                tuple(TIMESHARE_COMMAND),
                [" 1772675917 124520000\n", " 1772675918 124520000\n"],
            )
        )
        self.assertEqual(result["health"]["category"], "timeshare_frozen")
        self.assertFalse(result["health"]["timeshare_changed"])

    def test_timeshare_samples_have_explicit_half_second_interval(self):
        runner = MappingRunner(healthy_mapping())
        delays = []
        result = probe(runner, sleeper=delays.append)
        self.assertEqual(result["health"]["category"], "healthy")
        self.assertEqual(delays, [0.5])

    def test_timeshare_malformed_od_text_is_query_failed(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(
                tuple(TIMESHARE_COMMAND), ["not two integers\n", " 1 2\n"]
            )
        )
        self.assertEqual(result["health"]["category"], "query_failed")
        self.assertIn("timeshare_first:parse", result["errors"])

    def test_oak_f63c_crash(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(tuple(USB_COMMAND), "ID 03e7:f63c Intel\n")
        )
        self.assertEqual(result["health"]["category"], "oak_xlink_crash")
        self.assertEqual(result["usb_product"], "f63c")

    def test_oak_missing_with_no_publishers_is_xlink_crash(self):
        def mutate(mapping):
            mapping[tuple(SENSOR_PROCESSES_COMMAND)] = (
                "PID COMMAND\n21 livox_ros_driver2_node\n23 oak_keyframe_stitcher\n"
            )
            for camera in "ABC":
                mapping[tuple(camera_info_command(camera))] = NO_PUBLISHER

        result, _ = collect_with(mutate)
        self.assertEqual(result["health"]["category"], "oak_xlink_crash")

    def test_stale_publishers_do_not_replace_oak_process(self):
        def mutate(mapping):
            mapping[tuple(SENSOR_PROCESSES_COMMAND)] = (
                "PID COMMAND\n21 livox_ros_driver2_node\n23 oak_keyframe_stitcher\n"
            )

        result, _ = collect_with(mutate)
        self.assertEqual(result["health"]["category"], "sensor_process_missing")

    def test_camera_no_data_for_publisher(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(tuple(camera_info_command("A")), NO_PUBLISHER)
        )
        self.assertEqual(result["health"]["category"], "camera_no_data")

    def test_camera_no_data_for_rate(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(tuple(camera_rate_command("B")), "no new messages\n")
        )
        self.assertEqual(result["health"]["category"], "camera_no_data")

    def test_camera_no_data_for_temperature(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(
                tuple(CAMERA_TEMPERATURE_INFO_COMMAND), NO_PUBLISHER
            )
        )
        self.assertEqual(result["health"]["category"], "camera_no_data")

    def test_keyframe_no_data(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(tuple(KEYFRAME_RATE_COMMAND), "no new messages\n")
        )
        self.assertEqual(result["health"]["category"], "keyframe_no_data")

    def test_optional_led_failure_does_not_change_health(self):
        result, _ = collect_with(
            lambda mapping: mapping.__setitem__(
                tuple(LED_CONTROL_PING_COMMAND), CommandResult(1, "", "missing")
            )
        )
        self.assertEqual(result["health"]["category"], "healthy")
        self.assertFalse(result["led"]["led_control_alive"])
        self.assertIn("led_control_ping:exit_1", result["errors"])

    def test_only_expected_fixed_read_only_argv_are_called(self):
        _, runner = collect_with()
        called = [argv for argv, _ in runner.calls]
        self.assertEqual(len(called), 21)
        self.assertEqual(called.count(TIMESHARE_COMMAND), 2)
        self.assertIn(SENSOR_PROCESSES_COMMAND, called)
        self.assertEqual(
            SENSOR_PROCESSES_COMMAND,
            ["docker", "top", "firmware-sensors", "-eo", "pid,args"],
        )
        self.assertNotIn(["ps", "-eo", "pid,args"], called)
        flattened = [item for argv in called for item in argv]
        forbidden = [
            "docker " + "restart",
            "p" + "kill",
            "/stm32" + "_cmd",
            "rgb" + "control",
            "rostopic pub",
        ]
        for token in forbidden:
            self.assertFalse(any(token in item for item in flattened), token)


if __name__ == "__main__":
    unittest.main()
