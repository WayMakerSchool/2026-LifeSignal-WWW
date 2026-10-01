"""AI 전처리·추론 파이프라인 회귀 테스트."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from AI.inference import ModelPrediction, SVMClassifier, SensorAIEngine
from AI.preprocessing import (
    DEFAULT_CHANNELS,
    SUPPORTED_LABELS,
    build_windows,
    engineer_features,
    normalize_label,
)
from AI.svm import train_svm


class DummyClassifier:
    channels = DEFAULT_CHANNELS
    window_size = 4
    model_name = "dummy"

    def __init__(self) -> None:
        self.calls = 0

    def predict(self, window: np.ndarray) -> ModelPrediction:
        self.calls += 1
        target = "human" if window[-1, -1] == 1.0 else "empty"
        return ModelPrediction(target, 0.8)


class PreprocessingTest(unittest.TestCase):
    def test_builds_temporal_windows_and_features(self) -> None:
        rows = []
        values_by_label = {
            "human": (3000, 1500, True),
            "empty": (0, 0, False),
            "dog": (1000, 700, True),
        }
        for label in SUPPORTED_LABELS:
            for session_index in range(2):
                for sample_index in range(12):
                    score, distance, status = values_by_label[label]
                    rows.append(
                        {
                            "session_id": f"{label}_{session_index}",
                            "label": label,
                            "timestamp": sample_index,
                            "presence_score": score,
                            "distance_mm": distance,
                            "motion": sample_index % 2 == 0,
                            "status": status,
                        }
                    )
        dataset = build_windows(
            pd.DataFrame(rows),
            window_size=8,
            step_size=4,
        )
        self.assertEqual(dataset.samples.shape, (12, 8, 4))
        features, names = engineer_features(dataset.samples, dataset.channels)
        self.assertEqual(features.shape[0], 12)
        self.assertEqual(features.shape[1], len(names))
        self.assertIn("presence_score_mean", names)

    def test_normalizes_three_labels_and_legacy_pet(self) -> None:
        self.assertEqual(normalize_label("사람"), "human")
        self.assertEqual(normalize_label("빈 공간"), "empty")
        self.assertEqual(normalize_label("개"), "dog")
        self.assertEqual(normalize_label("pet"), "dog")


class InferenceIntervalTest(unittest.TestCase):
    def test_refreshes_prediction_only_every_five_seconds(self) -> None:
        classifier = DummyClassifier()
        engine = SensorAIEngine(classifier, update_interval=5.0)
        base = {
            "type": "radar_data",
            "sensor": "V-PR100",
            "room": 401,
            "location": "거실A",
            "status": True,
            "motion": True,
            "presence_score": 3000,
            "distance_mm": 1000,
        }

        for index in range(3):
            result = engine.enrich(base, now=float(index))
            self.assertFalse(result["ai"]["ready"])

        first = engine.enrich(base, now=3.0)
        self.assertTrue(first["ai"]["ready"])
        self.assertEqual(classifier.calls, 1)

        cached = engine.enrich(base, now=7.9)
        self.assertEqual(classifier.calls, 1)
        self.assertEqual(cached["ai"]["updated_at"], first["ai"]["updated_at"])

        refreshed = engine.enrich(base, now=8.0)
        self.assertEqual(classifier.calls, 2)
        self.assertTrue(refreshed["ai"]["ready"])

        for now in (9.0, 10.0, 11.0, 12.0):
            engine.enrich({**base, "status": False}, now=now)
        absent = engine.enrich({**base, "status": False}, now=13.0)
        self.assertTrue(absent["ai"]["ready"])
        self.assertEqual(absent["ai"]["target"], "empty")
        self.assertEqual(absent["rescue_priority"]["level"], "none")
        self.assertEqual(len(engine.buffers["V-PR100:401:거실A"]), 4)

    def test_without_model_keeps_explicit_absence_behavior(self) -> None:
        engine = SensorAIEngine(None, update_interval=5.0)
        result = engine.enrich(
            {
                "type": "radar_data",
                "sensor": "C4001",
                "room": 402,
                "location": "거실",
                "status": False,
                "target_energy": 0,
            },
            now=0.0,
        )
        self.assertEqual(result["ai"]["reason"], "no_target")
        self.assertEqual(result["rescue_priority"]["level"], "none")


class SVMArtifactTest(unittest.TestCase):
    def test_trains_saves_and_loads_svm_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = Path(temp_dir) / "training.csv"
            model_path = Path(temp_dir) / "svm.joblib"
            rows = []
            patterns = {
                "human": (3200, 1300, True),
                "empty": (50, 0, False),
                "dog": (1200, 650, True),
            }
            for label, (base_score, base_distance, status) in patterns.items():
                for session_index in range(4):
                    for sample_index in range(60):
                        rows.append(
                            {
                                "session_id": f"{label}_{session_index}",
                                "label": label,
                                "timestamp": sample_index,
                                "presence_score": (
                                    base_score + (sample_index % 7) * 10
                                ),
                                "distance_mm": (
                                    base_distance + (sample_index % 5) * 5
                                ),
                                "motion": status and sample_index % 3 == 0,
                                "status": status,
                            }
                        )
            pd.DataFrame(rows).to_csv(data_path, index=False)
            artifact = train_svm(
                [str(data_path)],
                str(model_path),
                window_size=20,
                step_size=10,
                sensor_type="vpr100",
                augment_copies=1,
            )
            self.assertEqual(artifact["model_type"], "svm")
            self.assertEqual(artifact["sensor_type"], "vpr100")
            self.assertEqual(artifact["augmentation"]["copies"], 1)
            self.assertEqual(
                artifact["training_windows"],
                artifact["original_training_windows"] * 2,
            )
            self.assertTrue(model_path.exists())

            classifier = SVMClassifier(model_path)
            frame = pd.read_csv(data_path)
            dataset = build_windows(frame, window_size=20, step_size=10)
            prediction = classifier.predict(dataset.samples[0])
            self.assertIn(prediction.target, set(SUPPORTED_LABELS))
            self.assertGreaterEqual(prediction.confidence, 0.0)
            self.assertLessEqual(prediction.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
