"""
modules/grim_dawn/ui.py

Grim Dawn module screen. Rolls: Mastery A -> main skill (from A's curated
list) -> Mastery B (secondary/support, no skill rolled for it). Each of
the three results can be locked independently across re-rolls.

Palette is intentionally desaturated/muted rather than neon, per feedback
on Hero Siege's first pass -- worth carrying into future modules too.
"""

import os
import platform
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame,
)
from PySide6.QtCore import Qt

from modules.grim_dawn.roller import load_masteries, save_masteries, roll
from modules.grim_dawn.editor import open_masteries_editor
from ui.version_badge import VersionBadge
# ── Palette: muted iron/bronze, not neon ─────────────────────────────────
BG        = "#14150f"
BG_PANEL  = "#1e2018"
GOLD      = "#a68a4c"
GOLD_DIM  = "#5c4d2a"
TEXT      = "#c7bfa4"
WARN      = "#c98a3a"

FONT_FAMILY = "Segoe UI"


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
            border: 1px solid {color}; padding: 8px 22px;
            font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {GOLD_DIM}; color: {TEXT}; }}
    """)
    return btn


class GrimDawnWidget(QWidget):
    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {BG};")

        self.masteries = load_masteries(self.config_dir / "masteries.yaml")
        self.last_result = None

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(16)

        title = QLabel("GRIM DAWN — DUAL MASTERY ROLLER")
        title.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 24px; font-weight: bold;")
        root.addWidget(title)

        self.version_badge = VersionBadge(self.config_dir, GOLD_DIM, GOLD_DIM, BG, FONT_FAMILY)
        root.addWidget(self.version_badge)

        # Tool row
        tools = QHBoxLayout()
        tools.setSpacing(14)
        tools.addStretch(1)

        manage_btn = _tool_button("Manage Masteries")
        manage_btn.clicked.connect(self._manage_masteries)
        tools.addWidget(manage_btn)

        open_folder_btn = _tool_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        tools.addWidget(open_folder_btn)

        root.addLayout(tools)
        root.addWidget(_divider())

        # Output panel: 3 result rows
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {BG_PANEL}; border-radius: 6px;")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(26, 24, 26, 24)
        panel_layout.setSpacing(18)

        self.mastery_a_lbl = self._result_row(panel_layout, "MASTERY A")
        self.skill_lbl = self._result_row(panel_layout, "MAIN SKILL")
        self.mastery_b_lbl = self._result_row(panel_layout, "MASTERY B (support)")

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setStyleSheet(f"color: {WARN}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        panel_layout.addWidget(self.warning_lbl)

        panel_layout.addStretch(1)
        root.addWidget(panel, stretch=1)

        # Lock row
        locks = QHBoxLayout()
        locks.setSpacing(16)
        lock_label = QLabel("LOCK:")
        lock_label.setStyleSheet(f"color: {GOLD_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        locks.addWidget(lock_label)

        self.lock_mastery_a = QCheckBox("Mastery A")
        self.lock_skill = QCheckBox("Skill")
        self.lock_mastery_b = QCheckBox("Mastery B")
        for cb in (self.lock_mastery_a, self.lock_skill, self.lock_mastery_b):
            cb.setStyleSheet(_checkbox_qss(GOLD_DIM))
            locks.addWidget(cb)
        locks.addStretch(1)
        root.addLayout(locks)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)
        footer.addStretch(1)

        clear_btn = _action_button("Clear", GOLD_DIM)
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)

        roll_btn = _action_button("ROLL", GOLD)
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

        root.addLayout(footer)

    def _result_row(self, parent_layout, label_text: str) -> QLabel:
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {GOLD_DIM}; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 1px;")
        parent_layout.addWidget(label)

        value = QLabel("—")
        value.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 20px; font-weight: bold;")
        parent_layout.addWidget(value)
        return value

    # ── Actions ──────────────────────────────────────────────────────

    def _do_roll(self):
        locked_a = self.last_result.get("mastery_a") if (self.lock_mastery_a.isChecked() and self.last_result) else None
        locked_skill = self.last_result.get("skill") if (self.lock_skill.isChecked() and self.last_result) else None
        locked_b = self.last_result.get("mastery_b") if (self.lock_mastery_b.isChecked() and self.last_result) else None

        result = roll(self.masteries, locked_mastery_a=locked_a, locked_skill=locked_skill, locked_mastery_b=locked_b)
        self.last_result = result
        self._update_display(result)

    def _update_display(self, result: dict):
        if "error" in result:
            self.mastery_a_lbl.setText("—")
            self.skill_lbl.setText("—")
            self.mastery_b_lbl.setText("—")
            self.warning_lbl.setText(result["error"])
            return

        self.mastery_a_lbl.setText(result["mastery_a"])
        self.skill_lbl.setText(result["skill"] or "(none available)")
        self.mastery_b_lbl.setText(result["mastery_b"])
        self.warning_lbl.setText(result.get("warning") or "")

    def _clear(self):
        self.last_result = None
        self.lock_mastery_a.setChecked(False)
        self.lock_skill.setChecked(False)
        self.lock_mastery_b.setChecked(False)
        self.mastery_a_lbl.setText("—")
        self.skill_lbl.setText("—")
        self.mastery_b_lbl.setText("—")
        self.warning_lbl.setText("")

    def _manage_masteries(self):
        result = open_masteries_editor(self, self.masteries)
        if result is not None:
            self.masteries = result
            save_masteries(self.config_dir / "masteries.yaml", self.masteries)

    def _open_config_folder(self):
        path = str(self.config_dir)
        system = platform.system()
        if system == "Windows":
            os.startfile(path)  # noqa: S606 -- Windows-only call, deliberate
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])