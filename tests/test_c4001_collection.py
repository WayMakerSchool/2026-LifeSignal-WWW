"""C4001 시리얼 수집 회귀 테스트."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from AI.collect_c4001_serial import (
    CSV_COLUMNS,
    SAMPLE_PREFIX,
    ActiveCaptureTimer,
    parse_sample_line,
    resolve_port,
)


class C4001SerialCollectionTest(unittest.TestCase):
    def test_converts_raw_serial_sample_to_training_row(self) -> None:
        sample = {
            "type": "c4001_sample",
            "sample_millis": 12345,
            "sensor": "C4001",
            "room": 402,
            "location": "거실",
            "motion": True,
            "instant_presence": True,
            "status": False,
            "target_number": 1,
            "target_speed_m_s": 0.125,
            "target_range_m": 0.72,
            "target_energy": 6321,
        }
        row = parse_sample_line(
            SAMPLE_PREFIX + json.dumps(sample),
            label="human",
            session_id="c4001_human_01",
            timestamp="2026-08-12T00:00:00+00:00",
        )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(tuple(row), CSV_COLUMNS)
        self.assertEqual(row["label"], "human")
        self.assertEqual(row["sensor_id"], "c4001")
        self.assertEqual(row["room"], 402)
        self.assertEqual(row["location"], "거실")
        self.assertFalse(row["status"])
        self.assertEqual(row["target_energy"], 6321)
        self.assertNotIn("sensor", row)
        self.assertNotIn("motion", row)
        self.assertNotIn("instant_presence", row)
        self.assertNotIn("target_number", row)
        self.assertNotIn("target_speed_m_s", row)
        self.assertNotIn("target_range_m", row)
        self.assertNotIn("work_status", row)
        self.assertNotIn("work_mode", row)
        self.assertNotIn("init_status", row)

    def test_keeps_existing_serial_output_out_of_csv(self) -> None:
        self.assertIsNone(
            parse_sample_line(
                '전송 데이터: {"type":"radar_data"}',
                label="dog",
                session_id="dog_01",
            )
        )

    def test_rejects_invalid_prefixed_sample(self) -> None:
        with self.assertRaises(ValueError):
            parse_sample_line(
                SAMPLE_PREFIX + "not-json",
                label="human",
                session_id="human_01",
            )

    def test_disconnected_time_is_excluded_after_collection_resumes(self) -> None:
        timer = ActiveCaptureTimer(duration=5.0)

        self.assertFalse(timer.observe_sample(10.0))
        self.assertFalse(timer.observe_sample(12.0))
        timer.pause()
        self.assertEqual(timer.elapsed, 2.0)

        # 88초 뒤 재연결되어도 단절 시간은 누적되지 않습니다.
        self.assertFalse(timer.observe_sample(100.0))
        self.assertTrue(timer.observe_sample(103.0))
        timer.pause()
        self.assertEqual(timer.elapsed, 5.0)

    @patch("AI.collect_c4001_serial.available_ports")
    def test_linux_usb_port_is_detected(self, available_ports) -> None:
        available_ports.return_value = ["/dev/ttyACM0"]
        self.assertEqual(resolve_port(None), "/dev/ttyACM0")


if __name__ == "__main__":
    unittest.main()
