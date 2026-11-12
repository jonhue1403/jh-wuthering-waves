"""Read-only native Qt Farming Assistant.

This UI intentionally does not import the game executor, input drivers, session
state or automation tasks. Target discovery uses the exact same path-free
FarmingAssistantView model as the web tab. It cannot start gameplay.
"""

from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIntValidator
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from ok.ui.qt.kit.icons import icon
from ok.ui.qt.widget.CustomTab import CustomTab
from src.automation.farming_view import FarmingAssistantView


class FarmingAssistantTab(CustomTab):
    """Qt presentation for discovery and read-only calibration preview only."""

    def __init__(self):
        super().__init__()
        self._model = FarmingAssistantView()
        self._kind = "material"
        self._selected_id = None
        self._preview = None

        page = QWidget(self.view)
        content = QVBoxLayout(page)
        content.setContentsMargins(12, 12, 12, 12)
        content.setSpacing(12)

        heading = QLabel(self.tr("Farming Assistant"), page)
        font = heading.font()
        font.setPointSize(max(font.pointSize(), 15))
        font.setBold(True)
        heading.setFont(font)
        content.addWidget(heading)

        intro = QLabel(
            self.tr("Choose a material or mob. Read-only preview: no game input, "
                    "combat or item spending is enabled."),
            page,
        )
        intro.setWordWrap(True)
        content.addWidget(intro)

        splitter = QSplitter(Qt.Horizontal, page)
        splitter.setChildrenCollapsible(False)
        content.addWidget(splitter, 1)
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)

        types = QHBoxLayout()
        self.kind_group = QButtonGroup(self)
        self.kind_group.setExclusive(True)
        self.material_button = QToolButton(left)
        self.material_button.setText(self.tr("Materials"))
        self.mob_button = QToolButton(left)
        self.mob_button.setText(self.tr("Mobs"))
        for button in (self.material_button, self.mob_button):
            button.setCheckable(True)
            self.kind_group.addButton(button)
            types.addWidget(button)
        self.material_button.setChecked(True)
        self.material_button.toggled.connect(
            lambda checked: self._switch_kind("material") if checked else None
        )
        self.mob_button.toggled.connect(
            lambda checked: self._switch_kind("mob") if checked else None
        )
        left_layout.addLayout(types)

        self.search = QLineEdit(left)
        self.search.setPlaceholderText(self.tr("Search by material or mob name"))
        self.search.setMaxLength(120)
        self.search.setAccessibleName(self.tr("Search farming targets"))
        self.search.textChanged.connect(self._refresh_targets)
        left_layout.addWidget(self.search)

        self.target_list = QListWidget(left)
        self.target_list.setAccessibleName(self.tr("Available farming targets"))
        self.target_list.currentRowChanged.connect(self._refresh_preview)
        left_layout.addWidget(self.target_list, 1)

        right = QWidget(splitter)
        detail = QVBoxLayout(right)
        detail.setContentsMargins(8, 0, 0, 0)
        detail.setSpacing(10)

        self.target_name = QLabel(self.tr("Select a target"), right)
        detail.addWidget(self.target_name)
        self.target_description = QLabel("", right)
        self.target_description.setWordWrap(True)
        detail.addWidget(self.target_description)

        self.readiness_label = QLabel(self.tr("Unresolved"), right)
        detail.addWidget(self.readiness_label)
        self.reason_label = QLabel("", right)
        self.reason_label.setWordWrap(True)
        detail.addWidget(self.reason_label)

        detail.addWidget(QLabel(self.tr("Possible enemy sources (informational only)"), right))
        self.source_list = QListWidget(right)
        self.source_list.setAccessibleName(self.tr("Documented enemy sources"))
        self.source_list.setMinimumHeight(130)
        self.source_list.currentRowChanged.connect(self._update_source_button)
        detail.addWidget(self.source_list, 1)

        self.reference_button = QToolButton(right)
        self.reference_button.setText(self.tr("Open selected source reference"))
        self.reference_button.setEnabled(False)
        self.reference_button.clicked.connect(self._open_reference)
        detail.addWidget(self.reference_button)

        goal_row = QHBoxLayout()
        goal_label = QLabel(self.tr("Desired inventory total (optional)"), right)
        self.goal = QLineEdit(right)
        self.goal.setPlaceholderText(self.tr("No goal set"))
        self.goal.setValidator(QIntValidator(1, 9_999_999, self.goal))
        self.goal.setAccessibleName(self.tr("Desired inventory total"))
        self.goal.textChanged.connect(self._refresh_preview)
        goal_row.addWidget(goal_label)
        goal_row.addWidget(self.goal, 1)
        detail.addLayout(goal_row)

        self.inventory_label = QLabel(self.tr("Current inventory: not measured"), right)
        detail.addWidget(self.inventory_label)

        self.calibration_label = QLabel(self.tr("Local receipts: none reviewed for execution"), right)
        self.calibration_label.setWordWrap(True)
        detail.addWidget(self.calibration_label)

        actions = QHBoxLayout()
        self.start_button = QToolButton(right)
        self.pause_button = QToolButton(right)
        self.stop_button = QToolButton(right)
        for button, title in (
            (self.start_button, self.tr("Start")),
            (self.pause_button, self.tr("Pause")),
            (self.stop_button, self.tr("Stop")),
        ):
            button.setText(title)
            button.setEnabled(False)
            button.setToolTip(self.tr("Current-game evidence and route qualification required"))
            actions.addWidget(button)
        actions.addStretch(1)
        detail.addLayout(actions)

        self.state_label = QLabel(self.tr("State: PREVIEW ONLY"), right)
        detail.addWidget(self.state_label)
        self.next_step = QLabel(self.tr("Verify sources and calibrate a route before farming."), right)
        self.next_step.setWordWrap(True)
        detail.addWidget(self.next_step)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        left.setMinimumWidth(230)
        right.setMinimumWidth(330)
        self.add_widget(page, stretch=1)
        self._refresh_targets()

    @property
    def name(self):
        return self.tr("Farming Assistant")

    @property
    def icon(self):
        return icon("search")

    def _switch_kind(self, kind):
        self._kind = kind
        self.goal.clear()
        self._selected_id = None
        self._refresh_targets()

    def _refresh_targets(self, *_):
        try:
            targets = self._model.targets(self._kind, self.search.text())
        except ValueError:
            targets = []
        self.target_list.blockSignals(True)
        self.target_list.clear()
        for target in targets:
            item = QListWidgetItem(target["name"])
            item.setData(Qt.UserRole, target["id"])
            item.setToolTip(target["description"])
            self.target_list.addItem(item)
        row = next(
            (i for i in range(self.target_list.count())
             if self.target_list.item(i).data(Qt.UserRole) == self._selected_id),
            0 if self.target_list.count() else -1,
        )
        self.target_list.setCurrentRow(row)
        self.target_list.blockSignals(False)
        self._refresh_preview()

    def _refresh_preview(self, *_):
        selected = self.target_list.currentItem()
        self._selected_id = selected.data(Qt.UserRole) if selected is not None else None
        self._preview = None
        if not self._selected_id:
            self.target_name.setText(self.tr("No matching targets"))
            self.target_description.clear()
            self.readiness_label.setText(self.tr("Unresolved"))
            self.reason_label.clear()
            self.source_list.clear()
            self.inventory_label.setText(self.tr("Current inventory: not measured"))
            self.calibration_label.setText(self.tr("Local receipts: none reviewed for execution"))
            self.state_label.setText(self.tr("State: PREVIEW ONLY"))
            self.next_step.setText(self.tr("Select a material or mob to preview."))
            self._update_source_button()
            self._disable_actions()
            return

        try:
            result = self._model.preview(self._kind, self._selected_id, self.goal.text())
        except ValueError as error:
            self.reason_label.setText(str(error))
            self._disable_actions()
            return

        self._preview = result
        self.target_name.setText(result["target"]["name"])
        self.target_description.setText(result["target"]["description"])
        readiness = result["readiness"]
        if readiness == "SOURCE_DOCUMENTED":
            label = self.tr("Known possible sources — route not calibrated")
        elif readiness == "ROUTE_UNQUALIFIED":
            label = self.tr("Route not calibrated")
        else:
            label = self.tr("Source unresolved")
        self.readiness_label.setText(label)
        self.reason_label.setText(result["reason"])
        self.source_list.clear()
        for source in result["source_candidates"]:
            item = QListWidgetItem(
                source["name"] + " · " + self.tr("documented only")
            )
            item.setData(Qt.UserRole, source["source_url"])
            self.source_list.addItem(item)
        self._update_source_button()
        self.inventory_label.setText(self.tr("Current inventory: not measured"))
        calibration = result["calibration"]
        candidate_count = calibration["receipt_candidate_count"]
        self.calibration_label.setText(
            self.tr("Local receipt candidates: {count} — not live-qualified").format(
                count=candidate_count
            ) if candidate_count else self.tr("No qualified local receipt observations")
        )
        if calibration["rejected_manifest_count"] or calibration["status"] == "AUDIT_INCOMPLETE":
            self.calibration_label.setText(
                self.calibration_label.text() + self.tr(
                    " · Evidence audit incomplete or invalid entries detected"
                )
            )
        self.state_label.setText(self.tr("State: PREVIEW ONLY"))
        self.next_step.setText(result["next_step"])
        self._disable_actions()

    def _disable_actions(self):
        # Never infer authorization from catalog data or widget state. Start,
        # Pause and Stop are intentionally not connected to gameplay.
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)

    def _update_source_button(self, *_):
        item = self.source_list.currentItem()
        self.reference_button.setEnabled(
            item is not None and self._is_safe_reference(item.data(Qt.UserRole))
        )

    @staticmethod
    def _is_safe_reference(value):
        if not isinstance(value, str):
            return False
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and not any(char.isspace() for char in value))

    def _open_reference(self):
        item = self.source_list.currentItem()
        if item is not None:
            url = item.data(Qt.UserRole)
            if self._is_safe_reference(url):
                QDesktopServices.openUrl(QUrl(url))
