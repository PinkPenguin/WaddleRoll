"""
modules/hero_siege/module.py

Plugin wrapper connecting the Hero Siege screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.hero_siege.ui import HeroSiegeWidget

MODULE_DIR = Path(__file__).parent
CONFIG_DIR = MODULE_DIR / "config"


class Module(GameModule):
    id = "hero_siege"
    display_name = "Hero Siege"
    description = "Class, skill & relic wildcard roller"

    background_color = "#150c08"   # keep in sync with BG in ui.py
    accent_color = "#ff8c3a"       # keep in sync with ORANGE in ui.py
    icon = "⚔"

    default_size = (800, 500)
    min_size = (800, 500)

    def get_widget(self, parent=None):
        return HeroSiegeWidget(config_dir=CONFIG_DIR, parent=parent)