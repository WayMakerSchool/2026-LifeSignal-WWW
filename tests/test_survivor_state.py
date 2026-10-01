"""영역별 생존자 상태 추적 회귀 테스트."""

from __future__ import annotations

import unittest

from AI.survivor_state import SurvivorStateTracker


def human_message(room: int, location: str, status: bool) -> dict:
    return {
        "type": "radar_data",
        "sensor": "C4001",
        "room": room,
        "location": location,
        "status": status,
        "ai": {"ready": True, "target": "human"},
    }


class SurvivorStateTrackerTest(unittest.TestCase):
    def test_tracks_each_room_location_independently(self) -> None:
        tracker = SurvivorStateTracker()

        room_a = tracker.enrich(human_message(401, "방A", True), now=10.0)
        living_a = tracker.enrich(
            human_message(401, "거실A", False),
            now=10.0,
        )
        room_a_later = tracker.enrich(
            human_message(401, "방A", True),
            now=14.0,
        )

        self.assertTrue(room_a["survivor_state"]["motion_active"])
        self.assertFalse(living_a["survivor_state"]["motion_active"])
        self.assertEqual(
            room_a_later["survivor_state"]["motion_duration_sec"],
            4.0,
        )
        self.assertEqual(
            living_a["survivor_state"]["sensor_key"],
            "C4001:401:거실A",
        )

    def test_keeps_recent_human_history_during_no_motion(self) -> None:
        tracker = SurvivorStateTracker(human_history_sec=15.0)
        tracker.enrich(human_message(402, "방B", True), now=20.0)

        result = tracker.enrich(human_message(402, "방B", False), now=23.0)
        later = tracker.enrich(human_message(402, "방B", False), now=26.0)

        self.assertTrue(result["survivor_state"]["human_recent"])
        self.assertEqual(later["survivor_state"]["no_motion_duration_sec"], 3.0)

    def test_human_becomes_danger_after_four_seconds_without_motion(self) -> None:
        tracker = SurvivorStateTracker()
        breathing = human_message(401, "거실A", True)
        breathing["motion"] = True
        normal = tracker.enrich(breathing, now=0.0)

        stopped = human_message(401, "거실A", False)
        stopped["motion"] = False
        tracker.enrich(stopped, now=1.0)
        still_normal = tracker.enrich(stopped, now=4.99)
        danger = tracker.enrich(stopped, now=5.0)

        self.assertEqual(normal["human_risk"]["level"], "normal")
        self.assertEqual(still_normal["human_risk"]["level"], "normal")
        self.assertEqual(danger["human_risk"]["level"], "danger")
        self.assertEqual(danger["human_risk"]["no_motion_duration_sec"], 4.0)

    def test_motion_resume_returns_human_to_normal(self) -> None:
        tracker = SurvivorStateTracker()
        tracker.enrich(human_message(401, "거실A", True), now=0.0)

        stopped = human_message(401, "거실A", False)
        stopped["motion"] = False
        tracker.enrich(stopped, now=4.0)

        resumed = human_message(401, "거실A", False)
        resumed["motion"] = True
        result = tracker.enrich(resumed, now=4.1)

        self.assertTrue(result["survivor_state"]["motion_active"])
        self.assertEqual(result["human_risk"]["level"], "normal")
        self.assertEqual(result["human_risk"]["no_motion_duration_sec"], 0.0)

    def test_explicit_motion_takes_priority_over_status(self) -> None:
        tracker = SurvivorStateTracker()
        first = human_message(401, "방A", True)
        first["motion"] = False
        result = tracker.enrich(first, now=0.0)

        self.assertFalse(result["survivor_state"]["motion_active"])
        self.assertEqual(result["human_risk"]["level"], "normal")

    def test_tracks_detected_dog_motion_without_human_risk(self) -> None:
        tracker = SurvivorStateTracker()
        dog = {
            "type": "radar_data",
            "sensor": "C4001",
            "room": 402,
            "location": "방B",
            "status": True,
            "ai": {"ready": True, "target": "dog"},
        }

        first = tracker.enrich(dog, now=10.0)
        later = tracker.enrich(dog, now=13.0)

        self.assertTrue(first["survivor_state"]["motion_active"])
        self.assertEqual(later["survivor_state"]["motion_duration_sec"], 3.0)
        self.assertFalse(later["survivor_state"]["human_recent"])
        self.assertNotIn("human_risk", later)


if __name__ == "__main__":
    unittest.main()
