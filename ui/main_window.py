"""
ui/main_window.py

The shell's main window. Owns a QStackedWidget with:
  index 0 -> the game picker
  index 1+ -> one page per discovered game module

Back navigation just flips the stack back to index 0. This file has zero
game-specific knowledge -- everything about a game lives in its own module.
"""

from PySide6.QtWidgets import (
    QMainWindow, QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
)
from PySide6.QtCore import Qt

from core.discovery import discover_modules
from core.launcher_settings import load_hidden_module_ids, save_hidden_module_ids
from ui.game_picker import GamePicker, MULTI_COLUMN_THRESHOLD
from ui.module_visibility import open_module_visibility_dialog

BG = "#F280A1"
PICKER_DEFAULT_SIZE = (420, 620)     # single column
PICKER_GRID_SIZE = (720, 620)        # 2-column grid -- needs real width, not just the single-column size stretched
PICKER_MIN_SIZE = (420, 700)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WaddleRoll, A build randomizer")
        self.setMinimumSize(*PICKER_MIN_SIZE)
        self.setStyleSheet(f"background-color: {BG};")

        self.modules = {m.id: m for m in discover_modules()}
        self._module_pages = {}  # id -> QWidget, built lazily on first visit
        self.hidden_module_ids = load_hidden_module_ids()

        self.resize(*self._picker_size())

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.picker = self._build_picker()
        self.stack.addWidget(self.picker)  # index 0

    def _visible_modules(self) -> list:
        return [m for m in self.modules.values() if m.id not in self.hidden_module_ids]

    def _build_picker(self) -> GamePicker:
        picker = GamePicker(self._visible_modules())
        picker.game_selected.connect(self._open_module)
        picker.manage_visibility_requested.connect(self._manage_visibility)
        return picker

    def _manage_visibility(self):
        result = open_module_visibility_dialog(self, list(self.modules.values()), self.hidden_module_ids)
        if result is None:
            return
        self.hidden_module_ids = result
        save_hidden_module_ids(self.hidden_module_ids)

        old_picker = self.picker
        self.picker = self._build_picker()
        self.stack.removeWidget(old_picker)
        self.stack.insertWidget(0, self.picker)
        old_picker.deleteLater()
        self.stack.setCurrentWidget(self.picker)
        self.resize(*self._picker_size())

    def _open_module(self, module_id: str):
        module = self.modules[module_id]

        if module_id not in self._module_pages:
            page = self._wrap_with_back_button(module.get_widget(), module.background_color)
            self._module_pages[module_id] = page
            self.stack.addWidget(page)

        self.setMinimumSize(*module.min_size)
        self.resize(*module.default_size)
        self.stack.setCurrentWidget(self._module_pages[module_id])

    def _show_picker(self):
        self.setMinimumSize(*PICKER_MIN_SIZE)
        self.resize(*self._picker_size())
        self.stack.setCurrentWidget(self.picker)

    def _picker_size(self) -> tuple:
        return PICKER_GRID_SIZE if len(self._visible_modules()) > MULTI_COLUMN_THRESHOLD else PICKER_DEFAULT_SIZE

    def _wrap_with_back_button(self, module_widget: QWidget, background_color: str) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet(f"background-color: {background_color};")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(12, 8, 12, 0)
        back_btn = QPushButton("← Back to games")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(
            "QPushButton { color: #8888a0; background: transparent; border: none; font-size: 11px; }"
            "QPushButton:hover { color: #e4e4f0; }"
        )
        back_btn.clicked.connect(self._show_picker)
        bar.addWidget(back_btn)
        bar.addStretch(1)
        layout.addLayout(bar)

        layout.addWidget(module_widget, stretch=1)
        return wrapper