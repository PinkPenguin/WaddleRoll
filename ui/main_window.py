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
from ui.game_picker import GamePicker, MULTI_COLUMN_THRESHOLD

BG = "#F280A1"
PICKER_DEFAULT_SIZE = (420, 620)     # single column
PICKER_GRID_SIZE = (720, 620)        # 2-column grid -- needs real width, not just the single-column size stretched
PICKER_MIN_SIZE = (420, 480)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WaddleRoll, A build randomizer")
        self.setMinimumSize(*PICKER_MIN_SIZE)
        self.setStyleSheet(f"background-color: {BG};")

        self.modules = {m.id: m for m in discover_modules()}
        self._module_pages = {}  # id -> QWidget, built lazily on first visit

        self.resize(*self._picker_size())

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.picker = GamePicker(list(self.modules.values()))
        self.picker.game_selected.connect(self._open_module)
        self.stack.addWidget(self.picker)  # index 0

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
        return PICKER_GRID_SIZE if len(self.modules) > MULTI_COLUMN_THRESHOLD else PICKER_DEFAULT_SIZE

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