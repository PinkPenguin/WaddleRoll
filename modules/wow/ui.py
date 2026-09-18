"""
modules/wow/ui.py

Rolls: Class -> Race, cascading (class lands, then race spins) --
unlike Torchlight's independent skill/hero-trait pair, race genuinely
depends on which class was rolled (the eligible race pool comes from
that specific class), so this is a real sequential dependency, same
shape as Grim Dawn's Mastery A -> its own skill list, not a
simultaneous-staggered reveal.

VISUAL DESIGN: grounded in WoW's own real duality rather than an
arbitrary palette swap -- Alliance blue vs Horde red is the actual
defining tension of the game, and this module's whole mechanic is
already about that split, so the color duality is made functional
here, not just decorative: the rolled race's own faction badge is
colored blue or red depending on the ACTUAL result, not a fixed accent
color the way every other module's result text is. Gold anchors the
structural chrome (borders, title), matching WoW's own UI framing.
`CrestPanel` (bordered rectangle with small diagonal gold corner
accents, a quiet heraldic touch) is the structural device here,
genuinely different from every other module's rounded/riveted/jagged
panel treatments.

Multi-ruleset support: WoW's class/race availability differs
meaningfully across versions (different classes existing at all, not
just different availability), so rather than one shared dataset with
per-version overrides, each ruleset (Classic, Retail, a private server
variant, etc.) is its own complete, self-contained YAML file under
config/rulesets/. Discovered by scanning that folder -- adding a new
ruleset is "drop a file in," no code changes, matching the project's
usual philosophy for this kind of thing. Which ruleset is active
persists in settings.yaml like any other sticky preference.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QRadioButton, QButtonGroup, QComboBox, QFrame,
)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor

from modules.wow.roller import (
    discover_rulesets, load_ruleset, save_ruleset, roll, race_factions,
)
from modules.wow.editor import open_classes_editor
from ui.slot_machine import SlotMachine
from ui.version_badge import VersionBadge
from ui.config_folder import open_config_folder
from ui.background_widget import BackgroundWidget
from ui.assets import find_module_background
from ui.colors import hex_to_rgba
from ui.last_roll import load_last_roll, save_last_roll
from ui.roll_history import append_roll_history, load_roll_history, open_roll_history_dialog

# ── Palette: gold structural chrome, functional Alliance/Horde duality ──
BG            = "#141110"
BG_PANEL      = "#1c1815"
GOLD          = "#c9a84c"
GOLD_DIM      = "#7a6530"
ALLIANCE_BLUE = "#4d7fc4"
HORDE_RED     = "#b5453e"
TEXT          = "#e8ddc7"
WARN          = "#d97b3d"
FONT_FAMILY   = "Palatino Linotype"


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
            color: {GOLD}; background-color: {hex_to_rgba(BG, 200)};
            border: 1px solid {GOLD_DIM}; border-radius: 4px; padding: 6px 14px;
            font-family: '{FONT_FAMILY}'; font-size: 12px;
        }}
        QPushButton:hover {{ background-color: {hex_to_rgba(GOLD, 60)}; }}
    """)
    return btn


def _flat_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {GOLD_DIM}; background-color: {hex_to_rgba(BG, 170)};
            border: none; border-radius: 4px; padding: 6px 10px;
            font-family: '{FONT_FAMILY}'; font-size: 12px;
        }}
        QPushButton:hover {{ color: {GOLD}; text-decoration: underline; }}
    """)
    return btn


def _primary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {BG}; background-color: {GOLD};
            border: none; padding: 9px 26px;
            font-family: '{FONT_FAMILY}'; font-size: 14px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: #ddc06a; }}
    """)
    return btn


class CrestPanel(QWidget):
    """Bordered rectangle with small diagonal gold corner accents, like
    a plain frame's mitered corner detail -- a quiet heraldic touch,
    distinct from every other module's rounded/riveted/jagged panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(30, 26, 30, 24)
        self.layout.setSpacing(14)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        fill = QColor(BG_PANEL)
        fill.setAlpha(230)
        painter.setBrush(fill)
        painter.setPen(QPen(QColor(GOLD_DIM), 1))
        painter.drawRect(1, 1, w - 2, h - 2)

        accent_len = 16
        painter.setPen(QPen(QColor(GOLD), 2))
        corners = [
            (QPointF(0, 0), QPointF(accent_len, 0), QPointF(0, accent_len)),
            (QPointF(w, 0), QPointF(w - accent_len, 0), QPointF(w, accent_len)),
            (QPointF(0, h), QPointF(accent_len, h), QPointF(0, h - accent_len)),
            (QPointF(w, h), QPointF(w - accent_len, h), QPointF(w, h - accent_len)),
        ]
        for corner, a, b in corners:
            painter.drawLine(corner, a)
            painter.drawLine(corner, b)


class WowWidget(QWidget):
    def __init__(self, config_dir: Path, assets_dir: Path = None, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.rulesets_dir = self.config_dir / "rulesets"

        self.setObjectName("wow_root")
        self.setStyleSheet(f"QWidget#wow_root {{ background-color: {BG}; }}")

        bg_path = find_module_background(assets_dir) if assets_dir else None
        self._background = BackgroundWidget(bg_path, parent=self)
        self._background.setGeometry(self.rect())
        self._background.lower()

        self.settings = self._load_settings()
        self.rulesets = discover_rulesets(self.rulesets_dir)
        self.current_ruleset = self.settings.get("ruleset") if self.settings.get("ruleset") in self.rulesets else (
            self.rulesets[0] if self.rulesets else None
        )
        self.classes = load_ruleset(self.rulesets_dir, self.current_ruleset) if self.current_ruleset else []

        self.last_result = None
        self._reveal_queue = []

        self._build_ui()
        self._restore_last_roll()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._background.setGeometry(self.rect())

    def showEvent(self, event):
        super().showEvent(event)
        self._background.setGeometry(self.rect())

    # ── Settings (separate from roller's own load/save -- this is a
    # UI preference file, not roll content) ─────────────────────────

    def _load_settings(self) -> dict:
        try:
            import yaml
            path = self.config_dir / "settings.yaml"
            if not path.exists():
                return {}
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _persist_settings(self, *_args):
        import yaml
        data = {
            "ruleset": self.current_ruleset,
            "faction_filter": self._current_faction_filter(),
            "remember_last_roll": self.settings.get("remember_last_roll", True),
        }
        self.settings = data
        with open(self.config_dir / "settings.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False)

    def _current_faction_filter(self) -> str:
        if self.faction_alliance.isChecked():
            return "alliance"
        if self.faction_horde.isChecked():
            return "horde"
        return "any"

    def _on_faction_filter_changed(self, *_args):
        """Only refreshes a slot that's actually idling -- doesn't
        interrupt a mid-spin or already-landed result just because the
        filter changed. QButtonGroup fires toggled for both the button
        being unchecked and the one being checked, so this may run
        twice per actual selection change -- harmless, just a cheap
        redundant recompute."""
        if self.race_slot._mode == "idle":
            self.race_slot.start_idle(self._all_race_entries() or ["—"])

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(16)

        title = QLabel("WORLD OF WARCRAFT — CLASS ROLLER")
        title.setStyleSheet(f"""
            color: {GOLD}; background-color: {hex_to_rgba(BG, 230)};
            border: 1px solid {GOLD_DIM}; border-radius: 4px; padding: 4px 14px;
            font-family: '{FONT_FAMILY}'; font-size: 20px; font-weight: bold; letter-spacing: 1px;
        """)
        root.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.version_badge = VersionBadge(self.config_dir, GOLD_DIM, GOLD_DIM, BG, FONT_FAMILY)
        root.addWidget(self.version_badge)

        # Tools row: ruleset dropdown + manage/config buttons
        tools = QHBoxLayout()
        tools.setSpacing(10)

        ruleset_label = QLabel("Ruleset:")
        ruleset_label.setStyleSheet(f"""
            color: {TEXT}; background-color: {hex_to_rgba(BG, 230)};
            border: 1px solid {GOLD_DIM}; border-radius: 4px; padding: 4px 8px;
            font-family: '{FONT_FAMILY}'; font-size: 12px;
        """)
        tools.addWidget(ruleset_label)

        self.ruleset_combo = QComboBox()
        self.ruleset_combo.setStyleSheet(f"""
            QComboBox {{
                color: {TEXT}; background-color: {hex_to_rgba(BG, 230)};
                border: 1px solid {GOLD_DIM}; border-radius: 4px; padding: 4px 8px;
                font-family: '{FONT_FAMILY}'; font-size: 12px;
            }}
        """)
        self.ruleset_combo.addItems(self.rulesets)
        if self.current_ruleset:
            self.ruleset_combo.setCurrentText(self.current_ruleset)
        self.ruleset_combo.currentTextChanged.connect(self._on_ruleset_changed)
        tools.addWidget(self.ruleset_combo)

        tools.addStretch(1)

        manage_btn = _tool_button("Manage Classes")
        manage_btn.clicked.connect(self._manage_classes)
        tools.addWidget(manage_btn)

        open_folder_btn = _tool_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        tools.addWidget(open_folder_btn)

        root.addLayout(tools)

        # Faction filter -- restricts the ELIGIBLE RACE pool for
        # whichever class gets rolled, not the class pool itself
        faction_row = QHBoxLayout()
        faction_row.setSpacing(10)
        self.faction_group = QButtonGroup(self)
        self.faction_any = QRadioButton("Any Faction")
        self.faction_alliance = QRadioButton("Alliance")
        self.faction_horde = QRadioButton("Horde")
        self.faction_any.setChecked(self.settings.get("faction_filter", "any") == "any")
        self.faction_alliance.setChecked(self.settings.get("faction_filter") == "alliance")
        self.faction_horde.setChecked(self.settings.get("faction_filter") == "horde")
        for rb, color in (
            (self.faction_any, GOLD_DIM),
            (self.faction_alliance, ALLIANCE_BLUE),
            (self.faction_horde, HORDE_RED),
        ):
            rb.setStyleSheet(f"""
                QRadioButton {{
                    color: {color}; background-color: {hex_to_rgba(BG, 230)};
                    border: 1px solid {color}; border-radius: 4px; padding: 4px 10px;
                    font-family: '{FONT_FAMILY}'; font-size: 12px;
                }}
                QRadioButton::indicator {{
                    width: 12px; height: 12px;
                    border: 1px solid {color}; border-radius: 6px;
                    background: transparent;
                }}
                QRadioButton::indicator:checked {{
                    background-color: {color};
                }}
            """)
            self.faction_group.addButton(rb)
            rb.toggled.connect(self._persist_settings)
            rb.toggled.connect(self._on_faction_filter_changed)
            faction_row.addWidget(rb)
        faction_row.addStretch(1)
        root.addLayout(faction_row)

        root.addWidget(_divider())

        # Output panel
        panel = CrestPanel()

        class_label = QLabel("CLASS")
        class_label.setStyleSheet(f"color: {GOLD}; background: transparent; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        panel.layout.addWidget(class_label)

        self.class_slot = SlotMachine(text_color=TEXT, dim_color=GOLD_DIM, font_family=FONT_FAMILY, compact=True)
        self.class_slot.finished.connect(self._on_class_landed)
        panel.layout.addWidget(self.class_slot)

        race_label = QLabel("RACE")
        race_label.setStyleSheet(f"color: {GOLD}; background: transparent; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        panel.layout.addWidget(race_label)

        self.race_slot = SlotMachine(text_color=TEXT, dim_color=GOLD_DIM, font_family=FONT_FAMILY, compact=True)
        self.race_slot.finished.connect(self._on_race_landed)
        panel.layout.addWidget(self.race_slot)

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_lbl.setStyleSheet(f"color: {WARN}; background: transparent; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        panel.layout.addWidget(self.warning_lbl)

        panel.layout.addStretch(1)
        root.addWidget(panel, stretch=1)

        # Lock row
        locks = QHBoxLayout()
        locks.setSpacing(14)
        lock_label = QLabel("LOCK:")
        lock_label.setStyleSheet(f"""
            color: {GOLD_DIM}; background-color: {hex_to_rgba(BG, 230)};
            border: 1px solid {GOLD_DIM}; border-radius: 4px; padding: 2px 8px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        """)
        locks.addWidget(lock_label)
        self.lock_class = QCheckBox("Class")
        self.lock_race = QCheckBox("Race")
        for cb in (self.lock_class, self.lock_race):
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {GOLD_DIM}; background-color: {hex_to_rgba(BG, 230)};
                    border: 1px solid {GOLD_DIM}; border-radius: 4px; padding: 2px 8px;
                    font-family: '{FONT_FAMILY}'; font-size: 11px;
                }}
                QCheckBox::indicator {{
                    width: 14px; height: 14px;
                    border: 1px solid {GOLD}; border-radius: 2px;
                    background: transparent;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {GOLD}; border: 1px solid {GOLD};
                }}
            """)
            locks.addWidget(cb)
        locks.addStretch(1)
        root.addLayout(locks)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)

        history_btn = _flat_button("View History")
        history_btn.clicked.connect(self._view_history)
        footer.addWidget(history_btn)

        footer.addStretch(1)

        clear_btn = _flat_button("Clear")
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)

        roll_btn = _primary_button("ROLL")
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

        root.addLayout(footer)

        self._start_idle()

    # ── Pools ────────────────────────────────────────────────────────

    def _all_class_names(self) -> list[str]:
        return [c["name"] for c in self.classes if not c.get("excluded", False)]

    def _faction_color(self, factions: list[str]) -> str:
        """Gold (the module's own neutral/structural accent) for a race
        playable by both factions, or with no faction specified at all
        -- neither Alliance blue nor Horde red would be accurate for a
        race that transcends the split, and gold already carries the
        "neutral" meaning everywhere else in this module."""
        if len(factions) == 1:
            if factions[0] == "alliance":
                return ALLIANCE_BLUE
            if factions[0] == "horde":
                return HORDE_RED
        return GOLD

    def _race_entries_for(self, class_name: str) -> list:
        """(name, color) tuples, colored by each race's own faction --
        SlotMachine's built-in color-tagging shows blue/red/gold names
        while spinning, and a plain-name result automatically reuses
        the matching pool entry's color once landed (see spin()'s own
        docstring), so the landed race is correctly colored without
        needing a separate badge or label.

        Respects the current faction filter -- this is a visual
        variety pool for the SPIN specifically, so it needs to only
        ever show races that could actually be the result under
        whatever's currently selected, same membership check roll()
        itself uses, not just the raw excluded flag."""
        faction_filter = self._current_faction_filter()
        for c in self.classes:
            if c.get("name") == class_name:
                return [
                    (r["name"], self._faction_color(race_factions(r)))
                    for r in c.get("races", [])
                    if not r.get("excluded", False)
                    and (faction_filter == "any" or faction_filter in race_factions(r))
                ]
        return []

    def _all_race_entries(self) -> list:
        """Same faction-filter respect as _race_entries_for, for the
        idle-spin pool (used before any class has been chosen yet, so
        this flattens across every class rather than one specific
        one)."""
        faction_filter = self._current_faction_filter()
        entries = []
        for c in self.classes:
            if c.get("excluded", False):
                continue
            entries.extend(
                (r["name"], self._faction_color(race_factions(r)))
                for r in c.get("races", [])
                if not r.get("excluded", False)
                and (faction_filter == "any" or faction_filter in race_factions(r))
            )
        return entries

    def _factions_for(self, class_name: str, race_name: str) -> list[str]:
        for c in self.classes:
            if c.get("name") != class_name:
                continue
            for r in c.get("races", []):
                if r.get("name") == race_name:
                    return race_factions(r)
        return []

    def _start_idle(self):
        self.class_slot.start_idle(self._all_class_names() or ["—"])
        self.race_slot.start_idle(self._all_race_entries() or ["—"])

    # ── Ruleset switching ────────────────────────────────────────────

    def _on_ruleset_changed(self, name: str):
        if not name or name == self.current_ruleset:
            return
        self.current_ruleset = name
        self.classes = load_ruleset(self.rulesets_dir, self.current_ruleset)
        self.last_result = None
        self.lock_class.setChecked(False)
        self.lock_race.setChecked(False)
        self.warning_lbl.setText("")
        self._start_idle()
        self._persist_settings()

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

    def _record_roll_history(self, result: dict):
        """Kept separate from _save_last_roll -- that one's a restore-
        on-launch mechanism (overwrite, single entry), this is an
        append-only log (capped, many entries). Different concerns,
        different files, even though both fire at the same "roll is
        fully settled" point."""
        if not result or "error" in result:
            return
        append_roll_history(self.config_dir / "roll_history.yaml", result)

    def _view_history(self):
        history = load_roll_history(self.config_dir / "roll_history.yaml")

        def format_entry(entry: dict) -> str:
            race = entry.get("race") or "(no race)"
            return f"{entry.get('class', '?')} — {race}"

        def restore_entry(entry: dict):
            self.last_result = entry
            self._show_static(entry)
            self._save_last_roll()

        open_roll_history_dialog(self, "Roll History", history, format_entry, on_restore=restore_entry)

    def _show_static(self, result: dict):
        if "error" in result:
            self.class_slot.set_static("—")
            self.race_slot.set_static("—")
            self.warning_lbl.setText(result["error"])
            return
        self.class_slot.set_static(result["class"])
        if result.get("race"):
            factions = self._factions_for(result["class"], result["race"])
            self.race_slot.set_static(result["race"], color=self._faction_color(factions))
        else:
            self.race_slot.set_static("—")
        self.warning_lbl.setText(result.get("warning") or "")

    def _do_roll(self):
        was_class_locked = bool(self.lock_class.isChecked() and self.last_result and self.last_result.get("class"))
        was_race_locked = bool(self.lock_race.isChecked() and self.last_result and self.last_result.get("race"))

        locked_class = self.last_result.get("class") if was_class_locked else None
        locked_race = self.last_result.get("race") if was_race_locked else None

        result = roll(
            self.classes,
            faction_filter=self._current_faction_filter(),
            locked_class=locked_class,
            locked_race=locked_race,
        )
        self.last_result = result

        if "error" in result:
            self.class_slot.set_static("—")
            self.race_slot.set_static("—")
            self.warning_lbl.setText(result["error"])
            self._save_last_roll()
            return

        self.warning_lbl.setText("")
        self._reveal_queue = [("race", was_race_locked)]

        if was_class_locked:
            self.class_slot.set_static(result["class"])
            self._advance_reveal_queue()
        else:
            self.class_slot.spin(self._all_class_names(), result["class"], duration_ms=1200)
            self.race_slot.start_idle(self._all_race_entries() or ["—"])

    def _on_class_landed(self, _class_name: str):
        if self.last_result:
            self._advance_reveal_queue()

    def _on_race_landed(self, _race_name: str):
        if self.last_result:
            self.warning_lbl.setText(self.last_result.get("warning") or "")
            self._advance_reveal_queue()

    def _advance_reveal_queue(self):
        result = self.last_result
        if not self._reveal_queue:
            self._save_last_roll()
            self._record_roll_history(result)
            return

        stage, was_locked = self._reveal_queue.pop(0)
        if stage == "race":
            if not result.get("race"):
                self.race_slot.set_static("—")
                self.warning_lbl.setText(result.get("warning") or "")
                self._advance_reveal_queue()
            elif was_locked:
                factions = self._factions_for(result["class"], result["race"])
                self.race_slot.set_static(result["race"], color=self._faction_color(factions))
                self._advance_reveal_queue()
            else:
                # Color-tagged pool -- SlotMachine shows each race in
                # its own faction's color while spinning, and reuses
                # the matching entry's color automatically once the
                # plain-name result lands (see spin()'s own docstring).
                pool = self._race_entries_for(result["class"]) or ["—"]
                self.race_slot.spin(pool, result["race"], duration_ms=1500)

    def _clear(self):
        self.last_result = None
        self.lock_class.setChecked(False)
        self.lock_race.setChecked(False)
        self.warning_lbl.setText("")
        self._start_idle()
        save_last_roll(self.config_dir / "last_roll.yaml", None)

    def _manage_classes(self):
        result = open_classes_editor(self, self.classes)
        if result is not None and self.current_ruleset:
            self.classes = result
            save_ruleset(self.rulesets_dir, self.current_ruleset, self.classes)
            if self.class_slot._mode == "idle":
                self.class_slot.start_idle(self._all_class_names() or ["—"])
            if self.race_slot._mode == "idle":
                self.race_slot.start_idle(self._all_race_entries() or ["—"])

    def _open_config_folder(self):
        open_config_folder(self.config_dir)