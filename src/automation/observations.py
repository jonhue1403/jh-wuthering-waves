"""Profile-backed routine/inventory observations; no inferred rewards."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import time

from src.automation.goals import compact_text
from src.automation.identity import fresh_observation, observe_identity
from src.automation.resource_policy import ResourcePolicyError, verify_inventory
from src.automation.routines import RoutineObservation


class RoutineObserver:
    def __init__(self, task, path, activity):
        self.task, self.activity = task, activity
        self.path = Path(path).resolve()
        try:
            self.profile = json.loads(self.path.read_text(encoding='utf-8'))
            p = self.profile
            if p['schema_version'] != 1 or p['qualified'] is not True:
                raise ValueError('not qualified')
            if p['framework_version'] != importlib.metadata.version('ok-script'):
                raise ValueError('framework drift')
            if p['language'] != task.game_lang or p['resolution'] != [task.width, task.height]:
                raise ValueError('capture profile drift')
            if p['activity'] != activity or not p['qualification_evidence']:
                raise ValueError('wrong activity')
            if hashlib.sha256((self.path.parent / p['screenshot']).read_bytes()).hexdigest() != p['screenshot_sha256']:
                raise ValueError('calibration reference drift')
            if not p['page_feature'] or not p['inventory']:
                raise ValueError('screen and actual inventory required')
            self.identity_profile = str((self.path.parent / p['identity_profile']).resolve())
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise ResourcePolicyError(f'Invalid routine observation profile: {error}') from error

    def _read(self, spec, *, quantity=False):
        b = spec['box']
        if (len(b) != 4 or not all(type(v) in (int, float) and 0 <= v <= 1 for v in b)
                or b[0] >= b[2] or b[1] >= b[3]):
            raise ResourcePolicyError('Invalid calibrated OCR rectangle')
        values = [compact_text(box.name) for box in self.task.ocr(*b)]
        if len(values) != 1:
            raise ResourcePolicyError('Missing or ambiguous calibrated observation')
        if quantity:
            if not re.fullmatch('[0-9]{1,7}', values[0]):
                raise ResourcePolicyError('Actual inventory quantity unreadable')
            return int(values[0])
        return values[0]

    def observe(self, inventory_before=None):
        p, task = self.profile, self.task
        identity = observe_identity(task, self.identity_profile, self.activity)
        previous = None
        sequence = None
        for _ in range(3):
            sequence = fresh_observation(task, sequence)
            if not task.find_one(p['page_feature']):
                raise ResourcePolicyError('Expected routine observation screen unavailable')
            status = self._read(p['status'])
            inventory = {}
            for name, spec in p['inventory'].items():
                if 'label_box' not in spec or not spec.get('item_text'):
                    raise ResourcePolicyError('Actual inventory requires a calibrated item-name cross-check')
                actual_name = self._read({'box': spec['label_box']})
                if actual_name != compact_text(spec['item_text']):
                    raise ResourcePolicyError('Observed inventory item name does not match the intended material')
                inventory[name] = self._read(spec, quantity=True)
            value = (status, inventory)
            if value == previous:
                received = False
                if inventory_before is not None:
                    verify_inventory(inventory_before, inventory)
                    received = True
                completed = status == compact_text(p['status']['completed_text'])
                eligible = status == compact_text(p['status']['eligible_text'])
                if not (completed or eligible):
                    raise ResourcePolicyError('Unknown routine status; no task dispatch')
                evidence = json.dumps({'profile': str(self.path), 'status': status,
                                       'actual_inventory': inventory}, sort_keys=True)
                observation = RoutineObservation(identity.account, identity.server, self.activity, identity.cycle,
                                                time.time(), eligible, completed, evidence,
                                                reward_received=received, profile=str(self.path), qualified=True)
                return observation, inventory
            previous = value
            task.sleep(0.3)
        raise ResourcePolicyError('Routine state failed to stabilize')

    def current_waveplates(self):
        if 'waveplate_box' not in self.profile:
            raise ResourcePolicyError('Fresh current-Waveplate OCR is uncalibrated; reconciliation remains uncertain')
        previous, sequence = None, None
        for _ in range(3):
            sequence = fresh_observation(self.task, sequence)
            if not self.task.find_one(self.profile['page_feature']):
                raise ResourcePolicyError('Resource reconciliation screen disappeared')
            value = self._read({'box': self.profile['waveplate_box']}, quantity=True)
            if value == previous:
                return value
            previous = value
            self.task.sleep(0.3)
        raise ResourcePolicyError('Current Waveplates did not stabilize')
