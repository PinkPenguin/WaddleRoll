"""
modules/fallout4/ui.py

Pip-Boy themed screen for the Fallout 4 module. Ported from the original
Tkinter fo4_gui.py to PySide6 so it can be mounted as a widget inside the
launcher shell's QStackedWidget. Same options, same behavior, same colors.

Weapon groups, named weapons, utility perks, and weapon-type tags are now
loaded from config/*.yaml (editable in-app via Manage buttons) instead of
being hardcoded constants -- same data-editor pattern the other modules
use.

Checkboxes are rendered as terminal-style "[X] Label" text toggles rather
than Qt's default checkbox indicator -- fits the Pip-Boy aesthetic and
sidesteps Qt's default checkmark rendering, which needs extra work to
show correctly once you override its box styling.
"""

import os
import platform
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt

from modules.fallout4.roller import (
    generate_special, roll_weapon, roll_utility_perks, STATS,
    load_weapon_groups, save_weapon_groups,
    load_named_weapons, save_named_weapons,
    load_utility_perks, save_utility_perks,
    load_weapon_tags, save_weapon_tags,
)
from modules.fallout4.editor import (
    open_weapon_groups_editor, open_named_weapons_editor,
    open_utility_perks_editor, open_weapon_tags_editor,
)
from ui.version_badge import VersionBadge

# ── Pip-Boy palette ──────────────────────────────────────────────────────
BG         = "#0a0f0a"
GREEN      = "#4aff91"
GREEN_DIM  = "#2a8a4a"
GREEN_DARK = "#163320"
AMBER      = "#ffb347"
WHITE      = "#d4f0d4"
BORDER     = "#1e3a1e"

FONT_FAMILY = "Courier New"


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {BORDER}; max-height: 1px; border: none;")
    return line


def _section_label(text: str) -> QLabel:
    lbl = QLabel(f"─── {text} ───")
    lbl.setStyleSheet(f"color: {GREEN_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
    return lbl


def _panel() -> tuple[QWidget, QVBoxLayout]:
    """
    A loosely-grouped section -- no border, no background box. Separation
    comes from spacing and the section label above it, same as the clean
    look of the original Tkinter version.
    """
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(8)
    return widget, layout


class TermCheckbox(QPushButton):
    """Terminal-style '[X] Label' toggle. Behaves like a checkbox
    (isChecked/setChecked/toggled) but renders as flat text, no box."""

    def __init__(self, text: str, checked: bool = True, dim: bool = False):
        super().__init__()
        self._label = text
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        color = GREEN_DIM if dim else WHITE
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                color: {color};
                background: transparent;
                border: none;
                font-family: '{FONT_FAMILY}';
                font-size: 11px;
                padding: 3px 2px;
            }}
            QPushButton:hover {{ color: {GREEN}; }}
        """)
        self._refresh_text()
        self.toggled.connect(self._refresh_text)

    def _refresh_text(self):
        mark = "X" if self.isChecked() else " "
        self.setText(f"[{mark}] {self._label}")


def _pip_button(text: str, color: str = GREEN, compact: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    padding = "4px 10px" if compact else "8px 20px"
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {color}; background-color: {BG};
            border: 1px solid {color}; padding: {padding};
            font-family: '{FONT_FAMILY}'; font-size: 14px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {GREEN_DARK}; color: {GREEN}; }}
    """)
    return btn


class FO4Widget(QWidget):
    def __init__(self, config_dir=None, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent / "config"
        self.setStyleSheet(f"background-color: {BG};")

        # ── Data ───────────────────────────────────────────────────────
        self.weapon_groups = load_weapon_groups(self.config_dir / "weapon_groups.yaml")
        self.named_weapons = load_named_weapons(self.config_dir / "named_weapons.yaml")
        self.utility_perks = load_utility_perks(self.config_dir / "utility_perks.yaml")
        self.weapon_tags = load_weapon_tags(self.config_dir / "weapon_tags.yaml")

        # ── State ──────────────────────────────────────────────────────
        self.num_perks = 1
        self.current_special = None
        self.current_roll = None
        self.current_perks = []

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 22, 30, 22)
        root.setSpacing(14)

        # Header
        title = QLabel("// VAULT-TEC IRONMAN RANDOMIZER //")
        title.setStyleSheet(f"color: {GREEN}; font-family: '{FONT_FAMILY}'; font-size: 22px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("FALLOUT 4 — CHARACTER GENERATION TERMINAL")
        subtitle.setStyleSheet(f"color: {GREEN_DIM}; font-family: '{FONT_FAMILY}'; font-size: 10px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        version_row = QHBoxLayout()
        version_row.addStretch(1)
        self.version_badge = VersionBadge(self.config_dir, GREEN_DIM, GREEN_DIM, BG, FONT_FAMILY)
        version_row.addWidget(self.version_badge)
        version_row.addStretch(1)
        root.addLayout(version_row)

        # Tool row -- data management
        tools = QHBoxLayout()
        tools.setSpacing(10)
        tools.addStretch(1)
        for label, handler in [
            ("Manage Weapon Groups", self._manage_weapon_groups),
            ("Manage Named Weapons", self._manage_named_weapons),
            ("Manage Perks", self._manage_perks),
            ("Manage Weapon Tags", self._manage_weapon_tags),
            ("Open Config Folder", self._open_config_folder),
        ]:
            btn = _pip_button(f"[ {label} ]", GREEN_DIM, compact=True)
            btn.clicked.connect(handler)
            tools.addWidget(btn)
        root.addLayout(tools)

        root.addWidget(_divider())

        # Body: sidebar | output
        body = QHBoxLayout()
        body.setSpacing(30)
        root.addLayout(body, stretch=1)

        body.addWidget(self._build_sidebar(), stretch=0)
        body.addWidget(self._build_output(), stretch=1)

        root.addWidget(_divider())

        # Footer: locks + buttons
        footer = QHBoxLayout()
        footer.setSpacing(14)
        root.addLayout(footer)

        lock_label = QLabel("LOCK:")
        lock_label.setStyleSheet(f"color: {GREEN_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        footer.addWidget(lock_label)

        self.special_locked = TermCheckbox("SPECIAL", checked=False, dim=True)
        self.weapon_locked = TermCheckbox("WEAPON", checked=False, dim=True)
        self.perk_locked = TermCheckbox("PERK", checked=False, dim=True)
        for cb in (self.special_locked, self.weapon_locked, self.perk_locked):
            footer.addWidget(cb)

        footer.addStretch(1)

        clear_btn = _pip_button("[ CLEAR ]", GREEN_DIM)
        clear_btn.clicked.connect(self._do_clear)
        footer.addWidget(clear_btn)

        roll_btn = _pip_button("[ ROLL ]", GREEN)
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

    def _build_sidebar(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        col.setFixedWidth(240)

        # Options
        opts_col = QVBoxLayout()
        opts_col.setSpacing(6)
        opts_col.addWidget(_section_label("OPTIONS"))
        opts_widget, opts_layout = _panel()
        self.varied_stats = TermCheckbox("Varied SPECIAL stats", True)
        self.allow_special = TermCheckbox("Allow special weapons", True)
        opts_layout.addWidget(self.varied_stats)
        opts_layout.addWidget(self.allow_special)

        prow = QHBoxLayout()
        prow.setSpacing(8)
        plabel = QLabel("Perks to roll:")
        plabel.setStyleSheet(f"color: {WHITE}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        prow.addWidget(plabel)
        prow.addStretch(1)
        minus_btn = _pip_button("−", GREEN, compact=True)
        minus_btn.setFixedWidth(32)
        minus_btn.clicked.connect(self._dec_perks)
        self.perk_count_lbl = QLabel("1")
        self.perk_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.perk_count_lbl.setFixedWidth(20)
        self.perk_count_lbl.setStyleSheet(f"color: {GREEN}; font-family: '{FONT_FAMILY}'; font-size: 14px; font-weight: bold;")
        plus_btn = _pip_button("+", GREEN, compact=True)
        plus_btn.setFixedWidth(32)
        plus_btn.clicked.connect(self._inc_perks)
        prow.addWidget(minus_btn)
        prow.addWidget(self.perk_count_lbl)
        prow.addWidget(plus_btn)
        opts_layout.addLayout(prow)
        opts_col.addWidget(opts_widget)
        layout.addLayout(opts_col)

        # DLC
        dlc_col = QVBoxLayout()
        dlc_col.setSpacing(6)
        dlc_col.addWidget(_section_label("DLC"))
        dlc_widget, dlc_layout = _panel()
        self.dlc_far_harbor = TermCheckbox("Far Harbor", True)
        self.dlc_nuka_world = TermCheckbox("Nuka-World", True)
        self.dlc_automatron = TermCheckbox("Automatron", True)
        dlc_layout.addWidget(self.dlc_far_harbor)
        dlc_layout.addWidget(self.dlc_nuka_world)
        dlc_layout.addWidget(self.dlc_automatron)
        dlc_col.addWidget(dlc_widget)
        layout.addLayout(dlc_col)

        # Weapon groups -- now sourced from loaded config, not a hardcoded dict,
        # so adding/removing a group via Manage Weapon Groups shows up here
        # automatically on next open.
        grp_col = QVBoxLayout()
        grp_col.setSpacing(6)
        grp_col.addWidget(_section_label("GROUPS"))
        grp_widget, grp_layout = _panel()
        self.group_toggles = {}
        for group in self.weapon_groups:
            cb = TermCheckbox(group["name"], True)
            self.group_toggles[group["name"]] = cb
            grp_layout.addWidget(cb)
        grp_col.addWidget(grp_widget)
        layout.addLayout(grp_col)

        layout.addStretch(1)
        return col

    def _build_output(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # SPECIAL
        sc_col = QVBoxLayout()
        sc_col.setSpacing(8)
        sc_col.addWidget(_section_label("S.P.E.C.I.A.L."))
        sc_widget, sc_layout = _panel()
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(10)
        self.special_labels = {}
        positions = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2)]
        for stat, (r, c) in zip(STATS, positions):
            cell = QHBoxLayout()
            cell.setSpacing(6)
            name_lbl = QLabel(f"{stat}:")
            name_lbl.setStyleSheet(f"color: {GREEN_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
            val_lbl = QLabel("--")
            val_lbl.setStyleSheet(f"color: {GREEN}; font-family: '{FONT_FAMILY}'; font-size: 15px; font-weight: bold;")
            cell.addWidget(name_lbl)
            cell.addWidget(val_lbl)
            cell.addStretch(1)
            wrapper = QWidget()
            wrapper.setLayout(cell)
            grid.addWidget(wrapper, r, c)
            self.special_labels[stat] = val_lbl
        sc_layout.addLayout(grid)
        sc_col.addWidget(sc_widget)
        layout.addLayout(sc_col)

        # Weapon
        wc_col = QVBoxLayout()
        wc_col.setSpacing(8)
        wc_col.addWidget(_section_label("WEAPON"))
        wc_widget, wc_layout = _panel()
        self.weapon_name_lbl = QLabel("--")
        self.weapon_name_lbl.setStyleSheet(f"color: {AMBER}; font-family: '{FONT_FAMILY}'; font-size: 15px; font-weight: bold;")
        self.weapon_meta_lbl = QLabel("")
        self.weapon_meta_lbl.setStyleSheet(f"color: {GREEN_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        wc_layout.addWidget(self.weapon_name_lbl)
        wc_layout.addWidget(self.weapon_meta_lbl)
        wc_col.addWidget(wc_widget)
        layout.addLayout(wc_col)

        # Perks
        pc_col = QVBoxLayout()
        pc_col.setSpacing(8)
        pc_col.addWidget(_section_label("PERK ASSIGNMENT"))
        pc_widget, pc_layout = _panel()
        pc_layout.setSpacing(6)
        self.perk_labels = []
        for _ in range(5):
            lbl = QLabel("")
            lbl.setStyleSheet(f"color: {GREEN}; font-family: '{FONT_FAMILY}'; font-size: 12px;")
            pc_layout.addWidget(lbl)
            self.perk_labels.append(lbl)
        pc_col.addWidget(pc_widget)
        layout.addLayout(pc_col)

        # Status
        self.status_lbl = QLabel("> AWAITING INPUT")
        self.status_lbl.setStyleSheet(f"color: {GREEN_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        layout.addWidget(self.status_lbl)

        layout.addStretch(1)
        return col

    # ── Helpers ────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = GREEN_DIM):
        self.status_lbl.setStyleSheet(f"color: {color}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        self.status_lbl.setText(msg)

    def _inc_perks(self):
        if self.num_perks < 5:
            self.num_perks += 1
            self.perk_count_lbl.setText(str(self.num_perks))

    def _dec_perks(self):
        if self.num_perks > 1:
            self.num_perks -= 1
            self.perk_count_lbl.setText(str(self.num_perks))

    def _active_group_names(self) -> set:
        return {name for name, cb in self.group_toggles.items() if cb.isChecked()}

    def _active_named_weapons(self) -> list:
        dlc_map = {
            "Far Harbor": self.dlc_far_harbor.isChecked(),
            "Nuka-World": self.dlc_nuka_world.isChecked(),
            "Automatron": self.dlc_automatron.isChecked(),
        }
        return [
            w for w in self.named_weapons
            if not w.get("dlc") or dlc_map.get(w["dlc"], True)
        ]

    # ── Roll logic ─────────────────────────────────────────────────────

    def _do_roll(self):
        active_group_names = self._active_group_names()
        if not active_group_names:
            self._set_status("> ERROR: NO WEAPON GROUPS ENABLED", AMBER)
            return

        if not self.special_locked.isChecked():
            self.current_special = generate_special(self.varied_stats.isChecked())

        if not self.weapon_locked.isChecked():
            self.current_roll = roll_weapon(
                self.current_special,
                named_weapons=self._active_named_weapons(),
                weapon_groups=self.weapon_groups,
                allow_special=self.allow_special.isChecked(),
                active_group_names=active_group_names,
            )

        if self.current_roll and self.current_roll.get("weapon") is None:
            self._set_status("> ERROR: NO NON-EXCLUDED WEAPONS IN ELIGIBLE GROUP(S)", AMBER)
            return

        if not self.perk_locked.isChecked() and self.current_roll:
            weapon_type = self.current_roll["weapon"]["type"]
            self.current_perks = roll_utility_perks(
                self.current_special,
                weapon_type,
                perks=self.utility_perks,
                weapon_tags=self.weapon_tags,
                num_perks=self.num_perks,
            )

        self._update_display()
        self._set_status("> ROLL COMPLETE — GOOD LUCK, VAULT DWELLER", GREEN)

    def _do_clear(self):
        self.current_special = None
        self.current_roll = None
        self.current_perks = []
        self.special_locked.setChecked(False)
        self.weapon_locked.setChecked(False)
        self.perk_locked.setChecked(False)
        for lbl in self.special_labels.values():
            lbl.setText("--")
        self.weapon_name_lbl.setText("--")
        self.weapon_meta_lbl.setText("")
        for lbl in self.perk_labels:
            lbl.setText("")
        self._set_status("> TERMINAL CLEARED", GREEN_DIM)

    def _update_display(self):
        if self.current_special:
            for stat, val in self.current_special.items():
                self.special_labels[stat].setText(str(val))

        if self.current_roll and self.current_roll.get("weapon"):
            w = self.current_roll["weapon"]
            cat = self.current_roll["category"]
            grp = self.current_roll.get("group")
            if grp and grp != w["type"]:
                meta = f"{cat}  |  {grp}  |  {w['type']}"
            else:
                meta = f"{cat}  |  {w['type']}"
            self.weapon_name_lbl.setText(w["name"].upper())
            self.weapon_meta_lbl.setText(meta)

        for i, lbl in enumerate(self.perk_labels):
            if i < len(self.current_perks):
                lbl.setText(f"▸ {self.current_perks[i]}")
            else:
                lbl.setText("")

    # ── Data management ─────────────────────────────────────────────────

    def _manage_weapon_groups(self):
        result = open_weapon_groups_editor(self, self.weapon_groups)
        if result is not None:
            self.weapon_groups = result
            save_weapon_groups(self.config_dir / "weapon_groups.yaml", self.weapon_groups)
            self._set_status("> WEAPON GROUPS UPDATED — REOPEN MODULE TO REFRESH GROUP TOGGLES", GREEN_DIM)

    def _manage_named_weapons(self):
        result = open_named_weapons_editor(self, self.named_weapons)
        if result is not None:
            self.named_weapons = result
            save_named_weapons(self.config_dir / "named_weapons.yaml", self.named_weapons)

    def _manage_perks(self):
        result = open_utility_perks_editor(self, self.utility_perks)
        if result is not None:
            self.utility_perks = result
            save_utility_perks(self.config_dir / "utility_perks.yaml", self.utility_perks)

    def _manage_weapon_tags(self):
        result = open_weapon_tags_editor(self, self.weapon_tags)
        if result is not None:
            self.weapon_tags = result
            save_weapon_tags(self.config_dir / "weapon_tags.yaml", self.weapon_tags)

    def _open_config_folder(self):
        path = str(self.config_dir)
        system = platform.system()
        if system == "Windows":
            os.startfile(path)  # noqa: S606 -- Windows-only call, deliberate
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])