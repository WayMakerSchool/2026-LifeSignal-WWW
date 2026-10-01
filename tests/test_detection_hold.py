"""센서의 순간적인 False를 완화하는 감지 유지 필터 테스트."""

from __future__ import annotations

import unittest

from server import DetectionHoldFilter


def radar_data(
    *,
    sensor: str,
    room: int,
    location: str,
    status: bool,
) -> dict:
    return {
        "type": "radar_data",
        "sensor": sensor,
        "room": room,
        "location": location,
        "status": status,
    }


class DetectionHoldFilterTest(unittest.TestCase):
    def test_holds_false_for_one_second_after_true(self) -> None:
        filter_ = DetectionHoldFilter(hold_seconds=1.0)
        detected = radar_data(
            sensor="V-PR100",
            room=401,
            location="거실A",
            status=True,
        )
        missed = {**detected, "status": False}

        self.assertTrue(filter_.apply(detected, now=10.0)["status"])
        self.assertTrue(filter_.apply(missed, now=10.9)["status"])
        self.assertFalse(filter_.apply(missed, now=11.0)["status"])

    def test_tracks_each_sensor_location_independently(self) -> None:
        filter_ = DetectionHoldFilter(hold_seconds=1.0)
        living_room = radar_data(
            sensor="V-PR100",
            room=401,
            location="거실A",
            status=True,
        )
        bedroom = radar_data(
            sensor="C4001",
            room=401,
            location="방A",
            status=False,
        )

        filter_.apply(living_room, now=20.0)

        self.assertFalse(filter_.apply(bedroom, now=20.5)["status"])
        self.assertTrue(
            filter_.apply({**living_room, "status": False}, now=20.5)[
                "status"
            ]
        )

    def test_supports_c4001(self) -> None:
        filter_ = DetectionHoldFilter(hold_seconds=1.0)
        detected = radar_data(
            sensor="C4001",
            room=402,
            location="방B",
            status=True,
        )

        filter_.apply(detected, now=30.0)

        self.assertTrue(
            filter_.apply({**detected, "status": False}, now=30.2)[
                "status"
            ]
        )


if __name__ == "__main__":
    unittest.main()
