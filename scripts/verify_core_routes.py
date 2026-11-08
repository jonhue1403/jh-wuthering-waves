"""Run risk-focused regressions in separate Qt processes and retain evidence."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

MODULES = '''TestAutomationSession TestAutomationAdapter TestResourceClaims
TestResourceGoals TestResourceRoutineTask TestCultivationTask TestStoryWatch
TestRuntimeQualification TestHuntMobTask TestHuntController TestHuntValidation
TestHuntProfileSetup TestHuntInputAccess TestHuntPlayerLocator TestHuntDiagnostics
TestOverworldMobHunt TestRouteFollower TestCalibrationCapture TestArrowHeading
TestConfig TestCustomCharLoader TestOneTimeCombatRestart TestDeathReentry
TestDomainRecoveryLoop TestScheduleSupport TestMultiAccountDailyTask TestMultiAccountConfig
TestMouseResetTask TestMouseResetImport TestAutoCombatTask TestAutoPickTask
TestSkipDialogConfirm TestSkipDialogWideMode TestNightmareNestTask TestFarmEchoPickup
TestFarmEchoTaskEchoRate TestFarmEchoTeleport TestBaseCombatTask TestGameLauncher
TestFeatureSet TestTacet TestWorld TestCharacterCodeTab'''.split()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes', action='store_true')
    parser.add_argument('--all', action='store_true', help='Reproduce CI discovery of every tests/*.py module')
    parser.add_argument('--output', default='logs/core-routes/verification')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()
    modules = ([p.stem for p in sorted((root / 'tests').glob('*.py')) if p.stem != '__init__']
               if args.all else MODULES + (['TestMaterialRoute', 'TestBoundedRouteTask'] if args.routes else []))
    results = []
    environment = dict(os.environ, PYTHONIOENCODING='utf-8', ONEDNN_MAX_CPU_ISA='AVX2')
    for module in modules:
        started = time.monotonic()
        command = [sys.executable, '-u', 'run_test.py', 'tests.' + module]
        try:
            process = subprocess.run(command, cwd=root, env=environment, capture_output=True,
                                     encoding='utf-8', errors='replace', timeout=150)
            log = process.stdout + process.stderr
            code = process.returncode
        except subprocess.TimeoutExpired as error:
            log, code = str(error), -999
        (output / (module + '.log')).write_text(log, encoding='utf-8')
        match = re.search(r'Ran (\d+) tests? in ', log)
        result = {'module': module, 'exit_code': code, 'tests': int(match[1]) if match else None,
                  'seconds': round(time.monotonic() - started, 3)}
        results.append(result)
        print(json.dumps(result), flush=True)
        (output / 'results.json').write_text(json.dumps({'sha': sha, 'dirty_at_start': bool(dirty),
            'python': sys.executable, 'results': results}, indent=2), encoding='utf-8')
    # CI also visits utility modules with no unittest cases. Preserve their zero
    # count explicitly; never include them in a measured test total.
    return int(any(r['exit_code'] or (not r['tests'] and not args.all) for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
