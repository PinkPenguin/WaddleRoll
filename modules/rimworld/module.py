"""
modules/rimworld/module.py

Plugin wrapper connecting the RimWorld screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.rimworld.ui import RimworldWidget

MODULE_DIR = Path(__file__).parent
CONFIG_DIR = MODULE_DIR / "config"


class Module(GameModule):
    id = "rimworld"
    display_name = "RimWorld"
    description = "Ideology structure + meme + precept roller"

    background_color = "#1a1a1c"   # keep in sync with BG in ui.py
    accent_color = "#c97b3d"       # keep in sync with ACCENT in ui.py
    icon = "🪐"

    default_size = (750, 680)
    min_size = (750, 680)

    def get_widget(self, parent=None):
        return RimworldWidget(config_dir=CONFIG_DIR, parent=parent)