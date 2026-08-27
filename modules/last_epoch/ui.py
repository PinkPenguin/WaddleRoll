"""
modules/last_epoch/ui.py

Last Epoch module screen. Rolls: Class -> main Skill (evenly from the
class's curated list) -> optional Notable (a node tagged notable from that
specific skill's own node list, on by default).

Distinct visual identity per your request: purple/pink + bronze palette
(matches the game's own UI), a serif font instead of the sans-serif used
by Hero Siege/Grim Dawn, and bordered/rounded panels rather than flat
rectangles -- without going overboard on structural differences yet.
"""

import os
import platform
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame,
)
from PySide6.QtCore import Qt

from modules.last_epoch.roller import load_classes, save_classes, load_settings, save_settings, roll
from modules.last_epoch.editor import open_classes_editor
from ui.version_badge import VersionBadge

# ── Palette: purple/pink + bronze, matching the game's own UI ───────────
BG        = "#160b1a"
BG_PANEL  = "#241030"
PINK      = "#e0679a"
PINK_DIM  = "#7a3a58"
BRONZE    = "#c08a4e"
BRONZE_DARK = "#7a5230"
TEXT      = "#e8d9e8"
WARN      = "#d99a4e"

FONT_FAMILY = "Georgia"


def _checkbox_qss(text_color: str) -> str:
    return f"""
        QCheckBox {{ color: {text_color}; font-family: '{FONT_FAMILY}'; font-size: 11px; }}
        QCheckBox::indicator {{
            width: 14px; height: 14px;
            border: 1px solid {PINK}; border-radius: 2px;
            background: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {PINK}; border: 1px solid {PINK};
        }}
    """


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {BRONZE}; max-height: 1px; border: none;")
    return line


def _tool_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {BRONZE}; background-color: {BG};
            border: 1px solid {BRONZE}; border-radius: 3px; padding: 6px 12px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        }}
        QPushButton:hover {{ background-color: {PINK_DIM}; color: {TEXT}; }}
    """)
    return btn


def _action_button(text: str, color: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {color}; background-color: {BG};
            border: 2px solid {color}; border-radius: 4px; padding: 8px 24px;
            font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {PINK_DIM}; color: {TEXT}; }}
    """)
    return btn


class LastEpochWidget(QWidget):
    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {BG};")

        self.classes = load_classes(self.config_dir / "classes.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")
        self.last_result = None

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(16)

        title = QLabel("LAST EPOCH — BUILD ROLLER")
        title.setStyleSheet(f"color: {PINK}; font-family: '{FONT_FAMILY}'; font-size: 25px; font-weight: bold; letter-spacing: 2px;")
        root.addWidget(title)

        self.version_badge = VersionBadge(self.config_dir, BRONZE, BRONZE, BG, FONT_FAMILY)
        root.addWidget(self.version_badge)

        # Tool row
        tools = QHBoxLayout()
        tools.setSpacing(14)

        self.notable_cb = QCheckBox("Roll Notable")
        self.notable_cb.setChecked(self.settings.get("notables_enabled", True))
        self.notable_cb.setStyleSheet(_checkbox_qss(TEXT))
        self.notable_cb.toggled.connect(self._persist_settings)
        tools.addWidget(self.notable_cb)

        tools.addStretch(1)

        manage_btn = _tool_button("Manage Classes")
        manage_btn.clicked.connect(self._manage_classes)
        tools.addWidget(manage_btn)

        open_folder_btn = _tool_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        tools.addWidget(open_folder_btn)

        root.addLayout(tools)
        root.addWidget(_divider())

        # Output panel -- bordered/rounded, distinct from the flat panels
        # used elsewhere
        panel = QFrame()
        panel.setStyleSheet(f"""
            background-color: {BG_PANEL};
            border: 1px solid {BRONZE_DARK};
            border-radius: 10px;
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(28, 26, 28, 26)
        panel_layout.setSpacing(18)

        self.class_lbl = self._result_row(panel_layout, "CLASS")
        self.skill_lbl = self._result_row(panel_layout, "MAIN SKILL")
        self.notable_lbl = self._result_row(panel_layout, "NOTABLE")

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
        lock_label.setStyleSheet(f"color: {PINK_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        locks.addWidget(lock_label)

        self.lock_class = QCheckBox("Class")
        self.lock_skill = QCheckBox("Skill")
        self.lock_notable = QCheckBox("Notable")
        for cb in (self.lock_class, self.lock_skill, self.lock_notable):
            cb.setStyleSheet(_checkbox_qss(PINK_DIM))
            locks.addWidget(cb)
        locks.addStretch(1)
        root.addLayout(locks)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)
        footer.addStretch(1)

        clear_btn = _action_button("Clear", PINK_DIM)
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)

        roll_btn = _action_button("ROLL", PINK)
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

        root.addLayout(footer)

    def _result_row(self, parent_layout, label_text: str) -> QLabel:
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {BRONZE}; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        parent_layout.addWidget(label)

        value = QLabel("—")
        value.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 20px; font-weight: bold;")
        parent_layout.addWidget(value)
        return value

    # ── Actions ──────────────────────────────────────────────────────

    def _do_roll(self):
        locked_class = self.last_result.get("class") if (self.lock_class.isChecked() and self.last_result) else None
        locked_skill = self.last_result.get("skill") if (self.lock_skill.isChecked() and self.last_result) else None
        locked_notable = self.last_result.get("notable") if (self.lock_notable.isChecked() and self.last_result) else None

        result = roll(
            self.classes,
            include_notable=self.notable_cb.isChecked(),
            locked_class=locked_class,
            locked_skill=locked_skill,
            locked_notable=locked_notable,
        )
        self.last_result = result
        self._update_display(result)

    def _update_display(self, result: dict):
        if "error" in result:
            self.class_lbl.setText("—")
            self.skill_lbl.setText("—")
            self.notable_lbl.setText("—")
            self.warning_lbl.setText(result["error"])
            return

        self.class_lbl.setText(result["class"])
        self.skill_lbl.setText(result["skill"] or "(none available)")
        self.notable_lbl.setText(result["notable"] or "—")
        self.warning_lbl.setText(result.get("warning") or "")

    def _clear(self):
        self.last_result = None
        self.lock_class.setChecked(False)
        self.lock_skill.setChecked(False)
        self.lock_notable.setChecked(False)
        self.class_lbl.setText("—")
        self.skill_lbl.setText("—")
        self.notable_lbl.setText("—")
        self.warning_lbl.setText("")

    def _manage_classes(self):
        result = open_classes_editor(self, self.classes)
        if result is not None:
            self.classes = result
            save_classes(self.config_dir / "classes.yaml", self.classes)

    def _persist_settings(self, *_args):
        self.settings = {"notables_enabled": self.notable_cb.isChecked()}
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