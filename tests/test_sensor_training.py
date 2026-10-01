"""센서별 학습 설정과 데이터 검증 회귀 테스트."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from AI.training_presets import (
    C4001_PRESET,
    VPR100_PRESET,
    _effective_test_size,
    validate_training_data,
)


class SensorTrainingPresetTest(unittest.TestCase):
    def test_uses_sensor_specific_channels_and_windows(self) -> None:
        self.assertEqual(
            VPR100_PRESET.channels,
            ("presence_score", "distance_mm", "status"),
        )
        self.assertEqual(VPR100_PRESET.window_size, 25)
        self.assertEqual(VPR100_PRESET.step_size, 5)
        self.assertEqual(C4001_PRESET.channels, ("target_energy", "status"))
        self.assertEqual(C4001_PRESET.window_size, 25)

    def test_raises_validation_fraction_for_two_sessions_per_label(self) -> None:
        summary = {"sessions": 6}
        self.assertEqual(_effective_test_size(0.25, summary), 0.5)

    def test_validates_complete_c4001_dataset(self) -> None:
        rows = []
        for label in ("human", "empty", "dog"):
            for session_index in range(2):
                for sample_index in range(30):
                    rows.append(
                        {
                            "session_id": f"{label}_{session_index + 1:02d}",
                            "label": label,
                            "sensor_id": "c4001",
                            "status": label != "empty",
                            "target_energy": 50 + sample_index,
                        }
                    )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "c4001.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            summary = validate_training_data([str(path)], C4001_PRESET)

        self.assertEqual(summary["sensor_type"], "c4001")
        self.assertEqual(summary["sessions"], 6)
        self.assertEqual(
            summary["session_counts"],
            {"human": 2, "empty": 2, "dog": 2},
        )

    def test_augmented_session_does_not_count_as_independent_session(self) -> None:
        rows = []
        for label in ("human", "empty", "dog"):
            for session_index in range(2):
                session_id = f"{label}_{session_index + 1:02d}"
                for sample_index in range(30):
                    rows.append(
                        {
                            "session_id": session_id,
                            "source_session_id": session_id,
                            "is_augmented": False,
                            "label": label,
                            "sensor_id": "c4001",
                            "status": label != "empty",
                            "target_energy": 50 + sample_index,
                        }
                    )
        for sample_index in range(30):
            rows.append(
                {
                    "session_id": "empty_01__aug_test_01",
                    "source_session_id": "empty_01",
                    "is_augmented": True,
                    "label": "empty",
                    "sensor_id": "c4001",
                    "status": False,
                    "target_energy": 55 + sample_index,
                }
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "c4001.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            summary = validate_training_data([str(path)], C4001_PRESET)

        self.assertEqual(summary["sessions"], 6)
        self.assertEqual(summary["actual_session_ids"], 7)

    def test_reports_missing_human_and_dog_labels(self) -> None:
        rows = [
            {
                "session_id": "empty_01",
                "label": "empty",
                "sensor_id": "c4001",
                "status": False,
                "target_energy": 50,
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty_only.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            with self.assertRaisesRegex(
                ValueError,
                "human, dog 데이터가 없습니다",
            ):
                validate_training_data([str(path)], C4001_PRESET)

    def test_rejects_vpr100_csv_without_score(self) -> None:
        rows = [
            {
                "session_id": "empty_01",
                "label": "empty",
                "sensor": "V-PR100",
                "status": False,
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "vpr100.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "presence_score"):
                validate_training_data([str(path)], VPR100_PRESET)


if __name__ == "__main__":
    unittest.main()
