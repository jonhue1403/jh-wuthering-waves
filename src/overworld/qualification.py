"""Evidence-bound runtime qualification, separate from historic profile flags.

This never promotes old screenshots or a successful import to a live PASS.
Sidecars are written/reviewed after the actual staged qualification procedure.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path


LIVE_PENDING = "LIVE_VERIFICATION_PENDING"
STAGES = ("LOCALIZATION", "WALK", "SINGLE_CAMP", "MATERIAL_ROUTE", "BEACON")
REQUIRED_SOURCES = (
    "src/overworld/controller.py",
    "src/overworld/navigation/player_locator.py",
    "src/overworld/navigation/image_matcher.py",
    "src/overworld/navigation/route_follower.py",
    "src/overworld/navigation/ok_adapter.py",
    "src/task/HuntMobTask.py",
    "src/task/BaseWWTask.py",
    "src/task/BaseCombatTask.py",
    "src/automation/session.py",
    "src/automation/input_guard.py",
)


def file_sha256(path):
    with Path(path).open("rb") as stream:
        digest = sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_files(base, entries):
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Qualification needs file hashes and actual evidence")
    for name, expected in entries.items():
        path = (Path(base) / name).resolve()
        if (not isinstance(expected, str) or len(expected) != 64 or not path.is_file()
                or file_sha256(path) != expected):
            raise ValueError(f"Stale or missing qualification file: {name}")


@dataclass(frozen=True)
class RuntimeQualification:
    path: Path
    data: dict

    @classmethod
    def load(cls, path):
        if not path or not Path(path).is_file():
            raise ValueError(f"{LIVE_PENDING}: select a reviewed runtime qualification")
        resolved = Path(path).resolve()
        data = json.loads(resolved.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or data.get("status") != "REVIEWED":
            raise ValueError(f"{LIVE_PENDING}: runtime qualification is not reviewed")
        return cls(resolved, data)

    def assert_compatible(self, profile_path, profile, *, runtime_version, game_version,
                          stage, source_root):
        data = self.data
        if (stage not in STAGES or stage not in data.get("permitted_stages", [])
                or not game_version or runtime_version != data.get("ok_script_version")
                or game_version != data.get("game_version")):
            raise ValueError(f"{LIVE_PENDING}: runtime, game version or stage differs")
        if (data.get("state_id"), str(data.get("floor_id", ""))) != profile.layer:
            raise ValueError("Runtime qualification belongs to another map/layer")
        bindings = data.get("bindings", {})
        actual = {"profile": Path(profile_path), "reference": profile.image_path,
                  "database": profile.database_path}
        if profile.matcher_calibration_path:
            actual["matcher_calibration"] = profile.matcher_calibration_path
        if set(bindings) != set(actual):
            raise ValueError("Qualification does not bind the complete calibration")
        for name, path in actual.items():
            if not path.is_file() or file_sha256(path) != bindings[name]:
                raise ValueError(f"Stale runtime qualification binding: {name}")
        sources = data.get("source_sha256", {})
        required = set(REQUIRED_SOURCES)
        if stage in ("MATERIAL_ROUTE", "BEACON"):
            required.update(("src/overworld/material_route.py", "src/task/BoundedRouteTask.py"))
        if not required.issubset(sources):
            raise ValueError("Qualification must bind capture, navigation and combat adapters")
        verify_files(source_root, sources)
        verify_files(self.path.parent, data.get("evidence_sha256"))
        if data.get("independent_review") is not True:
            raise ValueError("Runtime qualification needs independent evidence review")
