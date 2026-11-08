import re


from ok import Logger, run_task
from config import config
from src.Labels import Labels
from src.task.BaseWWTask import BaseWWTask
from src.task.WWOneTimeTask import WWOneTimeTask
from src.task.task_icons import task_icon
from src.automation.weekly import WeeklyActivityAdapter
from src.automation.resource_policy import UncertainReceipt

logger = Logger.get_logger(__name__)


class GardenTask(WWOneTimeTask, BaseWWTask):
    GARDEN_TARGET_POINTS = re.compile('6000')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "🎡 自动周常乐园"
        self.icon = task_icon('garden')
        self.group_name = 'Daily Activities'
        self.group_icon = task_icon('category-daily')
        self.description = "Detect and click garden actions until the task is stopped."
        self.default_config.update({'Weekly Activity Profile': ''})
        self.config_description.update({'Weekly Activity Profile':
            'Current Fantasies Weekly Activity calibration. Empty pauses; historical Remnant Crystal claim flow is disabled.'})
        self.garden_features = [
            label.value for label in Labels
            if label.value.startswith("garden_")
        ]
        self.garden_priority_features = [
            "garden_get_skip",
            "garden_not_interested_confirm",
        ]

    def run(self):
        WWOneTimeTask.run(self)
        self.ensure_main()
        self.open_garden_weekly_page()
        if self.is_weekly_garden_completed():
            self.log_info(self.tr('Garden task completed; limit reached'), notify=True)
            return
        if not self._weekly_activity.enter_garden():
            return
        while True:
            self.sleep(0.1)
            target = self.find_best_garden_feature()
            self.sleep(0.2)
            if target:
                self.info_set("current task", target.name)
                if target.name == 'garden_get_skip':
                    self.sleep(1)
                    self.log_info(self.tr('click garden_get_confirm'))
                    if gold := self.find_one('garden_get_gold', horizontal_variance=0.9):
                        self.click(gold, after_sleep=1)
                    elif purple := self.find_one('garden_get_purple', horizontal_variance=0.9):
                        self.click(purple, after_sleep=1)
                    else:
                        self.click(0.5, 0.2, after_sleep=1)
                    self.click(self.get_box_by_name('garden_get_confirm_gray'), after_sleep=1)
                    continue
                elif target.name == 'garden_not_interested':
                    not_interested = self.find_feature('garden_not_interested', vertical_variance=0.4)
                    self.click(not_interested[-1], after_sleep=1)
                    self.click(self.get_box_by_name('garden_not_interested_confirm'), after_sleep=1)
                    continue
                elif target.name == 'garden_start_game':
                    # At Garden Entrance, choose blessing1
                    self._choose_first_blessing()
                self.log_info(self.tr('click {name} {confidence:.3f}').format(name=target.name, confidence=target.confidence))
                self.click(target, after_sleep=1)
            else:
                garden_restart = self.find_one('a_garden_restart')
                garden_back = self.find_one('a_garden_back')
                if garden_restart and garden_back:
                    # 避免因点击太快，导致[挑战失败]页面中点击[返回主页]失败
                    self.sleep(2)
                    texts = self.ocr(0.373, 0.346, 0.859, 0.615)
                    self.log_info(self.tr('Garden finished: {texts}').format(texts=texts))
                    if self.is_garden_done(texts):
                        self.click(garden_back, after_sleep=1)
                        if self.wait_feature('garden_start_game', settle_time=1, time_out=5):
                            self.back(after_sleep=1)
                        self.open_garden_weekly_page()
                        if not self.is_weekly_garden_completed():
                            raise UncertainReceipt('Garden returned without verified Weekly Activity completion')
                        break
                    else:
                        self.click(garden_restart, after_sleep=1)
                self.sleep(0.2)
        self.log_info('Weekly Activity progress verified; reward claim requires a separately qualified receipt screen', notify=True)

    def open_garden_weekly_page(self):
        self._weekly_activity = WeeklyActivityAdapter(self, self.config.get('Weekly Activity Profile', ''))
        self._weekly_activity.open()

    def is_weekly_garden_completed(self):
        current, target = self._weekly_activity.observe_progress()
        self.info_set('Weekly Activity progress', f'{current}/{target}')
        return current >= target

    def is_garden_done(self, texts):
        text = " ".join(str(getattr(box, "name", box)) for box in texts)
        return text.count(self.GARDEN_TARGET_POINTS.pattern) != 1

    def find_best_garden_feature(self):
        matches = []
        for feature_name in self.garden_features:
            if not self.feature_exists(feature_name):
                continue
            if feature_name == 'garden_get_confirm_gray' or feature_name == 'garden_not_interested_confirm':
                continue
            if feature_name == 'garden_not_interested':
                matches.extend(self.find_feature(feature_name, vertical_variance=0.4))
            else:
                matches.extend(self.find_feature(feature_name))
        for priority_feature in self.garden_priority_features:
            priority_matches = [
                match for match in matches
                if match.name == priority_feature
            ]
            if priority_matches:
                return max(priority_matches, key=lambda box: box.confidence)
        return max(matches, key=lambda box: box.confidence, default=None)

    def _choose_first_blessing(self):
        """At Garden Entrance, choose first blessing"""
        # click blessing botton
        self.click(965 / 1920, 860 / 1080, after_sleep=2)
        # choose blessing1(Add-on)
        self.click(700 / 1920, 666 / 1080, after_sleep=2)
        # confirm
        self.click(1600 / 1920, 900 / 1080, after_sleep=2)


if __name__ == "__main__":
    run_task(config, task=GardenTask, debug=True)
