"""
modules/wow/ui.py

Rolls: Class -> Race, cascading (class lands, then race spins) --
unlike Torchlight's independent skill/hero-trait pair, race genuinely
depends on which class was rolled (the eligible race pool comes from
that specific class), so this is a real sequential dependency, same
shape as Grim Dawn's Mastery A -> its own skill list, not a
simultaneous-staggered reveal.

Spec (talent tree) is also class-dependent -- rolled from the chosen
class's own spec list once the class is fixed -- but revealed with a
fade-in (FadeLabel, opacity 0->1) rather than a SlotMachine spin: it's
meant to read as a quiet refinement of the class choice sitting just
beneath it, not a third roll competing for the same attention.

Professions are a separate, unrelated roll -- any class can learn any
profession in real WoW, so this has no dependency on class/race/spec
at all, same relationship PoE1/PoE2's skill + independent ascendancy
roll has. Two independently lockable slots, always exactly 2 PRIMARY
professions (secondary professions are never rolled -- see
roller.py's own docstring for why).

Save/record timing: fires immediately at the end of _do_roll(), not
deferred until the class/race visual cascade finishes landing. This
used to wait for the cascade (mirroring Last Epoch's own queue
pattern), but every other module in this project already saves the
instant roll() returns, since the DATA is fully known regardless of
how long the visual reveal takes -- and extending the old deferred
queue to also track two new, entirely independent profession slots
landing at their own pace would have added real complexity for no
real benefit. The visual cascade itself (class spins, race spins after
it lands) is unchanged -- only when results get written to disk
changed, and it's now simpler, not more complex.

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
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QComboBox, QFrame, QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QPointF, QPropertyAnimation, Signal, QTimer
from PySide6.QtGui import QPainter, QPen, QColor

from modules.wow.roller import (
    discover_rulesets, load_ruleset, save_ruleset, roll, roll_professions, race_factions,
)
from modules.wow.editor import open_classes_editor, open_professions_editor
from ui.slot_machine import SlotMachine, LockToggle
from ui.version_badge import VersionBadge
from ui.config_folder import open_config_folder
from ui.background_widget import BackgroundWidget
from ui.assets import find_module_background
from ui.colors import hex_to_rgba
from ui.last_roll import load_last_roll, save_last_roll
from ui.roll_history import append_roll_history, load_roll_history, open_roll_history_dialog
from ui.manage_menu import open_manage_menu

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
        self.layout.setSpacing(10)

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


class FadeLabel(QWidget):
    """A label that fades in from fully transparent to fully opaque
    over a short duration, rather than just appearing -- used
    specifically for the spec reveal, since a spin/land animation
    (SlotMachine) would be the wrong register for something meant to
    read as a quiet, secondary refinement of the class choice sitting
    just beneath it, not a competing "third roll" fighting for the
    same attention as class/race.

    Optional lock checkbox (show_lock=True) -- spec doesn't use
    SlotMachine, but it's still an independently lockable result like
    every other one in this module, so it gets the same lock mechanism.
    Floating overlay, not a layout sibling: the inner label always
    fills this widget's FULL width regardless of show_lock, so its
    text is always centered on the true center of the row. A
    [label][lock] side-by-side layout (an earlier version of this)
    can't achieve that -- the lock only eats space from the right, so
    the label's own centered point drifts left of the row's true
    center by half the lock's footprint. The checkbox is positioned
    manually in resizeEvent instead, same approach SlotMachine's own
    lock checkbox now uses.

    A QWidget wrapping an inner QLabel, not a QLabel directly -- the
    checkbox needs a widget to overlay ON TOP of. setAlignment/
    setStyleSheet forward to that inner label, so this class's own call
    sites (which style the visible text) work unchanged.

    fade_duration_ms: how long the fade-in itself takes, defaults to
    500ms (unchanged from before this was a parameter).

    fade_delay_ms: how long to wait BEFORE the fade-in starts, separate
    from how long the fade itself takes -- defaults to 0 (no delay,
    unchanged prior behavior). Implemented via a real QTimer instance
    (not the static QTimer.singleShot helper) specifically so a pending
    delayed start can be CANCELLED if set_static() or a fresh
    fade_in_with_text() call comes in before it fires -- otherwise a
    stale delayed fade could still go off later and visually stomp on
    whatever's been shown in the meantime."""

    lock_toggled = Signal(bool)

    def __init__(self, parent=None, show_lock: bool = False, fade_duration_ms: int = 500, fade_delay_ms: int = 2250):
        super().__init__(parent)
        super().setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("")
        layout.addWidget(self._label)

        self._effect = QGraphicsOpacityEffect(self._label)
        self._effect.setOpacity(1.0)
        self._label.setGraphicsEffect(self._effect)
        self._animation = QPropertyAnimation(self._effect, b"opacity", self)
        self._animation.setDuration(fade_duration_ms)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)

        self._fade_delay_ms = fade_delay_ms
        self._delay_timer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.timeout.connect(self._animation.start)

        self.lock_checkbox = None
        if show_lock:
            # Same LockToggle as SlotMachine's own lock -- GOLD (not
            # GOLD_DIM), matching that file's choice of the "prominent"
            # color over the dim one, since LockToggle's own
            # unlocked_opacity already handles being quiet before it's
            # checked, rather than needing a separately dimmer color.
            self.lock_checkbox = LockToggle(color=GOLD, size=14, parent=self)
            self.lock_checkbox.setToolTip("Lock this result so it stays the same on the next roll")
            self.lock_checkbox.toggled.connect(self.lock_toggled.emit)
            self._position_lock_checkbox()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_lock_checkbox()

    def _position_lock_checkbox(self):
        if self.lock_checkbox is None:
            return
        margin = 2
        x = self.width() - self.lock_checkbox.width() - margin
        y = (self.height() - self.lock_checkbox.height()) // 2
        self.lock_checkbox.move(max(0, x), max(0, y))

    def setAlignment(self, alignment):
        self._label.setAlignment(alignment)

    def setStyleSheet(self, style: str):
        self._label.setStyleSheet(style)

    def is_locked(self) -> bool:
        return bool(self.lock_checkbox and self.lock_checkbox.isChecked())

    def set_locked(self, locked: bool):
        if self.lock_checkbox:
            self.lock_checkbox.setChecked(locked)

    def fade_in_with_text(self, text: str):
        self._label.setText(text)
        self._delay_timer.stop()  # cancel any earlier pending delayed start
        self._animation.stop()
        self._effect.setOpacity(0.0)
        if self._fade_delay_ms > 0:
            self._delay_timer.start(self._fade_delay_ms)
        else:
            self._animation.start()

    def set_static(self, text: str):
        """Sets text with no animation -- used for locked/restored
        results, where there's no "just landed" moment to fade in
        from."""
        self._delay_timer.stop()  # cancel any pending delayed fade-in too
        self._animation.stop()
        self._label.setText(text)
        self._effect.setOpacity(1.0)


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
        data = load_ruleset(self.rulesets_dir, self.current_ruleset) if self.current_ruleset else {"classes": [], "professions": []}
        self.classes = data["classes"]
        self.professions = data["professions"]

        self.last_result = None
        self.last_profession_result = None
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

        manage_btn = _tool_button("Manage Config")
        manage_btn.clicked.connect(self._open_manage_config)
        tools.addWidget(manage_btn)

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

        # Class + spec grouped into their own tight sub-layout, separate
        # from the panel's own spacing (which governs gaps BETWEEN
        # sections -- class-group, race, professions). Spec is a sub-
        # detail of the class result, not its own independent section,
        # so it should read as visually closer to class than the gap
        # to race below it.
        class_group = QVBoxLayout()
        class_group.setContentsMargins(0, 0, 0, 0)
        class_group.setSpacing(2)

        self.class_slot = SlotMachine(text_color=TEXT, dim_color=GOLD_DIM, font_family=FONT_FAMILY, compact=True, show_lock=True)
        self.class_slot.finished.connect(self._on_class_landed)
        class_group.addWidget(self.class_slot)

        # Sits close under the class, smaller and dimmer -- a quiet
        # refinement of the class choice, not a competing result.
        self.spec_label = FadeLabel(show_lock=False)
        self.spec_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spec_label.setStyleSheet(f"color: {GOLD_DIM}; background: transparent; font-family: '{FONT_FAMILY}'; font-size: 15px; font-style: italic;")
        class_group.addWidget(self.spec_label)

        panel.layout.addLayout(class_group)

        race_label = QLabel("RACE")
        race_label.setStyleSheet(f"color: {GOLD}; background: transparent; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        panel.layout.addWidget(race_label)

        self.race_slot = SlotMachine(text_color=TEXT, dim_color=GOLD_DIM, font_family=FONT_FAMILY, compact=True, show_lock=True)
        self.race_slot.finished.connect(self._on_race_landed)
        panel.layout.addWidget(self.race_slot)

        profession_label = QLabel("PROFESSIONS")
        profession_label.setStyleSheet(f"color: {GOLD}; background: transparent; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        panel.layout.addWidget(profession_label)

        profession_row = QHBoxLayout()
        profession_row.setSpacing(10)
        self.profession_a_slot = SlotMachine(text_color=TEXT, dim_color=GOLD_DIM, font_family=FONT_FAMILY, compact=True, show_lock=True, current_font_size=22)
        profession_row.addWidget(self.profession_a_slot)
        self.profession_b_slot = SlotMachine(text_color=TEXT, dim_color=GOLD_DIM, font_family=FONT_FAMILY, compact=True, show_lock=True, current_font_size=22)
        profession_row.addWidget(self.profession_b_slot)
        panel.layout.addLayout(profession_row)

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_lbl.setStyleSheet(f"color: {WARN}; background: transparent; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        panel.layout.addWidget(self.warning_lbl)

        panel.layout.addStretch(1)
        root.addWidget(panel, stretch=1)

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

    def _all_profession_names(self) -> list[str]:
        """Idle/spin pool -- only PRIMARY, non-excluded professions,
        matching roll_professions()'s own filtering exactly (secondary
        professions are never shown here since they're never a
        possible result)."""
        return [p["name"] for p in self.professions if not p.get("excluded", False) and p.get("category") == "primary"]

    def _start_idle(self):
        self.class_slot.start_idle(self._all_class_names() or ["—"])
        self.race_slot.start_idle(self._all_race_entries() or ["—"])
        self.spec_label.set_static("")
        self.profession_a_slot.start_idle(self._all_profession_names() or ["—"])
        self.profession_b_slot.start_idle(self._all_profession_names() or ["—"])

    # ── Ruleset switching ────────────────────────────────────────────

    def _on_ruleset_changed(self, name: str):
        if not name or name == self.current_ruleset:
            return
        self.current_ruleset = name
        data = load_ruleset(self.rulesets_dir, self.current_ruleset)
        self.classes = data["classes"]
        self.professions = data["professions"]
        self.last_result = None
        self.last_profession_result = None
        self.class_slot.set_locked(False)
        self.race_slot.set_locked(False)
        self.profession_a_slot.set_locked(False)
        self.profession_b_slot.set_locked(False)
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

        # "roll" key present -> current bundled shape. Its absence
        # means a file saved before professions existed, back when
        # this file WAS the class/race/spec result directly -- handled
        # so an existing user's saved last-roll doesn't just vanish or
        # crash the first time they update.
        if "roll" in saved:
            self.last_result = saved.get("roll")
            self.last_profession_result = saved.get("professions")
        else:
            self.last_result = saved
            self.last_profession_result = None

        if self.last_result:
            self._show_static(self.last_result)
        self._show_static_professions(self.last_profession_result)

    def _save_last_roll(self):
        if not self.settings.get("remember_last_roll", True):
            return
        data = {"roll": self.last_result, "professions": self.last_profession_result}
        save_last_roll(self.config_dir / "last_roll.yaml", data)

    def _record_roll_history(self):
        """Fires immediately at the end of _do_roll -- see the module
        docstring for why this no longer waits on the class/race visual
        cascade. Bundles the class/race/spec roll and the entirely
        independent profession roll into ONE history entry (a history
        entry represents the whole roll someone made from one click of
        Roll, not two separate logs for two separate concerns).
        Records if EITHER half produced a genuine result, same "don't
        require both to succeed" reasoning PoE1/PoE2 already use for
        their own two independent rolls."""
        class_roll_ok = bool(self.last_result and "error" not in self.last_result)
        profession_roll_ok = bool(self.last_profession_result and "error" not in self.last_profession_result)
        if not class_roll_ok and not profession_roll_ok:
            return
        entry = {"roll": self.last_result, "professions": self.last_profession_result}
        append_roll_history(self.config_dir / "roll_history.yaml", entry)

    def _view_history(self):
        history = load_roll_history(self.config_dir / "roll_history.yaml")

        def format_entry(entry: dict) -> str:
            # "roll" key present -> current shape; its absence means an
            # old, pre-professions history entry that WAS the roll dict
            # directly -- same backward-compat handling as restore.
            roll = entry.get("roll", entry) or {}
            race = roll.get("race") or "(no race)"
            spec = roll.get("spec")
            spec_text = f" ({spec})" if spec else ""
            class_race = f"{roll.get('class', '?')}{spec_text} — {race}"

            professions = entry.get("professions")
            prof_text = ""
            if professions and "error" not in professions:
                prof_text = f" | {', '.join(professions['professions'])}"

            return f"{class_race}{prof_text}"

        def restore_entry(entry: dict):
            roll = entry.get("roll", entry) or {}
            self.last_result = roll
            self._show_static(roll)

            self.last_profession_result = entry.get("professions")
            self._show_static_professions(self.last_profession_result)

            self._save_last_roll()

        open_roll_history_dialog(self, "Roll History", history, format_entry, on_restore=restore_entry)

    def _show_static(self, result: dict):
        if "error" in result:
            self.class_slot.set_static("—")
            self.race_slot.set_static("—")
            self.spec_label.set_static("")
            self.warning_lbl.setText(result["error"])
            return
        self.class_slot.set_static(result["class"])
        self._reveal_spec(result, animate=False)
        if result.get("race"):
            factions = self._factions_for(result["class"], result["race"])
            self.race_slot.set_static(result["race"], color=self._faction_color(factions))
        else:
            self.race_slot.set_static("—")
        self.warning_lbl.setText(result.get("warning") or "")

    def _show_static_professions(self, profession_result: dict):
        if profession_result and "error" not in profession_result:
            prof_a, prof_b = profession_result["professions"]
            self.profession_a_slot.set_static(prof_a)
            self.profession_b_slot.set_static(prof_b)
        else:
            self.profession_a_slot.set_static("—")
            self.profession_b_slot.set_static("—")

    def _reveal_spec(self, result: dict, animate: bool):
        """Called once the class itself has settled, whether via an
        instant lock or an actual landed spin -- spec is purely class-
        dependent, so it only makes sense to reveal once the class is
        known, same timing _on_class_landed already uses to kick off
        the race spin. animate=False for the locked/restored case
        (there's no "just landed" moment to fade in from, so it just
        appears, matching how every other locked/restored result in
        this module shows up without animation)."""
        spec = result.get("spec")
        if not spec:
            self.spec_label.set_static("")
            return
        if animate:
            self.spec_label.fade_in_with_text(spec)
        else:
            self.spec_label.set_static(spec)

    def _do_roll(self):
        was_class_locked = bool(self.class_slot.is_locked() and self.last_result and self.last_result.get("class"))
        was_race_locked = bool(self.race_slot.is_locked() and self.last_result and self.last_result.get("race"))

        locked_class = self.last_result.get("class") if was_class_locked else None
        locked_race = self.last_result.get("race") if was_race_locked else None

        # spec is never independently locked -- it's rolled fresh
        # alongside whatever class comes up, locked or not, same
        # reasoning as every other class-dependent value in this
        # module: locking it separately from class would be a
        # confusing state (a locked spec that doesn't even exist on
        # whatever class gets rolled next).
        result = roll(
            self.classes,
            faction_filter=self._current_faction_filter(),
            locked_class=locked_class,
            locked_race=locked_race,
        )
        self.last_result = result

        # Professions: entirely independent of class/race/spec, so this
        # rolls and starts spinning regardless of what happened above
        # -- same "fires on the same Roll click, no ordering
        # dependency" relationship PoE1/PoE2's skill + independent
        # ascendancy roll has.
        prev_professions = self.last_profession_result.get("professions") if (
            self.last_profession_result and "error" not in self.last_profession_result
        ) else None
        was_profession_a_locked = bool(self.profession_a_slot.is_locked() and prev_professions)
        was_profession_b_locked = bool(self.profession_b_slot.is_locked() and prev_professions)
        locked_profession_a = prev_professions[0] if was_profession_a_locked else None
        locked_profession_b = prev_professions[1] if was_profession_b_locked else None

        profession_result = roll_professions(
            self.professions,
            locked_profession_a=locked_profession_a,
            locked_profession_b=locked_profession_b,
        )
        self.last_profession_result = profession_result

        if "error" in profession_result:
            self.profession_a_slot.set_static("—")
            self.profession_b_slot.set_static("—")
        else:
            prof_a, prof_b = profession_result["professions"]
            pool = self._all_profession_names() or ["—"]
            if was_profession_a_locked:
                self.profession_a_slot.set_static(prof_a)
            else:
                self.profession_a_slot.spin(pool, prof_a, duration_ms=1200)
            if was_profession_b_locked:
                self.profession_b_slot.set_static(prof_b)
            else:
                self.profession_b_slot.spin(pool, prof_b, duration_ms=1200)

        if "error" in result:
            self.class_slot.set_static("—")
            self.race_slot.set_static("—")
            self.spec_label.set_static("")
            self.warning_lbl.setText(result["error"])
            self._save_last_roll()
            self._record_roll_history()
            return

        self.warning_lbl.setText("")

        # A locked race (or a class with no eligible races at all) is
        # fully determined the instant roll() returns, regardless of
        # whether class has landed yet -- showing it via start_idle()
        # while waiting for class was the actual bug: idling visually
        # suggests a value is still being randomized, which a locked
        # race isn't. Both cases are handled immediately here, with
        # nothing queued for them -- only a genuinely unlocked race
        # with a real pool to spin from still needs to wait for class.
        race_already_shown = False
        if was_race_locked and result.get("race"):
            factions = self._factions_for(result["class"], result["race"])
            self.race_slot.set_static(result["race"], color=self._faction_color(factions))
            race_already_shown = True
        elif not result.get("race"):
            self.race_slot.set_static("—")
            self.warning_lbl.setText(result.get("warning") or "")
            race_already_shown = True

        self._reveal_queue = [] if race_already_shown else ["race"]

        if was_class_locked:
            self.class_slot.set_static(result["class"])
            self._reveal_spec(result, animate=False)
            self._advance_reveal_queue()
        else:
            self.class_slot.spin(self._all_class_names(), result["class"], duration_ms=1200)
            if not race_already_shown:
                self.race_slot.start_idle(self._all_race_entries() or ["—"])
            self.spec_label.set_static("")  # cleared while class spins, fades in once it lands

        self._save_last_roll()
        self._record_roll_history()

    def _on_class_landed(self, _class_name: str):
        if self.last_result:
            self._reveal_spec(self.last_result, animate=True)
            self._advance_reveal_queue()

    def _on_race_landed(self, _race_name: str):
        if self.last_result:
            self.warning_lbl.setText(self.last_result.get("warning") or "")
            self._advance_reveal_queue()

    def _advance_reveal_queue(self):
        """Purely visual, and now only ever has one real job left: spin
        race once class lands, for the single remaining case that needs
        to wait at all -- an unlocked race with a genuine pool to spin
        from. A locked race, or a class with no eligible races, is
        already fully handled in _do_roll itself with nothing queued,
        so this simply has nothing to do for either of those anymore."""
        result = self.last_result
        if not self._reveal_queue:
            return

        stage = self._reveal_queue.pop(0)
        if stage == "race":
            # Color-tagged pool -- SlotMachine shows each race in
            # its own faction's color while spinning, and reuses
            # the matching entry's color automatically once the
            # plain-name result lands (see spin()'s own docstring).
            pool = self._race_entries_for(result["class"]) or ["—"]
            # Shorter duration and a much shorter fizzle tail than
            # the default -- race is the LAST thing to land in this
            # cascade (starts only once class actually lands, which
            # itself already took ~2.2s including its own fizzle
            # tail), so by the time race reaches ITS fizzle tail,
            # class and both professions have long since gone
            # still. The default fizzle (3 ticks, up to 420ms each,
            # ~1.06s total) has nothing else animating alongside it
            # at that point to share the visual weight with, so it
            # reads as the reel visibly stalling rather than
            # smoothly decelerating -- confirmed by actually
            # computing the real tick schedule, not just guessing.
            # One short tick instead of three long ones keeps a
            # landing feel without the stall.
            # base_interval=90 -- every tick in this schedule now
            # starts already visible (see spin()'s own docstring
            # for the full reasoning): the previous fix (shorter
            # fizzle tail) helped, but the actual remaining issue
            # was the ease-out curve's FRONT end, not just its
            # tail -- most ticks were bunched into speeds too fast
            # to read as distinct movement, which (with nothing
            # else animating alongside race by this point) looked
            # like the reel freezing before a sudden visible catch-
            # up right at the end. Confirmed by computing the full
            # tick-by-tick schedule, not just guessing again.
            self.race_slot.spin(pool, result["race"], duration_ms=1000, fizzle_ticks=1, fizzle_max_interval=280, base_interval=90)

    def _clear(self):
        self.last_result = None
        self.last_profession_result = None
        self.class_slot.set_locked(False)
        self.race_slot.set_locked(False)
        self.profession_a_slot.set_locked(False)
        self.profession_b_slot.set_locked(False)
        self.warning_lbl.setText("")
        self._start_idle()
        save_last_roll(self.config_dir / "last_roll.yaml", None)

    def _manage_classes(self):
        result = open_classes_editor(self, self.classes)
        if result is not None and self.current_ruleset:
            self.classes = result
            save_ruleset(self.rulesets_dir, self.current_ruleset, self.classes, self.professions)
            if self.class_slot._mode == "idle":
                self.class_slot.start_idle(self._all_class_names() or ["—"])
            if self.race_slot._mode == "idle":
                self.race_slot.start_idle(self._all_race_entries() or ["—"])

    def _manage_professions(self):
        result = open_professions_editor(self, self.professions)
        if result is not None and self.current_ruleset:
            self.professions = result
            save_ruleset(self.rulesets_dir, self.current_ruleset, self.classes, self.professions)
            if self.profession_a_slot._mode == "idle":
                self.profession_a_slot.start_idle(self._all_profession_names() or ["—"])
            if self.profession_b_slot._mode == "idle":
                self.profession_b_slot.start_idle(self._all_profession_names() or ["—"])

    def _open_config_folder(self):
        open_config_folder(self.config_dir)

    def _open_manage_config(self):
        """One entry point replacing the old row of one button per
        editor -- picks which specific thing to manage from a short
        list instead. The existing _manage_classes/_manage_professions/
        _open_config_folder methods are unchanged; this just presents
        them differently."""
        open_manage_menu(self, "Manage Config", [
            ("Classes...", self._manage_classes),
            ("Professions...", self._manage_professions),
            ("Open Config Folder", self._open_config_folder),
        ])