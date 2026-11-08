"""Calibrated fresh OCR identity gate. No default game/cycle UI is invented."""
import hashlib
import json
from pathlib import Path

from src.automation.goals import compact_text
from src.automation.resource_policy import ClaimIdentity, ResourcePolicyError


def fresh_observation(task, previous_sequence=None):
    """Reject missing/cached captures before OCR can bless an old identity."""
    frame = task.next_frame()
    if frame is None:
        raise ResourcePolicyError('Fresh capture unavailable; cached OCR cannot authorize execution')
    from src.automation.input_guard import validate_observation
    return validate_observation(task, previous_sequence=previous_sequence)


def observe_identity(task, profile_path, activity):
    """Read account/server/immutable reset ID from an explicitly calibrated view.

    A PC date, countdown, configured identity string, or screenshot filename is
    not a reset observation. Until a supported view is captured/calibrated this
    gate deliberately prevents resource-consuming execution.
    """
    if not profile_path:
        raise ResourcePolicyError('LIVE_VERIFICATION_PENDING: calibrated account/server/reset identity profile required')
    path = Path(profile_path).resolve()
    try:
        profile = json.loads(path.read_text(encoding='utf-8'))
        import importlib.metadata
        if profile['schema_version'] != 1 or profile['qualified'] is not True:
            raise ValueError('unqualified profile')
        if profile['framework_version'] != importlib.metadata.version('ok-script'):
            raise ValueError('framework drift')
        if profile['language'] != task.game_lang or profile['resolution'] != [task.width, task.height]:
            raise ValueError('capture profile drift')
        if profile['cycle_kind'] != 'immutable_observed_reset_id':
            raise ValueError('countdown/PC date is not an observed reset identity')
        screenshot = (path.parent / profile['calibration_screenshot']).resolve()
        if hashlib.sha256(screenshot.read_bytes()).hexdigest() != profile['calibration_sha256']:
            raise ValueError('calibration reference changed')
        screen_feature = profile['screen_feature']
        if not isinstance(screen_feature, str) or not screen_feature:
            raise ValueError('recognized screen required')
        fields = profile['fields']
        if set(fields) != {'account', 'server', 'cycle'}:
            raise ValueError('identity fields incomplete')
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ResourcePolicyError(f'Invalid identity profile: {error}') from error
    previous = None
    sequence = None
    for _ in range(3):
        sequence = fresh_observation(task, sequence)
        if not task.find_one(screen_feature):
            raise ResourcePolicyError('Identity screen not recognized; no spending permitted')
        result = {}
        for name, spec in fields.items():
            box = spec.get('box', [])
            if (len(box) != 4 or not all(type(v) in (float, int) and 0 <= v <= 1 for v in box)
                    or box[0] >= box[2] or box[1] >= box[3]):
                raise ResourcePolicyError('Invalid identity OCR rectangle')
            matches = [compact_text(b.name) for b in task.ocr(*box)]
            expected = compact_text(spec['expected_text'])
            if not expected or matches != [expected]:
                raise ResourcePolicyError(f'Fresh {name} does not match calibrated identity')
            result[name] = expected
        if result == previous:
            return ClaimIdentity(result['account'], result['server'], activity, result['cycle'])
        previous = result
        task.sleep(0.3)
    raise ResourcePolicyError('Identity did not stabilize within three captures')
