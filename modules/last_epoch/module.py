"""
modules/last_epoch/module.py

Plugin wrapper connecting the Last Epoch screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.last_epoch.ui import LastEpochWidget

MODULE_DIR = Path(__file__).parent
CONFIG_DIR = MODULE_DIR / "config"


class Module(GameModule):
    id = "last_epoch"
    display_name = "Last Epoch"
    description = "Class + main skill + notable roller"

    background_color = "#160b1a"   # keep in sync with BG in ui.py
    accent_color = "#e0679a"       # keep in sync with PINK in ui.py
    icon = "⏳"

    # Distinct window proportions per-module, per your request
    default_size = (580, 600)
    min_size = (580, 600)

    def get_widget(self, parent=None):
        return LastEpochWidget(config_dir=CONFIG_DIR, parent=parent)