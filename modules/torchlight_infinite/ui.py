"""
modules/torchlight_infinite/ui.py

Torchlight Infinite module screen. Rolls a skill by default; an
optional (off by default) hero-trait roll sits alongside it, fully
independent of the skill roll.

Skills carry tags ("Spell"/"Attack" matter for damage; others don't,
for now). No tag-based filter UI here on purpose -- whether a skill
deals damage is handled by marking non-damage skills excluded=true
directly, not a second filter dimension (see CONVENTIONS.md). Tags
are still captured in the editor since a future hero-trait-scaling
match will need them.

Heroes (12 base) each have 2-3 traits. The roll flattens every
non-excluded trait across every non-excluded hero into one pool --
hero grouping is purely an editing convenience, not a two-step roll.

A one-click "Exclude This Skill" button on the result mirrors Hero
Siege's exactly (confirm dialog, defaults to No), since the person
doesn't know this game well enough yet to curate exclusions up front.

No wiki link yet -- flagged as a possible future add, not built now.

Distinct visual identity: electric cyan/teal against a deep indigo
background -- no other module uses this hue family. Verdana, not used
elsewhere. Sharp-edged (2px radius) bordered panel, distinct from the
flat 6px-radius panels most other modules use and from Last Epoch's
10px rounded one.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame,
    QMessageBox,
)
from PySide6.QtCore import Qt

from modules.torchlight_infinite.roller import (
    load_skills, save_skills, load_heroes, save_heroes,
    load_settings, save_settings, roll_skill, roll_hero_trait,
)
from modules.torchlight_infinite.editor import open_skills_editor, open_heroes_editor
from ui.version_badge import VersionBadge
from ui.config_folder import open_config_folder
from ui.last_roll import load_last_roll, save_last_roll

# ── Palette: electric cyan/teal against deep indigo -- new hue family ───
BG         = "#0a0e18"
BG_PANEL   = "#121a2a"
ACCENT     = "#2ee6d6"
ACCENT_DIM = "#1a6b68"
TEXT       = "#dceef0"
WARN       = "#e8a34e"

FONT_FAMILY = "Verdana"


def _checkbox_qss(text_color: str) -> str:
    return f"""
        QCheckBox {{ color: {text_color}; font-family: '{FONT_FAMILY}'; font-size: 11px; }}
        QCheckBox::indicator {{
            width: 14px; height: 14px;
            border: 1px solid {ACCENT}; border-radius: 2px;
            background: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {ACCENT}; border: 1px solid {ACCENT};
        }}
    """


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {ACCENT_DIM}; max-height: 1px; border: none;")
    return line


def _tool_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {ACCENT}; background-color: {BG};
            border: 1px solid {ACCENT}; padding: 6px 12px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        }}
        QPushButton:hover {{ background-color: {ACCENT_DIM}; color: {TEXT}; }}
    """)
    return btn


def _action_button(text: str, color: str, compact: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    padding = "4px 10px" if compact else "8px 22px"
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {color}; background-color: {BG};
            border: 1px solid {color}; padding: {padding};
            font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {ACCENT_DIM}; color: {TEXT}; }}
    """)
    return btn


class TorchlightInfiniteWidget(QWidget):
    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {BG};")

        self.skills = load_skills(self.config_dir / "skills.yaml")
        self.heroes = load_heroes(self.config_dir / "heroes.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")

        self.last_skill_result = None
        self.last_hero_trait_result = None

        self._build_ui()
        self._restore_last_roll()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(16)

        title = QLabel("TORCHLIGHT INFINITE — SKILL ROLLER")
        title.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 22px; font-weight: bold;")
        root.addWidget(title)

        self.version_badge = VersionBadge(self.config_dir, ACCENT_DIM, ACCENT_DIM, BG, FONT_FAMILY)
        root.addWidget(self.version_badge)

        # Tool row
        tools = QHBoxLayout()
        tools.setSpacing(14)

        self.hero_trait_roll_cb = QCheckBox("Also Roll Hero Trait")
        self.hero_trait_roll_cb.setChecked(self.settings.get("hero_trait_roll_enabled", False))
        self.hero_trait_roll_cb.setStyleSheet(_checkbox_qss(TEXT))
        self.hero_trait_roll_cb.toggled.connect(self._persist_settings)
        self.hero_trait_roll_cb.toggled.connect(self._update_hero_trait_visibility)
        tools.addWidget(self.hero_trait_roll_cb)

        tools.addStretch(1)

        manage_skills_btn = _tool_button("Manage Skills")
        manage_skills_btn.clicked.connect(self._manage_skills)
        tools.addWidget(manage_skills_btn)

        manage_heroes_btn = _tool_button("Manage Heroes")
        manage_heroes_btn.clicked.connect(self._manage_heroes)
        tools.addWidget(manage_heroes_btn)

        open_folder_btn = _tool_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        tools.addWidget(open_folder_btn)

        root.addLayout(tools)
        root.addWidget(_divider())

        # Output panel -- sharp-edged, bordered, distinct panel shape
        panel = QFrame()
        panel.setStyleSheet(f"""
            background-color: {BG_PANEL};
            border: 1px solid {ACCENT};
            border-radius: 2px;
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(26, 24, 26, 24)
        panel_layout.setSpacing(14)

        skill_label = QLabel("SKILL")
        skill_label.setStyleSheet(f"color: {ACCENT}; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        panel_layout.addWidget(skill_label)

        self.skill_lbl = QLabel("—")
        self.skill_lbl.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 22px; font-weight: bold;")
        panel_layout.addWidget(self.skill_lbl)

        self.exclude_btn = _action_button("Exclude This Skill", ACCENT_DIM, compact=True)
        self.exclude_btn.setEnabled(False)
        self.exclude_btn.clicked.connect(self._exclude_current_skill)
        panel_layout.addWidget(self.exclude_btn)

        panel_layout.addWidget(_divider())

        self.hero_caption = QLabel("HERO")
        self.hero_caption.setStyleSheet(f"color: {ACCENT}; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        panel_layout.addWidget(self.hero_caption)

        self.hero_lbl = QLabel("—")
        self.hero_lbl.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 22px; font-weight: bold;")
        panel_layout.addWidget(self.hero_lbl)

        self.trait_caption = QLabel("TRAIT")
        self.trait_caption.setStyleSheet(f"color: {ACCENT}; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        panel_layout.addWidget(self.trait_caption)

        self.trait_lbl = QLabel("—")
        self.trait_lbl.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 22px; font-weight: bold;")
        panel_layout.addWidget(self.trait_lbl)

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
        lock_label.setStyleSheet(f"color: {ACCENT_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        locks.addWidget(lock_label)

        self.lock_skill = QCheckBox("Skill")
        self.lock_hero_trait = QCheckBox("Hero Trait")
        for cb in (self.lock_skill, self.lock_hero_trait):
            cb.setStyleSheet(_checkbox_qss(ACCENT_DIM))
            locks.addWidget(cb)
        locks.addStretch(1)
        root.addLayout(locks)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)
        footer.addStretch(1)

        clear_btn = _action_button("Clear", ACCENT_DIM)
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)

        roll_btn = _action_button("ROLL", ACCENT)
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

        root.addLayout(footer)

        self._update_hero_trait_visibility()

    def _update_hero_trait_visibility(self):
        """setEnabled, not setVisible -- same Qt pre-first-paint timing
        quirk every other module works around the same way."""
        enabled = self.hero_trait_roll_cb.isChecked()
        self.hero_caption.setEnabled(enabled)
        self.hero_lbl.setEnabled(enabled)
        self.trait_caption.setEnabled(enabled)
        self.trait_lbl.setEnabled(enabled)
        self.lock_hero_trait.setEnabled(enabled)

    # ── Actions ──────────────────────────────────────────────────────

    def _restore_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        saved = load_last_roll(self.config_dir / "last_roll.yaml")
        if not saved:
            return

        skill_result = saved.get("skill_result")
        if skill_result and skill_result.get("skill"):
            self.last_skill_result = skill_result
            self.skill_lbl.setText(skill_result["skill"])
            self.exclude_btn.setEnabled(True)
            self.warning_lbl.setText(skill_result.get("warning") or "")

        hero_trait_result = saved.get("hero_trait_result")
        if hero_trait_result and hero_trait_result.get("trait"):
            self.last_hero_trait_result = hero_trait_result
            self.hero_lbl.setText(hero_trait_result["hero"])
            self.trait_lbl.setText(hero_trait_result["trait"])

    def _save_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        data = {
            "skill_result": self.last_skill_result,
            "hero_trait_result": self.last_hero_trait_result,
        }
        save_last_roll(self.config_dir / "last_roll.yaml", data)

    def _do_roll(self):
        locked_skill = self.last_skill_result.get("skill") if (self.lock_skill.isChecked() and self.last_skill_result) else None
        skill_result = roll_skill(self.skills, locked_skill=locked_skill)
        self.last_skill_result = skill_result

        if skill_result["skill"] is None:
            self.skill_lbl.setText("—")
            self.warning_lbl.setText(skill_result.get("warning") or "")
            self.exclude_btn.setEnabled(False)
        else:
            self.skill_lbl.setText(skill_result["skill"])
            self.warning_lbl.setText("")
            self.exclude_btn.setText("Exclude This Skill")
            self.exclude_btn.setEnabled(True)

        if self.hero_trait_roll_cb.isChecked():
            locked_hero = self.last_hero_trait_result.get("hero") if (self.lock_hero_trait.isChecked() and self.last_hero_trait_result) else None
            locked_trait = self.last_hero_trait_result.get("trait") if (self.lock_hero_trait.isChecked() and self.last_hero_trait_result) else None
            hero_trait_result = roll_hero_trait(self.heroes, locked_hero=locked_hero, locked_trait=locked_trait)
            self.last_hero_trait_result = hero_trait_result
            if hero_trait_result.get("trait"):
                self.hero_lbl.setText(hero_trait_result["hero"])
                self.trait_lbl.setText(hero_trait_result["trait"])
            else:
                self.hero_lbl.setText("—")
                self.trait_lbl.setText("—")
            if hero_trait_result.get("warning"):
                self.warning_lbl.setText(hero_trait_result["warning"])

        self._save_last_roll()

    def _exclude_current_skill(self):
        """Mirrors Hero Siege's one-click exclude: confirms first, since
        this is a single click with permanent effect and no review step
        (unlike toggling a checkbox in the editor, which already
        confirms via Save). Defaults to No."""
        if not self.last_skill_result or not self.last_skill_result.get("skill"):
            return
        skill_name = self.last_skill_result["skill"]

        reply = QMessageBox.question(
            self,
            "Exclude Skill",
            f'Exclude "{skill_name}"?\n\n'
            f"This removes it from every future roll until you manually "
            f"re-include it via Manage Skills.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for s in self.skills:
            if s.get("name") == skill_name:
                s["excluded"] = True
                break

        save_skills(self.config_dir / "skills.yaml", self.skills)
        self.exclude_btn.setText("Excluded ✓")
        self.exclude_btn.setEnabled(False)

    def _clear(self):
        self.last_skill_result = None
        self.last_hero_trait_result = None
        self.lock_skill.setChecked(False)
        self.lock_hero_trait.setChecked(False)
        self.skill_lbl.setText("—")
        self.hero_lbl.setText("—")
        self.trait_lbl.setText("—")
        self.warning_lbl.setText("")
        self.exclude_btn.setText("Exclude This Skill")
        self.exclude_btn.setEnabled(False)
        save_last_roll(self.config_dir / "last_roll.yaml", None)

    def _manage_skills(self):
        result = open_skills_editor(self, self.skills)
        if result is not None:
            self.skills = result
            save_skills(self.config_dir / "skills.yaml", self.skills)

    def _manage_heroes(self):
        result = open_heroes_editor(self, self.heroes)
        if result is not None:
            self.heroes = result
            save_heroes(self.config_dir / "heroes.yaml", self.heroes)

    def _persist_settings(self, *_args):
        self.settings = {
            "hero_trait_roll_enabled": self.hero_trait_roll_cb.isChecked(),
            "remember_last_roll": self.settings.get("remember_last_roll", True),
        }
        save_settings(self.config_dir / "settings.yaml", self.settings)

    def _open_config_folder(self):
        open_config_folder(self.config_dir)