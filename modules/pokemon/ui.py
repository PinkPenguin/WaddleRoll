"""
modules/pokemon/ui.py

Pokemon module screen. Rolls a variable-size team (1-6, stepper-
controlled) from a generation-bounded, fully-evolved-only pool.

No SlotMachine here -- it's built for one result landing, not up to
six simultaneously, and stacking six spinning reels would be solving a
problem nobody asked for. Instead: a dynamic stack of up to 6 slot
rows, each independently lockable (reroll only the unlocked ones) and
with its own quick "Exclude" button -- both are just the existing
per-result patterns from every other module, extended to a variable
count instead of a fixed 2-3. Only the first team_size rows are ever
visible; the rest are pre-built but hidden (setVisible toggling is
safe here since it only ever happens post-first-paint, in response to
the stepper, not before the dialog's first show()).

Generation and team size are both [-] N [+] steppers, same pattern
FO4's perk count already uses -- not dropdowns. Generation's upper
bound is computed from the real loaded roster (roller.max_generation),
never hardcoded.

Locks are session-only, same as every other module -- only the actual
rolled team persists across a restart, not which slots were locked.

Roster management uses the shared ToggleGridDialog (wider than Dota's,
8 columns instead of 5, sortable by Dex #/Name) -- built for exactly
this "way too many entries for a normal table" problem.

Distinct visual identity: actual Poké Ball red and white -- the one
module that's genuinely LIGHT rather than dark, which is its own
strong distinguisher on top of the hue itself (every other module is
dark-background). Tahoma, unused elsewhere. Borderless rounded (14px)
panel, and the only module where a single solid-filled button (ROLL)
is the sole bordered/boxed element on screen -- everything else is
flat text or a subtle filled shape, deliberately, after the first pass
read as too many competing borders.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame,
    QMessageBox,
)
from PySide6.QtCore import Qt

from modules.pokemon.roller import (
    load_pokemon, save_pokemon, load_settings, save_settings,
    max_generation, roll_team,
)
from modules.pokemon.editor import open_pokemon_grid
from ui.config_folder import open_config_folder
from ui.last_roll import load_last_roll, save_last_roll

# ── Palette: golden-yellow against warm near-black -- new primary hue ───
# ── Palette: red + white, actual Poké Ball colors -- the one module
# that's LIGHT rather than dark, which is its own strong distinguisher
# from every other module on top of the hue itself. Text flips dark-
# on-light instead of light-on-dark, so a separate HOVER_TEXT exists
# for filled/hover button states (dark text on a dark-red fill would
# be unreadable -- that state needs light text instead).
BG          = "#f2ede3"   # warm ivory, not stark white
BG_PANEL    = "#fffdf8"
ACCENT      = "#e3350d"   # Poké Ball red
ACCENT_DIM  = "#8f2308"   # darker red, for hover fills and dividers
TEXT        = "#241f1b"   # near-black, warm-toned
HOVER_TEXT  = "#fdf8f0"   # light text for use on a filled ACCENT_DIM background
WARN        = "#a9540c"   # darker/more saturated than other modules' amber -- needs to hold up against a light background
BORDER_SOFT = "#c4b8a4"   # muted neutral tan -- stepper fill/hover and the lock checkbox indicator; the panel and ROLL button are the only things with a real border/fill left

FONT_FAMILY = "Tahoma"


def _checkbox_qss(text_color: str, indicator_color: str = None) -> str:
    indicator_color = indicator_color or ACCENT
    return f"""
        QCheckBox {{ color: {text_color}; font-family: '{FONT_FAMILY}'; font-size: 11px; }}
        QCheckBox::indicator {{
            width: 14px; height: 14px;
            border: 1px solid {indicator_color}; border-radius: 2px;
            background: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {indicator_color}; border: 1px solid {indicator_color};
        }}
    """


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {ACCENT_DIM}; max-height: 1px; border: none;")
    return line


def _flat_button(text: str, color: str = None) -> QPushButton:
    """No border at all -- just colored text with a hover underline.
    Used for every secondary action (tool buttons, Clear, per-slot
    Exclude) so the only real 'boxes' on screen are the panel and the
    ROLL button."""
    color = color or ACCENT_DIM
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {color}; background-color: transparent;
            border: none; padding: 4px 6px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        }}
        QPushButton:hover {{ color: {ACCENT}; text-decoration: underline; }}
        QPushButton:disabled {{ color: #c8bfae; }}
    """)
    return btn


def _stepper_btn(text: str) -> QPushButton:
    """Small filled square, no border -- a subtle background tint
    instead, distinct from both the flat text buttons and the one
    bordered panel."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedWidth(26)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {ACCENT_DIM}; background-color: {BG_PANEL};
            border: none; border-radius: 4px;
            font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {BORDER_SOFT}; color: {TEXT}; }}
    """)
    return btn


def _primary_button(text: str) -> QPushButton:
    """Solid filled red, no outline -- the one button that should
    actually look like the main action on the page."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {HOVER_TEXT}; background-color: {ACCENT};
            border: none; border-radius: 6px; padding: 10px 30px;
            font-family: '{FONT_FAMILY}'; font-size: 14px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {ACCENT_DIM}; }}
    """)
    return btn


def _stepper_row(label_text: str, minus_handler, plus_handler) -> tuple[QHBoxLayout, QLabel, QPushButton, QPushButton]:
    row = QHBoxLayout()
    row.setSpacing(8)
    label = QLabel(label_text)
    label.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 12px;")
    row.addWidget(label)

    minus_btn = _stepper_btn("−")
    minus_btn.clicked.connect(minus_handler)
    row.addWidget(minus_btn)

    value_lbl = QLabel("0")
    value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    value_lbl.setFixedWidth(24)
    value_lbl.setStyleSheet(f"color: {ACCENT}; font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;")
    row.addWidget(value_lbl)

    plus_btn = _stepper_btn("+")
    plus_btn.clicked.connect(plus_handler)
    row.addWidget(plus_btn)

    return row, value_lbl, minus_btn, plus_btn


class PokemonWidget(QWidget):
    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {BG};")

        self.pokemon = load_pokemon(self.config_dir / "pokemon.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")

        self.max_gen = max_generation(self.pokemon)
        self.team_size = min(self.settings.get("team_size", 6), 6)
        self.generation = self.settings.get("generation")
        if self.generation is None or self.generation > self.max_gen:
            self.generation = self.max_gen

        self.slots = []  # populated in _build_ui, each a dict of widgets + current_name

        self._build_ui()
        self._restore_last_roll()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        title = QLabel("POKÉMON — TEAM ROLLER")
        title.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 22px; font-weight: bold;")
        root.addWidget(title)

        # No VersionBadge here -- unlike every other module, this one
        # isn't tied to a single specific game's patch version.

        # Settings row: team size + generation steppers
        settings_row = QHBoxLayout()
        settings_row.setSpacing(24)

        team_row, self.team_size_lbl, _, _ = _stepper_row("Team Size:", self._dec_team_size, self._inc_team_size)
        self.team_size_lbl.setText(str(self.team_size))
        settings_row.addLayout(team_row)

        gen_row, self.generation_lbl, _, _ = _stepper_row("Generation:", self._dec_generation, self._inc_generation)
        self.generation_lbl.setText(str(self.generation))
        settings_row.addLayout(gen_row)

        settings_row.addStretch(1)

        manage_btn = _flat_button("Manage Pokémon")
        manage_btn.clicked.connect(self._manage_pokemon)
        settings_row.addWidget(manage_btn)

        open_folder_btn = _flat_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        settings_row.addWidget(open_folder_btn)

        root.addLayout(settings_row)
        root.addWidget(_divider())

        # Team panel -- borderless, just a rounded, slightly lighter fill
        panel = QFrame()
        panel.setStyleSheet(f"""
            background-color: {BG_PANEL};
            border-radius: 14px;
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(8)

        for i in range(6):
            self.slots.append(self._build_slot_row(panel_layout, i))

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setStyleSheet(f"color: {WARN}; font-family: '{FONT_FAMILY}'; font-size: 11px; border: none;")
        panel_layout.addWidget(self.warning_lbl)

        panel_layout.addStretch(1)
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

        self._update_slot_visibility()

    def _build_slot_row(self, parent_layout, index: int) -> dict:
        row_widget = QWidget()
        row_widget.setObjectName("pokemon_slot_row")
        # Needs WA_StyledBackground or Qt silently ignores the stylesheet
        # border on a plain QWidget -- same gotcha documented elsewhere
        # in this project (GameCard, ToggleGridDialog's grid_widget).
        # The #pokemon_slot_row ID selector is load-bearing here, not
        # decoration -- an unscoped rule on a QWidget cascades into every
        # QWidget-derived child inside it (the label, checkbox, and
        # button are all QWidget subclasses), which is exactly what
        # produced three nested borders instead of one.
        row_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row_widget.setStyleSheet(f"""
            QWidget#pokemon_slot_row {{
                background-color: transparent;
                border: 1px solid {BORDER_SOFT};
                border-radius: 8px;
            }}
        """)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.setSpacing(14)

        name_lbl = QLabel("—")
        name_lbl.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 22px; font-weight: bold;")
        row_layout.addWidget(name_lbl, stretch=1)

        lock_cb = QCheckBox("Lock")
        lock_cb.setStyleSheet(_checkbox_qss(ACCENT_DIM, BORDER_SOFT))
        row_layout.addWidget(lock_cb)

        exclude_btn = _flat_button("Exclude")
        exclude_btn.setEnabled(False)
        exclude_btn.clicked.connect(self._make_exclude_handler(index))
        row_layout.addWidget(exclude_btn)

        parent_layout.addWidget(row_widget)

        return {
            "row_widget": row_widget,
            "name_lbl": name_lbl,
            "lock_cb": lock_cb,
            "exclude_btn": exclude_btn,
            "current_name": None,
        }

    def _update_slot_visibility(self):
        for i, slot in enumerate(self.slots):
            slot["row_widget"].setVisible(i < self.team_size)

    # ── Steppers ─────────────────────────────────────────────────────

    def _inc_team_size(self):
        if self.team_size < 6:
            self.team_size += 1
            self.team_size_lbl.setText(str(self.team_size))
            self._update_slot_visibility()
            self._persist_settings()

    def _dec_team_size(self):
        if self.team_size > 1:
            self.team_size -= 1
            self.team_size_lbl.setText(str(self.team_size))
            self._update_slot_visibility()
            self._persist_settings()

    def _inc_generation(self):
        if self.generation < self.max_gen:
            self.generation += 1
            self.generation_lbl.setText(str(self.generation))
            self._persist_settings()

    def _dec_generation(self):
        if self.generation > 1:
            self.generation -= 1
            self.generation_lbl.setText(str(self.generation))
            self._persist_settings()

    # ── Actions ──────────────────────────────────────────────────────

    def _restore_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        saved = load_last_roll(self.config_dir / "last_roll.yaml")
        if not saved:
            return
        team = saved.get("team") or []
        for i, name in enumerate(team):
            if i >= len(self.slots):
                break
            self.slots[i]["current_name"] = name
            self.slots[i]["name_lbl"].setText(name)
            self.slots[i]["exclude_btn"].setEnabled(True)

    def _save_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        team = [s["current_name"] for s in self.slots[:self.team_size] if s["current_name"]]
        save_last_roll(self.config_dir / "last_roll.yaml", {"team": team})

    def _do_roll(self):
        locked_names = []
        unlocked_indices = []
        for i in range(self.team_size):
            slot = self.slots[i]
            if slot["lock_cb"].isChecked() and slot["current_name"]:
                locked_names.append(slot["current_name"])
            else:
                unlocked_indices.append(i)

        result = roll_team(self.pokemon, len(unlocked_indices), self.generation, exclude_names=locked_names)
        rolled = result["rolled"]

        for idx, name in zip(unlocked_indices, rolled):
            slot = self.slots[idx]
            slot["current_name"] = name
            slot["name_lbl"].setText(name)
            slot["exclude_btn"].setText("Exclude")
            slot["exclude_btn"].setEnabled(True)

        # Pool ran short -- leave any remaining unlocked slots empty
        # rather than pretending there's a result.
        for idx in unlocked_indices[len(rolled):]:
            slot = self.slots[idx]
            slot["current_name"] = None
            slot["name_lbl"].setText("—")
            slot["exclude_btn"].setEnabled(False)

        self.warning_lbl.setText(result.get("warning") or "")
        self._save_last_roll()

    def _make_exclude_handler(self, index: int):
        """Factory, not a plain lambda in the loop -- avoids the classic
        late-binding closure bug where every handler would end up
        capturing the same final index."""
        def handler():
            slot = self.slots[index]
            name = slot["current_name"]
            if not name:
                return

            reply = QMessageBox.question(
                self,
                "Exclude Pokémon",
                f'Exclude "{name}"?\n\n'
                f"This removes it from every future roll until you manually "
                f"re-include it via Manage Pokémon.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            for p in self.pokemon:
                if p.get("name") == name:
                    p["excluded"] = True
                    break

            save_pokemon(self.config_dir / "pokemon.yaml", self.pokemon)
            slot["exclude_btn"].setText("Excluded ✓")
            slot["exclude_btn"].setEnabled(False)

        return handler

    def _clear(self):
        for slot in self.slots:
            slot["current_name"] = None
            slot["name_lbl"].setText("—")
            slot["lock_cb"].setChecked(False)
            slot["exclude_btn"].setText("Exclude")
            slot["exclude_btn"].setEnabled(False)
        self.warning_lbl.setText("")
        save_last_roll(self.config_dir / "last_roll.yaml", None)

    def _manage_pokemon(self):
        result = open_pokemon_grid(self, self.pokemon)
        if result is not None:
            self.pokemon = result
            save_pokemon(self.config_dir / "pokemon.yaml", self.pokemon)

    def _persist_settings(self, *_args):
        self.settings = {
            "team_size": self.team_size,
            "generation": self.generation,
            "remember_last_roll": self.settings.get("remember_last_roll", True),
        }
        save_settings(self.config_dir / "settings.yaml", self.settings)

    def _open_config_folder(self):
        open_config_folder(self.config_dir)