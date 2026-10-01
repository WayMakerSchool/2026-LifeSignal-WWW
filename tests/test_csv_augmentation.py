"""CSV 어그멘테이션 회귀 테스트."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from AI.augment_sensor_csv import augment_csv_file
from AI.preprocessing import build_windows
from AI.training_presets import C4001_PRESET, validate_training_data


def _complete_c4001_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for label, base_energy, status in (
        ("empty", 50, False),
        ("human", 500, True),
        ("dog", 250, True),
    ):
        for session_index in range(1, 3):
            for sample_index in range(30):
                rows.append(
                    {
                        "session_id": f"{label}_{session_index:02d}",
                        "label": label,
                        "timestamp": sample_index,
                        "sample_millis": sample_index * 200,
                        "sensor_id": "c4001",
                        "room": 401,
                        "location": "거실A",
                        "status": status,
                        "target_energy": base_energy + sample_index,
                    }
                )
    return rows


class CsvAugmentationTest(unittest.TestCase):
    def test_preview_does_not_modify_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "c4001.csv"
            original = pd.DataFrame(_complete_c4001_rows())
            original.to_csv(path, index=False)
            original_text = path.read_text(encoding="utf-8")

            result = augment_csv_file(
                path,
                C4001_PRESET,
                sessions=["empty_01"],
                count=37,
                apply=False,
            )

            self.assertFalse(result.applied)
            self.assertEqual(result.generated_rows, 37)
            self.assertEqual(path.read_text(encoding="utf-8"), original_text)
            self.assertFalse((path.parent / "backups").exists())

    def test_appends_augmented_rows_and_keeps_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "c4001.csv"
            original = pd.DataFrame(_complete_c4001_rows())
            original.to_csv(path, index=False)

            result = augment_csv_file(
                path,
                C4001_PRESET,
                sessions=["empty_01"],
                count=17,
                jitter=0.05,
                scale=0.05,
                random_state=7,
                apply=True,
            )

            saved = pd.read_csv(path)
            augmented = saved.loc[saved["is_augmented"] == True]  # noqa: E712
            self.assertTrue(result.applied)
            self.assertEqual(len(saved), len(original) + 17)
            self.assertEqual(len(augmented), 17)
            self.assertTrue(result.backup_path and result.backup_path.exists())
            self.assertEqual(set(augmented["source_session_id"]), {"empty_01"})
            self.assertEqual(set(augmented["session_id"]), {"empty_01__aug"})
            self.assertEqual(set(augmented["label"]), {"empty"})
            self.assertEqual(set(augmented["status"]), {False})
            self.assertTrue((augmented["target_energy"] >= 0).all())
            self.assertTrue(augmented["timestamp"].is_monotonic_increasing)
            self.assertTrue(augmented["sample_millis"].is_monotonic_increasing)

    def test_augmented_sessions_stay_in_source_training_group(self) -> None:
        frame = pd.DataFrame(_complete_c4001_rows())
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "c4001.csv"
            frame.to_csv(path, index=False)
            result = augment_csv_file(
                path,
                C4001_PRESET,
                sessions=["empty_01"],
                count=30,
                apply=True,
            )
            saved = pd.read_csv(path)
            summary = validate_training_data([str(path)], C4001_PRESET)
            self.assertEqual(summary["sessions"], 6)
            self.assertEqual(summary["actual_session_ids"], 7)

            dataset = build_windows(
                saved,
                window_size=25,
                step_size=5,
                channels=C4001_PRESET.channels,
            )
            augmented_session = result.generated_session_ids[0]
            session_ids = saved["session_id"].astype(str)
            source_window_count = 2
            self.assertEqual(
                int((dataset.groups == "empty_01").sum()),
                source_window_count * 2,
            )
            self.assertIn(augmented_session, set(session_ids))

    def test_rejects_augmented_session_as_new_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "c4001.csv"
            pd.DataFrame(_complete_c4001_rows()).to_csv(path, index=False)
            first = augment_csv_file(
                path,
                C4001_PRESET,
                sessions=["empty_01"],
                count=30,
                apply=True,
            )
            with self.assertRaisesRegex(ValueError, "원본 데이터에서 세션"):
                augment_csv_file(
                    path,
                    C4001_PRESET,
                    sessions=[first.generated_session_ids[0]],
                    count=30,
                    apply=False,
                )

    def test_distributes_exact_count_across_selected_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "c4001.csv"
            pd.DataFrame(_complete_c4001_rows()).to_csv(path, index=False)
            result = augment_csv_file(
                path,
                C4001_PRESET,
                sessions=["empty_01", "empty_02"],
                count=701,
                apply=False,
            )

        self.assertEqual(result.generated_rows, 701)
        self.assertEqual(sum(dict(result.generated_rows_by_source).values()), 701)
        self.assertEqual(dict(result.generated_rows_by_source)["empty_01"], 351)
        self.assertEqual(dict(result.generated_rows_by_source)["empty_02"], 350)

    def test_repeated_augmentation_appends_to_same_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "c4001.csv"
            pd.DataFrame(_complete_c4001_rows()).to_csv(path, index=False)
            first = augment_csv_file(
                path,
                C4001_PRESET,
                sessions=["empty_01"],
                count=17,
                apply=True,
            )
            second = augment_csv_file(
                path,
                C4001_PRESET,
                sessions=["empty_01"],
                count=13,
                apply=True,
            )
            saved = pd.read_csv(path)

            augmented = saved.loc[saved["session_id"] == "empty_01__aug"]
            self.assertEqual(len(augmented), 30)
            self.assertEqual(first.generated_session_ids, ("empty_01__aug",))
            self.assertEqual(second.generated_session_ids, ("empty_01__aug",))
            self.assertTrue(augmented["timestamp"].is_monotonic_increasing)
            self.assertEqual(first.backup_path.name, "c4001_backup_001.csv")
            self.assertEqual(second.backup_path.name, "c4001_backup_002.csv")


if __name__ == "__main__":
    unittest.main()
