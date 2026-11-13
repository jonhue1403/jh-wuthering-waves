"""Synthetic regression: frozen observation claims must be revalidated at every read boundary."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.overworld.qualification import REQUIRED_SOURCES
from src.automation.farming_live_handoff import (
    build_observation_handoff, validate_observation_handoff_integrity,
)
from src.automation.farming_capture_binding import (
    FrameBindingBlocked, bind_retained_frame_files,
)
from src.automation.farming_capture_session import (
    CaptureSessionBlocked, inspect_readonly_capture_session,
)
from src.automation.farming_capture_verify import verify_local_capture_claim

NOW = datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc)


def sample_handoff():
    return build_observation_handoff({
        "schema_version": 1,
        "purpose": "SOURCE_DROP",
        "target_kind": "material",
        "target_id": "ff-mech-core",
        "game_mob_id": "000123",
        "game_version": "synthetic-1",
        "ok_script_version": "3.0.4",
        "session_id": "synthetic-session",
        "observed_at": (NOW - timedelta(seconds=5)).isoformat(),
        "stage": "SINGLE_CAMP",
        "route_id": "",
        "state_id": "map-a",
        "floor_id": "0",
        "frame_ids": ["before", "after"],
        "frame_sha256": {"before": "a" * 64, "after": "b" * 64},
        "bindings_sha256": {
            "profile": "c" * 64, "reference": "d" * 64,
            "database": "e" * 64,
        },
        "source_sha256": {key: "f" * 64 for key in REQUIRED_SOURCES},
        "inventory_before": 4,
        "inventory_after": 5,
    }, now=NOW)


class TestFarmingHandoffIntegrity(unittest.TestCase):
    def test_unmodified_packet_revalidates_without_approval(self):
        packet = sample_handoff()
        self.assertIs(validate_observation_handoff_integrity(packet, now=NOW), packet)
        self.assertIs(packet.public_summary()["can_start"], False)

    def test_replaced_material_or_enemy_identity_is_rejected(self):
        packet = sample_handoff()
        for change in (
            {"target_id": "another-material"},
            {"game_mob_id": "000456"},
            {"game_version": "synthetic-2"},
            {"inventory_after": 99},
        ):
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, "HANDOFF_INTEGRITY_INVALID"):
                    validate_observation_handoff_integrity(
                        replace(packet, **change), now=NOW,
                    )

    def test_replaced_digest_or_claimed_packet_hash_is_rejected(self):
        packet = sample_handoff()
        for modified in (
            replace(packet, record_sha256="0" * 64),
            replace(packet, frame_sha256=tuple(reversed(packet.frame_sha256))),
            replace(packet, source_sha256=(packet.source_sha256[0],) + packet.source_sha256),
            replace(packet, bindings_sha256=(("profile", "0" * 64),) +
                    tuple(pair for pair in packet.bindings_sha256 if pair[0] != "profile")),
        ):
            with self.subTest(modified=modified):
                with self.assertRaisesRegex(ValueError, "HANDOFF_INTEGRITY_INVALID"):
                    validate_observation_handoff_integrity(modified, now=NOW)

    def test_rejects_noncanonical_timestamp_and_expired_packet(self):
        packet = sample_handoff()
        changed = replace(packet, observed_at_utc=packet.observed_at_utc.replace("+00:00", "Z"))
        with self.assertRaisesRegex(ValueError, "HANDOFF_INTEGRITY_INVALID"):
            validate_observation_handoff_integrity(changed, now=NOW)
        with self.assertRaisesRegex(ValueError, "HANDOFF_INTEGRITY_INVALID"):
            validate_observation_handoff_integrity(packet, now=NOW + timedelta(minutes=16))

    def test_private_frame_binding_rejects_forged_handoff_before_references(self):
        packet = replace(sample_handoff(), record_sha256="0" * 64)
        with self.assertRaisesRegex(FrameBindingBlocked, "HANDOFF_INTEGRITY_INVALID"):
            bind_retained_frame_files(packet, {}, now=NOW)

    def test_session_coherence_rejects_forged_handoff_before_snapshot_reads(self):
        packet = replace(sample_handoff(), record_sha256="0" * 64)
        with self.assertRaisesRegex(CaptureSessionBlocked, "HANDOFF_INTEGRITY_INVALID"):
            inspect_readonly_capture_session(packet, {}, {}, now=NOW)

    def test_local_byte_verifier_rejects_forged_handoff_without_touching_disk(self):
        packet = replace(sample_handoff(), target_id="forged-material")
        result = verify_local_capture_claim(
            packet, source_root="/unneeded", evidence_root="/unneeded",
            frame_files={}, binding_files={}, now=NOW,
        )
        self.assertEqual("REJECTED", result.status)
        self.assertEqual("HANDOFF_INTEGRITY_INVALID", result.reason_code)
        self.assertEqual("", result.packet_sha256)
        self.assertIs(result.public_summary()["can_start"], False)


if __name__ == "__main__":
    unittest.main()
