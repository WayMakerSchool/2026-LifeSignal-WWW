"""기본 구조 우선순위 매핑 회귀 테스트."""

from __future__ import annotations

import unittest

from AI.priority import build_rescue_priority


class RescuePriorityTest(unittest.TestCase):
    def test_maps_empty_pet_and_human_priorities(self) -> None:
        empty = build_rescue_priority({"ready": True, "target": "empty"})
        dog = build_rescue_priority({"ready": True, "target": "dog"})
        human = build_rescue_priority({"ready": True, "target": "human"})

        self.assertEqual((empty["level"], empty["rank"]), ("none", 0))
        self.assertEqual((dog["level"], dog["rank"]), ("low", 3))
        self.assertEqual(dog["label_ko"], "3순위 · 반려동물")
        self.assertEqual((human["level"], human["rank"]), ("normal", 2))
        self.assertEqual(human["label_ko"], "2순위 · 보통 · 사람")

    def test_promotes_only_human_when_risk_is_danger(self) -> None:
        human = build_rescue_priority(
            {"ready": True, "target": "human"},
            human_risk={"score": 0.82},
        )
        dog = build_rescue_priority(
            {"ready": True, "target": "dog"},
            human_risk={"score": 0.99},
        )

        self.assertEqual((human["level"], human["rank"]), ("danger", 1))
        self.assertEqual(human["label_ko"], "1순위 · 위험 · 사람")
        self.assertEqual((dog["level"], dog["rank"]), ("low", 3))

    def test_pending_ai_has_no_numeric_rank(self) -> None:
        pending = build_rescue_priority(
            {"ready": False, "reason": "collecting_window"}
        )
        self.assertEqual(pending["level"], "pending")
        self.assertIsNone(pending["rank"])


if __name__ == "__main__":
    unittest.main()
