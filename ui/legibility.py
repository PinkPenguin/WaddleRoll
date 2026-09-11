"""
ui/legibility.py

Keeps text readable over an arbitrary, uncontrolled background image --
a soft, zero-offset dark drop shadow directly behind text acts like a
halo/outline, holding up against busy art without needing an opaque
box behind it at all. Same QGraphicsDropShadowEffect mechanism already
used for SlotMachine's landing glow, just tuned for legibility instead
of a colored flourish: dark, centered, soft-edged rather than a
bright, offset glow.

Deliberately NOT a blanket rule or anything automatic -- applied one
widget at a time, same reasoning as making transparency explicit
per-widget rather than via a descendant selector: nothing here should
make a decision on behalf of a widget that might want different
treatment later.
"""

from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget
from PySide6.QtGui import QColor


def add_legibility_shadow(widget: QWidget, color: str = "#000000", blur_radius: int = 5) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setColor(QColor(color))
    shadow.setBlurRadius(blur_radius)
    shadow.setOffset(0, 0)
    widget.setGraphicsEffect(shadow)