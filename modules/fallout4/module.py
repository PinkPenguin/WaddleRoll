"""
modules/fallout4/module.py

Implements the GameModule contract for Fallout 4. This is the only file
the launcher's discovery system looks for -- it just needs a class named
`Module` that returns a widget when asked.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.fallout4.ui import FO4Widget

MODULE_DIR = Path(__file__).parent
CONFIG_DIR = MODULE_DIR / "config"


class Module(GameModule):
    id = "fallout4"
    display_name = "Fallout 4"
    description = "SPECIAL, weapon & perk ironman roller"
    background_color = "#0f1a10"
    default_size = (700, 650)
    min_size = (700, 650)
    accent_color = "#4aff91"
    icon = "☢"

    def get_widget(self, parent=None):
        return FO4Widget(config_dir=CONFIG_DIR, parent=parent)