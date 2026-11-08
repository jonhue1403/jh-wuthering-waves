"""Current Weekly Activity adapter; old Remnant Crystal claims are excluded.

No current screenshot/profile ships with this candidate. Uncalibrated Garden
weekly coordination pauses instead of clicking historical reward coordinates.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path

from src.automation.goals import compact_text, parse_quantity
from src.automation.resource_policy import ResourcePolicyError
from src.automation.identity import fresh_observation


class WeeklyActivityAdapter:
    def __init__(self, task, path):
        self.task = task
        if not path:
            raise ResourcePolicyError('LIVE_VERIFICATION_PENDING: current Fantasies Weekly Activity profile required')
        path = Path(path).resolve()
        try:
            self.profile = json.loads(path.read_text(encoding='utf-8'))
            p = self.profile
            if p['schema_version'] != 1 or p['qualified'] is not True:
                raise ValueError('not qualified')
            if p['framework_version'] != importlib.metadata.version('ok-script'):
                raise ValueError('framework drift')
            if p['language'] != task.game_lang or p['resolution'] != [task.width, task.height]:
                raise ValueError('capture profile drift')
            if not p['qualification_evidence'] or p['ui'] != 'fantasies_weekly_activity':
                raise ValueError('wrong weekly UI')
            if hashlib.sha256((path.parent / p['screenshot']).read_bytes()).hexdigest() != p['screenshot_sha256']:
                raise ValueError('calibration screenshot drift')
            for key in ('weekly_tab_feature', 'garden_entry_feature', 'page_feature'):
                if not isinstance(p[key], str) or not p[key]:
                    raise ValueError('missing calibrated screen feature')
            for key in ('title_box', 'progress_box'):
                b = p[key]
                if (len(b) != 4 or not all(type(v) in (int, float) and 0 <= v <= 1 for v in b)
                        or b[0] >= b[2] or b[1] >= b[3]):
                    raise ValueError('invalid OCR box')
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ResourcePolicyError(f'Invalid Weekly Activity calibration: {error}') from error

    def open(self):
        task, p = self.task, self.profile
        task.openF2Book('gray_book_quest')
        task.wait_click_feature(p['weekly_tab_feature'], time_out=5, raise_if_not_found=True)
        self.observe_progress()

    def observe_progress(self):
        task, p = self.task, self.profile
        previous = None
        sequence = None
        for _ in range(3):
            sequence = fresh_observation(task, sequence)
            if not task.find_one(p['page_feature']):
                raise ResourcePolicyError('Current Weekly Activity page not recognized')
            titles = {compact_text(b.name) for b in task.ocr(*p['title_box'])}
            if not titles.intersection({'WeeklyActivity', '周常活动', '每周活动', '每週活動'}):
                raise ResourcePolicyError('Weekly Activity title unavailable; legacy flow prohibited')
            values = [parse_quantity(b.name) for b in task.ocr(*p['progress_box'])]
            values = [v for v in values if v is not None]
            if len(values) != 1:
                raise ResourcePolicyError('Weekly progress/limit unreadable or ambiguous')
            if values[0] == previous:
                return values[0]
            previous = values[0]
            task.sleep(0.3)
        raise ResourcePolicyError('Weekly progress is unstable')

    def enter_garden(self):
        current, target = self.observe_progress()
        if current >= target:
            return False
        self.task.wait_click_feature(self.profile['garden_entry_feature'], time_out=5, raise_if_not_found=True)
        return True
