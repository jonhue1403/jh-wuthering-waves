"""One-command *offline* qualification for the material-first Farming Assistant.

Run in a local Windows checkout with repository dependencies installed:
    .\.venv\Scripts\python.exe scripts/qualify_farming_one_shot.py

This runner NEVER controls the game, authenticates a drop, approves a route or
changes a runtime qualification. Browser visual and live-game acceptance remain
independent, explicitly reported manual gates.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
TARGET_MODULES = (
    "tests.TestFarmingSelection",
    "tests.TestFarmingAcquisitionReference",
    "tests.TestFarmingStrategy",
    "tests.TestFarmingStopPolicy",
    "tests.TestMaterialRoute",
    "tests.TestFarmingAssistantView",
    "tests.TestFarmingAssistantQt",
    "tests.TestFarmingStandaloneWeb",
    "tests.TestConfig",
    "tests.TestMainWebCompatibility",
)
PY_FILES = (
    "src/automation/farming_selection.py",
    "src/automation/farming_acquisition_reference.py",
    "src/automation/farming_strategy.py",
    "src/automation/farming_stop_policy.py",
    "src/automation/farming_view.py",
    "src/overworld/material_route.py",
    "tests/TestMaterialRoute.py",
    "src/automation/farming_web_server.py",
    "src/gui/FarmingAssistantTab.py",
    "main_farming_web.py",
    "main_web.py",
    "config.py",
    "scripts/qualify_farming_one_shot.py",
)
JS_FILES = (
    "src/web/farming_assistant/index.js",
    "src/web/farming_assistant/standalone.js",
)
LIVE_GATES = (
    "Real Windows Qt appearance, accessibility and close/reopen smoke",
    "Real standalone Chromium/Edge browser console and search/selection smoke",
    "Windows NTFS ACL, junction/reparse and private screenshot retention",
    "Exact observed current game + OK Script versions and enemy/item identities",
    "Independent drop inventory receipt for each acquisition source",
    "Calibrated, SHA-bound route/other producer and permitted runtime stages",
    "Terra Medium independent source and controlled live-stage review",
)


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(path.name + ".tmp")
    scratch.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False),
                       encoding="utf-8")
    os.replace(scratch, path)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=15,
        check=True, encoding="utf-8", errors="replace",
    )
    return result.stdout.strip()


def _phase(name: str, command: list[str], *, timeout: int, output: Path) -> dict:
    started = time.monotonic()
    result = {"name": name, "command": command, "exit_code": None,
              "state": "ERROR", "seconds": 0.0, "log": name + ".log"}
    try:
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            env=dict(os.environ, PYTHONIOENCODING="utf-8",
                     QT_QPA_PLATFORM="offscreen", ONEDNN_MAX_CPU_ISA="AVX2"),
        )
        code = completed.returncode
        log = completed.stdout + completed.stderr
        result["exit_code"] = code
        result["state"] = "PASS" if code == 0 else "FAIL"
    except subprocess.TimeoutExpired as error:
        code = -999
        log = "Timeout: " + str(error)
        result["exit_code"] = code
        result["state"] = "TIMEOUT"
    except OSError as error:
        log = "Command could not launch: " + type(error).__name__
        result["state"] = "BLOCKED"
    result["seconds"] = round(time.monotonic() - started, 3)
    (output / result["log"]).write_text(log, encoding="utf-8")
    return result


def _module_counts(verification_dir: Path, *, expected_sha: str,
                   expected_modules: set[str] | None = None) -> dict:
    """Derive actual counts from the verifier, not optimistic command success."""
    report_path = verification_dir / "results.json"
    if not report_path.is_file():
        raise ValueError("Full verifier did not write results.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("sha") != expected_sha:
        raise ValueError("Verifier ran against a different commit")
    modules = report.get("results")
    if not isinstance(modules, list) or not modules:
        raise ValueError("Verifier produced no module results")
    failures = []
    found_names = [entry.get("module") for entry in modules
                   if isinstance(entry, dict)]
    if len(found_names) != len(set(found_names)):
        failures.append("Duplicate module results")
    if expected_modules is not None and set(found_names) != expected_modules:
        failures.append("Incomplete or unexpected full-suite module coverage")
    skipped = 0
    tests = 0
    for module in modules:
        if (not isinstance(module, dict) or not isinstance(module.get("module"), str)
                or type(module.get("exit_code")) is not int):
            raise ValueError("Malformed module verification result")
        count = module.get("tests")
        if type(count) is not int or count < 0:
            failures.append(module["module"] + " (missing count)")
        elif count == 0:
            # Isolated utility modules can legitimately contain no tests.
            if module["exit_code"] != 0:
                failures.append(module["module"] + " (failed utility)")
        else:
            tests += count
        if module["exit_code"] != 0:
            failures.append(module["module"] + " (exit " +
                            str(module["exit_code"]) + ")")
        log = verification_dir / (module["module"] + ".log")
        if not log.is_file():
            failures.append(module["module"] + " (missing log)")
            continue
        transcript = log.read_text(encoding="utf-8", errors="replace")
        counts = re.findall(r"OK \(skipped=(\d+)\)", transcript)
        if counts:
            skipped += int(counts[-1])
    return {
        "module_count": len(modules), "tests_run": tests,
        "skipped": skipped, "passed": tests - skipped if not failures else None,
        "failed_modules": sorted(set(failures)),
        "verifier_dirty_at_start": report.get("dirty_at_start"),
    }


def _catalog_snapshot() -> dict:
    # No game or OK Script task imports here. The view uses read-only offline
    # audits but does not promote historical receipts to live approval.
    from src.automation.farming_selection import SCREENSHOT_MATERIALS, TargetKind, starting_catalog
    from src.automation.farming_view import FarmingAssistantView

    if len(SCREENSHOT_MATERIALS) != 27:
        raise ValueError("Expected exactly 27 user-supplied material names")
    if len({slug for slug, _ in SCREENSHOT_MATERIALS}) != 27:
        raise ValueError("Duplicate user-facing material identifiers")
    view = FarmingAssistantView()
    listed = view.targets("material")
    if len(listed) != 27 or len({item["id"] for item in listed}) != 27:
        raise ValueError("Catalog is missing or duplicating screenshot materials")
    if listed[0]["id"] != "ff-mech-core":
        raise ValueError("FF Mech Core featured selection was lost")
    if len(view.targets("mob")) != 5:
        raise ValueError("FF Mech Core mob candidates were unexpectedly changed")
    catalog = starting_catalog()
    records = []
    for slug, name in SCREENSHOT_MATERIALS:
        found = view.targets("material", name)
        if len(found) != 1 or found[0]["id"] != slug:
            raise ValueError("Material search mismatch for " + name)
        if not catalog.search(name, kind=TargetKind.MATERIAL):
            raise ValueError("Catalog missing material " + name)
        preview = view.preview("material", slug, "3")
        if (preview["target"]["name"] != name
                or preview["stop_criterion"]["mode"] != "INVENTORY_TOTAL"
                or preview["stop_criterion"]["requested"] != 3
                or preview["stop_criterion"]["state"] != "PLANNED_ONLY"
                or preview["stop_criterion"]["enforced"] is not False
                or preview["owned_quantity"] is not None
                or preview["can_start"] is not False
                or preview["can_pause"] is not False
                or preview["can_stop"] is not False
                or preview["qualified_route_ids"]):
            raise ValueError("Unqualified material presented as executable: " + name)
        reference = preview["acquisition_reference"]
        if (reference["status"] != "REFERENCE_ONLY"
                or reference["can_start"] is not False
                or not reference["methods"]
                or reference["executable_source_ids"]):
            raise ValueError("Unreviewed acquisition method was promoted: " + name)
        strategy = preview["acquisition_plan"]
        if (strategy["can_dispatch"] is not False
                or strategy["can_start"] is not False
                or strategy["selected_provider"] is not None
                or strategy["qualified_provider_ids"]
                or not strategy["possible_methods"]):
            raise ValueError("Unreviewed farming strategy was promoted: " + name)
        policy = preview["stop_criterion"]
        if (policy["decision"] != "FRESH_OBSERVATION_REQUIRED"
                or policy["can_continue"] is not False
                or policy["can_dispatch"] is not False):
            raise ValueError("Unverified material stop rule was bypassed: " + name)
        expected = "SOURCE_DOCUMENTED" if slug == "ff-mech-core" else "SOURCE_UNRESOLVED"
        if preview["readiness"] != expected:
            raise ValueError("Material acquisition state changed without approval: " + name)
        records.append({
            "id": slug, "name": name,
            "readiness": preview["readiness"],
            "documented_possible_source_count": len(preview["source_candidates"]),
            "acquisition_reference_kinds": [
                source["kind"] for source in reference["methods"]
            ],
            "qualified_route_count": 0,
            "live_qualification": "NOT_RUN",
            "can_start": False,
        })
    return {"material_count": 27, "materials": records,
            "game_input_issued": False, "qualification": "CATALOG_ONLY"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-shot offline farming qualification; never controls gameplay")
    parser.add_argument("--smoke", action="store_true",
                        help="Run a smaller diagnostic, not full acceptance")
    parser.add_argument("--output", default=None,
                        help="Report directory under ignored logs/ (optional)")
    args = parser.parse_args(argv)

    sha = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    dirty = bool(_git("status", "--porcelain", "--untracked-files=normal"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = ROOT / "logs" / "farming-one-shot"
    if args.output is not None:
        candidate = Path(args.output)
        if candidate.is_absolute() or ".." in candidate.parts:
            parser.error("--output must be a relative subdirectory of logs/farming-one-shot")
        base = base / candidate
    else:
        base = base / (timestamp + "-" + sha[:9])
    base.mkdir(parents=True, exist_ok=False)
    report_path = base / "qualification.json"
    report = {
        "schema_version": 1, "timestamp_utc": timestamp, "branch": branch,
        "commit": sha, "source_dirty_at_start": dirty,
        "mode": "SMOKE_ONLY" if args.smoke else "FULL_OFFLINE",
        "status": "IN_PROGRESS", "phases": [], "full_suite": None,
        "material_catalog": None,
        "live_status": "LIVE_VERIFICATION_PENDING",
        "manual_acceptance_gates": list(LIVE_GATES),
    }
    _atomic_json(report_path, report)
    try:
        report["material_catalog"] = _catalog_snapshot()
        catalog_state = "PASS"
    except Exception as error:
        catalog_state = "FAIL"
        report["catalog_error"] = type(error).__name__ + ": " + str(error)
    report["phases"].append({"name": "27-material-catalog", "state": catalog_state})
    _atomic_json(report_path, report)

    commands = [
        ("python-compile", [sys.executable, "-m", "py_compile", *PY_FILES], 120),
        ("node-web-module", ["node", "--check", JS_FILES[0]], 90),
        ("node-standalone-module", ["node", "--check", JS_FILES[1]], 90),
    ]
    # Isolate each framework/Qt test in its own Python process; this matches
    # verify_core_routes.py and prevents cross-module GUI state contamination.
    commands.extend(
        ("target-" + module.split(".")[-1],
         [sys.executable, "-u", "run_test.py", module], 150)
        for module in TARGET_MODULES
    )
    if not args.smoke:
        commands.append((
            "full-repository-isolated",
            [sys.executable, "scripts/verify_core_routes.py", "--all",
             "--output", str(base / "full-suite")],
            3600,
        ))
    for name, command, timeout in commands:
        result = _phase(name, command, timeout=timeout, output=base)
        report["phases"].append(result)
        _atomic_json(report_path, report)
    if not args.smoke:
        try:
            expected = {
                path.stem for path in (ROOT / "tests").glob("*.py")
                if path.stem != "__init__"
            }
            report["full_suite"] = _module_counts(
                base / "full-suite", expected_sha=sha,
                expected_modules=expected)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            report["full_suite_error"] = type(error).__name__ + ": " + str(error)

    all_pass = all(row.get("state") == "PASS" for row in report["phases"])
    full = report["full_suite"]
    if args.smoke:
        report["status"] = "SMOKE_PASS_NOT_ACCEPTANCE" if all_pass else "SMOKE_FAIL"
    elif not all_pass or full is None or full["failed_modules"]:
        report["status"] = "OFFLINE_FAIL"
    elif dirty or full["verifier_dirty_at_start"] is not False:
        report["status"] = "OFFLINE_INCONCLUSIVE_DIRTY_SOURCE"
    else:
        report["status"] = "OFFLINE_TESTS_PASS_LIVE_PENDING"
    _atomic_json(report_path, report)
    print(json.dumps({
        "status": report["status"], "commit": sha, "report": str(report_path),
        "full_suite": report["full_suite"], "live": report["live_status"],
    }, indent=2, ensure_ascii=False))
    return 0 if report["status"] in (
        "SMOKE_PASS_NOT_ACCEPTANCE", "OFFLINE_TESTS_PASS_LIVE_PENDING"
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
