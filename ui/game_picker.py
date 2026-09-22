"""
ui/game_picker.py

The first screen the user sees: a list of every discovered game module.
Clicking one tells the main window to switch to that module's widget.
Purely generic -- knows nothing about any specific game.

Palette: pink/magenta, matching the PNGN (PinkPenguin) branding.

Layout: card size is FIXED (CARD_WIDTH x CARD_HEIGHT), not derived from
available width -- the window grows to fit as more modules get added,
via increasing column count at fixed tiers (columns_for_count()), not
the other way around. This replaced an earlier version where the card
itself stretched to fill whatever width the layout handed it: harmless
for the flat-color/text cards, but real card art uses crop-to-fill
(KeepAspectRatioByExpanding in GameCard.paintEvent), and the same
source image was cropping completely differently depending on whether
it landed in the single-column strip or the old 2-column grid -- a
layout-dependent bug, not a rendering one. CARD_WIDTH/CARD_HEIGHT now
match the actual generated card art's ratio exactly (3:1, see that
constant's own comment) rather than an arbitrary placeholder -- the
source files themselves are still oversized for a UI card, which is a
separate, already-acknowledged thing to fix on the asset side, not
something this file's display sizing needs to compensate for.

compute_picker_size() is exported so main_window.py can size the
window from actual current module count, the same "measured, not
guessed" principle already applied to every module's own window sizing
-- just applied to the picker shell itself now. Its per-section height
estimates are exactly that, estimates (no way to measure real Qt
layout metrics without actually running the UI) -- worth a real check
against the live app and nudging CHROME_HEIGHT_ESTIMATE if the numbers
turn out to be off in practice.

Either way, the whole card area stays wrapped in a QScrollArea as a
genuine safety net for the case column growth alone can't handle
(module counts large enough that even the top column tier still needs
more rows than reasonably fit on screen) -- not the primary mechanism.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QScrollArea,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QPixmap, QPen, QColor

from core.paths import get_app_root
from core.launcher_settings import load_launcher_visual_settings
from ui.assets import find_asset, find_module_card
from ui.background_widget import BackgroundWidget
from ui.colors import hex_to_rgba

BG = "#F280A1"
CHIP_BG = "#3d1f2e"   # dedicated dark chip color -- BG is the light pink theme itself, reusing it gave title/subtitle chips zero real contrast, just more pink on pink
CARD_BG = "#20101a"
CARD_HOVER = "#2c1524"
ACCENT = "#ff5fa8"
TEXT = "#f7e4ef"
TEXT_DIM = "#a3708f"

# Fixed card size, matching the actual generated card art's ratio
# (2172x724 = exactly 3:1) -- the source files themselves are much
# larger than needed for a UI card (that's a separate, already-
# acknowledged thing to fix on the asset side), but the DISPLAY ratio
# here should match them exactly now that there's a real number,
# rather than the earlier placeholder guess (which happened to land
# close, 3.09:1, but wasn't actually derived from anything).
CARD_WIDTH = 270
CARD_HEIGHT = 90
CARD_GAP = 12

# (max_module_count_for_this_tier, columns) -- checked in order, first
# match wins. Growing in steps rather than one binary switch, so the
# jump from 1 to 2 columns isn't the only transition that ever
# happens as the roster grows over time.
COLUMN_TIERS = [
    (4, 1),
    (10, 2),   # each column's last full row before stepping up -- not just an even number
    (18, 3),   # 16 (the old boundary) would leave 3 columns' last row 1/3 filled at the switch point
    (28, 4),   # same reasoning as above, 25 wasn't a multiple of 4 either
]
MAX_COLUMNS = 5   # beyond the last tier's cap -- QScrollArea covers whatever this still doesn't fit

# Rough estimate of everything in the picker's outer layout that ISN'T
# the card grid itself (margins, logo/title, subtitle, manage-visible-
# games row, inter-widget spacing) -- see module docstring on why this
# is an estimate, not a measurement.
CHROME_HEIGHT_ESTIMATE = 328   # was 360 before margins dropped from 40 to 24 per side (-32 total)
CHROME_WIDTH_ESTIMATE = 68     # was 100 before the same margin change (-32 total)

LAUNCHER_ASSETS_DIR = get_app_root() / "assets"   # top-level, not under any module -- background/logo for the picker itself
WADDLEROLL_PINK = "#F280A1"   # the project's own established brand color, per HANDOFF.md


def columns_for_count(n: int) -> int:
    for max_count, cols in COLUMN_TIERS:
        if n <= max_count:
            return cols
    return MAX_COLUMNS


def compute_picker_size(module_count: int) -> tuple:
    """Window size derived from the fixed card size and however many
    columns/rows the current module count needs -- not a hand-picked
    constant per layout mode. Falls back to at least 1 column/row so
    an empty or tiny module count doesn't compute something degenerate."""
    if module_count <= 0:
        columns, rows = 1, 1
    else:
        columns = columns_for_count(module_count)
        rows = -(-module_count // columns)  # ceil division without importing math

    grid_width = columns * CARD_WIDTH + (columns - 1) * CARD_GAP
    grid_height = rows * CARD_HEIGHT + (rows - 1) * CARD_GAP

    width = grid_width + CHROME_WIDTH_ESTIMATE
    height = grid_height + CHROME_HEIGHT_ESTIMATE
    return (width, height)


class GameCard(QWidget):
    clicked = Signal()
    CORNER_RADIUS = 4

    def __init__(self, module, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)

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
        if self._card_pixmap and not self._card_pixmap.isNull():
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
            painter.end()  # close this painter explicitly before opening a new one below --
                            # Qt only allows one active QPainter per widget at a time
        else:
            super().paintEvent(event)

        self._draw_stroke()

    def _draw_stroke(self):
        """Double stroke on every card, image or text -- a pink outer
        line (WaddleRoll's own established brand color) with a thin
        white line layered just inside it, so every card ties back to
        the app's own identity rather than looking like a random photo
        or a flat color block dropped onto the picker."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        pink_width = 0
        if pink_width > 0:
            pink_pen = QPen(QColor(WADDLEROLL_PINK))
            pink_pen.setWidthF(pink_width)
            painter.setPen(pink_pen)
            inset = pink_width / 2
            painter.drawRoundedRect(
                QRectF(inset, inset, self.width() - 2 * inset, self.height() - 2 * inset),
                self.CORNER_RADIUS, self.CORNER_RADIUS,
            )

        white_width = 2.0
        white_pen = QPen(QColor("#ffffff"))
        white_pen.setWidthF(white_width)
        painter.setPen(white_pen)
        inset2 = pink_width + white_width / 2
        painter.drawRoundedRect(
            QRectF(inset2, inset2, self.width() - 2 * inset2, self.height() - 2 * inset2),
            max(self.CORNER_RADIUS - 2, 0), max(self.CORNER_RADIUS - 2, 0),
        )

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
        self.setObjectName("game_picker_root")
        self.setStyleSheet(f"QWidget#game_picker_root {{ background-color: {BG}; }}")

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
        outer_layout.setContentsMargins(24, 24, 24, 24)
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
            title.setStyleSheet("background: transparent;")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer_layout.addWidget(title)
        else:
            title = QLabel("🐧 WADDLEROLL")
            title.setStyleSheet(f"""
                color: {TEXT}; background-color: {hex_to_rgba(CHIP_BG, 230)};
                border: 1px solid {ACCENT}; border-radius: 8px; padding: 6px 16px;
                font-size: 32px; font-weight: bold; letter-spacing: 1px;
            """)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Choose a game to randomize a build")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"""
            color: {TEXT}; background-color: {hex_to_rgba(CHIP_BG, 230)};
            border: 1px solid {ACCENT}; border-radius: 6px; padding: 3px 12px;
            font-size: 14px; font-style: italic;
        """)
        outer_layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignCenter)

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

        columns = columns_for_count(len(modules))
        grid = QGridLayout(cards_widget)
        grid.setSpacing(CARD_GAP)
        for i, module in enumerate(modules):
            row, col = divmod(i, columns)
            grid.addWidget(self._make_card(module), row, col)

        # Push all rows to the top rather than letting Qt spread them
        # out to fill the scroll area's viewport when there's more
        # vertical space than the grid actually needs -- same ceil
        # division compute_picker_size uses, so this lines up with
        # whatever row count the window was actually sized for.
        final_row = -(-len(modules) // columns)
        grid.setRowStretch(final_row, 1)

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