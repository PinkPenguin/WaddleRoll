"""
modules/pokemon/module.py

Plugin wrapper connecting the Pokemon screen to the launcher shell.
"""

from pathlib import Path

from core.plugin_base import GameModule
from modules.pokemon.ui import PokemonWidget

MODULE_DIR = Path(__file__).parent
CONFIG_DIR = MODULE_DIR / "config"


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
    default_size = (520, 680)
    min_size = (520, 680)

    def get_widget(self, parent=None):
        return PokemonWidget(config_dir=CONFIG_DIR, parent=parent)