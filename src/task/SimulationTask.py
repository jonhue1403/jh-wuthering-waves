import re

from ok import Logger
from src.task.DomainTask import DomainTask
from src.automation.domain_selection import validate_domain_selector
from src.automation.goals import MaterialGoal, compact_text
from src.automation.material_domain import MaterialDomainAdapter
from src.task.task_icons import task_icon

logger = Logger.get_logger(__name__)


class SimulationTask(MaterialDomainAdapter, DomainTask):

    PROVIDER_NAME = 'SimulationTask'
    SELECTOR_KEY = 'Material Selection'
    COST = 40

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '🧪 Simulation Challenge'
        self.icon = task_icon('simulation')
        self.group_name = 'Daily Activities'
        self.group_icon = task_icon('category-daily')
        self.description = 'Farms the selected Simulation Challenge. Must be able to teleport (F2).'
        self.support_schedule_task = True
        self.default_config = {
            'Material Selection': 'Shell Credit',
        }
        material_option_list = ['Resonator EXP', 'Weapon EXP', 'Shell Credit']
        self.config_type['Material Selection'] = {'type': 'drop_down', 'options': material_option_list}
        self.config_description = {
            'Material Selection': 'Resonator EXP / Weapon EXP / Shell Credit',
        }
        self.stamina_once = 40
        self.init_material_adapter()

    def run(self):
        queued = getattr(self, '_queued_goals', None)
        target = self.config.get('Target Material', '')
        if queued or target:
            validate_domain_selector(self.PROVIDER_NAME, self.config.get(self.SELECTOR_KEY))
            goals = queued or [MaterialGoal(target, 0, 1, origin='user_supplied')]
            self._load_material_binding(goals)
            self._run_material_workflow(
                enter=self._enter_material_simulation,
                fight=self._fight_material_simulation,
                claim_ui_ready=self.has_claim_stamina,
                restart=self._restart_material_simulation,
                leave=self.make_sure_in_world,
            )
            return
        validate_domain_selector('SimulationTask', self.config.get('Material Selection', 'Shell Credit'))
        super().run()
        self.make_sure_in_world()
        self.farm_simulation()

    def farm_simulation(self, daily=False, used_stamina=0, config=None):
        if daily:
            must_use = 180 - used_stamina
        else:
            must_use = 0
        if config is None:
            config = self.config
        selection = validate_domain_selector('SimulationTask', config.get('Material Selection', 'Shell Credit'))

        def teleport_once():
            self.teleport_into_domain(selection)

        self.farm_domain_with_recovery_loop(must_use, teleport_once)

    def _enter_material_simulation(self):
        selection = validate_domain_selector(self.PROVIDER_NAME, self.config[self.SELECTOR_KEY])
        self.open_boss_book('moni')
        self.click(0.9730, 0.8806, after_sleep=1)
        index = {'Resonator EXP': 0, 'Weapon EXP': 1, 'Shell Credit': 2}[selection]
        self.click(0.898, 0.533 + index * 0.14, after_sleep=1)
        self._verify_selected_challenge()
        self.click_relative(0.93, 0.90, after_sleep=1)
        self.click_team_challenge()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)

    def _restart_material_simulation(self):
        buttons = {compact_text(b.name): b for b in self.ocr(0.25, 0.78, 0.76, 0.90)}
        restart = buttons.get('重新挑战')
        if restart is None:
            raise RuntimeError('Simulation restart action was not recognized; stopping')
        self.click(restart, after_sleep=1)
        if not self.wait_confirm_challenge_action('restart', time_out=3):
            raise RuntimeError('Simulation restart confirmation was not recognized; stopping')
        self.wait_in_team_and_world(time_out=self.teleport_timeout)

    def _fight_material_simulation(self):
        self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
        self.pick_f()
        self.combat_once(wait_combat_time=30, target=True)
        self.sleep(3)
        self.walk_to_treasure()
        self.pick_f(handle_claim=False)

    def teleport_into_domain(self, selection):
        validate_domain_selector('SimulationTask', selection)
        self.open_boss_book('moni')
        self.info_set('Target Simulation Challenge', selection)
        if selection == 'Resonator EXP':
            index = 0
        elif selection == 'Weapon EXP':
            index = 1
        else:  # The only remaining validated option is Shell Credit.
            index = 2
        # go buttom
        self.click(0.9730, 0.8806, after_sleep=1)
        # click target
        self.click(0.898, 0.533 + index * 0.14, after_sleep=1)
        self.click_relative(0.93, 0.90, after_sleep=1)
        self.click_team_challenge()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)
