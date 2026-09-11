"""
modules/last_epoch/ui.py

Last Epoch module screen. Rolls: Class -> main Skill (evenly from the
class's curated list) -> optional Notable (a node tagged notable from that
specific skill's own node list, on by default).

Distinct visual identity per your request: purple/pink + bronze palette
(matches the game's own UI), a serif font instead of the sans-serif used
by Hero Siege/Grim Dawn, and bordered/rounded panels rather than flat
rectangles -- without going overboard on structural differences yet.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QFrame,
)
from PySide6.QtCore import Qt

from modules.last_epoch.roller import load_classes, save_classes, load_settings, save_settings, roll
from modules.last_epoch.editor import open_classes_editor
from ui.version_badge import VersionBadge
from ui.config_folder import open_config_folder
from ui.last_roll import load_last_roll, save_last_roll
from ui.background_widget import BackgroundWidget
from ui.assets import find_module_background
from ui.colors import hex_to_rgba
from ui.slot_machine import SlotMachine

# ── Palette: purple/pink + bronze, matching the game's own UI ───────────
BG        = "#160b1a"
BG_PANEL  = "#241030"
PINK      = "#e0679a"
PINK_DIM  = "#7a3a58"
BRONZE    = "#c08a4e"
BRONZE_DARK = "#7a5230"
TEXT      = "#e8d9e8"
WARN      = "#d99a4e"

FONT_FAMILY = "Georgia"


def _checkbox_qss(text_color: str) -> str:
    return f"""
        QCheckBox {{
            color: {text_color}; background-color: {hex_to_rgba(BG, 230)};
            border: 1px solid {PINK}; border-radius: 6px; padding: 2px 8px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        }}
        QCheckBox::indicator {{
            width: 14px; height: 14px;
            border: 1px solid {PINK}; border-radius: 2px;
            background: transparent;
        }}
        QCheckBox::indicator:checked {{
            background-color: {PINK}; border: 1px solid {PINK};
        }}
    """


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {BRONZE}; max-height: 1px; border: none;")
    return line


def _tool_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {BRONZE}; background-color: {BG};
            border: 1px solid {BRONZE}; border-radius: 3px; padding: 6px 12px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        }}
        QPushButton:hover {{ background-color: {PINK_DIM}; color: {TEXT}; }}
    """)
    return btn


def _action_button(text: str, color: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {color}; background-color: {BG};
            border: 2px solid {color}; border-radius: 4px; padding: 8px 24px;
            font-family: '{FONT_FAMILY}'; font-size: 13px; font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {PINK_DIM}; color: {TEXT}; }}
    """)
    return btn


class LastEpochWidget(QWidget):
    def __init__(self, config_dir: Path, assets_dir: Path = None, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)
        self.setObjectName("last_epoch_root")
        self.setStyleSheet(f"QWidget#last_epoch_root {{ background-color: {BG}; }}")

        bg_path = find_module_background(assets_dir)
        self._background = BackgroundWidget(bg_path, parent=self)
        self._background.setGeometry(self.rect())
        self._background.lower()

        self.classes = load_classes(self.config_dir / "classes.yaml")
        self.settings = load_settings(self.config_dir / "settings.yaml")
        self.last_result = None
        self._reveal_queue = []

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
        root.setSpacing(16)

        title = QLabel("LAST EPOCH — BUILD ROLLER")
        title.setStyleSheet(f"""
            color: {PINK}; background-color: {hex_to_rgba(BG, 230)};
            border: 1px solid {BRONZE}; border-radius: 6px; padding: 4px 14px;
            font-family: '{FONT_FAMILY}'; font-size: 25px; font-weight: bold; letter-spacing: 2px;
        """)
        root.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.version_badge = VersionBadge(self.config_dir, BRONZE, BRONZE, BG, FONT_FAMILY)
        root.addWidget(self.version_badge)

        # Tool row
        tools = QHBoxLayout()
        tools.setSpacing(14)

        self.notable_cb = QCheckBox("Roll Notable")
        self.notable_cb.setChecked(self.settings.get("notables_enabled", True))
        self.notable_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {TEXT}; background-color: {hex_to_rgba(BG, 230)};
                border: 1px solid {PINK}; border-radius: 6px; padding: 2px 8px;
                font-family: '{FONT_FAMILY}'; font-size: 11px;
            }}
            QCheckBox::indicator {{
                width: 14px; height: 14px;
                border: 1px solid {PINK}; border-radius: 2px;
                background: transparent;
            }}
            QCheckBox::indicator:checked {{
                background-color: {PINK}; border: 1px solid {PINK};
            }}
        """)
        self.notable_cb.toggled.connect(self._persist_settings)
        tools.addWidget(self.notable_cb)

        tools.addStretch(1)

        manage_btn = _tool_button("Manage Classes")
        manage_btn.clicked.connect(self._manage_classes)
        tools.addWidget(manage_btn)

        open_folder_btn = _tool_button("Open Config Folder")
        open_folder_btn.clicked.connect(self._open_config_folder)
        tools.addWidget(open_folder_btn)

        root.addLayout(tools)
        root.addWidget(_divider())

        # Output panel -- bordered/rounded, distinct from the flat panels
        # used elsewhere
        panel = QFrame()
        panel.setObjectName("last_epoch_panel")
        panel.setStyleSheet(f"""
            QFrame#last_epoch_panel {{
                background-color: {hex_to_rgba(BG_PANEL, 230)};
                border: 1px solid {BRONZE_DARK};
                border-radius: 10px;
            }}
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(28, 26, 28, 26)
        panel_layout.setSpacing(18)

        self.class_slot = self._build_slot_row(panel_layout, "CLASS")
        self.skill_slot = self._build_slot_row(panel_layout, "MAIN SKILL")
        self.notable_slot = self._build_slot_row(panel_layout, "NOTABLE")

        self.class_slot.finished.connect(self._on_class_landed)
        self.skill_slot.finished.connect(self._on_skill_landed)
        self.notable_slot.finished.connect(self._on_notable_landed)

        self.warning_lbl = QLabel("")
        self.warning_lbl.setWordWrap(True)
        self.warning_lbl.setStyleSheet(f"color: {WARN}; background: transparent; font-family: '{FONT_FAMILY}'; font-size: 11px;")
        panel_layout.addWidget(self.warning_lbl)

        panel_layout.addStretch(1)
        root.addWidget(panel, stretch=1)

        # Lock row
        locks = QHBoxLayout()
        locks.setSpacing(16)
        lock_label = QLabel("LOCK:")
        lock_label.setStyleSheet(f"""
            color: {PINK_DIM}; background-color: {hex_to_rgba(BG, 230)};
            border: 1px solid {PINK}; border-radius: 6px; padding: 2px 8px;
            font-family: '{FONT_FAMILY}'; font-size: 11px;
        """)
        locks.addWidget(lock_label)

        self.lock_class = QCheckBox("Class")
        self.lock_skill = QCheckBox("Skill")
        self.lock_notable = QCheckBox("Notable")
        for cb in (self.lock_class, self.lock_skill, self.lock_notable):
            cb.setStyleSheet(_checkbox_qss(PINK_DIM))
            locks.addWidget(cb)
        locks.addStretch(1)
        root.addLayout(locks)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(14)
        footer.addStretch(1)

        clear_btn = _action_button("Clear", PINK_DIM)
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(clear_btn)

        roll_btn = _action_button("ROLL", PINK)
        roll_btn.clicked.connect(self._do_roll)
        footer.addWidget(roll_btn)

        root.addLayout(footer)

        pool = [c["name"] for c in self.classes if not c.get("excluded", False)]
        self.class_slot.start_idle(pool)
        self.skill_slot.start_idle(self._all_skill_names())
        self.notable_slot.start_idle(self._all_notable_names() or ["—"])

    def _build_slot_row(self, parent_layout, caption_text: str) -> SlotMachine:
        caption = QLabel(caption_text)
        caption.setStyleSheet(f"color: {BRONZE}; background: transparent; font-family: '{FONT_FAMILY}'; font-size: 10px; letter-spacing: 2px;")
        parent_layout.addWidget(caption)

        row_frame = QFrame()
        row_frame.setObjectName("slot_row_frame")
        row_frame.setStyleSheet(f"""
            QFrame#slot_row_frame {{
                background-color: {hex_to_rgba(BG_PANEL, 230)};
                border: 1px solid {BRONZE_DARK};
                border-radius: 8px;
            }}
        """)
        row_layout = QVBoxLayout(row_frame)
        row_layout.setContentsMargins(4, 2, 4, 2)

        slot = SlotMachine(
            text_color=TEXT, dim_color=PINK_DIM, font_family=FONT_FAMILY,
            compact=True, current_font_size=20, min_height=0,
        )
        row_layout.addWidget(slot)
        parent_layout.addWidget(row_frame)
        return slot

    # ── Pools ────────────────────────────────────────────────────────

    def _all_skill_names(self) -> list[str]:
        names = []
        for c in self.classes:
            if c.get("excluded", False):
                continue
            names.extend(s["name"] for s in c.get("skills", []) if not s.get("excluded", False))
        return names

    def _skill_names_for(self, class_name: str) -> list[str]:
        for c in self.classes:
            if c.get("name") == class_name:
                return [s["name"] for s in c.get("skills", []) if not s.get("excluded", False)]
        return []

    def _all_notable_names(self) -> list[str]:
        names = []
        for c in self.classes:
            if c.get("excluded", False):
                continue
            for s in c.get("skills", []):
                if s.get("excluded", False):
                    continue
                names.extend(
                    n["name"] for n in s.get("nodes", [])
                    if n.get("notable", False) and not n.get("excluded", False)
                )
        return names

    def _notable_names_for(self, class_name: str, skill_name: str) -> list[str]:
        for c in self.classes:
            if c.get("name") != class_name:
                continue
            for s in c.get("skills", []):
                if s.get("name") != skill_name:
                    continue
                return [
                    n["name"] for n in s.get("nodes", [])
                    if n.get("notable", False) and not n.get("excluded", False)
                ]
        return []

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

    def _show_static(self, result: dict):
        """Used for restore -- already resolved, nothing to animate."""
        if "error" in result:
            self.class_slot.set_static("—")
            self.skill_slot.set_static("—")
            self.notable_slot.set_static("—")
            self.warning_lbl.setText(result["error"])
            return
        self.class_slot.set_static(result["class"])
        self.skill_slot.set_static(result["skill"] or "(none available)")
        self.notable_slot.set_static(result["notable"] or "—")
        self.warning_lbl.setText(result.get("warning") or "")

    def _do_roll(self):
        was_class_locked = bool(self.lock_class.isChecked() and self.last_result and "class" in self.last_result)
        was_skill_locked = bool(self.lock_skill.isChecked() and self.last_result and "skill" in self.last_result)
        was_notable_locked = bool(self.lock_notable.isChecked() and self.last_result and "notable" in self.last_result)

        locked_class = self.last_result.get("class") if was_class_locked else None
        locked_skill = self.last_result.get("skill") if was_skill_locked else None
        locked_notable = self.last_result.get("notable") if was_notable_locked else None

        result = roll(
            self.classes,
            include_notable=self.notable_cb.isChecked(),
            locked_class=locked_class,
            locked_skill=locked_skill,
            locked_notable=locked_notable,
        )
        self.last_result = result

        if "error" in result:
            self.class_slot.set_static("—")
            self.skill_slot.set_static("—")
            self.notable_slot.set_static("—")
            self.warning_lbl.setText(result["error"])
            self._save_last_roll()
            return

        self.warning_lbl.setText("")

        # Queue holds what's left after the class -- each entry either
        # resolves instantly (locked) and advances itself right away,
        # or spins and waits for its own slot's finished signal.
        self._reveal_queue = [
            ("skill", was_skill_locked),
            ("notable", was_notable_locked),
        ]

        if was_class_locked:
            self.class_slot.set_static(result["class"])
            self._advance_reveal_queue()
        else:
            pool = [c["name"] for c in self.classes if not c.get("excluded", False)]
            self.class_slot.spin(pool, result["class"], duration_ms=1200)
            # Idle the rest so they don't sit showing the previous
            # roll's stale result during the ~1.2s the class spins.
            self.skill_slot.start_idle(self._all_skill_names())
            self.notable_slot.start_idle(self._all_notable_names() or ["—"])

    def _on_class_landed(self, _class_name: str):
        if self.last_result:
            self._advance_reveal_queue()

    def _on_skill_landed(self, _skill_name: str):
        if self.last_result:
            self._advance_reveal_queue()

    def _on_notable_landed(self, _notable_name: str):
        if self.last_result:
            self.warning_lbl.setText(self.last_result.get("warning") or "")
            self._save_last_roll()

    def _advance_reveal_queue(self):
        result = self.last_result
        if not self._reveal_queue:
            self._save_last_roll()
            return

        stage, was_locked = self._reveal_queue.pop(0)

        if stage == "skill":
            if was_locked:
                self.skill_slot.set_static(result["skill"] or "(none available)")
                self._advance_reveal_queue()
            else:
                pool = self._skill_names_for(result["class"]) or self._all_skill_names()
                self.skill_slot.spin(pool, result["skill"] or "(none available)", duration_ms=1800)
                # Notable may not have been idled yet if the class was
                # locked (skipping straight to here) -- idle it now so
                # it doesn't show a stale value while skill spins.
                self.notable_slot.start_idle(self._all_notable_names() or ["—"])

        elif stage == "notable":
            if not self.notable_cb.isChecked():
                self.notable_slot.set_static("—")
                self.warning_lbl.setText(result.get("warning") or "")
                self._advance_reveal_queue()  # queue is empty now -- this saves
            elif was_locked:
                self.notable_slot.set_static(result["notable"] or "—")
                self.warning_lbl.setText(result.get("warning") or "")
                self._advance_reveal_queue()  # queue is empty now -- this saves
            else:
                pool = self._notable_names_for(result["class"], result["skill"]) or ["—"]
                self.notable_slot.spin(pool, result["notable"] or "—", duration_ms=2400)

    def _clear(self):
        self.last_result = None
        self.lock_class.setChecked(False)
        self.lock_skill.setChecked(False)
        self.lock_notable.setChecked(False)
        pool = [c["name"] for c in self.classes if not c.get("excluded", False)]
        self.class_slot.start_idle(pool)
        self.skill_slot.start_idle(self._all_skill_names())
        self.notable_slot.start_idle(self._all_notable_names() or ["—"])
        self.warning_lbl.setText("")
        save_last_roll(self.config_dir / "last_roll.yaml", None)

    def _manage_classes(self):
        result = open_classes_editor(self, self.classes)
        if result is not None:
            self.classes = result
            save_classes(self.config_dir / "classes.yaml", self.classes)
            if self.class_slot._mode == "idle":
                pool = [c["name"] for c in self.classes if not c.get("excluded", False)]
                self.class_slot.start_idle(pool)
            if self.skill_slot._mode == "idle":
                self.skill_slot.start_idle(self._all_skill_names())
            if self.notable_slot._mode == "idle":
                self.notable_slot.start_idle(self._all_notable_names() or ["—"])

    def _persist_settings(self, *_args):
        self.settings = {
            "notables_enabled": self.notable_cb.isChecked(),
            "remember_last_roll": self.settings.get("remember_last_roll", True),
        }
        save_settings(self.config_dir / "settings.yaml", self.settings)

    def _open_config_folder(self):
        open_config_folder(self.config_dir)