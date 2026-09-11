"""
modules/last_epoch/module.py

Plugin wrapper connecting the Last Epoch screen to the launcher shell.
"""

from core.paths import get_app_root

from core.plugin_base import GameModule
from modules.last_epoch.ui import LastEpochWidget

CONFIG_DIR = get_app_root() / "modules" / "last_epoch" / "config"
ASSETS_DIR = get_app_root() / "modules" / "last_epoch" / "assets"


class Module(GameModule):
    id = "last_epoch"
    display_name = "Last Epoch"
    description = "Class + main skill + notable roller"

    background_color = "#160b1a"   # keep in sync with BG in ui.py
    accent_color = "#e0679a"       # keep in sync with PINK in ui.py
    icon = "⏳"

    # Distinct window proportions per-module, per your request
    default_size = (580, 650)
    min_size = (580, 650)

    def get_widget(self, parent=None):
        return LastEpochWidget(config_dir=CONFIG_DIR, assets_dir=ASSETS_DIR, parent=parent)