"""
modules/pokemon/module.py

Plugin wrapper connecting the Pokemon screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.fallout4.module import ASSETS_DIR
from modules.pokemon.ui import PokemonWidget
from core.paths import get_app_root

CONFIG_DIR = get_app_root() / "modules" / "pokemon" / "config"
ASSETS_DIR = get_app_root() / "modules" / "pokemon" / "assets"


class Module(GameModule):
    id = "pokemon"
    display_name = "Pokémon"
    description = "Random team roller"

    background_color = "#f2ede3"   # keep in sync with BG in ui.py
    accent_color = "#e3350d"       # keep in sync with ACCENT in ui.py
    icon = "⚡"

    # Unmeasured placeholder -- needs a real sizeHint() measurement once
    # this is running with real data (and once team_size=6 shows all
    # six slot rows at once, which is the tallest the panel ever gets).
    default_size = (700, 620)
    min_size = (700, 620)

    def get_widget(self, parent=None):
        return PokemonWidget(config_dir=CONFIG_DIR, assets_dir=ASSETS_DIR, parent=parent)