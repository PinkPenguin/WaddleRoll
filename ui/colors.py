"""
ui/colors.py

hex_to_rgba() converts a "#RRGGBB" string into a QSS rgba(r, g, b, a)
string. QSS's rgba() functional syntax is reliably supported across Qt
versions; the 8-digit hex-with-alpha extension some CSS dialects
support has had spottier support in Qt specifically, so this sticks to
the functional form.

Built for making result panels translucent instead of fully opaque, so
a module's own background art shows through underneath rather than
being blocked by a flat color -- the art itself is expected to carry a
darkened/higher-contrast zone where a panel sits, with this alpha tint
only providing a light unifying assist on top of that, not doing the
legibility work by itself.
"""


def hex_to_rgba(hex_color: str, alpha: int) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"