"""Raspberry Pi 서버와 V-PR100 브리지 분리 서비스 설정 테스트."""

from __future__ import annotations

import unittest
from pathlib import Path


class DeploymentServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        service_dir = Path(__file__).resolve().parents[1] / "deploy" / "systemd"
        cls.server = (service_dir / "lifesignal-server.service").read_text(
            encoding="utf-8"
        )
        cls.bridge = (
            service_dir / "lifesignal-vpr100-bridge.service"
        ).read_text(encoding="utf-8")

    def test_server_service_runs_only_server(self) -> None:
        self.assertIn("server.py", self.server)
        self.assertNotIn("serial_bridge.py", self.server)
        self.assertNotIn("run_pi.py", self.server)

    def test_bridge_service_runs_only_serial_bridge(self) -> None:
        self.assertIn("serial_bridge.py", self.bridge)
        self.assertNotIn("server.py --", self.bridge)
        self.assertNotIn("run_pi.py", self.bridge)
        self.assertIn("After=lifesignal-server.service", self.bridge)


if __name__ == "__main__":
    unittest.main()
