"""Bounded material/daily queue registered with the existing OK scheduler."""
from dataclasses import replace
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import time

from src.automation.goals import MaterialGoal, ResourceGoalQueue, SourceMapping
from src.automation.material_receipt import verify_selected_inventory_receipt
from src.automation.observations import RoutineObserver
from src.automation.identity import observe_identity
from src.automation.resource_policy import ActionJournal, ResourceBudget, ResourceLedger, ResourcePolicyError, UncertainReceipt
from src.automation.routines import INHERITED_ACTIVITIES, RoutineCoordinator
from src.automation.session import get_session
from src.task.BaseWWTask import BaseWWTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.task_icons import task_icon


class ResourceRoutineTask(WWOneTimeTask, BaseWWTask):
    EXECUTORS = {**{cls: (module, cls) for module, cls in INHERITED_ACTIVITIES.values()},
                 'CultivationTask': ('src.task.CultivationTask', 'CultivationTask'),
                 'BoundedRouteTask': ('src.task.BoundedRouteTask', 'BoundedRouteTask'),
                 'ForgeryTask': ('src.task.ForgeryTask', 'ForgeryTask'),
                 'SimulationTask': ('src.task.SimulationTask', 'SimulationTask'),
                 'TacetTask': ('src.task.TacetTask', 'TacetTask')}

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

    @staticmethod
    def _require_budget_cycle(observed, budget_identity, context):
        """Reject observations from a different account/server/reset allowance.

        The shared budget scope is derived from the independently observed
        budget cycle. Passing a different observed cycle to a task or ledger
        could otherwise charge actions to the wrong allowance.
        """
        observed_scope = (observed.account, observed.server, observed.cycle)
        budget_scope = (budget_identity.account, budget_identity.server, budget_identity.cycle)
        if observed_scope != budget_scope:
            raise ResourcePolicyError(
                f'{context} account/server/reset cycle differs from the observed shared budget identity')

    # Domain providers have an adapter now, but their source-specific live
    # runtime and publisher-permission qualification is still unavailable.
    _MATERIAL_GOAL_EXECUTORS = frozenset({
        'CultivationTask', 'BoundedRouteTask', 'ForgeryTask', 'SimulationTask', 'TacetTask',
    })

    @classmethod
    def _material_provider_readiness(cls, executor):
        if executor in {'ForgeryTask', 'SimulationTask', 'TacetTask'}:
            return (False, f'{executor}: LIVE_VERIFICATION_PENDING; publisher permission and a reviewed current-runtime provider qualification are not configured')
        if executor not in cls._MATERIAL_GOAL_EXECUTORS:
            return (False, f'{executor}: UNSUPPORTED_MATERIAL_PROVIDER; no adapted goal receipt')
        return (True, 'CANDIDATE_ONLY: runtime, route, spending and inventory gates still apply')

    @staticmethod
    def _prepare_bounded_material_overrides(overrides, queued_goals):
        """Bind a material to one reviewed route before creating an attempt.

        This is a read-only local preflight, NOT proof of live game success.
        HuntMobTask independently checks the actual runtime source hashes and
        qualified stage again when the inherited executor starts.
        """
        if type(overrides) is not dict or len(queued_goals) != 1:
            raise ResourcePolicyError('One material and explicit route configuration are required')
        for key in ('Route Manifest', 'Runtime Qualification', 'Observed Game Version'):
            if type(overrides.get(key)) is not str or not overrides[key].strip():
                raise ResourcePolicyError(f'BOUNDED_ROUTE_NOT_QUALIFIED: explicit {key} required')
        for key, expected in (('Preview Only', False), ('Localization Only', False),
                              ('Test Walk Only', False), ('Safe Test Mode', True),
                              ('Use Teleport', False), ('Use Motorcycle', False),
                              ('Surface Only', True)):
            if key in overrides and overrides[key] is not expected:
                raise ResourcePolicyError(f'Incompatible bounded material route option: {key}')

        from src.overworld.material_route import MaterialRoute
        from src.overworld.navigation.player_locator import SurfaceProfile
        from src.overworld.qualification import RuntimeQualification
        try:
            route = MaterialRoute.load(overrides['Route Manifest'])
            profile = SurfaceProfile.load(route.profile_path)
            RuntimeQualification.load(overrides['Runtime Qualification']).assert_compatible(
                str(route.profile_path), profile,
                runtime_version=importlib.metadata.version('ok-script'),
                game_version=overrides['Observed Game Version'],
                stage='MATERIAL_ROUTE', source_root=Path(__file__).resolve().parents[2])
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise ResourcePolicyError(f'BOUNDED_ROUTE_NOT_QUALIFIED: {error}') from error
        if route.target_mob != profile.target_mob or route.layer != profile.layer:
            raise ResourcePolicyError('Reviewed material route disagrees with the mob or map layer')
        goal = queued_goals[0]
        if goal.name not in (route.material_id, route.inventory_reader['item_text']):
            raise ResourcePolicyError('Reviewed route material does not match the queued material')
        derived = {'Target Mob': route.target_mob, 'Max Camps': len(route.segments),
                   'User Material Target': goal.required}
        for key, expected in derived.items():
            if key in overrides and (type(overrides[key]) is not type(expected)
                                     or overrides[key] != expected):
                raise ResourcePolicyError(f'Configured {key} disagrees with reviewed route/goal')
        if 'Hunt Profile' in overrides and overrides['Hunt Profile']:
            if (type(overrides['Hunt Profile']) is not str
                    or Path(overrides['Hunt Profile']).resolve() != route.profile_path):
                raise ResourcePolicyError('Configured Hunt Profile differs from reviewed route')
        return {**overrides, **derived, 'Preview Only': False,
                'Localization Only': False, 'Test Walk Only': False}

    def _dispatch(self, name, overrides, ledger, queued_goals=None, source_profile_path=None,
                  inventory_before=None):
        if queued_goals:
            supported, reason = self._material_provider_readiness(name)
            if not supported:
                raise ResourcePolicyError(reason)
        if name == 'BoundedRouteTask' and queued_goals:
            # No fallback to a previously reused task's manifest or game version.
            overrides = self._prepare_bounded_material_overrides(overrides, queued_goals)
        if name not in self.EXECUTORS:
            raise ResourcePolicyError('No qualified registered executor for this source')
        module, class_name = self.EXECUTORS[name]
        cls = getattr(importlib.import_module(module), class_name)
        task = self.get_task_by_class(cls)
        overrides = dict(overrides)
        if queued_goals and name in {'ForgeryTask', 'SimulationTask', 'TacetTask'}:
            if len(queued_goals) != 1 or source_profile_path is None:
                raise ResourcePolicyError(f'{name} requires one exact goal and its mapped source profile')
            profile_path = Path(source_profile_path).resolve()
            try:
                source_profile = json.loads(profile_path.read_text(encoding='utf-8'))
                binding = source_profile['source_binding']
                selector_key = getattr(cls, 'SELECTOR_KEY')
                if (binding.get('provider') != name
                        or binding.get('material') != queued_goals[0].name
                        or selector_key not in overrides
                        or binding.get('selector') != overrides[selector_key]):
                    raise ValueError('provider, material or selected challenge differs from calibrated mapping')
                overrides['Observation Profile'] = str(profile_path)
                overrides['Challenge Identity'] = binding['challenge_text']
                overrides['Preview Only'] = False
            except (OSError, KeyError, TypeError, ValueError) as error:
                raise ResourcePolicyError(f'{name} source binding is not exact: {error}') from error
        if name == 'CultivationTask' and queued_goals:
            overrides['Preview Only'] = False
        if any(k not in task.default_config for k in overrides):
            raise ResourcePolicyError('Unknown inherited task configuration key')
        additional = overrides.get('Additional Tasks to Run After Daily Task',
                                   task.config.get('Additional Tasks to Run After Daily Task', []))
        if 'Merge Echo If discarded > 1000' in additional:
            raise ResourcePolicyError('Valuable-item destruction is disabled in resource routines')
        original = {k: task.config.get(k) for k in overrides}
        old_ledger = getattr(task, '_resource_ledger', None)
        old_goals = getattr(task, '_queued_goals', None)
        old_inventory = getattr(task, '_queued_inventory_before', None)
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
            task._queued_inventory_before = inventory_before
            session.resource_ledger = ledger
            self.run_task_by_class(cls)
        finally:
            task._resource_ledger = old_ledger
            task._external_resource_ledger = old_external
            task._queued_goals = old_goals
            task._queued_inventory_before = old_inventory
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
            raise ResourcePolicyError('Material providers remain disabled pending source/runtime qualification: '
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
        # A pending/uncertain material attempt on this account may refer to a
        # different goal, route, source or reset cycle. Reject it before game
        # startup; begin_activity repeats the gate atomically at journal write.
        # Do not create a new journal merely to inspect a fresh plan.
        if journal.path.exists() and journal.unresolved_material_activities(budget_identity):
            raise UncertainReceipt('Prior unfinished material attempt requires reconciliation before game startup')
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
            self._require_budget_cycle(before, budget_identity, 'Routine activity')
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
                # Satisfied targets are not pending receipts. An incidental gain
                # for one must never validate a different unmet material goal.
                if not candidate.missing:
                    continue
                choices = [s for s in queue.mappings if s.matches(candidate, runtime)]
                if len(choices) == 1 and (
                    choices[0].kind, choices[0].executor, choices[0].profile,
                    choices[0].evidence, choices[0].runtime
                ) == binding:
                    source_goals.append(candidate)
            if not source_goals or goal not in source_goals:
                raise ResourcePolicyError('Selected source has no uniquely bound unmet material goal')
            # A reviewed bounded route certifies exactly one material. Reject
            # incompatible multi-goal plans before any inventory/journal write.
            if source.executor == 'BoundedRouteTask' and len(source_goals) != 1:
                raise ResourcePolicyError('Bounded material route requires exactly one unmet material goal')
            executor_config = plan.get('executor_config', {})
            if type(executor_config) is not dict:
                raise ResourcePolicyError('Executor configuration must be a mapping')
            overrides = executor_config.get(source.executor, {})
            if source.executor == 'BoundedRouteTask':
                # Reject stale, missing, or mismatched route evidence BEFORE
                # inventory reads, game input and durable attempt creation.
                overrides = self._prepare_bounded_material_overrides(overrides, source_goals)
            observer = RoutineObserver(self, path.parent / source.profile, source.kind)
            before, inventory_before = observer.observe()
            if any(inventory_before.get(g.name) != g.owned for g in source_goals):
                raise ResourcePolicyError('Fresh inventory disagrees with one or more queued goals; refresh the plan preview')
            self._require_budget_cycle(before, budget_identity, 'Material goal')
            attempt = self._goal_attempt_identity(before.identity, source, source_goals, inventory_before)
            ledger = ResourceLedger(journal, before.identity, budget, budget_scope=budget_scope)
            ledger.started = started
            session.check()
            ledger.check_time()
            if journal.unresolved(before.identity):
                raise ResourcePolicyError('Prior unconfirmed spending requires reconciliation before another material attempt')
            # The adapted domain providers journal every individual reward
            # confirmation in ActionJournal with its exact pre-claim inventory.
            # Avoid a second activity marker that cannot be reconciled when a
            # task is cancelled before its first claim.
            provider_claim_journal = source.executor in {'ForgeryTask', 'SimulationTask', 'TacetTask'}
            if not provider_claim_journal and not journal.begin_activity(attempt, before.evidence):
                raise ResourcePolicyError('This material attempt was already completed; refresh the observed inventory')
            try:
                self._dispatch(source.executor, overrides, ledger, queued_goals=source_goals,
                               source_profile_path=path.parent / source.profile,
                               inventory_before=inventory_before)
                ledger.check_time()
                session.check()
                after, inventory = observer.observe(inventory_before)
                if after.identity != before.identity or after.observed_at <= before.observed_at:
                    raise ResourcePolicyError('Goal inventory identity/cycle changed or post-observation is stale')
                names = {g.name for g in source_goals}
                # OCR was performed by RoutineObserver using the existing
                # BaseWWTask framework. Independently check that the specific
                # queued material(s), not an unrelated OCR inventory row,
                # actually increased before completing the durable attempt.
                receipt = verify_selected_inventory_receipt(
                    inventory_before, inventory, names
                )
                queue.receive({name: inventory[name] for name in names if name in inventory}, materials=names)
                if not provider_claim_journal:
                    journal.complete(attempt, after.evidence)
                self.info_set('Selected material OCR receipt', [
                    {'material': row.material, 'received': row.received,
                     'owned': row.after, 'status': 'OBSERVED_OCR_ONLY'}
                    for row in receipt
                ])
            except BaseException as error:
                # A crash, cancellation, absent receipt or a mismatched OCR
                # result must not allow a second automatic dispatch.
                if not provider_claim_journal:
                    journal.uncertain_activity(attempt, error)
                raise
            self.info_set('Goal queue progress', queue.preview(runtime))
            count += 1
        self.info_set('Queue result', queue.preview(runtime))
