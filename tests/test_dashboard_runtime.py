"""메인 대시보드의 Raspberry Pi 자동 연결 설정 테스트."""

from __future__ import annotations

import unittest
from pathlib import Path


class DashboardRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (
            Path(__file__).resolve().parents[1] / "LifeSignal.html"
        ).read_text(encoding="utf-8")

    def test_uses_serving_host_for_automatic_websocket_connection(self) -> None:
        self.assertIn("ipInput.value = window.location.host", self.html)
        self.assertIn("connectWebSocket(true)", self.html)

    def test_retries_websocket_after_disconnect(self) -> None:
        self.assertIn("AUTO_RECONNECT_DELAY_MS", self.html)
        self.assertIn("setTimeout(() =>", self.html)

    def test_keeps_sensor_readings_by_room_and_location(self) -> None:
        self.assertIn("let zoneReadings = {}", self.html)
        self.assertIn("function readingKey(reading)", self.html)
        self.assertIn("normalizeLocation(reading.location)", self.html)

    def test_lists_detected_locations_and_selects_zone_markers(self) -> None:
        self.assertIn("const activeLocations", self.html)
        self.assertIn("`${location} 감지`", self.html)
        self.assertIn("function selectSurvivor(key)", self.html)
        self.assertIn("data-reading-key", self.html)

    def test_subscribes_as_dashboard_after_connection(self) -> None:
        self.assertIn("type: 'subscribe', role: 'dashboard'", self.html)


if __name__ == "__main__":
    unittest.main()
