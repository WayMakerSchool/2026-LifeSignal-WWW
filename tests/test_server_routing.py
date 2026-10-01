"""서버 센서별 AI 모델 라우팅 회귀 테스트."""

from __future__ import annotations

import json
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import server
from AI.survivor_state import SurvivorStateTracker


class ServerModelRoutingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_engines = server.sensor_ai_engines
        self.original_fallback = server.ai_engine
        self.original_tracker = server.survivor_state_tracker
        self.original_c4001_demo = server.c4001_demo_engine
        self.original_hold_filter = server.detection_hold_filter
        server.c4001_demo_engine = server.C4001DemoEngine(update_interval=5.0)
        server.detection_hold_filter = server.DetectionHoldFilter()

    def tearDown(self) -> None:
        server.sensor_ai_engines = self.original_engines
        server.ai_engine = self.original_fallback
        server.survivor_state_tracker = self.original_tracker
        server.c4001_demo_engine = self.original_c4001_demo
        server.detection_hold_filter = self.original_hold_filter

    def test_recognizes_supported_sensor_families(self) -> None:
        self.assertEqual(server.sensor_family({"sensor": "V-PR100"}), "vpr100")
        self.assertEqual(server.sensor_family({"sensor": "V_PR100"}), "vpr100")
        self.assertEqual(server.sensor_family({"sensor": "C4001"}), "c4001")
        self.assertIsNone(server.sensor_family({"sensor": "unknown"}))

    def test_selects_vpr100_engine_and_disables_c4001_ai(self) -> None:
        fallback = object()
        vpr100 = object()
        c4001 = object()
        server.ai_engine = fallback  # type: ignore[assignment]
        server.sensor_ai_engines = {  # type: ignore[assignment]
            "vpr100": vpr100,
            "c4001": c4001,
        }

        self.assertIs(server.select_ai_engine({"sensor": "V-PR100"}), vpr100)
        self.assertIsNone(server.select_ai_engine({"sensor": "C4001"}))
        self.assertIs(server.select_ai_engine({"sensor": "other"}), fallback)

    def test_unconfigured_c4001_location_keeps_ai_and_priority_blank(self) -> None:
        server.ai_engine = object()  # type: ignore[assignment]
        server.sensor_ai_engines = {}
        server.survivor_state_tracker = SurvivorStateTracker()
        message, _ = server.process_message(json.dumps({
            "type": "radar_data",
            "sensor": "C4001",
            "room": 401,
            "location": "방A",
            "status": True,
        }))
        result = json.loads(message)
        self.assertTrue(result["ai"]["disabled"])
        self.assertIsNone(result["ai"]["target"])
        self.assertNotIn("rescue_priority", result)

    def test_c4001_living_b_maps_detection_to_normal_human(self) -> None:
        server.survivor_state_tracker = SurvivorStateTracker()
        with patch.object(server.random, "randint", return_value=913):
            message, key = server.process_message(json.dumps({
                "type": "radar_data",
                "sensor": "C4001",
                "room": 402,
                "location": "거실 B",
                "status": True,
            }))

        result = json.loads(message)
        self.assertEqual(key, "C4001:402:거실 B")
        self.assertTrue(result["ai"]["ready"])
        self.assertTrue(result["ai"]["simulated"])
        self.assertEqual(result["ai"]["model"], "rule_based_demo")
        self.assertEqual(result["ai"]["target"], "human")
        self.assertEqual(result["ai"]["confidence"], 0.913)
        self.assertEqual(result["rescue_priority"]["rank"], 2)
        self.assertEqual(result["rescue_priority"]["level"], "normal")
        self.assertTrue(result["survivor_state"]["motion_active"])

    def test_c4001_room_b_maps_detection_to_pet_priority(self) -> None:
        server.survivor_state_tracker = SurvivorStateTracker()
        with patch.object(server.random, "randint", return_value=955):
            message, _ = server.process_message(json.dumps({
                "type": "radar_data",
                "sensor": "C4001",
                "room": 402,
                "location": "방B",
                "status": True,
            }))

        result = json.loads(message)
        self.assertEqual(result["ai"]["target"], "dog")
        self.assertEqual(result["ai"]["confidence"], 0.955)
        self.assertEqual(result["rescue_priority"]["rank"], 3)
        self.assertEqual(result["rescue_priority"]["level"], "low")
        self.assertTrue(result["survivor_state"]["motion_active"])

    def test_c4001_demo_confidence_is_stable_and_refreshes_at_five_seconds(self) -> None:
        engine = server.C4001DemoEngine(update_interval=5.0)
        data = {
            "type": "radar_data",
            "sensor": "C4001",
            "room": 402,
            "location": "거실B",
            "status": True,
        }
        with (
            patch.object(server.random, "randint", return_value=876),
            patch.object(server, "_utc_now", side_effect=["t0", "t5"]),
        ):
            first = engine.enrich(data, now=0.0)
            before_refresh = engine.enrich(data, now=4.99)
            refreshed = engine.enrich(data, now=5.0)

        self.assertEqual(first["ai"]["confidence"], 0.876)
        self.assertEqual(before_refresh["ai"]["confidence"], 0.876)
        self.assertEqual(refreshed["ai"]["confidence"], 0.876)
        self.assertEqual(first["ai"]["updated_at"], "t0")
        self.assertEqual(before_refresh["ai"]["updated_at"], "t0")
        self.assertEqual(refreshed["ai"]["updated_at"], "t5")

    def test_c4001_demo_clears_target_when_detection_ends(self) -> None:
        engine = server.C4001DemoEngine(update_interval=5.0)
        detected = {
            "type": "radar_data",
            "sensor": "C4001",
            "room": 402,
            "location": "방B",
            "status": True,
        }
        with patch.object(server.random, "randint", return_value=950):
            engine.enrich(detected, now=0.0)
        absent = engine.enrich({**detected, "status": False}, now=1.0)

        self.assertEqual(absent["ai"]["target"], "empty")
        self.assertIsNone(absent["ai"]["confidence"])
        self.assertNotIn(engine.sensor_key(detected), engine.latest_results)

    def test_process_message_recomputes_priority_from_human_motion_risk(self) -> None:
        class HumanEngine:
            def enrich(self, data: dict) -> dict:
                enriched = dict(data)
                enriched["ai"] = {
                    "ready": True,
                    "target": "human",
                    "target_ko": "사람",
                }
                return enriched

        server.ai_engine = HumanEngine()  # type: ignore[assignment]
        server.sensor_ai_engines = {}
        server.survivor_state_tracker = SurvivorStateTracker()
        base = {
            "type": "radar_data",
            "sensor": "V-PR100",
            "room": 401,
            "location": "거실A",
            "presence_score": 2000,
            "distance_mm": 300,
        }

        breathing = {**base, "status": True, "motion": True}
        stopped = {**base, "status": False, "motion": False}
        with patch(
            "AI.survivor_state.monotonic",
            side_effect=[0.0, 1.0, 5.0],
        ):
            normal_message, _ = server.process_message(json.dumps(breathing))
            server.process_message(json.dumps(stopped))
            danger_message, _ = server.process_message(json.dumps(stopped))

        normal = json.loads(normal_message)
        danger = json.loads(danger_message)
        self.assertEqual(normal["rescue_priority"]["level"], "normal")
        self.assertEqual(danger["rescue_priority"]["level"], "danger")

    def test_configures_only_vpr100_model(self) -> None:
        class FakeClassifier:
            channels = ("status",)
            window_size = 2
            model_name = "svm"

            def __init__(self, sensor_type: str) -> None:
                self.sensor_type = sensor_type

        def fake_loader(path: object, model_type: str) -> FakeClassifier:
            sensor_type = "vpr100" if "vpr100" in str(path) else "c4001"
            return FakeClassifier(sensor_type)

        args = SimpleNamespace(
            ai_update_interval=5.0,
            ai_model=None,
            ai_model_type="auto",
            vpr100_model="vpr100.joblib",
            c4001_model="c4001.joblib",
        )
        with patch.object(server, "load_classifier", side_effect=fake_loader):
            server.configure_ai(args)

        self.assertEqual(set(server.sensor_ai_engines), {"vpr100"})
        self.assertEqual(
            server.sensor_ai_engines["vpr100"].classifier.sensor_type,
            "vpr100",
        )

    def test_rejects_model_in_wrong_sensor_slot(self) -> None:
        class WrongClassifier:
            channels = ("status",)
            window_size = 2
            model_name = "svm"
            sensor_type = "c4001"

        args = SimpleNamespace(
            ai_update_interval=5.0,
            ai_model=None,
            ai_model_type="auto",
            vpr100_model="wrong.joblib",
            c4001_model=None,
        )
        with patch.object(server, "load_classifier", return_value=WrongClassifier()):
            with self.assertRaisesRegex(SystemExit, "사용할 수 없는 모델"):
                server.configure_ai(args)

    def test_discovers_default_models_after_training(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            vpr100 = artifact_dir / "vpr100-svm.joblib"
            c4001 = artifact_dir / "c4001-cnn.keras"
            vpr100.touch()
            c4001.touch()
            candidates = {
                "vpr100": (
                    vpr100,
                    artifact_dir / "vpr100-cnn.keras",
                ),
                "c4001": (
                    artifact_dir / "c4001-svm.joblib",
                    c4001,
                ),
            }

            discovered = server.discover_default_models(candidates)

        self.assertEqual(discovered, {"vpr100": vpr100, "c4001": c4001})

    def test_automatically_configures_discovered_default_models(self) -> None:
        class FakeClassifier:
            channels = ("status",)
            window_size = 2
            model_name = "svm"

            def __init__(self, sensor_type: str) -> None:
                self.sensor_type = sensor_type

        def fake_loader(path: object, model_type: str) -> FakeClassifier:
            family = "vpr100" if "vpr100" in str(path) else "c4001"
            return FakeClassifier(family)

        args = SimpleNamespace(
            ai_update_interval=5.0,
            ai_model=None,
            ai_model_type="auto",
            vpr100_model=None,
            c4001_model=None,
            no_auto_models=False,
        )
        discovered = {
            "vpr100": Path("vpr100-svm.joblib"),
            "c4001": Path("c4001-svm.joblib"),
        }
        with (
            patch.object(server, "discover_default_models", return_value=discovered),
            patch.object(server, "load_classifier", side_effect=fake_loader),
        ):
            server.configure_ai(args)

        self.assertEqual(set(server.sensor_ai_engines), {"vpr100"})


if __name__ == "__main__":
    unittest.main()
