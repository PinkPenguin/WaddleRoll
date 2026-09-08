"""
modules/poe2/module.py

Plugin wrapper connecting the PoE2 screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.poe2.ui import PoE2Widget
from core.paths import get_app_root

CONFIG_DIR = get_app_root() / "modules" / "poe2" / "config"


class Module(GameModule):
    id = "poe2"
    display_name = "Path of Exile 2"
    description = "Skill gem + optional ascendancy roller"

    background_color = "#170d0a"   # keep in sync with BG in ui.py
    accent_color = "#c9a227"       # keep in sync with GOLD in ui.py
    icon = "💎"

    default_size = (480, 640)
    min_size = (480, 640)

    def get_widget(self, parent=None):
        return PoE2Widget(config_dir=CONFIG_DIR, parent=parent)