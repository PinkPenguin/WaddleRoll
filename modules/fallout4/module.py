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
    description = "S.P.E.C.I.A.L, weapon & perk ironman roller"

    background_color = "#0a0f0a"   # keep in sync with BG in ui.py
    accent_color = "#4aff91"       # keep in sync with GREEN in ui.py
    icon = "☢"

    # Measured via sizeHint() rather than guessed
    default_size = (1100, 690)
    min_size = (1100, 690)

    def get_widget(self, parent=None):
        return FO4Widget(config_dir=CONFIG_DIR, parent=parent)