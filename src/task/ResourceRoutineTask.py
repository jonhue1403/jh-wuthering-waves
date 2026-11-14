"""Bounded material/daily queue registered with the existing OK scheduler."""
from dataclasses import replace
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import time

from src.automation.goals import MaterialGoal, ResourceGoalQueue, SourceMapping
from src.automation.observations import RoutineObserver
from src.automation.identity import observe_identity
from src.automation.resource_policy import ActionJournal, ResourceBudget, ResourceLedger, ResourcePolicyError
from src.automation.routines import INHERITED_ACTIVITIES, RoutineCoordinator
from src.automation.session import get_session
from src.task.BaseWWTask import BaseWWTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.task_icons import task_icon


class ResourceRoutineTask(WWOneTimeTask, BaseWWTask):
    EXECUTORS = {**{cls: (module, cls) for module, cls in INHERITED_ACTIVITIES.values()},
                 'CultivationTask': ('src.task.CultivationTask', 'CultivationTask'),
                 'BoundedRouteTask': ('src.task.BoundedRouteTask', 'BoundedRouteTask')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Resource Goal and Routine Queue'
        self.description = 'Preview labelled goals and bounded daily/weekly plans; execute only qualified source profiles.'
        self.icon = task_icon('daily')
        self.group_name = 'Daily Activities'
        self.group_icon = task_icon('category-daily')
        self.support_schedule_task = True
        self.default_config.update({'Plan Path': '', 'Preview Only': True, 'Maximum Activities': 3,
                                    'Reconcile Pending Only': False})
        self.config_description.update({
            'Plan Path': 'Explicit JSON goals, source mappings, observed identity profiles and shared budgets.',
            'Preview Only': 'Default true: show unresolved mappings and resource limits without game input.',
            'Maximum Activities': '1..3 dispatches through existing registered tasks per invocation.',
            'Reconcile Pending Only': 'Read fresh matching identity, inventory and current balance; never issue a claim.',
        })

    def _load_plan(self):
        path = Path(self.config.get('Plan Path', '')).resolve()
        if not path.is_file():
            raise ResourcePolicyError('Configure an explicit local resource/routine plan')
        plan = json.loads(path.read_text(encoding='utf-8'))
        if plan.get('schema_version') != 1:
            raise ResourcePolicyError('Unsupported plan version')
        maximum = self.config.get('Maximum Activities', 3)
        if type(maximum) is not int or not 1 <= maximum <= 3:
            raise ResourcePolicyError('Maximum Activities must be 1..3')
        activities = plan.get('activities', [])
        if len(activities) > maximum:
            raise ResourcePolicyError('Plan exceeds explicit activity bound')
        goals = []
        for entry in plan.get('goals', []):
            if entry.get('origin') not in ('native_verified', 'user_supplied'):
                raise ResourcePolicyError('Every target must be explicitly labelled native_verified or user_supplied')
            goals.append(MaterialGoal(**entry))
        mappings = []
        for entry in plan.get('sources', []):
            item = dict(entry)
            proof = item.pop('evidence_path', '')
            digest = item.pop('evidence_sha256', '')
            evidence_path = path.parent / proof
            valid = bool(proof and digest and evidence_path.is_file()
                         and hashlib.sha256(evidence_path.read_bytes()).hexdigest() == digest)
            item['qualified'] = bool(item.get('qualified') is True and valid)
            if item.get('executor') not in self.EXECUTORS:
                item['qualified'] = False
            if any(g.name == item.get('material') and g.origin == 'native_verified' for g in goals):
                # Only the adapted Guidebook task currently rechecks a native
                # target requirement. Other producers may use labelled user goals.
                if item.get('executor') != 'CultivationTask':
                    item['qualified'] = False
            mappings.append(SourceMapping(**item))
        return path, plan, ResourceGoalQueue(goals, mappings)

    @staticmethod
    def _goal_attempt_identity(identity, source, goals, inventory_before):
        """Bind a durable material attempt to its observed initial inventory.

        A verified quantity increase changes the next attempt's identity, while
        an interrupted run with the same baseline cannot silently repeat.
        This is a journal correlation key, NOT live provider qualification.
        """
        names = tuple(sorted(goal.name for goal in goals))
        if (not names or any(name not in inventory_before
                             or type(inventory_before[name]) is not int
                             or inventory_before[name] < 0 for name in names)):
            raise ResourcePolicyError('Fresh inventory baseline required for every selected material')
        binding = {
            'executor': source.executor, 'kind': source.kind,
            'profile': source.profile, 'evidence': source.evidence,
            'runtime': source.runtime,
            'inventory_before': {name: inventory_before[name] for name in names},
        }
        fingerprint = hashlib.sha256(json.dumps(binding, sort_keys=True).encode('utf-8')).hexdigest()
        return replace(identity, activity='material-goal:' + fingerprint)

    # The inherited domain tasks currently use DomainTask/TacetTask's generic
    # use_stamina loop. Unlike CultivationTask, they do not bind a selected
    # challenge to a fresh observed reward identity or journal each debit and
    # inventory receipt through the injected ResourceLedger. Merely attaching
    # the ledger to the task cannot make those inherited loops safe for goals.
    _UNADAPTED_MATERIAL_PROVIDERS = frozenset({
        'ForgeryTask', 'SimulationTask', 'TacetTask',
    })

    @classmethod
    def _material_provider_readiness(cls, executor):
        if executor in cls._UNADAPTED_MATERIAL_PROVIDERS:
            return (False, f'{executor}: PROVIDER_ADAPTER_PENDING; fresh challenge-identity '
                    'binding, per-claim resource journal and actual material receipt are required')
        return (True, 'CANDIDATE_ONLY: runtime, route, spending and inventory gates still apply')

    def _dispatch(self, name, overrides, ledger, queued_goals=None):
        if queued_goals:
            supported, reason = self._material_provider_readiness(name)
            if not supported:
                raise ResourcePolicyError(reason)
        if name not in self.EXECUTORS:
            raise ResourcePolicyError('No qualified registered executor for this source')
        module, class_name = self.EXECUTORS[name]
        cls = getattr(importlib.import_module(module), class_name)
        task = self.get_task_by_class(cls)
        overrides = dict(overrides)
        if name == 'CultivationTask' and queued_goals:
            overrides['Preview Only'] = False
        if name == 'BoundedRouteTask' and queued_goals:
            if len(queued_goals) != 1:
                raise ResourcePolicyError('A bounded material route supports one explicit material target')
            overrides['User Material Target'] = queued_goals[0].required
            from src.overworld.material_route import MaterialRoute
            route = MaterialRoute.load(overrides.get('Route Manifest', task.config.get('Route Manifest', '')))
            if queued_goals[0].name not in (route.material_id, route.inventory_reader['item_text']):
                raise ResourcePolicyError('Reviewed route material does not match the queued material')
        if any(k not in task.default_config for k in overrides):
            raise ResourcePolicyError('Unknown inherited task configuration key')
        additional = overrides.get('Additional Tasks to Run After Daily Task',
                                   task.config.get('Additional Tasks to Run After Daily Task', []))
        if 'Merge Echo If discarded > 1000' in additional:
            raise ResourcePolicyError('Valuable-item destruction is disabled in resource routines')
        original = {k: task.config.get(k) for k in overrides}
        old_ledger = getattr(task, '_resource_ledger', None)
        old_goals = getattr(task, '_queued_goals', None)
        old_external = getattr(task, '_external_resource_ledger', False)
        session = get_session(self)
        old_shared = getattr(session, 'resource_ledger', None)
        try:
            for key, value in overrides.items():
                if type(value) is not type(task.default_config[key]):
                    raise ResourcePolicyError('Inherited task configuration type mismatch')
                task.config[key] = value
            task._resource_ledger = ledger
            task._external_resource_ledger = True
            task._queued_goals = queued_goals
            session.resource_ledger = ledger
            self.run_task_by_class(cls)
        finally:
            task._resource_ledger = old_ledger
            task._external_resource_ledger = old_external
            task._queued_goals = old_goals
            session.resource_ledger = old_shared
            for key, value in original.items():
                task.config[key] = value

    def run(self):
        path, plan, queue = self._load_plan()
        runtime = importlib.metadata.version('ok-script')
        self.info_set('Goal queue preview', queue.preview(runtime))
        self.info_set('Routine plan preview', plan.get('activities', []))
        self.info_set('Shared resource limits', plan.get('budget', {}))
        # Distinguish a structurally matched source from a usable executor.
        # This check precedes session startup and any pre-dispatch journal write.
        provider_readiness = {}
        blocked_providers = []
        for goal in queue.goals:
            if not goal.missing:
                continue
            choices = [s for s in queue.mappings if s.matches(goal, runtime)]
            if len(choices) == 1:
                supported, reason = self._material_provider_readiness(choices[0].executor)
                provider_readiness[goal.name] = reason
                if not supported:
                    blocked_providers.append(goal.name)
            else:
                provider_readiness[goal.name] = 'UNRESOLVED: unique compatible source required'
        self.info_set('Material provider readiness', provider_readiness)
        if self.config.get('Preview Only', True):
            return
        if blocked_providers and not self.config.get('Reconcile Pending Only', False):
            raise ResourcePolicyError('Unadapted material providers cannot start: '
                                      + ', '.join(sorted(blocked_providers)))
        budget = ResourceBudget(**plan.get('budget', {}))
        journal = ActionJournal(path.parent / plan.get('journal_path', 'automation-actions.json'))
        maximum = self.config.get('Maximum Activities', 3)
        if self.config.get('Reconcile Pending Only', False):
            profiles = [(e['activity'], e['observation_profile']) for e in plan.get('activities', [])]
            profiles.extend((source.kind, source.profile) for source in queue.mappings if source.qualified)
            for activity, profile in profiles:
                observer = RoutineObserver(self, path.parent / profile, activity)
                observation, inventory = observer.observe()
                current = observer.current_waveplates()
                for action in journal.unresolved(observation.identity):
                    identity = replace(observation.identity, activity=action['identity']['activity'])
                    required_inventory = action['inventory_before']
                    actual = {name: inventory[name] for name in required_inventory if name in inventory}
                    journal.reconcile(action['id'], observed_identity=identity, current=current,
                                      inventory=actual, fresh=True)
            self.info_set('Reconciliation', 'Fresh observations checked; no claim inputs sent')
            return
        if not plan.get('budget_identity_profile'):
            raise ResourcePolicyError('Calibrated observed budget-cycle identity is required for a shared plan allowance')
        budget_identity = observe_identity(self, path.parent / plan['budget_identity_profile'], 'resource_budget')
        budget_scope = hashlib.sha256(json.dumps({'account': budget_identity.account,
                                     'server': budget_identity.server, 'observed_budget_cycle': budget_identity.cycle},
                                    sort_keys=True).encode()).hexdigest()
        WWOneTimeTask.run(self)
        session = get_session(self)
        started = time.monotonic()
        if session.owner is not None:
            session.deadline = min(session.deadline, session.clock() + budget.max_seconds)
        count = 0
        for entry in plan.get('activities', []):
            session.check()
            activity = entry['activity']
            observer = RoutineObserver(self, path.parent / entry['observation_profile'], activity)
            before, inventory_before = observer.observe()
            if (before.account, before.server) != (budget_identity.account, budget_identity.server):
                raise ResourcePolicyError('Activity account/server differs from the observed shared budget identity')
            ledger = ResourceLedger(journal, before.identity, budget, budget_scope=budget_scope)
            ledger.started = started
            coordinator = RoutineCoordinator(journal, budget)
            coordinator.run_one(before,
                dispatch=lambda target, e=entry, l=ledger: self._dispatch(target[1], e.get('task_config', {}), l),
                observe_after=lambda o=observer, inv=inventory_before: o.observe(inv)[0],
                checkpoint=lambda: (session.check(), ledger.check_time()))
            count += 1
        while count < maximum:
            selected = queue.next_source(runtime)
            if selected is None:
                break
            goal, source = selected
            # Batch only uniquely mapped goals bound to this exact producer
            # evidence; another candidate sharing an executor/profile must not
            # enter the same receipt or silently redirect a challenge.
            source_goals = []
            binding = (source.kind, source.executor, source.profile, source.evidence, source.runtime)
            for candidate in queue.goals:
                choices = [s for s in queue.mappings if s.matches(candidate, runtime)]
                if len(choices) == 1 and (
                    choices[0].kind, choices[0].executor, choices[0].profile,
                    choices[0].evidence, choices[0].runtime
                ) == binding:
                    source_goals.append(candidate)
            observer = RoutineObserver(self, path.parent / source.profile, source.kind)
            before, inventory_before = observer.observe()
            if any(inventory_before.get(g.name) != g.owned for g in source_goals):
                raise ResourcePolicyError('Fresh inventory disagrees with one or more queued goals; refresh the plan preview')
            if (before.account, before.server) != (budget_identity.account, budget_identity.server):
                raise ResourcePolicyError('Goal account/server differs from the observed shared budget identity')
            attempt = self._goal_attempt_identity(before.identity, source, source_goals, inventory_before)
            ledger = ResourceLedger(journal, before.identity, budget, budget_scope=budget_scope)
            ledger.started = started
            session.check()
            ledger.check_time()
            if journal.unresolved(before.identity):
                raise ResourcePolicyError('Prior unconfirmed spending requires reconciliation before another material attempt')
            if not journal.begin_activity(attempt, before.evidence):
                raise ResourcePolicyError('This material attempt was already completed; refresh the observed inventory')
            try:
                self._dispatch(source.executor, plan.get('executor_config', {}).get(source.executor, {}),
                               ledger, queued_goals=source_goals)
                ledger.check_time()
                session.check()
                after, inventory = observer.observe(inventory_before)
                if after.identity != before.identity or after.observed_at <= before.observed_at:
                    raise ResourcePolicyError('Goal inventory identity/cycle changed or post-observation is stale')
                names = {g.name for g in source_goals}
                queue.receive({name: inventory[name] for name in names if name in inventory}, materials=names)
                journal.complete(attempt, after.evidence)
            except BaseException as error:
                # A crash, cancellation, absent receipt or a mismatched OCR
                # result must not allow a second automatic dispatch.
                journal.uncertain_activity(attempt, error)
                raise
            self.info_set('Goal queue progress', queue.preview(runtime))
            count += 1
        self.info_set('Queue result', queue.preview(runtime))
