"""
modules/dota2/ui.py

Dota 2 module screen. Single flat hero roll, using SlotMachine for the
reveal (same as PoE1/PoE2) -- clicking the landed result opens the
wiki, same click mechanism.

Two things beyond the usual roll+exclude shape:

1. "Manage Heroes" opens a grid (ToggleGridDialog, shared) instead of
   a row-per-item table -- ~120 heroes would be a long scroll otherwise.
   Clicking a hero's name in that grid opens the same notes dialog as
   below, via the grid's on_name_click hook.
2. A small "view notes" link sits right under the slot machine,
   enabled once a hero's actually rolled -- opens a browsable list of
   that hero's named builds (e.g. "Support", "Core"), each with its
   own general + item notes, not just one blob per hero. Deliberately
   unobtrusive, not a full-width button, per the request to not give
   it much real estate.

Distinct visual identity: true royal blue against near-black navy --
no other module is this hue (Torchlight's is cyan/teal, cooler and
greener). Calibri, unused elsewhere. Flat panel with no border and no
radius at all -- a combination none of the other modules use (they're
either rounded+bordered, sharp+bordered, or boxless-with-dividers).
"""

from pathlib import Path
from urllib.parse import quote_plus

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from modules.dota2.roller import (
    load_heroes, save_heroes, load_notes, save_notes,
    get_builds_for_hero, save_builds_for_hero,
    load_settings, save_settings, roll_hero,
)
from modules.dota2.editor import open_heroes_grid, open_builds_editor
from ui.slot_machine import SlotMachine
from ui.version_badge import VersionBadge
from ui.config_folder import open_config_folder
from ui.last_roll import load_last_roll, save_last_roll

# ── Palette: royal blue against near-black navy -- new hue family ───────
BG         = "#0a0c14"
BG_PANEL   = "#121525"
ACCENT     = "#4d7dff"
ACCENT_DIM = "#2a3d73"
TEXT       = "#dde3f5"
WARN       = "#e8a34e"

FONT_FAMILY = "Calibri"

# Same MediaWiki-style search pattern as PoE's wikis
WIKI_SEARCH_URL = "https://liquipedia.net/dota2/index.php?search=%s"


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


def _action_button(text: str, color: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {color}; background-color: {BG};
            border: 1px solid {color}; padding: 8px 22px;
            font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {ACCENT_DIM}; color: {TEXT}; }}
    """)
    return btn


def _notes_link_button() -> QPushButton:
    """Deliberately small and low-key -- not a full action button, just
    a quiet text link sitting under the slot machine."""
    btn = QPushButton("view notes")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {ACCENT_DIM}; background-color: transparent;
            border: none; padding: 2px; font-family: '{FONT_FAMILY}'; font-size: 10px;
        }}
        QPushButton:hover {{ color: {ACCENT}; text-decoration: underline; }}
        QPushButton:disabled {{ color: #333333; }}
    """)
    return btn


class Dota2Widget(QWidget):
    def __init__(self, config_dir: Path, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setStyleSheet(f"background-color: {BG};")

        self.heroes = load_heroes(self.config_dir / "heroes.yaml")
        self.notes = load_notes(self.config_dir / "notes.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")

        self.last_hero_result = None

        self._build_ui()
        self._restore_last_roll()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(14)

        title = QLabel("DOTA 2 — HERO ROLLER")
        title.setStyleSheet(f"color: {TEXT}; font-family: '{FONT_FAMILY}'; font-size: 23px; font-weight: bold;")
        root.addWidget(title)

        self.version_badge = VersionBadge(self.config_dir, ACCENT_DIM, ACCENT_DIM, BG, FONT_FAMILY)
        root.addWidget(self.version_badge)

        # Tool row
        tools = QHBoxLayout()
        tools.setSpacing(10)
        tools.addStretch(1)
        manage_heroes_btn = _tool_button("Manage Heroes")
        manage_heroes_btn.clicked.connect(self._manage_heroes)
        tools.addWidget(manage_heroes_btn)
        open_folder_btn = _tool_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        tools.addWidget(open_folder_btn)
        root.addLayout(tools)

        root.addWidget(_divider())

        # Slot machine panel -- flat, no border, no radius at all
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {BG_PANEL};")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 22, 20, 14)
        panel_layout.setSpacing(6)

        hero_label = QLabel("HERO")
        hero_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_label.setStyleSheet(f"color: {ACCENT}; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        panel_layout.addWidget(hero_label)

        self.slot_machine = SlotMachine(text_color=TEXT, dim_color=ACCENT_DIM, font_family=FONT_FAMILY)
        self.slot_machine.clicked.connect(self._open_wiki)
        self.slot_machine.finished.connect(self._on_spin_finished)
        panel_layout.addWidget(self.slot_machine)

        notes_row = QHBoxLayout()
        notes_row.addStretch(1)
        self.notes_btn = _notes_link_button()
        self.notes_btn.setEnabled(False)
        self.notes_btn.clicked.connect(self._view_notes_for_current_hero)
        notes_row.addWidget(self.notes_btn)
        notes_row.addStretch(1)
        panel_layout.addLayout(notes_row)

        root.addWidget(panel)

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
        lock_label.setStyleSheet(f"color: {ACCENT_DIM}; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        locks.addWidget(lock_label)
        self.lock_hero = QCheckBox("Hero")
        self.lock_hero.setStyleSheet(_checkbox_qss(ACCENT_DIM))
        locks.addWidget(self.lock_hero)
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

        self._start_idle()

    def _eligible_pool_names(self) -> list[str]:
        return [h["name"] for h in self.heroes if not h.get("excluded", False)]

    def _start_idle(self):
        self.slot_machine.start_idle(self._eligible_pool_names())

    # ── Actions ──────────────────────────────────────────────────────

    def _restore_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        saved = load_last_roll(self.config_dir / "last_roll.yaml")
        if not saved or not saved.get("hero"):
            return
        self.last_hero_result = saved
        self.slot_machine.set_static(saved["hero"])
        self.notes_btn.setEnabled(True)

    def _save_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        save_last_roll(self.config_dir / "last_roll.yaml", self.last_hero_result)

    def _do_roll(self):
        locked_hero = self.last_hero_result.get("hero") if (self.lock_hero.isChecked() and self.last_hero_result) else None
        result = roll_hero(self.heroes, locked_hero=locked_hero)
        self.last_hero_result = result

        if result["hero"] is None:
            self.warning_lbl.setText(result.get("warning") or "")
            self.slot_machine.set_static("—")
            self.notes_btn.setEnabled(False)
        else:
            self.warning_lbl.setText("")
            if locked_hero:
                self.slot_machine.set_static(result["hero"])
                self.notes_btn.setEnabled(True)  # already landed, no animation to wait on
            else:
                self.notes_btn.setEnabled(False)  # wait for _on_spin_finished
                self.slot_machine.spin(self._eligible_pool_names(), result["hero"])

        self._save_last_roll()

    def _clear(self):
        self.last_hero_result = None
        self.lock_hero.setChecked(False)
        self.warning_lbl.setText("")
        self.notes_btn.setEnabled(False)
        self._start_idle()
        save_last_roll(self.config_dir / "last_roll.yaml", None)

    def _on_spin_finished(self, hero_name: str):
        """Only fires when an actual animated spin lands -- set_static()
        (locked rolls, restoring last roll) doesn't go through this at
        all, since those are already-resolved states, not animations."""
        self.notes_btn.setEnabled(True)

    def _open_wiki(self, hero_name: str):
        url = WIKI_SEARCH_URL.replace("%s", quote_plus(hero_name))
        QDesktopServices.openUrl(QUrl(url))

    def _open_notes_for(self, hero_name: str):
        builds = get_builds_for_hero(self.notes, hero_name)
        result = open_builds_editor(self, hero_name, builds)
        if result is not None:
            self.notes = save_builds_for_hero(self.notes, hero_name, result)
            save_notes(self.config_dir / "notes.yaml", self.notes)

    def _view_notes_for_current_hero(self):
        if self.last_hero_result and self.last_hero_result.get("hero"):
            self._open_notes_for(self.last_hero_result["hero"])

    def _on_hero_name_clicked_in_grid(self, hero_row: dict):
        self._open_notes_for(hero_row["name"])

    def _manage_heroes(self):
        result = open_heroes_grid(self, self.heroes, on_name_click=self._on_hero_name_clicked_in_grid)
        if result is not None:
            self.heroes = result
            save_heroes(self.config_dir / "heroes.yaml", self.heroes)
            if self.slot_machine._mode == "idle":
                self._start_idle()

    def _open_config_folder(self):
        open_config_folder(self.config_dir)