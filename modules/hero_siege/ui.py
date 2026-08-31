"""
modules/hero_siege/ui.py

Hero Siege module screen. Roll a class -> a skill, or (wildcard) a
tag-matched relic instead. Includes buttons to open the in-app data
editors and to open the config folder directly in the OS file browser.
"""

import os
import platform
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QFrame, QMessageBox,
)
from PySide6.QtCore import Qt

from modules.hero_siege.roller import (
    load_classes, save_classes, load_relics, save_relics,
    load_settings, save_settings, roll,
)
from ui.last_roll import load_last_roll, save_last_roll
from modules.hero_siege.editor import open_classes_editor, open_relics_editor
from ui.version_badge import VersionBadge

# ── Palette (distinct from FO4 -- own identity per the plan) ────────────
BG        = "#150c08"
BG_PANEL  = "#2b1a10"
ORANGE     = "#ff8c3a"
ORANGE_DIM = "#8a4a1f"
WHITE      = "#f0ddc8"
AMBER      = "#ffb347"

FONT_FAMILY = "Segoe UI"


def _checkbox_qss(text_color: str) -> str:
    return f"""
        QCheckBox {{ color: {text_color}; font-family: '{FONT_FAMILY}'; font-size: 11px; }}
        QCheckBox::indicator {{
            width: 14px; height: 14px;
            border: 1px solid {ORANGE}; border-radius: 2px;
            background: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {ORANGE}; border: 1px solid {ORANGE};
        }}
    """


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {ORANGE_DIM}; max-height: 1px; border: none;")
    return line


def _tool_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {ORANGE}; background-color: {BG};
            border: 1px solid {ORANGE}; padding: 6px 12px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        }}
        QPushButton:hover {{ background-color: {ORANGE_DIM}; color: white; }}
    """)
    return btn


def _action_button(text: str, color: str, compact: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    padding = "4px 8px" if compact else "8px 22px"
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {color}; background-color: {BG};
            border: 1px solid {color}; padding: {padding};
            font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {ORANGE_DIM}; color: white; }}
    """)
    return btn


class HeroSiegeWidget(QWidget):
    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {BG};")

        self.classes = load_classes(self.config_dir / "classes.yaml")
        self.relics = load_relics(self.config_dir / "relics.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")

        self.last_result = None

        self._build_ui()
        self._restore_last_roll()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(16)

        title = QLabel("HERO SIEGE — BUILD ROLLER")
        title.setStyleSheet(f"color: {WHITE}; font-family: '{FONT_FAMILY}'; font-size: 26px; font-weight: bold;")
        root.addWidget(title)

        self.version_badge = VersionBadge(self.config_dir, ORANGE_DIM, ORANGE_DIM, BG, FONT_FAMILY)
        root.addWidget(self.version_badge)

        # Options row
        opts = QHBoxLayout()
        opts.setSpacing(14)

        self.wildcard_cb = QCheckBox("Enable Relic Wildcard")
        self.wildcard_cb.setChecked(self.settings.get("wildcard_enabled", True))
        self.wildcard_cb.setStyleSheet(_checkbox_qss(WHITE))
        self.wildcard_cb.toggled.connect(self._persist_settings)
        opts.addWidget(self.wildcard_cb)

        chance_label = QLabel("Chance:")
        chance_label.setStyleSheet(f"color: {WHITE}; font-family: '{FONT_FAMILY}'; font-size: 12px;")
        opts.addWidget(chance_label)

        self.wildcard_chance_pct = round(self.settings.get("wildcard_chance", 0.12) * 100)

        chance_minus = _action_button("−", ORANGE, compact=True)
        chance_minus.setFixedWidth(30)
        chance_minus.clicked.connect(self._dec_chance)
        opts.addWidget(chance_minus)

        self.chance_value_lbl = QLabel(f"{self.wildcard_chance_pct}%")
        self.chance_value_lbl.setFixedWidth(40)
        self.chance_value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chance_value_lbl.setStyleSheet(f"color: {ORANGE}; font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;")
        opts.addWidget(self.chance_value_lbl)

        chance_plus = _action_button("+", ORANGE, compact=True)
        chance_plus.setFixedWidth(30)
        chance_plus.clicked.connect(self._inc_chance)
        opts.addWidget(chance_plus)


        opts.addStretch(1)

        manage_classes_btn = _tool_button("Manage Classes")
        manage_classes_btn.clicked.connect(self._manage_classes)
        opts.addWidget(manage_classes_btn)

        manage_relics_btn = _tool_button("Manage Relics")
        manage_relics_btn.clicked.connect(self._manage_relics)
        opts.addWidget(manage_relics_btn)

        open_folder_btn = _tool_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        opts.addWidget(open_folder_btn)

        root.addLayout(opts)
        root.addWidget(_divider())

        # Output panel
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {BG_PANEL}; border-radius: 6px;")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(26, 26, 26, 26)
        panel_layout.setSpacing(10)

        self.class_lbl = QLabel("—")
        self.class_lbl.setStyleSheet(f"color: {WHITE}; font-family: '{FONT_FAMILY}'; font-size: 24px; font-weight: bold;")
        panel_layout.addWidget(self.class_lbl)

        self.mode_lbl = QLabel("")
        self.mode_lbl.setStyleSheet(f"color: {ORANGE}; font-family: '{FONT_FAMILY}'; font-size: 12px; font-weight: bold;")
        panel_layout.addWidget(self.mode_lbl)

        self.result_lbl = QLabel("Roll to get started")
        self.result_lbl.setStyleSheet(f"color: {WHITE}; font-family: '{FONT_FAMILY}'; font-size: 19px;")
        panel_layout.addWidget(self.result_lbl)

        self.exclude_btn = _action_button("Exclude This Skill", ORANGE_DIM, compact=True)
        self.exclude_btn.setEnabled(False)
        self.exclude_btn.clicked.connect(self._exclude_current_skill)
        panel_layout.addWidget(self.exclude_btn)

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setStyleSheet(f"color: {AMBER}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        panel_layout.addWidget(self.warning_lbl)

        self.debug_lbl = QLabel("")
        self.debug_lbl.setWordWrap(True)
        self.debug_lbl.setStyleSheet(f"color: {ORANGE_DIM}; font-family: '{FONT_FAMILY}'; font-size: 10px;")
        panel_layout.addWidget(self.debug_lbl)

        panel_layout.addStretch(1)
        root.addWidget(panel, stretch=1)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)

        self.lock_class_cb = QCheckBox("Lock Class")
        self.lock_class_cb.setStyleSheet(_checkbox_qss(ORANGE_DIM))
        footer.addWidget(self.lock_class_cb)

        self.ignore_exclusions_cb = QCheckBox("Ignore Exclusions")
        self.ignore_exclusions_cb.setChecked(self.settings.get("ignore_exclusions", False))
        self.ignore_exclusions_cb.setStyleSheet(_checkbox_qss(ORANGE_DIM))
        self.ignore_exclusions_cb.toggled.connect(self._persist_settings)
        footer.addWidget(self.ignore_exclusions_cb)

        footer.addStretch(1)

        clear_btn = _action_button("Clear", ORANGE_DIM)
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)

        roll_btn = _action_button("ROLL", ORANGE)
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

        root.addLayout(footer)

    # ── Actions ──────────────────────────────────────────────────────

    def _restore_last_roll(self):
        """Called once after the UI is built. Reuses _update_display --
        a restored result should look exactly like a freshly rolled one,
        no separate rendering path to keep in sync."""
        if not self.settings.get("remember_last_roll", True):
            return
        saved = load_last_roll(self.config_dir / "last_roll.yaml")
        if not saved:
            return
        self.last_result = saved
        self._update_display(saved)

    def _save_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        save_last_roll(self.config_dir / "last_roll.yaml", self.last_result)

    def _do_roll(self):
        wildcard_enabled = self.wildcard_cb.isChecked()
        wildcard_chance = self.wildcard_chance_pct / 100.0

        classes = self.classes
        if self.lock_class_cb.isChecked() and self.last_result and "class" in self.last_result:
            locked_name = self.last_result["class"]
            classes = [c for c in self.classes if c["name"] == locked_name] or self.classes

        result = roll(classes, self.relics, wildcard_enabled, wildcard_chance, self.ignore_exclusions_cb.isChecked())
        self.last_result = result
        self._update_display(result)
        self._save_last_roll()

    def _update_display(self, result: dict):
        if "error" in result:
            self.class_lbl.setText("—")
            self.mode_lbl.setText("")
            self.result_lbl.setText(result["error"])
            self.warning_lbl.setText("")
            self.debug_lbl.setText("")
            self.exclude_btn.setEnabled(False)
            return

        self.class_lbl.setText(result["class"])
        self.mode_lbl.setText("⚡ RELIC WILDCARD" if result["mode"] == "relic" else "SKILL")
        self.result_lbl.setText(result["result"] or "(none available)")
        self.warning_lbl.setText(result.get("warning") or "")

        skipped = result.get("skipped_classes") or []
        self.debug_lbl.setText(
            f"Skipped (no relic tag match): {', '.join(skipped)}" if skipped else ""
        )

        # Only meaningful for an actual skill result -- relic rolls and
        # empty results have nothing here to exclude.
        self.exclude_btn.setText("Exclude This Skill")
        self.exclude_btn.setEnabled(result["mode"] == "skill" and bool(result["result"]))

    def _clear(self):
        self.last_result = None
        self.lock_class_cb.setChecked(False)
        self.class_lbl.setText("—")
        self.mode_lbl.setText("")
        self.result_lbl.setText("Roll to get started")
        self.warning_lbl.setText("")
        self.debug_lbl.setText("")
        self.exclude_btn.setText("Exclude This Skill")
        self.exclude_btn.setEnabled(False)
        save_last_roll(self.config_dir / "last_roll.yaml", None)

    def _manage_classes(self):
        result = open_classes_editor(self, self.classes)
        if result is not None:
            self.classes = result
            save_classes(self.config_dir / "classes.yaml", self.classes)

    def _exclude_current_skill(self):
        """Flips excluded=true on the exact skill just rolled, within the
        exact class it came from (not a global name search -- skill names
        aren't guaranteed unique across classes, only within one). Saves
        immediately, same as any other edit made through the editors.
        Confirms first -- this is a single click with permanent effect and
        no review step, unlike toggling a checkbox in the editor (which
        already has Save as its natural confirmation)."""
        if not self.last_result or self.last_result.get("mode") != "skill":
            return
        class_name = self.last_result.get("class")
        skill_name = self.last_result.get("result")
        if not class_name or not skill_name:
            return

        reply = QMessageBox.question(
            self,
            "Exclude Skill",
            f'Exclude "{skill_name}" ({class_name})?\n\n'
            f"This removes it from every future roll until you manually "
            f"re-include it via Manage Classes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for c in self.classes:
            if c.get("name") != class_name:
                continue
            for s in c.get("skills", []):
                if s.get("name") == skill_name:
                    s["excluded"] = True
                    break
            break

        save_classes(self.config_dir / "classes.yaml", self.classes)
        self.exclude_btn.setText("Excluded ✓")
        self.exclude_btn.setEnabled(False)

    def _manage_relics(self):
        result = open_relics_editor(self, self.relics)
        if result is not None:
            self.relics = result
            save_relics(self.config_dir / "relics.yaml", self.relics)

    def _inc_chance(self):
        if self.wildcard_chance_pct < 100:
            self.wildcard_chance_pct += 1
            self.chance_value_lbl.setText(f"{self.wildcard_chance_pct}%")
            self._persist_settings()

    def _dec_chance(self):
        if self.wildcard_chance_pct > 0:
            self.wildcard_chance_pct -= 1
            self.chance_value_lbl.setText(f"{self.wildcard_chance_pct}%")
            self._persist_settings()

    def _persist_settings(self, *_args):
        self.settings = {
            "wildcard_enabled": self.wildcard_cb.isChecked(),
            "wildcard_chance": self.wildcard_chance_pct / 100.0,
            "ignore_exclusions": self.ignore_exclusions_cb.isChecked(),
            "remember_last_roll": self.settings.get("remember_last_roll", True),
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