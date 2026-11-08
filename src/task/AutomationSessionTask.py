"""GUI controls for the existing executor's shared activity/resource policy."""
from ok import Logger

from src.task.BaseWWTask import BaseWWTask
from src.task.task_icons import task_icon
from src.automation.session import get_session, SessionStopped
from src.automation.resource_policy import ResourceBudget


class AutomationSessionTask(BaseWWTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Automation Session Controls'
        self.description = 'Preview budgets, pause, cancel, take over, or explicitly choose a compatible mode.'
        self.icon = task_icon('daily')
        self.group_name = 'Daily Activities'
        self.default_config.update({
            'Operation': 'Preview', 'Max Waveplates': 0, 'Max Claims': 0,
            'Max Seconds': 600, 'Minimum Waveplates': 0, 'Identity Profile': '',
            'Journal Path': 'configs/automation-actions.json',
        })
        self.config_type['Operation'] = {'type': 'drop_down', 'options': [
            'Preview', 'Apply Budget', 'Pause', 'Cancel', 'Manual Takeover',
            'Resume', 'STORY_WATCH', 'NORMAL',
        ]}
        self.config_description.update({
            'Operation': 'NORMAL explicitly permits skipping only on a fresh safe world screen. STORY_WATCH stays locked after stopping.',
            'Identity Profile': 'Reviewed current-game account/server/reset OCR profile; no PC-date scheduling key.',
            'Max Waveplates': 'Explicit shared spend cap. Zero blocks spending; reserve/refills/premium are forbidden.',
        })

    def run(self):
        session = get_session(self)
        operation = self.config.get('Operation', 'Preview')
        if operation == 'Pause':
            session.pause('Operator pause')
        elif operation == 'Cancel':
            session.cancel('Operator cancellation')
        elif operation == 'Manual Takeover':
            session.takeover('Operator manual takeover')
        elif operation == 'STORY_WATCH':
            session.enter_story_watch()
        elif operation in ('NORMAL', 'Resume'):
            if self.next_frame() is None:
                raise SessionStopped('Fresh capture unavailable; mode remains locked')
            from src.automation.input_guard import validate_observation
            validate_observation(self)
            safe = bool(self.in_team_and_world())
            if operation == 'NORMAL':
                session.select_mode('NORMAL', safe_state=safe)
            else:
                session.resume(safe_state=safe)
        elif operation == 'Apply Budget':
            budget = ResourceBudget(self.config['Max Waveplates'], self.config['Max Claims'],
                                    self.config['Max Seconds'], self.config['Minimum Waveplates'])
            session.resource_profile = dict(budget.preview(),
                identity_profile=self.config.get('Identity Profile', ''),
                journal_path=self.config.get('Journal Path', 'configs/automation-actions.json'))
            session._save()
        elif operation != 'Preview':
            raise ValueError('Unknown session control operation')
        self.info_set('Session', {'mode': session.mode, 'state': session.state,
                                 'story_locked': session.story_locked, 'reason': session.reason})
        self.info_set('Resource budget preview', session.resource_profile or 'Not configured; spending blocked')
