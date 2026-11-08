import json
from pathlib import Path
import tempfile
import unittest

from src.overworld.models import MapCoordinate
from src.overworld.navigation.player_locator import SurfaceProfile
from src.overworld.qualification import REQUIRED_SOURCES, RuntimeQualification, file_sha256


class TestRuntimeQualification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for name in ("profile.json", "map.png", "map.db", "evidence.png", *REQUIRED_SOURCES):
            path = self.folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic test fixture, not game evidence")
        self.profile = SurfaceProfile(self.folder / "map.png", self.folder / "map.db", "Target", 8, "",
                                      MapCoordinate(0, 0), 1, (1920, 1080), frozenset({"a"}))
        self.data = {"schema_version": 1, "status": "REVIEWED", "ok_script_version": "3.0.4",
                     "game_version": "test-version", "state_id": 8, "floor_id": "",
                     "permitted_stages": ["WALK", "SINGLE_CAMP"], "independent_review": True,
                     "bindings": {"profile": file_sha256(self.folder / "profile.json"),
                                  "reference": file_sha256(self.profile.image_path),
                                  "database": file_sha256(self.profile.database_path)},
                     "source_sha256": {name: file_sha256(self.folder / name) for name in REQUIRED_SOURCES},
                     "evidence_sha256": {"evidence.png": file_sha256(self.folder / "evidence.png")}}

    def assert_qualified(self, **kwargs):
        path = self.folder / "qualification.json"
        path.write_text(json.dumps(self.data), encoding="utf-8")
        RuntimeQualification.load(path).assert_compatible(
            self.folder / "profile.json", self.profile, source_root=self.folder,
            runtime_version=kwargs.get("runtime_version", "3.0.4"),
            game_version=kwargs.get("game_version", "test-version"),
            stage=kwargs.get("stage", "SINGLE_CAMP"))

    def test_exact_runtime_profile_and_evidence_binding_accepts(self):
        self.assert_qualified()

    def test_historical_runtime_or_unknown_game_cannot_authorize_movement(self):
        for kwargs in ({"runtime_version": "2.0.7b1"}, {"game_version": ""}, {"stage": "MATERIAL_ROUTE"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, "LIVE_VERIFICATION_PENDING"):
                    self.assert_qualified(**kwargs)

    def test_changed_reference_database_sources_and_evidence_fail(self):
        for name in ("map.png", "map.db", "profile.json", "evidence.png", REQUIRED_SOURCES[0]):
            with self.subTest(name=name):
                path = self.folder / name
                original = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "Stale"):
                    self.assert_qualified()
                path.write_bytes(original)

    def test_missing_review_and_wrong_map_layer_fail(self):
        self.data["independent_review"] = False
        with self.assertRaisesRegex(ValueError, "independent"):
            self.assert_qualified()
        self.data["independent_review"] = True
        self.data["floor_id"] = "B1"
        with self.assertRaisesRegex(ValueError, "map/layer"):
            self.assert_qualified()

    def test_no_sidecar_means_live_pending(self):
        with self.assertRaisesRegex(ValueError, "LIVE_VERIFICATION_PENDING"):
            RuntimeQualification.load("")


if __name__ == "__main__":
    unittest.main()
