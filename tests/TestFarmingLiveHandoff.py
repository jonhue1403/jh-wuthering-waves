"""Synthetic-only contract tests: no game input or reviewer authentication."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import unittest

from src.overworld.qualification import REQUIRED_SOURCES
from src.automation.farming_live_handoff import build_observation_handoff


NOW = datetime(2026, 11, 13, 2, 0, tzinfo=timezone.utc)


def sample_packet():
    return {
        "schema_version": 1,
        "purpose": "SOURCE_DROP",
        "target_kind": "material",
        "target_id": "ff-mech-core",
        "game_mob_id": "000123",
        "game_version": "3.0.2",
        "ok_script_version": "1.2.3",
        "session_id": "session-1",
        "observed_at": (NOW - timedelta(seconds=30)).isoformat(),
        "stage": "MATERIAL_ROUTE",
        "route_id": "bounded-route-1",
        "state_id": "state-1",
        "floor_id": "0",
        "frame_ids": ["frame-before", "frame-after"],
        "frame_sha256": {
            "frame-before": "a" * 64, "frame-after": "b" * 64,
        },
        "bindings_sha256": {
            "profile": "c" * 64,
            "reference": "d" * 64,
            "database": "e" * 64,
        },
        "source_sha256": {
            **{name: "f" * 64 for name in REQUIRED_SOURCES},
            "src/overworld/material_route.py": "1" * 64,
            "src/task/BoundedRouteTask.py": "2" * 64,
        },
        "inventory_before": 5,
        "inventory_after": 6,
    }


class TestFarmingLiveHandoff(unittest.TestCase):
    def build(self, payload=None):
        return build_observation_handoff(
            sample_packet() if payload is None else payload, now=NOW,
        )

    def test_valid_packet_is_immutable_and_untrusted(self):
        packet = self.build()
        self.assertEqual("000123", packet.game_mob_id)
        self.assertEqual((5, 6), (packet.inventory_before, packet.inventory_after))
        self.assertEqual(64, len(packet.record_sha256))
        self.assertIsInstance(packet.frame_sha256, tuple)
        self.assertIsInstance(packet.source_sha256, tuple)
        with self.assertRaises(FrozenInstanceError):
            packet.record_sha256 = "0" * 64
        report = packet.public_summary()
        self.assertEqual(
            "CAPTURE_CLAIM_PENDING_INDEPENDENT_REVIEW", report["status"],
        )
        for key in ("can_start", "current_version_authenticated", "source_verified",
                    "route_qualified", "reviewer_authenticated"):
            self.assertIs(report[key], False)

    def test_stable_canonical_digest_and_mutation_changes_identity(self):
        first = sample_packet()
        second = dict(reversed(list(first.items())))
        second["source_sha256"] = dict(reversed(list(first["source_sha256"].items())))
        self.assertEqual(self.build(first).record_sha256,
                         self.build(second).record_sha256)
        second["source_sha256"]["src/task/HuntMobTask.py"] = "3" * 64
        self.assertNotEqual(self.build(first).record_sha256,
                            self.build(second).record_sha256)
        # Frozen tuples are unaffected by mutations of an input dict.
        self.assertEqual(self.build(first).source_sha256,
                         self.build(dict(first)).source_sha256)

    def test_rejects_claimed_approval_and_unexpected_fields(self):
        for replacement in (
            {"can_start": True}, {"status": "REVIEWED"},
            {"independent_review": True}, {"reviewer_signature": "fake"},
        ):
            with self.subTest(replacement=replacement):
                payload = sample_packet()
                payload.update(replacement)
                with self.assertRaises(ValueError):
                    self.build(payload)
        for invalid_schema in (True, 2, "1", 0):
            with self.subTest(invalid_schema=invalid_schema):
                payload = sample_packet()
                payload["schema_version"] = invalid_schema
                with self.assertRaises(ValueError):
                    self.build(payload)
        payload = sample_packet()
        del payload["source_sha256"]
        with self.assertRaises(ValueError):
            self.build(payload)

    def test_capture_timestamp_and_clock_must_be_current_and_aware(self):
        for timestamp in (
            (NOW - timedelta(minutes=16)).isoformat(),
            (NOW + timedelta(minutes=3)).isoformat(),
            NOW.replace(tzinfo=None).isoformat(),
            "not-a-time",
        ):
            with self.subTest(timestamp=timestamp):
                payload = sample_packet()
                payload["observed_at"] = timestamp
                with self.assertRaises(ValueError):
                    self.build(payload)
        with self.assertRaises(ValueError):
            build_observation_handoff(
                sample_packet(), now=NOW.replace(tzinfo=None),
            )

    def test_rejects_forged_or_ambiguous_ids_and_versions(self):
        invalid = (
            ("target_id", "ff mech core"),
            ("game_mob_id", 123),
            ("game_mob_id", "1O01"),
            ("session_id", "../private"),
            ("state_id", "/config"),
            ("route_id", "C:\\local\\route.json"),
            ("game_version", ""),
            ("ok_script_version", "3.0 ;"),
        )
        for key, value in invalid:
            with self.subTest(key=key, value=value):
                payload = sample_packet()
                payload[key] = value
                with self.assertRaises(ValueError):
                    self.build(payload)

    def test_missing_or_malformed_sha_bound_digests_rejected(self):
        for key, remove in (
            ("source_sha256", "src/automation/input_guard.py"),
            ("bindings_sha256", "profile"),
            ("frame_sha256", "frame-before"),
        ):
            with self.subTest(key=key):
                payload = sample_packet()
                payload[key].pop(remove)
                with self.assertRaises(ValueError):
                    self.build(payload)
        payload = sample_packet()
        payload["source_sha256"]["unlisted/private/secret.py"] = "a" * 64
        with self.assertRaises(ValueError):
            self.build(payload)
        payload = sample_packet()
        payload["frame_sha256"]["frame-before"] = "NOT_A_SHA256"
        with self.assertRaises(ValueError):
            self.build(payload)

    def test_receipt_requires_two_unique_frames_and_positive_delta(self):
        for changed in (
            {"frame_ids": ["frame-before", "frame-before"]},
            {"frame_ids": ["frame-before"]},
            {"inventory_after": 5},
            {"inventory_before": True},
            {"inventory_after": 10_000_000},
            {"purpose": "SOURCE_DROP", "stage": "LOCALIZATION"},
            {"target_kind": "mob"},
        ):
            with self.subTest(changed=changed):
                payload = sample_packet()
                payload.update(changed)
                with self.assertRaises(ValueError):
                    self.build(payload)

    def test_distinct_frame_ids_cannot_reuse_identical_image_digest(self):
        payload = sample_packet()
        payload["frame_sha256"]["frame-after"] = payload["frame_sha256"]["frame-before"]
        with self.assertRaises(ValueError):
            self.build(payload)

    def test_route_survey_has_no_material_receipt_and_needs_route_id(self):
        payload = sample_packet()
        payload.update(
            purpose="ROUTE_SURVEY", target_kind="mob",
            target_id="geospider-s4", stage="WALK",
            inventory_before=None, inventory_after=None,
        )
        del payload["source_sha256"]["src/overworld/material_route.py"]
        del payload["source_sha256"]["src/task/BoundedRouteTask.py"]
        packet = self.build(payload)
        self.assertEqual("ROUTE_SURVEY", packet.purpose)
        self.assertFalse(packet.public_summary()["can_start"])
        payload["inventory_after"] = 1
        with self.assertRaises(ValueError):
            self.build(payload)
        payload["inventory_after"] = None
        payload["route_id"] = ""
        with self.assertRaises(ValueError):
            self.build(payload)

    def test_public_summary_excludes_private_packet_fields_and_paths(self):
        packet = self.build()
        report = packet.public_summary()
        for field in (
            "source_sha256", "bindings_sha256", "frame_sha256",
            "frame_ids", "session_id", "game_mob_id",
            "inventory_before", "inventory_after", "observed_at_utc",
        ):
            self.assertNotIn(field, report)
        for forbidden in ("Hunt Profile", "Runtime Qualification", ".json",
                          "src/task/", "C:\\", "Z:\\", "session-1"):
            self.assertNotIn(forbidden, repr(report))


if __name__ == "__main__":
    unittest.main()
