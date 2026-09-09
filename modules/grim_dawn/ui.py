"""
modules/grim_dawn/ui.py

Grim Dawn module screen. Rolls: Mastery A -> main skill (from A's curated
list) -> Mastery B (secondary/support, no skill rolled for it). Each of
the three results can be locked independently across re-rolls.

VISUAL DESIGN NOTE (second real design-process pass in this project,
same approach as Hero Siege's): grounded in Grim Dawn's actual subject
matter -- weathered industrial-gothic decay, rusted iron, bolted
plating, a diseased/plague undertone (cultists, corruption), not
vibrant or ornate. Checked against the same generic-tell list:
- two colors genuinely in tension (RUST + PLAGUE) rather than one
  accent on flat dark -- a different hue pairing from Hero Siege's
  blood+mustard, not a re-run of the same idea.
- no "WORD — fragment" title -- just "GRIM DAWN" alone.
- no all-caps eyebrow captions floating above content -- small,
  sentence-case labels instead, grouped directly with what they label.
- a real custom-painted RivetedPanel (QPainter) instead of another
  rounded QFrame -- bordered rectangle with small drawn rivets at the
  corners, evoking bolted metal plating. Genuinely different structural
  device from Hero Siege's jagged torn edges, not the same trick reused.

Reveal mechanic: the old version was a flat instant text swap -- boring
for a roll with three separate results. Now each result gets its own
compact (single-line) SlotMachine, and instead of a boring simultaneous
reveal, all three spin at once but with STAGGERED DURATIONS so they
land in sequence -- Mastery A first, Skill second, Mastery B last.
Three independent widgets each spinning once per roll made this simpler
than RimWorld's chained-queue approach: no signal-chaining needed, Qt's
per-widget timers just naturally produce the cascade. Glow stays on
here (unlike RimWorld) since nothing calls spin() rapidly in succession
on the same widget -- each one spins once and stays landed.

Rockwell for the one headline moment (the title, chosen for its
stamped-into-metal feel); Bahnschrift for everything else -- both
unused elsewhere in this project. Same font-availability caveat as
Hero Siege's Impact/Franklin Gothic Medium: can't verify either is
actually installed from here.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor

from modules.grim_dawn.roller import load_masteries, save_masteries, load_settings, save_settings, roll
from modules.grim_dawn.editor import open_masteries_editor
from ui.slot_machine import SlotMachine
from ui.version_badge import VersionBadge
from ui.config_folder import open_config_folder
from ui.last_roll import load_last_roll, save_last_roll

# ── Palette: two colors in tension, a different pairing from Hero Siege ──
IRON     = "#0e1210"   # cold, blue-tinged near-black -- tarnished steel in shadow
BG_PANEL = "#181d19"
RUST     = "#7a3420"   # deep oxidized red -- not RimWorld's warmer orange-rust
PLAGUE   = "#8a9c3a"   # sickly, diseased yellow-green -- the tension color
BONE     = "#c9c0a8"   # aged parchment/bone, not pure white
WARN     = "#c98a3a"

DISPLAY_FONT = "Rockwell"      # one headline moment only -- the title
BODY_FONT    = "Bahnschrift"   # everything else

MASTERY_A_DURATION_MS = 1200
SKILL_DURATION_MS     = 2200
MASTERY_B_DURATION_MS = 3200


class RivetedPanel(QWidget):
    """A bordered rectangle with small drawn rivets at the corners --
    real QPainter work evoking bolted metal plating, not another
    rounded QFrame."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 26, 30, 24)
        self.layout.setSpacing(16)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin = 12
        rivet_r = 4

        painter.setPen(QPen(QColor(RUST), 2))
        painter.setBrush(QColor(BG_PANEL))
        painter.drawRect(1, 1, w - 2, h - 2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PLAGUE))
        for x, y in [
            (margin, margin), (w - margin, margin),
            (margin, h - margin), (w - margin, h - margin),
        ]:
            painter.drawEllipse(QPointF(x, y), rivet_r, rivet_r)


def _checkbox_qss(text_color: str) -> str:
    return f"""
        QCheckBox {{ color: {text_color}; font-family: '{BODY_FONT}'; font-size: 11px; }}
        QCheckBox::indicator {{
            width: 14px; height: 14px;
            border: 1px solid {PLAGUE}; border-radius: 2px;
            background: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {PLAGUE}; border: 1px solid {PLAGUE};
        }}
    """


def _tool_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {RUST}; background-color: transparent;
            border: none; padding: 6px 10px;
            font-family: '{BODY_FONT}'; font-size: 11px;
        }}
        QPushButton:hover {{ color: {PLAGUE}; text-decoration: underline; }}
    """)
    return btn


def _flat_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {RUST}; background-color: transparent;
            border: none; padding: 4px 6px;
            font-family: '{BODY_FONT}'; font-size: 11px;
        }}
        QPushButton:hover {{ color: {PLAGUE}; text-decoration: underline; }}
    """)
    return btn


def _primary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {BONE}; background-color: {RUST};
            border: none; padding: 9px 26px;
            font-family: '{BODY_FONT}'; font-size: 14px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {PLAGUE}; color: {IRON}; }}
    """)
    return btn


class GrimDawnWidget(QWidget):
    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {IRON};")

        self.masteries = load_masteries(self.config_dir / "masteries.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")
        self.last_result = None

        self._build_ui()
        self._restore_last_roll()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(16)

        title = QLabel("GRIM DAWN")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {RUST}; font-family: '{DISPLAY_FONT}'; font-size: 34px; letter-spacing: 1px;")
        root.addWidget(title)

        self.version_badge = VersionBadge(self.config_dir, PLAGUE, PLAGUE, IRON, BODY_FONT)
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

        # Output panel: riveted plate, three columns (Mastery A / Skill / Mastery B)
        panel = RivetedPanel()

        slots_col = QVBoxLayout()
        slots_col.setSpacing(18)

        self.mastery_a_slot, self.lock_mastery_a = self._build_slot_row(
            slots_col, "Mastery A"
        )
        self.skill_slot, self.lock_skill = self._build_slot_row(
            slots_col, "Main Skill"
        )
        self.mastery_b_slot, self.lock_mastery_b = self._build_slot_row(
            slots_col, "Mastery B (support)"
        )

        panel.layout.addLayout(slots_col)

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_lbl.setStyleSheet(f"color: {WARN}; font-family: '{BODY_FONT}'; font-size: 11px; border: none;")
        panel.layout.addWidget(self.warning_lbl)

        panel.layout.addStretch(1)
        root.addWidget(panel, stretch=1)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)
        footer.addStretch(1)

        clear_btn = _flat_button("Clear")
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)

        roll_btn = _primary_button("ROLL")
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

        root.addLayout(footer)

        self._start_idle()

    def _build_slot_row(self, parent_layout, caption_text: str):
        row = QHBoxLayout()
        row.setSpacing(14)

        caption = QLabel(caption_text)
        caption.setFixedWidth(140)
        caption.setStyleSheet(f"color: {PLAGUE}; font-family: '{BODY_FONT}'; font-size: 11px;")
        row.addWidget(caption)

        slot = SlotMachine(text_color=BONE, dim_color=RUST, font_family=BODY_FONT, compact=True)
        row.addWidget(slot, stretch=1)

        lock_cb = QCheckBox("Lock")
        lock_cb.setStyleSheet(_checkbox_qss(PLAGUE))
        row.addWidget(lock_cb)

        parent_layout.addLayout(row)
        return slot, lock_cb

    # ── Pools ────────────────────────────────────────────────────────

    def _mastery_names(self, exclude: str = None) -> list[str]:
        return [
            m["name"] for m in self.masteries
            if not m.get("excluded", False) and m["name"] != exclude
        ]

    def _all_skill_names(self) -> list[str]:
        names = []
        for m in self.masteries:
            if m.get("excluded", False):
                continue
            names.extend(s["name"] for s in m.get("skills", []) if not s.get("excluded", False))
        return names

    def _skill_names_for(self, mastery_name: str) -> list[str]:
        for m in self.masteries:
            if m.get("name") == mastery_name:
                return [s["name"] for s in m.get("skills", []) if not s.get("excluded", False)]
        return self._all_skill_names()

    def _start_idle(self):
        self.mastery_a_slot.start_idle(self._mastery_names())
        self.skill_slot.start_idle(self._all_skill_names())
        self.mastery_b_slot.start_idle(self._mastery_names())

    # ── Actions ──────────────────────────────────────────────────────

    def _restore_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        saved = load_last_roll(self.config_dir / "last_roll.yaml")
        if not saved:
            return
        self.last_result = saved
        self._show_static(saved)

    def _save_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        save_last_roll(self.config_dir / "last_roll.yaml", self.last_result)

    def _do_roll(self):
        locked_a = self.last_result.get("mastery_a") if (self.lock_mastery_a.isChecked() and self.last_result) else None
        locked_skill = self.last_result.get("skill") if (self.lock_skill.isChecked() and self.last_result) else None
        locked_b = self.last_result.get("mastery_b") if (self.lock_mastery_b.isChecked() and self.last_result) else None

        result = roll(self.masteries, locked_mastery_a=locked_a, locked_skill=locked_skill, locked_mastery_b=locked_b)
        self.last_result = result

        if "error" in result:
            self.mastery_a_slot.set_static("—")
            self.skill_slot.set_static("—")
            self.mastery_b_slot.set_static("—")
            self.warning_lbl.setText(result["error"])
            self._save_last_roll()
            return

        self.warning_lbl.setText(result.get("warning") or "")

        # Mastery A -- lands first
        if locked_a:
            self.mastery_a_slot.set_static(result["mastery_a"])
        else:
            self.mastery_a_slot.spin(self._mastery_names(), result["mastery_a"], duration_ms=MASTERY_A_DURATION_MS)

        # Skill -- lands second, spun against the pool of the actual
        # chosen mastery for visual consistency, not just any skill
        if locked_skill:
            self.skill_slot.set_static(result["skill"] or "(none available)")
        else:
            skill_pool = self._skill_names_for(result["mastery_a"]) or self._all_skill_names()
            self.skill_slot.spin(skill_pool, result["skill"] or "(none available)", duration_ms=SKILL_DURATION_MS)

        # Mastery B -- lands last
        if locked_b:
            self.mastery_b_slot.set_static(result["mastery_b"])
        else:
            self.mastery_b_slot.spin(self._mastery_names(), result["mastery_b"], duration_ms=MASTERY_B_DURATION_MS)

        self._save_last_roll()

    def _show_static(self, result: dict):
        """Used for restore -- already resolved, nothing to animate."""
        if "error" in result:
            self.mastery_a_slot.set_static("—")
            self.skill_slot.set_static("—")
            self.mastery_b_slot.set_static("—")
            self.warning_lbl.setText(result["error"])
            return
        self.mastery_a_slot.set_static(result["mastery_a"])
        self.skill_slot.set_static(result["skill"] or "(none available)")
        self.mastery_b_slot.set_static(result["mastery_b"])
        self.warning_lbl.setText(result.get("warning") or "")

    def _clear(self):
        self.last_result = None
        self.lock_mastery_a.setChecked(False)
        self.lock_skill.setChecked(False)
        self.lock_mastery_b.setChecked(False)
        self.warning_lbl.setText("")
        self._start_idle()
        save_last_roll(self.config_dir / "last_roll.yaml", None)

    def _persist_settings(self, *_args):
        self.settings = {
            "remember_last_roll": self.settings.get("remember_last_roll", True),
        }
        save_settings(self.config_dir / "settings.yaml", self.settings)

    def _manage_masteries(self):
        result = open_masteries_editor(self, self.masteries)
        if result is not None:
            self.masteries = result
            save_masteries(self.config_dir / "masteries.yaml", self.masteries)
            if self.mastery_a_slot._mode == "idle":
                self._start_idle()

    def _open_config_folder(self):
        open_config_folder(self.config_dir)