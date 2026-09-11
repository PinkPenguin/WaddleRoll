"""
modules/torchlight_infinite/module.py

Plugin wrapper connecting the Torchlight Infinite screen to the
launcher shell.
"""

from core.paths import get_app_root

from core.plugin_base import GameModule
from modules.torchlight_infinite.ui import TorchlightInfiniteWidget

CONFIG_DIR = get_app_root() / "modules" / "torchlight_infinite" / "config"
ASSETS_DIR = get_app_root() / "modules" / "torchlight_infinite" / "assets"


class Module(GameModule):
    id = "torchlight_infinite"
    display_name = "Torchlight Infinite"
    description = "Skill + optional hero-trait roller"

    background_color = "#0a0e18"   # keep in sync with BG in ui.py
    accent_color = "#2ee6d6"       # keep in sync with ACCENT in ui.py
    icon = "🔥"

    # Unmeasured placeholder -- needs a real sizeHint() measurement once
    # this is running with real data, same gap every new module starts
    # with (see the measure-script approach used for PoE2/PoE1).
    default_size = (630, 650)
    min_size = (630, 650)

    def get_widget(self, parent=None):
        return TorchlightInfiniteWidget(config_dir=CONFIG_DIR, assets_dir=ASSETS_DIR, parent=parent)