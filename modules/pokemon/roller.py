"""
modules/pokemon/roller.py

Pure roll logic for the Pokemon module. No UI code here.

Roll shape: a variable-size team (1-6, stepper-controlled in the UI,
same pattern as FO4's perk count) rolled from a flat, generation-
bounded, fully-evolved-only pool.

"Fully evolved" is derived, not a separate flag: a Pokemon with no
next_evolution set is eligible, one with a next_evolution isn't -- one
source of truth instead of two that could drift apart. excluded still
layers on top as a manual override, same as everywhere else.
previous_evolution is deliberately not modeled -- nothing here needs
it, only "is there a next step" matters for filtering.

Generation cutoff is a UI-level stepper, bounded dynamically by
whatever's actually in the loaded data (max_generation() below) rather
than a hardcoded number, so it scales automatically as more Pokemon
get added without needing a code change.

dex_id is purely a sort/display field, never a lookup key (name is,
same as every other module) -- alternate forms sharing a dex number
with their base species is a non-issue here. Mega evolutions/alternate
forms aren't specially modeled at all, per an explicit "don't care
about these" call -- just more flat entries if they're ever added.
"""

import random
from pathlib import Path

import yaml


# ── Loading / saving ────────────────────────────────────────────────────

def load_pokemon(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("pokemon", [])


def save_pokemon(path: Path, pokemon: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"pokemon": pokemon}, f, sort_keys=False, allow_unicode=True)


def load_settings(path: Path) -> dict:
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return {
        "team_size": data.get("team_size", 6),
        "generation": data.get("generation"),  # None until first saved -- ui.py defaults this to max_generation()
        "remember_last_roll": data.get("remember_last_roll", True),
    }


def save_settings(path: Path, settings: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, sort_keys=False)


# ── Roll logic ───────────────────────────────────────────────────────────

def max_generation(pokemon: list[dict]) -> int:
    """The generation stepper's upper bound -- computed from the real
    loaded data, never hardcoded, so it's always accurate to whatever's
    actually in the roster."""
    gens = [p.get("generation", 1) for p in pokemon]
    return max(gens) if gens else 1


def eligible_pool(pokemon: list[dict], generation: int) -> list[dict]:
    return [
        p for p in pokemon
        if not p.get("excluded", False)
        and not p.get("next_evolution")
        and p.get("generation", 1) <= generation
    ]


def roll_team(
    pokemon: list[dict],
    num_to_roll: int,
    generation: int,
    exclude_names: list[str] | None = None,
) -> dict:
    """
    Rolls num_to_roll NEW team members (i.e. for whichever slots aren't
    currently locked) -- sampling without replacement, so duplicates
    within a single roll are structurally impossible, not just
    unlikely. exclude_names keeps a reroll from picking something
    that's already locked into a different slot on the same team.

    Returns {"rolled": list[str], "warning": str|None}. If the eligible
    pool is smaller than requested, returns everything available with a
    warning instead of erroring -- same "degrade gracefully" shape
    every other module's roll() already uses. Position assignment
    (which specific slot each rolled name lands in) is the UI's job,
    not this function's -- this only guarantees a valid, duplicate-free
    set of new names.
    """
    exclude_names = set(exclude_names or [])
    pool = [p["name"] for p in eligible_pool(pokemon, generation) if p["name"] not in exclude_names]

    if num_to_roll <= 0:
        return {"rolled": [], "warning": None}

    if len(pool) < num_to_roll:
        return {
            "rolled": pool,
            "warning": f"Only {len(pool)} eligible Pokémon available (needed {num_to_roll}).",
        }

    return {"rolled": random.sample(pool, num_to_roll), "warning": None}