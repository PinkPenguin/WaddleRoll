"""
ui/game_picker.py

The first screen the user sees: a list of every discovered game module.
Clicking one tells the main window to switch to that module's widget.
Purely generic -- knows nothing about any specific game.

Palette: pink/magenta, matching the PNGN (PinkPenguin) branding.

Layout: a single column while there aren't too many modules, switching
automatically to a 2-column grid past MULTI_COLUMN_THRESHOLD -- not a
manual toggle, since the person expects to keep every module visible
rather than hiding most of them, so the layout itself needs to handle
"many visible modules" gracefully rather than depending on a
visibility toggle keeping the count low. Either way, the whole card
area is wrapped in a QScrollArea now (it wasn't before) as a safety net
-- this shouldn't need to be perfectly tuned forever as more modules
get added later.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QScrollArea,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPixmap

from core.paths import get_app_root
from core.launcher_settings import load_launcher_visual_settings
from ui.assets import find_asset, find_module_card
from ui.background_widget import BackgroundWidget

BG = "#F280A1"
CARD_BG = "#20101a"
CARD_HOVER = "#2c1524"
ACCENT = "#ff5fa8"
TEXT = "#f7e4ef"
TEXT_DIM = "#a3708f"

MULTI_COLUMN_THRESHOLD = 6   # switch from 1 column to a grid once more than this many modules are visible
GRID_COLUMNS = 2

LAUNCHER_ASSETS_DIR = get_app_root() / "assets"   # top-level, not under any module -- background/logo for the picker itself


class GameCard(QWidget):
    clicked = Signal()
    CORNER_RADIUS = 4

    def __init__(self, module, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(70)

        assets_dir = get_app_root() / "modules" / module.id / "assets"
        card_image = find_module_card(assets_dir)

        self._card_pixmap = QPixmap(str(card_image)) if card_image else None

        if self._card_pixmap:
            # Image-only card, per the "everything's in the image, no
            # text/icon/description needed" decision -- paints the
            # crop-to-fill art directly rather than embedding a
            # BackgroundWidget child, since there's nothing else
            # layered on top of it that would need keeping separate.
            self.setStyleSheet("GameCard { border: none; border-radius: 4px; }")
        else:
            self._build_text_card(module)

    def paintEvent(self, event):
        if not self._card_pixmap or self._card_pixmap.isNull():
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Clip to the same rounded-corner shape the text-based cards
        # already use, so an image card doesn't look inconsistent
        # sitting next to one that hasn't gotten art yet.
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.CORNER_RADIUS, self.CORNER_RADIUS)
        painter.setClipPath(path)

        scaled = self._card_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)

    def _build_text_card(self, module):
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
    manage_visibility_requested = Signal()  # "Manage Visible Games" clicked -- MainWindow owns the actual dialog/rebuild

    def __init__(self, modules, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG};")

        launcher_visuals = load_launcher_visual_settings()

        # No-op until assets/background.png (or .jpg) exists at the app
        # root -- same pattern as every module's own background, so
        # this is always safe to construct regardless of whether real
        # art has been added yet.
        bg_path = None if launcher_visuals["ignore_background"] else find_asset(LAUNCHER_ASSETS_DIR, "background")
        self._background = BackgroundWidget(bg_path, parent=self)
        self._background.setGeometry(self.rect())
        self._background.lower()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(40, 40, 40, 40)
        outer_layout.setSpacing(12)

        # Logo image replaces the plain emoji+text title when present --
        # unlike a module's own title (which stays as text even once a
        # background exists), the picker is the actual brand identity
        # screen, so a real logo graphic is worth swapping in here
        # specifically.
        logo_path = None if launcher_visuals["ignore_logo"] else find_asset(LAUNCHER_ASSETS_DIR, "logo")
        if logo_path:
            logo_pixmap = QPixmap(str(logo_path))
            if logo_pixmap.width() > 360 or logo_pixmap.height() > 140:
                logo_pixmap = logo_pixmap.scaled(
                    360, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            title = QLabel()
            title.setPixmap(logo_pixmap)
        else:
            title = QLabel("🐧 WADDLEROLL")
            title.setStyleSheet(f"color: {TEXT}; font-size: 32px; font-weight: bold; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer_layout.addWidget(title)

        subtitle = QLabel("Choose a game to randomize a build")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-style: italic;")
        outer_layout.addWidget(subtitle)

        manage_row = QHBoxLayout()
        manage_row.addStretch(1)
        manage_btn = QPushButton("Manage Visible Games")
        manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manage_btn.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_DIM}; background-color: transparent;
                border: none; padding: 2px; font-size: 10px;
            }}
            QPushButton:hover {{ color: {TEXT}; text-decoration: underline; }}
        """)
        manage_btn.clicked.connect(self.manage_visibility_requested.emit)
        manage_row.addWidget(manage_btn)
        manage_row.addStretch(1)
        outer_layout.addLayout(manage_row)

        outer_layout.addSpacing(16)

        if not modules:
            empty = QLabel("No game modules found in modules/")
            empty.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
            outer_layout.addWidget(empty)
            return

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        cards_widget = QWidget()
        cards_widget.setStyleSheet("background: transparent;")

        if len(modules) > MULTI_COLUMN_THRESHOLD:
            grid = QGridLayout(cards_widget)
            grid.setSpacing(12)
            for i, module in enumerate(modules):
                row, col = divmod(i, GRID_COLUMNS)
                grid.addWidget(self._make_card(module), row, col)
        else:
            col_layout = QVBoxLayout(cards_widget)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(12)
            for module in modules:
                col_layout.addWidget(self._make_card(module))
            col_layout.addStretch(1)

        scroll.setWidget(cards_widget)
        outer_layout.addWidget(scroll, stretch=1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._background.setGeometry(self.rect())

    def showEvent(self, event):
        # Same fix as every module -- resizeEvent alone isn't reliable
        # here, since Qt's resize() is a no-op (fires no event at all)
        # if the target size happens to already match the current one.
        super().showEvent(event)
        self._background.setGeometry(self.rect())

    def _make_card(self, module) -> GameCard:
        card = GameCard(module)
        card.clicked.connect(lambda: self.game_selected.emit(module.id))
        return card