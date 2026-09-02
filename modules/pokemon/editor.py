"""
modules/pokemon/editor.py

Wires the shared ToggleGridDialog to Pokemon's roster -- wider than
Dota's (8 columns instead of 5, given how much bigger the full species
list is), sortable by Dex # or Name.
"""

from ui.toggle_grid import ToggleGridDialog


def open_pokemon_grid(parent, pokemon: list[dict]):
    dlg = ToggleGridDialog(
        "Manage Pokémon", pokemon, columns=6,
        sort_options={
            "Dex #": lambda p: p.get("dex_id", 0),
            "Name": lambda p: p.get("name", ""),
        },
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None