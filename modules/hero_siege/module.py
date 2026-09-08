"""
modules/hero_siege/module.py

Plugin wrapper connecting the Hero Siege screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.hero_siege.ui import HeroSiegeWidget
from core.paths import get_app_root

CONFIG_DIR = get_app_root() / "modules" / "hero_siege" / "config"


class Module(GameModule):
    id = "hero_siege"
    display_name = "Hero Siege"
    description = "Class, skill & relic wildcard roller"

    background_color = "#100b0a"   # keep in sync with INK in ui.py
    accent_color = "#8f1616"       # keep in sync with BLOOD in ui.py
    icon = "⚔"

    default_size = (550, 610)
    min_size = (550, 610)

    def get_widget(self, parent=None):
        return HeroSiegeWidget(config_dir=CONFIG_DIR, parent=parent)