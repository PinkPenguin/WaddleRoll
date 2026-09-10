"""
modules/hero_siege/ui.py

Hero Siege module screen. Roll a class -> a skill, or (wildcard) a
tag-matched relic instead. Includes buttons to open the in-app data
editors and to open the config folder directly in the OS file browser.

VISUAL DESIGN NOTE (first real design-process pass in this project, not
another palette swap): grounded in Hero Siege's actual subject matter --
a chaotic, gory, dark-carnival hack-and-slash where dying constantly is
part of the joke, not a restrained/prestige aesthetic. Checked against
the specific generic-AI-design tells this project had been repeating
all night, and deliberately dropped:
- "near-black bg + one bright accent" (every other module) -> two
  colors genuinely in tension instead (BLOOD + MUSTARD), like a
  jester's parti-color costume, not one brand color on flat dark.
- the "WORD — fragment" title pattern (every other module's title) ->
  just "HERO SIEGE" alone, treated as a poster headline.
- small all-caps eyebrow labels above content (every other module's
  "SKILL"/"HERO"/etc. captions) -> mode (skill vs relic wildcard) is
  now conveyed through color and an inline tag only when it's actually
  notable (wildcard), not a floating label every single time.
- the 4th flat-radius rounded QFrame panel -> TornPanel below, a real
  custom-painted jagged/torn shape (QPainter, not QSS), since QSS
  itself can't do irregular borders -- an honest example of a genuine
  Qt limitation that a bit more code gets past rather than settling for.

Impact for the one headline moment only (the title); Franklin Gothic
Medium for everything else -- both unused elsewhere in this project,
clearly distinct from each other per the design skill's own guidance
on using two typefaces.
"""

import random
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPolygonF, QPen, QColor

from modules.hero_siege.roller import (
    load_classes, save_classes, load_relics, save_relics,
    load_settings, save_settings, roll,
)
from ui.last_roll import load_last_roll, save_last_roll
from modules.hero_siege.editor import open_classes_editor, open_relics_editor
from ui.slot_machine import SlotMachine
from ui.version_badge import VersionBadge
from ui.config_folder import open_config_folder
from ui.background_widget import BackgroundWidget
from ui.assets import find_module_background

# ── Palette: two colors in real tension, not one accent on flat dark ────
INK      = "#100b0a"   # warm near-black -- ink/stage-shadow, not neutral gray
BG_PANEL = "#1c1310"
BLOOD    = "#8f1616"   # dried-blood red, not neon
MUSTARD  = "#c99a2e"   # sickly torch-gold
BONE     = "#d8cdb8"   # off-white, not pure white
ROT      = "#7a9c4e"   # small, sparing use -- wildcard/relic moments only

DISPLAY_FONT = "Impact"                  # one headline moment only -- the title
BODY_FONT    = "Franklin Gothic Medium"  # everything else


class TornPanel(QWidget):
    """A jagged, torn-edge panel instead of another rounded rectangle.
    QSS can't draw an irregular border, so this is real QPainter work --
    a fixed-seed pseudo-random zigzag per edge, stable across repaints
    (not re-randomized every frame, which would look glitchy)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(32, 30, 32, 28)
        self.layout.setSpacing(10)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        jag = 7
        steps = 12
        rng = random.Random(42)  # fixed seed -- stable shape, not flickering

        points = []
        for i in range(steps + 1):
            points.append((w * i / steps, rng.uniform(0, jag)))
        for i in range(1, steps + 1):
            points.append((w - rng.uniform(0, jag), h * i / steps))
        for i in range(1, steps + 1):
            points.append((w - (w * i / steps), h - rng.uniform(0, jag)))
        for i in range(1, steps + 1):
            points.append((rng.uniform(0, jag), h - (h * i / steps)))

        polygon = QPolygonF([QPointF(x, y) for x, y in points])
        painter.setBrush(QColor(BG_PANEL))
        painter.setPen(QPen(QColor(MUSTARD), 2))
        painter.drawPolygon(polygon)


def _checkbox_qss(text_color: str) -> str:
    return f"""
        QCheckBox {{ color: {text_color}; font-family: '{BODY_FONT}'; font-size: 11px; }}
        QCheckBox::indicator {{
            width: 14px; height: 14px;
            border: 1px solid {MUSTARD}; border-radius: 2px;
            background: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {MUSTARD}; border: 1px solid {MUSTARD};
        }}
    """


def _tool_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {MUSTARD}; background-color: transparent;
            border: none; padding: 6px 10px;
            font-family: '{BODY_FONT}'; font-size: 11px;
        }}
        QPushButton:hover {{ color: {BONE}; text-decoration: underline; }}
    """)
    return btn


def _flat_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {BLOOD}; background-color: transparent;
            border: none; padding: 4px 6px;
            font-family: '{BODY_FONT}'; font-size: 11px;
        }}
        QPushButton:hover {{ color: {MUSTARD}; text-decoration: underline; }}
        QPushButton:disabled {{ color: #4a3a30; }}
    """)
    return btn


def _stepper_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedWidth(28)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {MUSTARD}; background-color: {BG_PANEL};
            border: none; border-radius: 3px;
            font-family: '{BODY_FONT}'; font-size: 13px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {BLOOD}; color: {BONE}; }}
    """)
    return btn


def _primary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {BONE}; background-color: {BLOOD};
            border: none; padding: 9px 26px;
            font-family: '{BODY_FONT}'; font-size: 14px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {MUSTARD}; color: {INK}; }}
    """)
    return btn


class HeroSiegeWidget(QWidget):
    def __init__(self, config_dir: Path, assets_dir: Path = None, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {INK};")

        bg_path = find_module_background(assets_dir)
        self._background = BackgroundWidget(bg_path, parent=self)
        self._background.setGeometry(self.rect())
        self._background.lower()

        self.classes = load_classes(self.config_dir / "classes.yaml")
        self.relics = load_relics(self.config_dir / "relics.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")

        self.last_result = None

        self._build_ui()
        self._restore_last_roll()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._background.setGeometry(self.rect())

    def showEvent(self, event):
        # resizeEvent alone isn't reliable here -- Qt's resize() is a
        # no-op (fires NO event at all) if the target size happens to
        # already match the widget's current size, which can leave the
        # background stuck at whatever geometry existed at __init__
        # time (before this widget was ever placed in its real parent
        # layout). showEvent is guaranteed to fire whenever the widget
        # actually becomes visible, with its geometry already finalized
        # by then, so this catches the case resizeEvent can silently miss.
        super().showEvent(event)
        self._background.setGeometry(self.rect())

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(14)

        # Poster headline -- no "— fragment" subtitle, Impact carries
        # the personality on its own
        title = QLabel("HERO SIEGE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {BLOOD}; font-family: '{DISPLAY_FONT}'; font-size: 40px; letter-spacing: 1px;")
        root.addWidget(title)

        self.version_badge = VersionBadge(self.config_dir, MUSTARD, MUSTARD, INK, BODY_FONT)
        root.addWidget(self.version_badge)

        # Roll options row -- just the wildcard controls
        opts = QHBoxLayout()
        opts.setSpacing(14)

        self.wildcard_cb = QCheckBox("Enable Relic Wildcard")
        self.wildcard_cb.setChecked(self.settings.get("wildcard_enabled", True))
        self.wildcard_cb.setStyleSheet(_checkbox_qss(BONE))
        self.wildcard_cb.toggled.connect(self._persist_settings)
        opts.addWidget(self.wildcard_cb)

        chance_label = QLabel("Chance:")
        chance_label.setStyleSheet(f"color: {BONE}; font-family: '{BODY_FONT}'; font-size: 12px;")
        opts.addWidget(chance_label)

        self.wildcard_chance_pct = round(self.settings.get("wildcard_chance", 0.12) * 100)

        chance_minus = _stepper_btn("−")
        chance_minus.clicked.connect(self._dec_chance)
        opts.addWidget(chance_minus)

        self.chance_value_lbl = QLabel(f"{self.wildcard_chance_pct}%")
        self.chance_value_lbl.setFixedWidth(40)
        self.chance_value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chance_value_lbl.setStyleSheet(f"color: {MUSTARD}; font-family: '{BODY_FONT}'; font-size: 13px; font-weight: bold;")
        opts.addWidget(self.chance_value_lbl)

        chance_plus = _stepper_btn("+")
        chance_plus.clicked.connect(self._inc_chance)
        opts.addWidget(chance_plus)

        opts.addStretch(1)
        root.addLayout(opts)

        # Tool row -- own row, not forcing the window wide alongside roll options
        tools = QHBoxLayout()
        tools.setSpacing(10)
        tools.addStretch(1)

        manage_classes_btn = _tool_button("Manage Classes")
        manage_classes_btn.clicked.connect(self._manage_classes)
        tools.addWidget(manage_classes_btn)

        manage_relics_btn = _tool_button("Manage Relics")
        manage_relics_btn.clicked.connect(self._manage_relics)
        tools.addWidget(manage_relics_btn)

        open_folder_btn = _tool_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        tools.addWidget(open_folder_btn)

        root.addLayout(tools)

        # Output panel -- real torn/jagged shape, not another rounded QFrame
        panel = TornPanel()

        self.slot_machine = SlotMachine(text_color=BONE, dim_color=MUSTARD, font_family=BODY_FONT)
        self.slot_machine.finished.connect(self._on_class_landed)
        panel.layout.addWidget(self.slot_machine)

        # Mode + result merged into one line -- no floating all-caps
        # eyebrow caption. Wildcard gets a small inline tag only when
        # it's actually notable; a normal skill roll doesn't announce
        # "SKILL" every single time.
        self.result_lbl = QLabel("Roll to get started")
        self.result_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_lbl.setWordWrap(True)
        self.result_lbl.setStyleSheet(f"color: {BONE}; font-family: '{BODY_FONT}'; font-size: 19px;")
        panel.layout.addWidget(self.result_lbl)

        self.exclude_btn = _flat_button("Exclude This Skill")
        self.exclude_btn.setEnabled(False)
        self.exclude_btn.clicked.connect(self._exclude_current_skill)
        panel.layout.addWidget(self.exclude_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_lbl.setStyleSheet(f"color: {ROT}; font-family: '{BODY_FONT}'; font-size: 11px; border: none;")
        panel.layout.addWidget(self.warning_lbl)

        self.debug_lbl = QLabel("")
        self.debug_lbl.setWordWrap(True)
        self.debug_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.debug_lbl.setStyleSheet(f"color: {MUSTARD}; font-family: '{BODY_FONT}'; font-size: 10px; border: none;")
        panel.layout.addWidget(self.debug_lbl)

        panel.layout.addStretch(1)
        root.addWidget(panel, stretch=1)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)

        self.lock_class_cb = QCheckBox("Lock Class")
        self.lock_class_cb.setStyleSheet(_checkbox_qss(MUSTARD))
        footer.addWidget(self.lock_class_cb)

        self.ignore_exclusions_cb = QCheckBox("Ignore Exclusions")
        self.ignore_exclusions_cb.setChecked(self.settings.get("ignore_exclusions", False))
        self.ignore_exclusions_cb.setStyleSheet(_checkbox_qss(MUSTARD))
        self.ignore_exclusions_cb.toggled.connect(self._persist_settings)
        footer.addWidget(self.ignore_exclusions_cb)

        footer.addStretch(1)

        clear_btn = _flat_button("Clear")
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)

        roll_btn = _primary_button("ROLL")
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

        root.addLayout(footer)

        pool = [c["name"] for c in self.classes if not c.get("excluded", False)]
        self.slot_machine.start_idle(pool)

    # ── Result text ──────────────────────────────────────────────────

    def _format_result_text(self, result: dict) -> str:
        if "error" in result:
            return result["error"]
        text = result["result"] or "(none available)"
        if result["mode"] == "relic":
            return f'{text} <span style="color:{ROT}; font-size:13px;">· Relic Wildcard</span>'
        return text

    # ── Actions ──────────────────────────────────────────────────────

    def _restore_last_roll(self):
        """A restored result is already resolved -- no reason to hide
        it behind a spin that isn't happening, shows immediately."""
        if not self.settings.get("remember_last_roll", True):
            return
        saved = load_last_roll(self.config_dir / "last_roll.yaml")
        if not saved:
            return
        self.last_result = saved
        self.slot_machine.set_static("—" if "error" in saved else saved["class"])
        self._reveal_result(saved)

    def _save_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        save_last_roll(self.config_dir / "last_roll.yaml", self.last_result)

    def _do_roll(self):
        wildcard_enabled = self.wildcard_cb.isChecked()
        wildcard_chance = self.wildcard_chance_pct / 100.0

        classes = self.classes
        locked_name = None
        if self.lock_class_cb.isChecked() and self.last_result and "class" in self.last_result:
            locked_name = self.last_result["class"]
            classes = [c for c in self.classes if c["name"] == locked_name] or self.classes

        result = roll(classes, self.relics, wildcard_enabled, wildcard_chance, self.ignore_exclusions_cb.isChecked())
        self.last_result = result

        if "error" in result:
            self.slot_machine.set_static("—")
            self._reveal_result(result)
            self._save_last_roll()
            return

        self.result_lbl.setText("")
        self.exclude_btn.setEnabled(False)
        self.warning_lbl.setText("")
        self.debug_lbl.setText("")

        if locked_name:
            self.slot_machine.set_static(result["class"])
            self._reveal_result(result)
            self._save_last_roll()
        else:
            pool = [c["name"] for c in self.classes if not c.get("excluded", False)]
            self.slot_machine.spin(pool, result["class"])

    def _on_class_landed(self, class_name: str):
        """Only fires for an actual animated spin landing -- locked
        rolls and restores call set_static(), which doesn't emit
        finished, and reveal immediately instead."""
        if self.last_result:
            self._reveal_result(self.last_result)
            self._save_last_roll()

    def _reveal_result(self, result: dict):
        self.result_lbl.setText(self._format_result_text(result))

        if "error" in result:
            self.warning_lbl.setText("")
            self.debug_lbl.setText("")
            self.exclude_btn.setEnabled(False)
            return

        self.warning_lbl.setText(result.get("warning") or "")

        skipped = result.get("skipped_classes") or []
        self.debug_lbl.setText(
            f"Skipped (no relic tag match): {', '.join(skipped)}" if skipped else ""
        )

        self.exclude_btn.setText("Exclude This Skill")
        self.exclude_btn.setEnabled(result["mode"] == "skill" and bool(result["result"]))

    def _clear(self):
        self.last_result = None
        self.lock_class_cb.setChecked(False)
        pool = [c["name"] for c in self.classes if not c.get("excluded", False)]
        self.slot_machine.start_idle(pool)
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
            if self.slot_machine._mode == "idle":
                pool = [c["name"] for c in self.classes if not c.get("excluded", False)]
                self.slot_machine.start_idle(pool)

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
        open_config_folder(self.config_dir)