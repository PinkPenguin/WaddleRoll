"""
modules/grim_dawn/module.py

Plugin wrapper connecting the Grim Dawn screen to the launcher shell.
"""

from core.paths import get_app_root

from core.plugin_base import GameModule
from modules.grim_dawn.ui import GrimDawnWidget

CONFIG_DIR = get_app_root() / "modules" / "grim_dawn" / "config"


class Module(GameModule):
    id = "grim_dawn"
    display_name = "Grim Dawn"
    description = "Dual mastery + main skill roller"

    background_color = "#0e1210"   # keep in sync with IRON in ui.py
    accent_color = "#7a3420"       # keep in sync with RUST in ui.py
    icon = "†"

    default_size = (550, 600)
    min_size = (550, 600)

    def get_widget(self, parent=None):
        return GrimDawnWidget(config_dir=CONFIG_DIR, parent=parent)