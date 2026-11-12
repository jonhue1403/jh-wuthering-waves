"""Read-only OK Script WebCustomTab for the material-first Farming Assistant.

The UI is discovery-only. This task cannot issue game input, dispatch routes,
change session controls or spend resources. The old HuntMobTask remains intact
for backwards compatibility until a separately qualified execution adapter is
ready to replace its ordinary user-facing configuration.
"""
from pathlib import Path

from ok import WebCustomTab, WebTabConfig, task_tab_action, task_tab_query

from src.automation.farming_view import FarmingAssistantView


class FarmingAssistantTask(WebCustomTab):
    web_tab = WebTabConfig(
        id="farming-assistant",
        name="Farming Assistant",
        icon="target",
        asset_dir=Path(__file__).resolve().parents[1] / "web" / "farming_assistant",
        add_after_default_tabs=True,
        task_controls=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Farming Assistant"
        self._view = FarmingAssistantView()

    @staticmethod
    def _payload(payload):
        if not isinstance(payload, dict):
            raise ValueError("Invalid Farming Assistant request")
        return payload

    @task_tab_query("targets")
    def targets(self, payload):
        request = self._payload(payload)
        return self._view.targets(request.get("kind", "material"),
                                  request.get("query", ""))

    @task_tab_query("preview")
    def preview(self, payload):
        request = self._payload(payload)
        return self._view.preview(request.get("kind", "material"),
                                  request.get("target_id", ""),
                                  request.get("desired_total"))

    @task_tab_action("start")
    def start(self, payload):
        # Enforce independently of the frontend's disabled Start control.
        self._payload(payload)
        raise ValueError(
            "Execution is unavailable: material source, current-game route "
            "and runtime safety gates have not yet been qualified."
        )
