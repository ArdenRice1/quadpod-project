import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import switch_network


class FakeResult:
    def __init__(self, returncode, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


class WifiAssociatedTests(unittest.TestCase):
    """wifi_associated must only report success when wlan0 is truly on the
    target SSID with an IP -- the anti-strand check for switch_to_wifi."""

    def setUp(self):
        self._orig_run = switch_network.run

    def tearDown(self):
        switch_network.run = self._orig_run

    def _stub(self, returncode, stdout):
        switch_network.run = lambda *a, **k: FakeResult(returncode, stdout)

    def test_true_when_connected_with_ip(self):
        self._stub(0, "GENERAL.CONNECTION:HomeNet\nIP4.ADDRESS[1]:192.168.1.20/24\n")
        self.assertTrue(switch_network.wifi_associated("HomeNet"))

    def test_false_when_no_ip_yet(self):
        self._stub(0, "GENERAL.CONNECTION:HomeNet\nIP4.ADDRESS[1]:\n")
        self.assertFalse(switch_network.wifi_associated("HomeNet"))

    def test_false_when_connected_to_other_ssid(self):
        self._stub(0, "GENERAL.CONNECTION:OtherNet\nIP4.ADDRESS[1]:192.168.1.20/24\n")
        self.assertFalse(switch_network.wifi_associated("HomeNet"))

    def test_false_when_nmcli_fails(self):
        self._stub(1, "")
        self.assertFalse(switch_network.wifi_associated("HomeNet"))


if __name__ == "__main__":
    unittest.main()
