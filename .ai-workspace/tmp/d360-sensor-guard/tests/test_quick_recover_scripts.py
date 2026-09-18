import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUICK_PATH = ROOT / "d360_quick_recover.sh"
AUTO_PATH = ROOT / "d360_auto_recover.sh"
SERVICE_PATH = ROOT / "d360-auto-recover.service"
TIMER_PATH = ROOT / "d360-auto-recover.timer"


class QuickRecoverScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quick = QUICK_PATH.read_text(encoding="utf-8")
        cls.auto = AUTO_PATH.read_text(encoding="utf-8")
        cls.service = SERVICE_PATH.read_text(encoding="utf-8")
        cls.timer = TIMER_PATH.read_text(encoding="utf-8")

    def test_bash_syntax(self):
        bash_executable = (
            r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else "bash"
        )
        result = subprocess.run(
            [bash_executable, "-n", QUICK_PATH.name, AUTO_PATH.name],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_quick_uses_exact_stop_timeout(self):
        self.assertIn('docker stop -t 20 "$CONTAINER"', self.quick)

    def test_quick_orders_stop_cleanup_start(self):
        self.assertLess(self.quick.index("docker stop -t 20"), self.quick.index("rosnode cleanup"))
        self.assertLess(self.quick.index("rosnode cleanup"), self.quick.index('docker start "$CONTAINER"'))

    def test_quick_requires_container_stopped_pid_zero(self):
        self.assertIn('"false 0 exited"', self.quick)

    def test_quick_never_kills_processes(self):
        self.assertNotIn("kill -9", self.quick)
        self.assertNotIn("pkill", self.quick)
        self.assertIn("不自动kill", self.quick)

    def test_quick_cleans_ros_stale_nodes(self):
        self.assertIn("printf 'y\\n' | rosnode cleanup", self.quick)

    def test_quick_blocks_active_acquisition(self):
        for name in ("rosbag", "record_node", "run_mapping_online", "laserMapping", "lidar_add_rgb"):
            self.assertIn(name, self.quick)
        self.assertLess(self.quick.index("BLOCKER_RE"), self.quick.index("docker stop -t 20"))

    def test_hotspot_is_allowed_without_ntp(self):
        self.assertIn("hotspot_active", self.quick)
        self.assertIn('"$hotspot_active" != "Hotspot"', self.quick)
        self.assertIn("hotspot_active", self.auto)

    def test_wifi_requires_ntp(self):
        self.assertIn("NTP尚未同步且不在Hotspot模式", self.quick)
        self.assertIn("NTP未同步且不在Hotspot模式", self.auto)

    def test_auto_checks_livox_packet_mode(self):
        self.assertIn("r > 100", self.auto)
        self.assertIn('"$point_num" -lt 1000', self.auto)
        self.assertIn("livox_packet_mode_", self.auto)

    def test_auto_checks_timeshare_content_change(self):
        self.assertGreaterEqual(self.auto.count("/dev/shm/timeshare"), 2)
        self.assertIn("timeshare_frozen", self.auto)

    def test_auto_checks_real_camera_frames(self):
        self.assertIn("camera_no_frames_", self.auto)
        self.assertIn('"$topic/header"', self.auto)
        self.assertIn("grep -q 'stamp:'", self.auto)

    def test_auto_checks_keyframe_frame(self):
        self.assertIn("/keyframe/header", self.auto)
        self.assertIn("keyframe_no_frames", self.auto)

    def test_auto_has_lock_and_cooldown(self):
        self.assertIn("flock -n 9", self.auto)
        self.assertIn("COOLDOWN=180", self.auto)

    def test_auto_does_not_recover_while_active(self):
        self.assertIn("检测到标定/采集进程，仅告警不恢复", self.auto)
        self.assertLess(self.auto.index("BLOCKER_RE"), self.auto.index('"$RECOVER"'))

    def test_scripts_never_control_led(self):
        combined = self.quick + self.auto
        self.assertNotIn("/stm32_cmd", combined)
        self.assertNotIn("rgbcontrol", combined)

    def test_scripts_never_use_docker_restart(self):
        self.assertNotIn("docker restart", self.quick + self.auto)

    def test_timer_runs_every_thirty_seconds(self):
        self.assertIn("OnBootSec=30s", self.timer)
        self.assertIn("OnUnitActiveSec=30s", self.timer)
        self.assertIn("Unit=d360-auto-recover.service", self.timer)

    def test_service_only_invokes_auto_script(self):
        self.assertIn("ExecStart=/usr/local/sbin/d360-auto-recover", self.service)
        self.assertNotIn("d360-quick-recover", self.service)


if __name__ == "__main__":
    unittest.main()
