"""
modules/poe2/ui.py

PoE2 module screen. Main skill roll uses the slot-machine spin reveal;
ascendancy roll (optional, off by default) is a simpler static result
since it's a secondary, less frequently used feature -- could get the
same spin treatment later if it turns out to be worth it.

Distinct palette/font from the other modules: deep crimson + gold,
Cambria serif.
"""

import os
import platform
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame,
)
from PySide6.QtCore import Qt

from modules.poe2.roller import (
    load_skills, save_skills, load_classes, save_classes,
    load_settings, save_settings, roll_skill, roll_ascendancy,
)
from modules.poe2.editor import open_skills_editor, open_classes_editor
from ui.slot_machine import SlotMachine
from ui.version_badge import VersionBadge

# ── Palette: deep crimson + gold ──────────────────────────────────────
BG        = "#0d0705"
BG_PANEL  = "#1a0f0c"
CRIMSON   = "#8a1f1f"
GOLD      = "#c9a227"
GOLD_DIM  = "#6e5818"
TEXT      = "#e8ddc7"
WARN      = "#d99a4e"

FONT_FAMILY = "Cambria"


def _checkbox_qss(text_color: str) -> str:
    return f"""
        QCheckBox {{ color: {text_color}; font-family: '{FONT_FAMILY}'; font-size: 11px; }}
        QCheckBox::indicator {{
            width: 14px; height: 14px;
            border: 1px solid {GOLD}; border-radius: 2px;
            background: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {GOLD}; border: 1px solid {GOLD};
        }}
    """


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {GOLD_DIM}; max-height: 1px; border: none;")
    return line


def _tool_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {GOLD}; background-color: {BG};
            border: 1px solid {GOLD}; padding: 6px 12px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        }}
        QPushButton:hover {{ background-color: {GOLD_DIM}; color: {TEXT}; }}
    """)
    return btn


def _action_button(text: str, color: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {color}; background-color: {BG};
            border: 2px solid {color}; border-radius: 3px; padding: 8px 24px;
            font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {GOLD_DIM}; color: {TEXT}; }}
    """)
    return btn


class PoE2Widget(QWidget):
    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {BG};")

        self.skills = load_skills(self.config_dir / "skills.yaml")
        self.classes = load_classes(self.config_dir / "classes.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")

        self.last_skill_result = None
        self.last_ascendancy_result = None

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(14)

        title = QLabel("PATH OF EXILE 2 — SKILL ROLLER")
        title.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 23px; font-weight: bold; letter-spacing: 1px;")
        root.addWidget(title)

        self.version_badge = VersionBadge(self.config_dir, GOLD_DIM, GOLD_DIM, BG, FONT_FAMILY)
        root.addWidget(self.version_badge)

        # Tool row
        tools = QHBoxLayout()
        tools.setSpacing(10)
        tools.addStretch(1)
        manage_skills_btn = _tool_button("Manage Skills")
        manage_skills_btn.clicked.connect(self._manage_skills)
        tools.addWidget(manage_skills_btn)
        manage_classes_btn = _tool_button("Manage Classes")
        manage_classes_btn.clicked.connect(self._manage_classes)
        tools.addWidget(manage_classes_btn)
        open_folder_btn = _tool_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        tools.addWidget(open_folder_btn)
        root.addLayout(tools)

        root.addWidget(_divider())

        # Filter toggles
        filters = QHBoxLayout()
        filters.setSpacing(16)
        self.allow_vaal_cb = QCheckBox("Allow Vaal Skills")
        self.allow_item_cb = QCheckBox("Allow Item Skills")
        self.allow_ascendancy_skill_cb = QCheckBox("Allow Ascendancy Skills")
        self.allow_vaal_cb.setChecked(self.settings.get("allow_vaal_skills", True))
        self.allow_item_cb.setChecked(self.settings.get("allow_item_skills", True))
        self.allow_ascendancy_skill_cb.setChecked(self.settings.get("allow_ascendancy_skills", True))
        for cb in (self.allow_vaal_cb, self.allow_item_cb, self.allow_ascendancy_skill_cb):
            cb.setStyleSheet(_checkbox_qss(TEXT))
            cb.toggled.connect(self._persist_settings)
            filters.addWidget(cb)
        filters.addStretch(1)
        root.addLayout(filters)

        # Skill slot machine panel
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {BG_PANEL}; border: 1px solid {CRIMSON}; border-radius: 6px;")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 22, 20, 22)
        panel_layout.setSpacing(10)

        skill_label = QLabel("MAIN SKILL")
        skill_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skill_label.setStyleSheet(f"color: {GOLD}; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        panel_layout.addWidget(skill_label)

        self.slot_machine = SlotMachine(text_color=TEXT, dim_color=GOLD_DIM, font_family=FONT_FAMILY)
        panel_layout.addWidget(self.slot_machine)

        root.addWidget(panel)

        # Ascendancy toggle + result (optional, off by default)
        asc_row = QHBoxLayout()
        asc_row.setSpacing(14)
        self.ascendancy_roll_cb = QCheckBox("Also Roll Ascendancy")
        self.ascendancy_roll_cb.setChecked(self.settings.get("ascendancy_roll_enabled", False))
        self.ascendancy_roll_cb.setStyleSheet(_checkbox_qss(TEXT))
        self.ascendancy_roll_cb.toggled.connect(self._persist_settings)
        self.ascendancy_roll_cb.toggled.connect(self._update_ascendancy_visibility)
        asc_row.addWidget(self.ascendancy_roll_cb)
        asc_row.addStretch(1)
        root.addLayout(asc_row)

        self.ascendancy_result_lbl = QLabel("")
        self.ascendancy_result_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ascendancy_result_lbl.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 15px;")
        root.addWidget(self.ascendancy_result_lbl)

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_lbl.setStyleSheet(f"color: {WARN}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        root.addWidget(self.warning_lbl)

        root.addStretch(1)

        # Lock row
        locks = QHBoxLayout()
        locks.setSpacing(16)
        lock_label = QLabel("LOCK:")
        lock_label.setStyleSheet(f"color: {GOLD_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        locks.addWidget(lock_label)
        self.lock_skill = QCheckBox("Skill")
        self.lock_class = QCheckBox("Class")
        self.lock_ascendancy = QCheckBox("Ascendancy")
        for cb in (self.lock_skill, self.lock_class, self.lock_ascendancy):
            cb.setStyleSheet(_checkbox_qss(GOLD_DIM))
            locks.addWidget(cb)
        locks.addStretch(1)
        root.addLayout(locks)

        self._update_ascendancy_visibility()

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)
        footer.addStretch(1)
        clear_btn = _action_button("Clear", GOLD_DIM)
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)
        roll_btn = _action_button("ROLL", CRIMSON)
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)
        root.addLayout(footer)

    def _update_ascendancy_visibility(self):
        """Uses setEnabled rather than setVisible -- setVisible(False) called
        before the widget's top-level window has ever been shown doesn't
        reliably survive a later show() call (a real Qt quirk), whereas
        setEnabled is unaffected by that timing issue."""
        enabled = self.ascendancy_roll_cb.isChecked()
        self.ascendancy_result_lbl.setEnabled(enabled)
        self.lock_class.setEnabled(enabled)
        self.lock_ascendancy.setEnabled(enabled)

    # ── Actions ──────────────────────────────────────────────────────

    def _do_roll(self):
        locked_skill = self.last_skill_result.get("skill") if (self.lock_skill.isChecked() and self.last_skill_result) else None

        skill_result = roll_skill(
            self.skills,
            allow_vaal_skills=self.allow_vaal_cb.isChecked(),
            allow_item_skills=self.allow_item_cb.isChecked(),
            allow_ascendancy_skills=self.allow_ascendancy_skill_cb.isChecked(),
            locked_skill=locked_skill,
        )
        self.last_skill_result = skill_result

        if skill_result["skill"] is None:
            self.warning_lbl.setText(skill_result.get("warning") or "")
            self.slot_machine.set_static("—")
        else:
            self.warning_lbl.setText("")
            if locked_skill:
                self.slot_machine.set_static(skill_result["skill"])
            else:
                self.slot_machine.spin(skill_result["pool_names"], skill_result["skill"])

        if self.ascendancy_roll_cb.isChecked():
            locked_class = self.last_ascendancy_result.get("class") if (self.lock_class.isChecked() and self.last_ascendancy_result) else None
            locked_asc = self.last_ascendancy_result.get("ascendancy") if (self.lock_ascendancy.isChecked() and self.last_ascendancy_result) else None
            asc_result = roll_ascendancy(self.classes, locked_class=locked_class, locked_ascendancy=locked_asc)
            self.last_ascendancy_result = asc_result
            if "error" in asc_result:
                self.ascendancy_result_lbl.setText(asc_result["error"])
            else:
                asc_text = asc_result["class"]
                if asc_result.get("ascendancy"):
                    asc_text += f"  →  {asc_result['ascendancy']}"
                self.ascendancy_result_lbl.setText(asc_text)
                if asc_result.get("warning"):
                    self.warning_lbl.setText(asc_result["warning"])

    def _clear(self):
        self.last_skill_result = None
        self.last_ascendancy_result = None
        self.lock_skill.setChecked(False)
        self.lock_class.setChecked(False)
        self.lock_ascendancy.setChecked(False)
        self.slot_machine.set_static("—")
        self.ascendancy_result_lbl.setText("")
        self.warning_lbl.setText("")

    def _manage_skills(self):
        result = open_skills_editor(self, self.skills)
        if result is not None:
            self.skills = result
            save_skills(self.config_dir / "skills.yaml", self.skills)

    def _manage_classes(self):
        result = open_classes_editor(self, self.classes)
        if result is not None:
            self.classes = result
            save_classes(self.config_dir / "classes.yaml", self.classes)

    def _persist_settings(self, *_args):
        self.settings = {
            "allow_vaal_skills": self.allow_vaal_cb.isChecked(),
            "allow_item_skills": self.allow_item_cb.isChecked(),
            "allow_ascendancy_skills": self.allow_ascendancy_skill_cb.isChecked(),
            "ascendancy_roll_enabled": self.ascendancy_roll_cb.isChecked(),
        }
        save_settings(self.config_dir / "settings.yaml", self.settings)

    def _open_config_folder(self):
        path = str(self.config_dir)
        system = platform.system()
        if system == "Windows":
            os.startfile(path)  # noqa: S606 -- Windows-only call, deliberate
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])