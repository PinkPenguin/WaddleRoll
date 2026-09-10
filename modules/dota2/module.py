"""
modules/dota2/module.py

Plugin wrapper connecting the Dota 2 screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.dota2.ui import Dota2Widget
from core.paths import get_app_root

CONFIG_DIR = get_app_root() / "modules" / "dota2" / "config"
ASSETS_DIR = get_app_root() / "modules" / "dota2" / "assets"


class Module(GameModule):
    id = "dota2"
    display_name = "Dota 2"
    description = "Hero roller"

    background_color = "#0a0c14"   # keep in sync with BG in ui.py
    accent_color = "#4d7dff"       # keep in sync with ACCENT in ui.py
    icon = "🛡️"

    # Unmeasured placeholder -- needs a real sizeHint() measurement once
    # this is running with real data.
    default_size = (480, 620)
    min_size = (480, 620)

    def get_widget(self, parent=None):
        return Dota2Widget(config_dir=CONFIG_DIR, assets_dir=ASSETS_DIR, parent=parent)