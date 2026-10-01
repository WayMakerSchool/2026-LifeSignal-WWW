"""서버 센서 로그 출력 회귀 테스트."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from server import print_sensor_summary


class ServerSensorLoggingTest(unittest.TestCase):
    def test_c4001_summary_omits_unavailable_score(self) -> None:
        message = json.dumps(
            {
                "type": "radar_data",
                "sensor": "C4001",
                "room": 402,
                "location": "거실",
                "status": False,
                "ai": {"ready": False, "reason": "no_target"},
            }
        )
        output = io.StringIO()

        with redirect_stdout(output):
            print_sensor_summary(message)

        self.assertEqual(
            output.getvalue().strip(),
            "센서 수신: 402호 거실 감지=False",
        )
        self.assertNotIn("점수", output.getvalue())


if __name__ == "__main__":
    unittest.main()
