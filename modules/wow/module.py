"""
modules/wow/module.py

Plugin wrapper connecting the WoW class/race roller to the launcher
shell.
"""

from core.paths import get_app_root

from core.plugin_base import GameModule
from modules.wow.ui import WowWidget

CONFIG_DIR = get_app_root() / "modules" / "wow" / "config"
ASSETS_DIR = get_app_root() / "modules" / "wow" / "assets"


class Module(GameModule):
    id = "wow"
    display_name = "World of Warcraft"
    description = "Class + race roller, multiple rulesets"

    background_color = "#141110"   # keep in sync with BG in ui.py
    accent_color = "#c9a84c"       # keep in sync with GOLD in ui.py
    icon = "⚔️"

    default_size = (540, 680)
    min_size = (540, 680)

    def get_widget(self, parent=None):
        return WowWidget(config_dir=CONFIG_DIR, assets_dir=ASSETS_DIR, parent=parent)