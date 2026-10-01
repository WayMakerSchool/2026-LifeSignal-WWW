from __future__ import annotations

import unittest

from AI.collection_plan import PRESETS_BY_NAME, get_preset, preset_names


class CollectionPlanTest(unittest.TestCase):
    def test_contains_required_sensor_sessions(self) -> None:
        expected = {
            "vpr100_empty_01",
            "vpr100_empty_02",
            "vpr100_empty_vibration_01",
            "vpr100_empty_vibration_02",
            "vpr100_dog_01",
            "vpr100_dog_02",
            "vpr100_human_danger_01",
            "vpr100_human_danger_02",
            "c4001_empty_01",
            "c4001_empty_02",
            "c4001_dog_01",
            "c4001_dog_02",
            "c4001_human_normal_01",
            "c4001_human_normal_02",
        }
        self.assertEqual(set(preset_names()), expected)
        self.assertEqual(set(PRESETS_BY_NAME), expected)

    def test_vpr100_vibration_empty_sessions_are_short_independent_presets(self) -> None:
        first = get_preset("vpr100_empty_vibration_01")
        second = get_preset("vpr100_empty_vibration_02")

        self.assertEqual(first.label, "empty")
        self.assertEqual(first.scenario, "empty_vibration")
        self.assertEqual(first.session_id, "empty_vibration_01")
        self.assertEqual(second.session_id, "empty_vibration_02")
        self.assertEqual(first.duration, 30.0)
        self.assertEqual(second.duration, 30.0)
        self.assertTrue(first.include_inactive)
        self.assertTrue(second.include_inactive)
        self.assertEqual(first.expected_room, 401)
        self.assertEqual(first.expected_location, "거실A")

    def test_risk_scenario_is_still_human_label(self) -> None:
        preset = get_preset("vpr100_human_danger_01")
        self.assertEqual(preset.label, "human")
        self.assertEqual(preset.scenario, "human_danger")
        self.assertEqual(preset.session_id, "human_danger_01")
        self.assertTrue(preset.include_inactive)

        normal = get_preset("c4001_human_normal_01")
        self.assertFalse(normal.include_inactive)

    def test_normal_human_and_dog_have_expected_placement(self) -> None:
        human = get_preset("c4001_human_normal_01")
        dog = get_preset("c4001_dog_01")
        self.assertEqual(human.expected_room, 402)
        self.assertEqual(human.expected_location, "거실B")
        self.assertEqual(dog.expected_room, 402)
        self.assertEqual(dog.expected_location, "방B")
        self.assertEqual(human.label, "human")
        self.assertEqual(dog.label, "dog")

    def test_unknown_preset_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_preset("vpr100_danger_human")


if __name__ == "__main__":
    unittest.main()
