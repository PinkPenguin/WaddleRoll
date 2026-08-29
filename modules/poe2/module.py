"""
modules/poe2/module.py

Plugin wrapper connecting the PoE2 screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.poe2.ui import PoE2Widget

MODULE_DIR = Path(__file__).parent
CONFIG_DIR = MODULE_DIR / "config"


class Module(GameModule):
    id = "poe2"
    display_name = "Path of Exile 2"
    description = "Skill gem + optional ascendancy roller"

    background_color = "#0d0705"   # keep in sync with BG in ui.py
    accent_color = "#c9a227"       # keep in sync with GOLD in ui.py
    icon = "💎"

    default_size = (560, 560)
    min_size = (480, 500)

    def get_widget(self, parent=None):
        return PoE2Widget(config_dir=CONFIG_DIR, parent=parent)