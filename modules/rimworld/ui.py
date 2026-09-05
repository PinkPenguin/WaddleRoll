"""
modules/rimworld/ui.py

RimWorld module screen. Rolls Structure, then 3 ordered Memes, then
every applicable Precept those memes resolve to -- all computed up
front by roller.py (pure logic, no animation concerns there), then
*revealed* one at a time through a single reused SlotMachine, each
landed result appended to one of two display sections below it.

Everything reveals through the same fast path now: set_static() +
a short fixed pause before the next item, no real spin() animation for
anything, including structure/memes -- there was no good reason for
those specifically to take longer than precepts do. The landing glow
is disabled entirely (show_glow=False) -- with reveals chained this
tightly, spin-based landings never got a chance to actually render the
glow before the next spin tore it down, and set_static() never clears
it between calls, so it just stayed permanently on through the whole
precept sequence. Neither was the intended "flash," so it's better off
than half-working.

Display is split into two sections rather than one long list:
- IDEOLOGY: Structure + the 3 memes, larger font, in reveal order (not
  sorted -- there are only ever at most 4 of these, order already
  carries meaning: meme 1 is the starting meme, 2/3 are evolution-
  gained). Small and fixed, not scrollable.
- PRECEPTS: the existing scrollable growing list, alphabetized by
  issue as each one lands (the roll and reveal order both stay
  randomized underneath -- only the display position is sorted, see
  _append_precept_row).

"Copy to Clipboard" gathers the whole resolved ideology (structure,
memes in order, every issue->precept pair) into clean plain text --
built for pasting straight into an LLM to flesh out the rest (deities,
roles, rituals, etc.), which is deliberately NOT something this module
tries to generate itself.
"""

import bisect
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QApplication,
)
from PySide6.QtCore import Qt, QTimer

from modules.rimworld.roller import (
    load_structures, save_structures, load_memes, save_memes,
    load_precepts, save_precepts, load_settings, save_settings,
    roll_structure, roll_memes, roll_precepts,
)
from modules.rimworld.editor import (
    open_structures_editor, open_memes_editor, open_precepts_editor,
)
from ui.slot_machine import SlotMachine
from ui.config_folder import open_config_folder
from ui.last_roll import load_last_roll, save_last_roll

# ── Palette: muted slate-gray + burnt orange -- desaturated-neutral
# base with a warm accent, distinct from every saturated-hue module ─────
BG         = "#1a1a1c"
BG_PANEL   = "#242426"
ACCENT     = "#c97b3d"
ACCENT_DIM = "#7a4a22"
TEXT       = "#e0ddd6"
WARN       = "#d94f4f"

FONT_FAMILY = "Century Gothic"

REVEAL_DELAY_MS = 350   # pacing between reveals -- same for everything now, not just precepts


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {ACCENT_DIM}; max-height: 1px; border: none;")
    return line


def _flat_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {ACCENT}; background-color: transparent;
            border: none; padding: 4px 6px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        }}
        QPushButton:hover {{ color: {TEXT}; text-decoration: underline; }}
    """)
    return btn


def _primary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {BG}; background-color: {ACCENT};
            border: none; border-radius: 6px; padding: 10px 30px;
            font-family: '{FONT_FAMILY}'; font-size: 14px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {ACCENT_DIM}; color: {TEXT}; }}
    """)
    return btn


class RimworldWidget(QWidget):
    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {BG};")

        self.structures = load_structures(self.config_dir / "structures.yaml")
        self.memes = load_memes(self.config_dir / "memes.yaml")
        self.precepts = load_precepts(self.config_dir / "precepts.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")

        self.last_structure = None
        self.last_memes = []
        self.last_precepts = {}

        self._reveal_queue = []
        self._precept_issues_sorted = []   # kept sorted alphabetically, parallel to the precept rows' positions

        self._build_ui()
        self._restore_last_roll()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        title = QLabel("RIMWORLD — IDEOLOGY ROLLER")
        title.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 22px; font-weight: bold;")
        root.addWidget(title)

        # Tool row
        tools = QHBoxLayout()
        tools.setSpacing(14)
        tools.addStretch(1)
        for label, handler in [
            ("Manage Structures", self._manage_structures),
            ("Manage Memes", self._manage_memes),
            ("Manage Precepts", self._manage_precepts),
            ("Open Config Folder", self._open_config_folder),
        ]:
            btn = _flat_button(label)
            btn.clicked.connect(handler)
            tools.addWidget(btn)
        root.addLayout(tools)
        root.addWidget(_divider())

        # Reveal slot machine -- compact (single line), glow disabled
        # (see module docstring for why), reused for every reveal
        self.slot_machine = SlotMachine(
            text_color=TEXT, dim_color=ACCENT_DIM, font_family=FONT_FAMILY,
            compact=True, show_glow=False,
        )
        root.addWidget(self.slot_machine)

        # IDEOLOGY summary -- Structure + 3 memes, larger font, fixed
        # (not scrollable, there's only ever at most 4 of these)
        ideology_label = QLabel("IDEOLOGY")
        ideology_label.setStyleSheet(f"color: {ACCENT}; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        root.addWidget(ideology_label)

        ideology_panel = QFrame()
        ideology_panel.setStyleSheet(f"background-color: {BG_PANEL};")
        self.ideology_layout = QVBoxLayout(ideology_panel)
        self.ideology_layout.setContentsMargins(14, 10, 14, 10)
        self.ideology_layout.setSpacing(4)
        root.addWidget(ideology_panel)

        # PRECEPTS -- the existing scrollable growing list
        precepts_label = QLabel("PRECEPTS")
        precepts_label.setStyleSheet(f"color: {ACCENT}; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        root.addWidget(precepts_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {BG_PANEL}; border: none; }}")
        results_widget = QWidget()
        results_widget.setStyleSheet(f"background-color: {BG_PANEL};")
        self.results_layout = QVBoxLayout(results_widget)
        self.results_layout.setContentsMargins(14, 10, 14, 10)
        self.results_layout.setSpacing(4)
        self.results_layout.addStretch(1)
        scroll.setWidget(results_widget)
        root.addWidget(scroll, stretch=1)

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setStyleSheet(f"color: {WARN}; font-family: '{FONT_FAMILY}'; font-size: 11px; border: none;")
        root.addWidget(self.warning_lbl)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)

        copy_btn = _flat_button("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        footer.addWidget(copy_btn)

        footer.addStretch(1)

        clear_btn = _flat_button("Clear")
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)

        roll_btn = _primary_button("ROLL")
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

        root.addLayout(footer)

    # ── Results display ──────────────────────────────────────────────

    def _append_ideology_row(self, label: str, value: str):
        row = QLabel(f"<b>{label}:</b> {value}")
        row.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 18px; font-weight: bold; border: none;")
        self.ideology_layout.addWidget(row)

    def _append_precept_row(self, issue: str, precept: str):
        row = QLabel(f"<b>{issue}:</b> {precept}")
        row.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 13px; border: none;")
        # Alphabetical position -- the underlying roll and reveal order
        # both stay randomized (the extremity tally's fairness depends
        # on that), this only reorders where the row lands visually.
        insert_at = bisect.bisect_left(self._precept_issues_sorted, issue)
        self._precept_issues_sorted.insert(insert_at, issue)
        self.results_layout.insertWidget(insert_at, row)

    def _clear_results_display(self):
        while self.ideology_layout.count():
            item = self.ideology_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._precept_issues_sorted = []

    # ── Actions ──────────────────────────────────────────────────────

    def _do_roll(self):
        structure_result = roll_structure(self.structures)
        meme_result = roll_memes(self.memes, count=3)
        precept_result = roll_precepts(self.precepts, meme_result["memes"])

        self.last_structure = structure_result["structure"]
        self.last_memes = meme_result["memes"]
        self.last_precepts = precept_result["precepts"]

        warnings = [w for w in (structure_result.get("warning"), meme_result.get("warning")) if w]
        self.warning_lbl.setText("  ".join(warnings))

        self._clear_results_display()

        self._reveal_queue = []
        if self.last_structure:
            self._reveal_queue.append(("Structure", self.last_structure, False))
        for i, name in enumerate(self.last_memes, start=1):
            self._reveal_queue.append((f"Meme {i}", name, False))
        for issue, precept in self.last_precepts.items():
            self._reveal_queue.append((issue, precept, True))

        self._reveal_next()

    def _reveal_next(self):
        if not self._reveal_queue:
            self._save_last_roll()
            return

        label, value, is_precept = self._reveal_queue.pop(0)
        self.slot_machine.set_static(f"{label}: {value}")

        if is_precept:
            self._append_precept_row(label, value)
        else:
            self._append_ideology_row(label, value)

        QTimer.singleShot(REVEAL_DELAY_MS, self._reveal_next)

    def _restore_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        saved = load_last_roll(self.config_dir / "last_roll.yaml")
        if not saved:
            return

        self.last_structure = saved.get("structure")
        self.last_memes = saved.get("memes") or []
        self.last_precepts = saved.get("precepts") or {}

        if self.last_structure:
            self._append_ideology_row("Structure", self.last_structure)
        for i, name in enumerate(self.last_memes, start=1):
            self._append_ideology_row(f"Meme {i}", name)
        for issue, precept in self.last_precepts.items():
            self._append_precept_row(issue, precept)

    def _save_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        data = {
            "structure": self.last_structure,
            "memes": self.last_memes,
            "precepts": self.last_precepts,
        }
        save_last_roll(self.config_dir / "last_roll.yaml", data)

    def _clear(self):
        self.last_structure = None
        self.last_memes = []
        self.last_precepts = {}
        self._reveal_queue = []
        self.warning_lbl.setText("")
        self._clear_results_display()
        save_last_roll(self.config_dir / "last_roll.yaml", None)

    def _copy_to_clipboard(self):
        lines = []
        if self.last_structure:
            lines.append(f"Structure: {self.last_structure}")
        for i, name in enumerate(self.last_memes, start=1):
            lines.append(f"Meme {i}: {name}")
        if self.last_precepts:
            lines.append("")
            lines.append("Precepts:")
            for issue, precept in self.last_precepts.items():
                lines.append(f"  {issue}: {precept}")

        if not lines:
            return
        QApplication.clipboard().setText("\n".join(lines))

    def _manage_structures(self):
        result = open_structures_editor(self, self.structures)
        if result is not None:
            self.structures = result
            save_structures(self.config_dir / "structures.yaml", self.structures)

    def _manage_memes(self):
        result = open_memes_editor(self, self.memes)
        if result is not None:
            self.memes = result
            save_memes(self.config_dir / "memes.yaml", self.memes)

    def _manage_precepts(self):
        result = open_precepts_editor(self, self.precepts)
        if result is not None:
            self.precepts = result
            save_precepts(self.config_dir / "precepts.yaml", self.precepts)

    def _open_config_folder(self):
        open_config_folder(self.config_dir)