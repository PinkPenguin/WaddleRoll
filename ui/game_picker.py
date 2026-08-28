"""
ui/game_picker.py

The first screen the user sees: a list of every discovered game module.
Clicking one tells the main window to switch to that module's widget.
Purely generic -- knows nothing about any specific game.

Palette: pink/magenta, matching the PNGN (PinkPenguin) branding.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, Signal

BG = "#F280A1"
CARD_BG = "#20101a"
CARD_HOVER = "#2c1524"
ACCENT = "#ff5fa8"
TEXT = "#f7e4ef"
TEXT_DIM = "#a3708f"


class GameCard(QWidget):
    clicked = Signal()

    def __init__(self, module, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(70)
        self.setStyleSheet(f"""
            GameCard {{
                background-color: {CARD_BG};
                border: none;
                border-radius: 4px;
            }}
            GameCard:hover {{ background-color: {CARD_HOVER}; }}
        """)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        accent = QFrame()
        accent.setFixedWidth(4)
        accent.setStyleSheet(
            f"background-color: {module.accent_color}; border: none; "
            f"border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
        )
        outer.addWidget(accent)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(14, 12, 18, 12)
        text_col.setSpacing(2)

        title = QLabel(f"{module.icon}  {module.display_name}")
        title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: bold; border: none; background: transparent;")
        text_col.addWidget(title)

        subtitle = QLabel(module.description)
        subtitle.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-style: italic; border: none; background: transparent;")
        text_col.addWidget(subtitle)

        outer.addLayout(text_col)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class GamePicker(QWidget):
    game_selected = Signal(str)  # emits the chosen module's id

    def __init__(self, modules, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("🐧 WADDLEROLL")
        title.setStyleSheet(f"color: {TEXT}; font-size: 32px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(title)

        subtitle = QLabel("Choose a game to randomize a build")
        subtitle.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-style: italic;")
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        if not modules:
            empty = QLabel("No game modules found in modules/")
            empty.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
            layout.addWidget(empty)

        for module in modules:
            layout.addWidget(self._make_card(module))

        layout.addStretch(1)

    def _make_card(self, module) -> GameCard:
        card = GameCard(module)
        card.clicked.connect(lambda: self.game_selected.emit(module.id))
        return card