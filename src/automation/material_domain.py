"""Shared, profile-backed receipt path for domain material tasks.

This module deliberately delegates capture, OCR, identity and item recognition
to the existing BaseWWTask and RoutineObserver implementations.
"""
import json
from pathlib import Path

from src.automation.goals import compact_text
from src.automation.identity import fresh_observation, observe_identity
from src.automation.material_receipt import verify_selected_inventory_receipt
from src.automation.observations import RoutineObserver
from src.automation.resource_policy import (
    ActionJournal, ResourceBudget, ResourceLedger, ResourcePolicyError,
    UncertainReceipt, verify_debit,
)

# Domain farming has no independently reviewed current-runtime qualification
# or publisher-permission record in this checkout. Keep task input disabled
# until those evidence contracts are supplied and wired here.
MATERIAL_DOMAIN_LIVE_ENABLED = False


class MaterialDomainAdapter:
    """Material binding and one-claim receipt contract shared by providers."""

    PROVIDER_NAME = None
    SELECTOR_KEY = None
    COST = None
    OBSERVATION_ACTIVITY = 'domain'

    def init_material_adapter(self):
        self.default_config.update({
            'Preview Only': True,
            'Max Waveplates': 0,
            'Max Claims': 0,
            'Max Seconds': 0,
            'Minimum Waveplates': 0,
            'Observation Profile': '',
            'Challenge Identity': '',
            'Target Material': '',
            'Journal Path': 'configs/automation-actions.json',
        })
        self._material_goals = []
        self._material_observer = None
        self._material_inventory = None
        self._material_profile = None
        self._material_pending = None
        self._resource_ledger = None
        self._external_resource_ledger = False
        self._queued_goals = None
        self._queued_inventory_before = None

    def sleep_check(self):
        ledger = getattr(self, '_resource_ledger', None)
        if ledger is not None:
            ledger.check_time()
        super().sleep_check()

    def _load_material_binding(self, goals):
        if not goals or len(goals) != 1:
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: exactly one material goal is required')
        goal = goals[0]
        selector = self.config.get(self.SELECTOR_KEY)
        if selector is None or (isinstance(selector, str) and not selector.strip()):
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: explicit {self.SELECTOR_KEY} required')
        path_text = self.config.get('Observation Profile', '')
        path = Path(path_text) if isinstance(path_text, str) and path_text.strip() else None
        if path is None or not path.is_file():
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: qualified provider observation profile required')
        try:
            profile = json.loads(path.read_text(encoding='utf-8'))
            identity_activity = profile['activity']
            observer = RoutineObserver(self, path, identity_activity)
            binding = profile['source_binding']
            challenge = profile['challenge_identity']
            expected_challenge = challenge['text']
            box = challenge['box']
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: incomplete qualified source binding: {error}') from error
        if (not isinstance(expected_challenge, str) or not expected_challenge.strip()
                or not isinstance(box, (list, tuple)) or len(box) != 4
                or not all(type(value) in (int, float) and 0 <= value <= 1 for value in box)
                or box[0] >= box[2] or box[1] >= box[3]):
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: invalid calibrated challenge OCR region')
        if (binding != {'provider': self.PROVIDER_NAME, 'selector': selector,
                        'material': goal.name, 'challenge_text': expected_challenge}
                or compact_text(self.config.get('Challenge Identity', '')) != compact_text(expected_challenge)):
            raise ResourcePolicyError(
                f'{self.PROVIDER_NAME}: exact provider, selector, challenge and material binding required')
        if goal.name not in observer.profile['inventory']:
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: selected material has no calibrated inventory OCR')
        self._material_goals = list(goals)
        self._material_observer = observer
        self._material_profile = profile
        self._material_inventory = None
        return observer

    def _verify_selected_challenge(self):
        """Compare fresh OCR in the provider selection UI before teleport/start."""
        if self._material_profile is None:
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: source binding was not loaded')
        challenge = self._material_profile['challenge_identity']
        previous = None
        sequence = None
        for _ in range(3):
            sequence = fresh_observation(self, sequence)
            matches = [compact_text(box.name) for box in self.ocr(*challenge['box'])]
            expected = compact_text(challenge['text'])
            if matches != [expected]:
                raise ResourcePolicyError(
                    f'{self.PROVIDER_NAME}: exact challenge OCR mismatch; expected {expected!r}, observed {matches!r}')
            if matches == previous:
                return expected
            previous = matches
            self.sleep(0.3)
        raise ResourcePolicyError(f'{self.PROVIDER_NAME}: challenge OCR did not stabilize')

    def _configure_material_ledger(self):
        from src.automation.session import get_session
        ledger = getattr(self, '_resource_ledger', None)
        if getattr(self, '_external_resource_ledger', False) and ledger is not None:
            if ledger.identity.activity != self._material_observer.activity:
                raise ResourcePolicyError('Shared resource ledger activity does not match provider profile')
            ledger.check_time()
            if ledger.journal.unresolved(ledger.identity):
                raise UncertainReceipt('Interrupted provider claim requires reconciliation')
            return ledger
        identity = observe_identity(self, self._material_observer.identity_profile,
                                    self._material_observer.activity)
        budget = ResourceBudget(
            self.config.get('Max Waveplates', 0), self.config.get('Max Claims', 0),
            self.config.get('Max Seconds', 0), self.config.get('Minimum Waveplates', 0))
        journal = ActionJournal(self.config.get('Journal Path', 'configs/automation-actions.json'))
        if journal.unresolved(identity):
            raise UncertainReceipt('Prior provider claim is unresolved; reconcile before another run')
        ledger = ResourceLedger(journal, identity, budget)
        self._resource_ledger = ledger
        session = get_session(self)
        if session.owner is not None:
            session.deadline = min(session.deadline, session.clock() + budget.max_seconds)
        return ledger

    def _read_material_baseline(self):
        observation, inventory = self._material_observer.observe()
        ledger = self._resource_ledger
        if ledger is not None and observation.identity != ledger.identity:
            raise UncertainReceipt('Fresh provider baseline identity differs from the resource ledger')
        if not observation.eligible and not observation.completed:
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: source is not eligible for a claim')
        goal = self._material_goals[0]
        if goal.name not in inventory:
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: selected material missing from fresh OCR inventory')
        goal.owned = inventory[goal.name]
        queued_baseline = getattr(self, '_queued_inventory_before', None)
        if queued_baseline is not None and queued_baseline != inventory:
            raise ResourcePolicyError('Fresh provider baseline differs from the selected source inventory snapshot')
        self._material_inventory = dict(inventory)
        return observation, inventory

    def _claim_material_receipt(self, *, claim_ui_ready):
        """Journal before confirmation; confirm only a fresh debit and exact receipt."""
        ledger = self._resource_ledger
        if ledger is None or self._material_inventory is None:
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: fresh baseline and resource ledger required')
        ledger.check_time()
        if not claim_ui_ready():
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: reward claim UI was not recognized')
        before, reserve, _ = self.get_stamina()
        if type(before) is not int or before < self.COST or reserve < 0:
            raise ResourcePolicyError(f'{self.PROVIDER_NAME}: insufficient current Waveplates; reserve use blocked')
        baseline = dict(self._material_inventory)
        prepared = []

        def prepare(cost, current, _reserve):
            if cost != self.COST or current != before:
                raise UncertainReceipt('Claim cost or balance changed before confirmation')
            observed_identity = observe_identity(
                self, self._material_observer.identity_profile,
                self._material_observer.activity)
            if observed_identity != ledger.identity:
                raise UncertainReceipt('Fresh account/server/reset identity changed before claim confirmation')
            prepared.append(ledger.prepare(cost, current, baseline))

        try:
            self.use_stamina(once=self.COST, force_single=True, allow_reserve=False,
                             before_confirm=prepare)
            if len(prepared) != 1:
                raise UncertainReceipt('Claim was not durably prepared exactly once')
            action_id = prepared[0]
            observation, after_inventory = self._material_observer.observe(baseline)
            if observation.identity != ledger.identity:
                raise UncertainReceipt('Account/server/reset identity changed during claim')
            after, reserve, _ = self.get_stamina()
            verify_debit(before, after, self.COST)
            goal = self._material_goals[0]
            receipt = verify_selected_inventory_receipt(
                baseline, after_inventory, {goal.name})
            ledger.journal.confirm(action_id, current=after, inventory=after_inventory)
            goal.owned = after_inventory[goal.name]
            self._material_inventory = dict(after_inventory)
            self._material_pending = None
            self.info_set('Selected material OCR receipt', [
                {'material': row.material, 'received': row.received,
                 'owned': row.after, 'status': 'OBSERVED_OCR_ONLY'} for row in receipt])
            self.info_incr('used stamina', self.COST)
            return after
        except BaseException as error:
            action_id = prepared[0] if prepared else None
            if action_id:
                ledger.journal.uncertain(action_id, error)
            raise

    def _material_loop(self, *, enter, fight, claim_ui_ready, restart, leave):
        """Bounded claim loop. No retry occurs after an uncertain receipt."""
        ledger = self._resource_ledger
        max_claims = min(ledger.budget.max_runs, ledger.budget.max_spend // self.COST)
        if max_claims <= 0:
            raise ResourcePolicyError('Explicit budget cannot fund one claim')
        try:
            enter()
            for count in range(max_claims):
                ledger.check_time()
                self.sleep_check()
                fight()
                self._claim_material_receipt(claim_ui_ready=claim_ui_ready)
                goal = self._material_goals[0]
                if goal.missing == 0:
                    self.info_set('停止原因', 'Selected material target reached')
                    return
                current, reserve, _ = self.get_stamina()
                if current < self.COST:
                    self.info_set('停止原因', 'Insufficient current Waveplates; stopped without reserve use')
                    return
                if count + 1 >= max_claims:
                    self.info_set('停止原因', 'Explicit claim or spend limit reached')
                    return
                restart()
        finally:
            leave()

    def _run_material_workflow(self, *, enter, fight, claim_ui_ready, restart, leave):
        if not self.config.get('Preview Only', True):
            if not MATERIAL_DOMAIN_LIVE_ENABLED:
                raise ResourcePolicyError(
                    'LIVE_VERIFICATION_PENDING: domain provider execution lacks publisher permission '
                    'and current-runtime independent qualification')
            external_ledger = getattr(self, '_external_resource_ledger', False)
            old_ledger = getattr(self, '_resource_ledger', None)
            session = None
            old_deadline = None
            if not external_ledger:
                from src.automation.session import get_session
                session = get_session(self)
                old_deadline = session.deadline
            try:
                self._configure_material_ledger()
                self._read_material_baseline()
                if self._material_goals[0].missing == 0:
                    self.info_set('停止原因', 'Selected material target already met; no challenge entered or resource spent')
                    return
                self._material_loop(enter=enter, fight=fight, claim_ui_ready=claim_ui_ready,
                                    restart=restart, leave=leave)
            finally:
                if not external_ledger:
                    self._resource_ledger = old_ledger
                    if session is not None:
                        session.deadline = old_deadline
            return
        self.info_set('停止原因', 'Preview only; no challenge entered and no resource spent')
