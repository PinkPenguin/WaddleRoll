"""
ui/background_widget.py

Paints a background image scaled to genuinely COVER its entire area --
uniform scale (never distorted/stretched), overflow cropped -- same
behavior as CSS's background-size: cover, which plain QSS has no
equivalent for at all. Shared because the cropping math is identical
for every module that uses this; only the actual image differs.

Meant to sit as the bottom-most child in a module's widget, manually
kept the same size as its parent (see resizeEvent in the module that
uses it) and lowered to the back of the paint order -- it doesn't
manage any layout of its own, real content just gets placed on top of
it normally.

If image_path is None (a module with no custom art yet -- these are
being rolled out one at a time), this paints nothing at all, so a
caller can construct it unconditionally and just let it be a no-op
until real art exists.
"""

from pathlib import Path

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import Qt


class BackgroundWidget(QWidget):
    def __init__(self, image_path: Path | None, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap(str(image_path)) if image_path else QPixmap()
        # Never intercept clicks/hover -- this sits behind real content
        # and should be functionally invisible to interaction.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)