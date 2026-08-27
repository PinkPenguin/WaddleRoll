"""
modules/grim_dawn/module.py

Plugin wrapper connecting the Grim Dawn screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.grim_dawn.ui import GrimDawnWidget

MODULE_DIR = Path(__file__).parent
CONFIG_DIR = MODULE_DIR / "config"


class Module(GameModule):
    id = "grim_dawn"
    display_name = "Grim Dawn"
    description = "Dual mastery + main skill roller"

    background_color = "#14150f"   # keep in sync with BG in ui.py
    accent_color = "#a68a4c"       # keep in sync with GOLD in ui.py
    icon = "†"

    default_size = (550, 600)
    min_size = (550, 600)

    def get_widget(self, parent=None):
        return GrimDawnWidget(config_dir=CONFIG_DIR, parent=parent)