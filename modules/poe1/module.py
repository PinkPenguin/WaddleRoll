"""
modules/poe1/module.py

Plugin wrapper connecting the PoE1 screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.poe1.ui import PoE1Widget

MODULE_DIR = Path(__file__).parent
CONFIG_DIR = MODULE_DIR / "config"


class Module(GameModule):
    id = "poe1"
    display_name = "Path of Exile"
    description = "Skill gem + optional ascendancy roller"

    background_color = "#0b0b0c"   # keep in sync with BG in ui.py
    accent_color = "#9a9d9f"       # keep in sync with ACCENT in ui.py
    icon = "🗡️"

    # Unmeasured placeholder -- now structurally close to PoE2's own
    # layout (skill roll + ascendancy roll), so borrowing PoE2's real
    # measured size as a starting guess. Still needs its own real
    # sizeHint() measurement once there's actual skill/class data loaded
    # -- don't trust this number as final.
    default_size = (480, 660)
    min_size = (480, 660)

    def get_widget(self, parent=None):
        return PoE1Widget(config_dir=CONFIG_DIR, parent=parent)