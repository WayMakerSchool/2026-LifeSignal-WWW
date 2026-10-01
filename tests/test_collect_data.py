from __future__ import annotations

import argparse
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from AI import collect_data


class FakeWebSocket:
    def __init__(self, message: str) -> None:
        self.message = message
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        return self.message


class FakeConnection:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> FakeWebSocket:
        return self.websocket

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class CollectDataTests(unittest.IsolatedAsyncioTestCase):
    async def test_subscribes_and_collects_expected_300_samples(self) -> None:
        sensor_message = json.dumps(
            {
                "type": "radar_data",
                "sensor": "V-PR100",
                "room": 401,
                "location": "거실A",
                "status": False,
                "motion": None,
                "presence_score": 0,
                "distance_mm": 0,
            },
            ensure_ascii=False,
        )
        websocket = FakeWebSocket(sensor_message)

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "vpr100_samples.csv"
            args = argparse.Namespace(
                server="ws://127.0.0.1:8881",
                label="empty",
                session="empty_01",
                duration=60.0,
                sample_interval=0.2,
                startup_timeout=20.0,
                sample_timeout=3.0,
                output=str(output),
                room=401,
                location="거실A",
                include_inactive=True,
            )

            with patch.object(
                collect_data.websockets,
                "connect",
                return_value=FakeConnection(websocket),
            ):
                await collect_data.collect(args)

            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))

        self.assertEqual(
            websocket.sent,
            [collect_data.SUBSCRIPTION_MESSAGE],
        )
        self.assertEqual(len(rows), 300)
        self.assertTrue(all(row["session_id"] == "empty_01" for row in rows))


if __name__ == "__main__":
    unittest.main()
