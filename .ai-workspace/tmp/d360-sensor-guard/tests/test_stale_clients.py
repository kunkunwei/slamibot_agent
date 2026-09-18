import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "d360_clear_stale_clients.sh"
AUTO = ROOT / "d360_auto_recover.sh"


class StaleClientCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.auto = AUTO.read_text(encoding="utf-8")

    def test_bash_syntax(self):
        bash = r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else "bash"
        result = subprocess.run(
            [bash, "-n", SCRIPT.name, AUTO.name],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_only_targets_client_ports(self):
        self.assertIn("PORTS='9090 5001'", self.script)
        self.assertNotIn("11311", self.script)

    def test_reads_current_assigned_ipv4(self):
        self.assertIn("ip -4 -o addr show", self.script)
        self.assertIn("is_current_ip", self.script)

    def test_current_ip_connections_are_skipped(self):
        current_check = 'if is_current_ip "$local_ip"; then'
        self.assertIn(current_check, self.script)
        self.assertLess(self.script.index(current_check), self.script.index("ss -K"))

    def test_only_established_connections_are_closed(self):
        self.assertIn("ss -Htn state established", self.script)
        self.assertIn("ss -K state established", self.script)

    def test_cleanup_has_independent_lock(self):
        self.assertIn("d360-stale-client-cleanup.lock", self.script)
        self.assertIn("flock -n 8", self.script)

    def test_cleanup_never_touches_services_or_led(self):
        forbidden = ("docker", "systemctl", "rosnode", "/stm32_cmd", "rgbcontrol")
        for token in forbidden:
            self.assertNotIn(token, self.script)

    def test_auto_runs_cleanup_before_ros_health_checks(self):
        self.assertIn("CLEAR_STALE=/usr/local/sbin/d360-clear-stale-clients", self.auto)
        self.assertIn('"$CLEAR_STALE"', self.auto)
        self.assertLess(self.auto.index('"$CLEAR_STALE"'), self.auto.index('source "$ROS_SETUP"'))


if __name__ == "__main__":
    unittest.main()
