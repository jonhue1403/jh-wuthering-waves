"""Fail-closed resource accounting shared by ordinary OK task invocations.

This module never sends input. A durable PENDING record must precede the click;
only an observed debit AND actual inventory progress can produce CONFIRMED.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid


class ResourcePolicyError(RuntimeError):
    pass


class UncertainReceipt(ResourcePolicyError):
    pass


def budget_scope_for(identity):
    """Same observed resource cycle shares allowance across entry points."""
    return hashlib.sha256(json.dumps({'account': identity.account, 'server': identity.server,
                                     'observed_budget_cycle': identity.cycle}, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class ClaimIdentity:
    account: str
    server: str
    activity: str
    cycle: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() for v in asdict(self).values()):
            raise ResourcePolicyError('Account, server, activity and observed reset/cycle identity are required')

    @property
    def key(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class ResourceBudget:
    max_spend: int
    max_runs: int
    max_seconds: float
    minimum_balance: int
    allow_reserve: bool = False
    allow_premium: bool = False
    allow_refill: bool = False
    allow_destruction: bool = False
    allow_valuable_items: bool = False

    def __post_init__(self):
        for name in ('max_spend', 'max_runs', 'minimum_balance'):
            if type(getattr(self, name)) is not int:
                raise ResourcePolicyError(f'{name} must be an explicit integer')
        if type(self.max_seconds) not in (int, float) or not math.isfinite(self.max_seconds):
            raise ResourcePolicyError('max_seconds must be a finite explicit number')
        if self.max_spend <= 0 or self.max_runs <= 0 or not 0 < self.max_seconds <= 3600 or self.minimum_balance < 0:
            raise ResourcePolicyError('Configure positive spend/run/time limits and a nonnegative minimum balance')
        if any((self.allow_reserve, self.allow_premium, self.allow_refill,
                self.allow_destruction, self.allow_valuable_items)):
            raise ResourcePolicyError('This qualified policy supports current Waveplates only; dangerous resources are disabled')

    def preview(self):
        return asdict(self)


def verify_debit(before, after, expected, *, observed_regeneration=0):
    """No one-sided allowance: a missing OR excessive debit is uncertain.

    Regeneration is zero by default. One point is accepted only when the caller
    independently observed the regeneration tick in the same claim interval.
    Elapsed time or a permissive OCR tolerance alone is not such evidence.
    """
    if any(type(v) is not int for v in (before, after, expected, observed_regeneration)):
        raise UncertainReceipt('Unreadable or ambiguous resource quantity')
    if min(before, after) < 0 or expected <= 0 or observed_regeneration not in (0, 1):
        raise UncertainReceipt('Invalid resource observation')
    if before - after + observed_regeneration != expected:
        raise UncertainReceipt(f'Observed debit {before - after}, expected {expected}; stop and reconcile')
    return expected


def verify_inventory(before, after):
    if not before or set(before) != set(after):
        raise UncertainReceipt('Actual inventory observation must cover every target material')
    if any(type(value) is not int or value < 0 for value in (*before.values(), *after.values())):
        raise UncertainReceipt('Unreadable actual inventory')
    if any(after[name] < owned for name, owned in before.items()):
        raise UncertainReceipt('Actual inventory decreased during claim')
    if not any(after[name] > owned for name, owned in before.items()):
        raise UncertainReceipt('Reward receipt unverified: no actual target inventory increase')


class ActionJournal:
    """Atomic, cross-process-serialized journal. Corruption/abandoned lock fails closed.

    Operators may reconcile a lock after confirming no controller is running;
    stale locks are never automatically stolen during a possible claim.
    """
    def __init__(self, path):
        self.path = Path(path).resolve()

    @contextmanager
    def _transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(self.path.suffix + '.lock')
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError as error:
            raise ResourcePolicyError(f'Journal busy or interrupted; inspect {lock}') from error
        try:
            os.close(fd)
            try:
                data = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {
                    'version': 1, 'actions': [], 'completed': {}}
                if data['version'] != 1 or not isinstance(data['actions'], list) or not isinstance(data['completed'], dict):
                    raise ValueError('schema')
            except (ValueError, KeyError, TypeError) as error:
                raise ResourcePolicyError('Journal unreadable; execution blocked pending reconciliation') from error
            yield data
            temp = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
            try:
                with temp.open('w', encoding='utf-8') as output:
                    json.dump(data, output, ensure_ascii=False, sort_keys=True, indent=2)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temp, self.path)
            finally:
                temp.unlink(missing_ok=True)
        finally:
            lock.unlink(missing_ok=True)

    @staticmethod
    def _scope(action, identity):
        # Spend/run budgets span activities for this account/server/reset identity.
        return all(action['identity'].get(k) == getattr(identity, k) for k in ('account', 'server', 'cycle'))

    @staticmethod
    def _account(action, identity):
        return all(action['identity'].get(k) == getattr(identity, k) for k in ('account', 'server'))

    def snapshot(self):
        with self._transaction() as data:
            return json.loads(json.dumps(data))

    def unresolved(self, identity):
        return [a for a in self.snapshot()['actions'] if self._account(a, identity)
                and a['state'] in ('PENDING', 'UNCERTAIN')]

    @staticmethod
    def _unfinished_material_activities(activities, identity):
        """Any unfinished material attempt for this account blocks another.

        Source, goal fingerprint and reset cycle may all differ after an
        interruption, so none can justify replay without reconciliation.
        Ordinary scheduled routines retain their independent activity rules.
        """
        return [entry for entry in activities.values()
                if isinstance(entry, dict)
                and entry.get('state') in ('PENDING', 'UNCERTAIN')
                and isinstance(entry.get('identity'), dict)
                and entry['identity'].get('account') == identity.account
                and entry['identity'].get('server') == identity.server
                and isinstance(entry['identity'].get('activity'), str)
                and entry['identity']['activity'].startswith('material-goal:')]

    def unresolved_material_activities(self, identity):
        return self._unfinished_material_activities(
            self.snapshot().get('activities', {}), identity)

    def prepare(self, identity, budget, *, cost, current, inventory, elapsed=0,
                receipt_kind='inventory', budget_scope=''):
        budget_scope = budget_scope or budget_scope_for(identity)
        if type(cost) is not int or cost <= 0 or type(current) is not int or current < cost:
            raise ResourcePolicyError('Insufficient current resource or unknown cost')
        if receipt_kind not in ('inventory', 'spend'):
            raise ResourcePolicyError('Unknown receipt kind')
        if (receipt_kind == 'inventory' and not inventory) or any(type(v) is not int or v < 0 for v in inventory.values()):
            raise ResourcePolicyError('Verified target inventory required before claim')
        with self._transaction() as data:
            account_actions = [a for a in data['actions'] if self._account(a, identity)]
            scope = [a for a in account_actions if a.get('budget_scope', '') == budget_scope
                     or (not a.get('budget_scope') and self._scope(a, identity))]
            if any(a['state'] in ('PENDING', 'UNCERTAIN') for a in account_actions):
                raise UncertainReceipt('Prior pending/uncertain claim must be reconciled; never repeat it')
            spent = sum(a['cost'] for a in scope if a['state'] == 'CONFIRMED')
            runs = sum(a['state'] == 'CONFIRMED' for a in scope)
            if spent + cost > budget.max_spend or runs + 1 > budget.max_runs:
                raise ResourcePolicyError('Shared spend/run budget reached')
            if elapsed < 0 or elapsed >= budget.max_seconds:
                raise ResourcePolicyError('Execution time limit reached')
            if current - cost < budget.minimum_balance:
                raise ResourcePolicyError('Minimum current balance would be violated')
            action_id = uuid.uuid4().hex
            data['actions'].append({'id': action_id, 'identity': asdict(identity), 'state': 'PENDING',
                                    'cost': cost, 'before': current, 'inventory_before': inventory.copy(),
                                    'prepared_at': time.time(), 'reason': '', 'receipt_kind': receipt_kind,
                                    'reward_received': False, 'budget_scope': budget_scope})
        return action_id

    def uncertain(self, action_id, reason):
        with self._transaction() as data:
            action = next(a for a in data['actions'] if a['id'] == action_id)
            if action['state'] != 'CONFIRMED':
                action.update(state='UNCERTAIN', reason=str(reason))

    def confirm(self, action_id, *, current, inventory, observed_regeneration=0):
        error = None
        with self._transaction() as data:
            action = next(a for a in data['actions'] if a['id'] == action_id)
            if action['state'] == 'CONFIRMED':
                return False  # An idempotent receipt, never a second spend.
            try:
                verify_debit(action['before'], current, action['cost'], observed_regeneration=observed_regeneration)
                verify_inventory(action['inventory_before'], inventory)
            except UncertainReceipt as caught:
                action.update(state='UNCERTAIN', reason=str(caught))
                error = caught
            else:
                action.update(state='CONFIRMED', after=current, inventory_after=inventory.copy(),
                              confirmed_at=time.time(), reward_received=True,
                              reason='fresh debit and actual inventory verified')
        if error:
            raise error
        return True

    def confirm_spend(self, action_id, *, current, observed_regeneration=0):
        """Verify spending separately from reward receipt for inherited tasks.

        A successful debit does not imply an inventory reward or goal completion.
        """
        error = None
        with self._transaction() as data:
            action = next(a for a in data['actions'] if a['id'] == action_id)
            if action['receipt_kind'] != 'spend':
                raise ResourcePolicyError('Inventory claim requires actual inventory confirmation')
            if action['state'] == 'CONFIRMED':
                return False
            try:
                verify_debit(action['before'], current, action['cost'], observed_regeneration=observed_regeneration)
            except UncertainReceipt as caught:
                action.update(state='UNCERTAIN', reason=str(caught))
                error = caught
            else:
                action.update(state='CONFIRMED', after=current, confirmed_at=time.time(),
                              reason='resource debit verified; reward receipt still unverified')
        if error:
            raise error
        return True

    def reconcile(self, action_id, *, observed_identity=None, current=None, inventory=None,
                  fresh=False, observed_regeneration=0):
        action = next(a for a in self.snapshot()['actions'] if a['id'] == action_id)
        if (not isinstance(observed_identity, ClaimIdentity)
                or asdict(observed_identity) != action['identity']):
            self.uncertain(action_id, 'Observed account/server/activity/reset identity does not match pending claim')
            raise UncertainReceipt('Wrong or missing observed identity; reconciliation forbidden')
        if not fresh or current is None or (action['receipt_kind'] == 'inventory' and inventory is None):
            self.uncertain(action_id, 'Fresh matching account/server/cycle state unavailable on resume')
            raise UncertainReceipt('Fresh reconciliation unavailable; manual inspection required')
        if action['receipt_kind'] == 'spend':
            return self.confirm_spend(action_id, current=current, observed_regeneration=observed_regeneration)
        return self.confirm(action_id, current=current, inventory=inventory,
                            observed_regeneration=observed_regeneration)

    def is_completed(self, identity):
        return identity.key in self.snapshot()['completed']

    def complete(self, identity, evidence):
        if not evidence:
            raise ResourcePolicyError('Verified completion evidence required')
        with self._transaction() as data:
            if any(self._account(a, identity) and a['state'] in ('PENDING', 'UNCERTAIN') for a in data['actions']):
                raise UncertainReceipt('Cannot complete work with unresolved resource receipt')
            data['completed'][identity.key] = {'identity': asdict(identity), 'evidence': evidence,
                                                'confirmed_at': time.time()}
            if identity.key in data.get('activities', {}):
                data['activities'][identity.key]['state'] = 'COMPLETE'

    def begin_activity(self, identity, evidence):
        if not evidence:
            raise ResourcePolicyError('Observed precondition evidence required')
        with self._transaction() as data:
            activities = data.setdefault('activities', {})
            if identity.key in data['completed']:
                return False
            # Atomic cross-source replay gate: a different material, profile or
            # reset cycle cannot hide an earlier uncertain acquisition attempt.
            if (identity.activity.startswith('material-goal:')
                    and self._unfinished_material_activities(activities, identity)):
                raise UncertainReceipt('Prior unfinished material attempt requires reconciliation before dispatch')
            previous = activities.get(identity.key)
            if previous and previous['state'] in ('PENDING', 'UNCERTAIN'):
                raise UncertainReceipt('Interrupted routine requires observed reconciliation before dispatch')
            activities[identity.key] = {'identity': asdict(identity), 'state': 'PENDING',
                                        'evidence': evidence, 'started_at': time.time()}
        return True

    def uncertain_activity(self, identity, reason):
        with self._transaction() as data:
            activity = data.setdefault('activities', {}).get(identity.key)
            if activity and activity['state'] != 'COMPLETE':
                activity.update(state='UNCERTAIN', reason=str(reason))

    def activity_state(self, identity):
        return self.snapshot().get('activities', {}).get(identity.key, {}).get('state')


class ResourceLedger:
    """A session view over persisted cross-activity accounting, not an executor."""
    def __init__(self, journal, identity, budget, clock=time.monotonic, *, budget_scope=''):
        self.journal, self.identity, self.budget = journal, identity, budget
        self.clock = clock
        self.started = clock()
        self.budget_scope = budget_scope

    def check_time(self):
        if self.clock() - self.started >= self.budget.max_seconds:
            raise ResourcePolicyError('Execution time limit reached')

    def prepare(self, cost, current, inventory):
        self.check_time()
        return self.journal.prepare(self.identity, self.budget, cost=cost, current=current,
                                    inventory=inventory, elapsed=self.clock() - self.started,
                                    budget_scope=self.budget_scope)

    def prepare_spend(self, cost, current, *, activity=None):
        self.check_time()
        identity = replace(self.identity, activity=activity) if activity is not None else self.identity
        return self.journal.prepare(identity, self.budget, cost=cost, current=current,
                                    inventory={}, receipt_kind='spend',
                                    elapsed=self.clock() - self.started, budget_scope=self.budget_scope)
