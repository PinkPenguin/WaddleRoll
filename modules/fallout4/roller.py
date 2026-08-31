"""
modules/fallout4/roller.py

Pure roll logic for the Fallout 4 module. Weapon groups, named weapons,
utility perks, and weapon-type tags are now loaded from config/*.yaml
instead of being hardcoded here -- editable via the in-app Manage
dialogs or by hand, same pattern as the other modules.

STATS, numeric tuning knobs (weight/penalty constants, special-roll
chance), and the tiny fixed pools (SPECIAL_CATEGORIES, ULTRA_HEAVY) stay
as plain constants -- they're not curated content pools the way weapons/
perks are, so an editor for them isn't warranted.
"""

import random
from pathlib import Path

import yaml

STATS = ["STR", "PER", "END", "CHA", "INT", "AGI", "LCK"]

SPECIAL_CATEGORIES = {
    "Named":        0.7,
    "UltraHeavy":   0.1,
    "Pipe Weapons": 0.2,
}

ULTRA_HEAVY = [
    {"name": "Fat Man", "type": "Fat Man"},
]

SPECIAL_WEIGHT = 1.01
WEIGHT_PENALTY = 0.5
WEIGHT_BONUS = 0.4
SPECIAL_ROLL_CHANCE = 0.1

POINTS_TO_DISTRIBUTE = 21
MAX_STAT = 10


# ── Loading / saving ────────────────────────────────────────────────────

def load_weapon_groups(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("groups", [])


def save_weapon_groups(path: Path, groups: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"groups": groups}, f, sort_keys=False, allow_unicode=True)


def load_named_weapons(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("named_weapons", [])


def save_named_weapons(path: Path, weapons: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"named_weapons": weapons}, f, sort_keys=False, allow_unicode=True)


def load_utility_perks(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("perks", [])


def save_utility_perks(path: Path, perks: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"perks": perks}, f, sort_keys=False, allow_unicode=True)


def load_weapon_tags(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("weapon_tags", [])


def save_weapon_tags(path: Path, tags: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"weapon_tags": tags}, f, sort_keys=False, allow_unicode=True)


def load_settings(path: Path) -> dict:
    """FO4 had no persisted settings before remember_last_roll was added
    -- every other toggle (varied stats, allow special, DLC, weapon
    groups, perk count) reset on every launch too. This now covers all
    of them. active_group_names is None until saved once -- meaning
    "every group active," matching the original hardcoded default -- a
    saved list means exactly those groups were checked last time."""
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return {
        "remember_last_roll": data.get("remember_last_roll", True),
        "varied_stats": data.get("varied_stats", True),
        "allow_special": data.get("allow_special", True),
        "dlc_far_harbor": data.get("dlc_far_harbor", True),
        "dlc_nuka_world": data.get("dlc_nuka_world", True),
        "dlc_automatron": data.get("dlc_automatron", True),
        "num_perks": data.get("num_perks", 1),
        "active_group_names": data.get("active_group_names", None),
    }


def save_settings(path: Path, settings: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, sort_keys=False)


# ── SPECIAL roll ─────────────────────────────────────────────────────────

def generate_special(skew=False):
    special = {stat: 1 for stat in STATS}
    for _ in range(POINTS_TO_DISTRIBUTE):
        if skew:
            weights = [special[stat] ** SPECIAL_WEIGHT for stat in STATS]
            chosen_stat = random.choices(STATS, weights=weights)[0]
        else:
            chosen_stat = random.choice(STATS)

        while special[chosen_stat] >= MAX_STAT:
            if skew:
                weights = [special[stat] ** SPECIAL_WEIGHT for stat in STATS]
                chosen_stat = random.choices(STATS, weights=weights)[0]
            else:
                chosen_stat = random.choice(STATS)

        special[chosen_stat] += 1
    return special


# ── Weapon roll ──────────────────────────────────────────────────────────

def _normalize_weapon(weapon):
    if isinstance(weapon, str):
        return {"name": weapon, "type": weapon}
    weapon = dict(weapon)
    if "type" not in weapon:
        weapon["type"] = weapon["name"]
    return weapon


def roll_weapon(special, named_weapons, weapon_groups, allow_special=True, active_group_names=None):
    """
    named_weapons: list of dicts (name, type, dlc, excluded) -- excluded
                   entries are always skipped; DLC filtering is expected
                   to already be applied by the caller (same as before).
    weapon_groups: list of dicts {"name":..., "weapons":[...]}, each
                   weapon a dict with name/min_stats/excluded.
    active_group_names: optional set restricting which groups are
                   eligible (defaults to every group in weapon_groups).
    allow_special: if False, forces a normal group roll (0% special
                   chance) instead of mutating global state.
    """
    pool = [w for w in named_weapons if not w.get("excluded", False)]
    groups = [
        g for g in weapon_groups
        if active_group_names is None or g["name"] in active_group_names
    ]
    special_chance = SPECIAL_ROLL_CHANCE if allow_special else 0.0

    if random.random() < special_chance:
        category = random.choices(
            list(SPECIAL_CATEGORIES.keys()),
            weights=list(SPECIAL_CATEGORIES.values()),
        )[0]

        if category == "Named" and pool:
            weapon = random.choice(pool)
            return {"category": category, "group": None, "weapon": _normalize_weapon(weapon)}
        elif category == "Pipe Weapons":
            weapon = {"name": "Pipe Weapon Only", "type": "Pipe Weapons"}
        else:
            weapon = random.choice(ULTRA_HEAVY)

        return {"category": category, "group": None, "weapon": _normalize_weapon(weapon)}

    if not groups:
        return {"category": "Normal", "group": None, "weapon": None}

    chosen_group = random.choice(groups)
    weapons = [w for w in chosen_group.get("weapons", []) if not w.get("excluded", False)]

    if not weapons:
        return {"category": "Normal", "group": chosen_group["name"], "weapon": None}

    weapon_weights = []
    for w in weapons:
        min_stats = w.get("min_stats", {})
        weight = 1.0
        for stat, min_val in min_stats.items():
            shortfall = max(0, min_val - special.get(stat, 0))
            weight *= WEIGHT_PENALTY ** shortfall
        weapon_weights.append(weight)

    chosen = random.choices(weapons, weights=weapon_weights)[0]
    return {
        "category": "Normal",
        "group": chosen_group["name"],
        "weapon": _normalize_weapon(chosen),
    }


# ── Perk roll ────────────────────────────────────────────────────────────

def _tags_for_weapon_type(weapon_type: str, weapon_tags: list[dict]) -> list[str]:
    for wt in weapon_tags:
        if wt.get("name") == weapon_type:
            return wt.get("tags", [])
    return []


def _perk_weight(min_stats: dict, special: dict) -> float:
    weight = 1.0
    for stat, min_val in min_stats.items():
        surplus = special.get(stat, 0) - min_val
        weight *= max(0.05, 1.0 + WEIGHT_BONUS * surplus)
    return weight


def roll_utility_perks(special, weapon_type, perks: list[dict], weapon_tags: list[dict], num_perks=1):
    """
    perks: list of dicts (name, min_stats, requires, excluded).
    weapon_tags: list of dicts (name, tags) mapping a weapon type to its
                 combat tags, used to check each perk's `requires` list.
    """
    tags = _tags_for_weapon_type(weapon_type, weapon_tags)

    weighted_perks = []
    weights = []

    for perk in perks:
        if perk.get("excluded", False):
            continue
        required = perk.get("requires", [])
        if required and not any(tag in tags for tag in required):
            continue

        weight = _perk_weight(perk.get("min_stats", {}), special)
        weighted_perks.append(perk["name"])
        weights.append(weight)

    num_perks = min(num_perks, len(weighted_perks))
    chosen = []
    for _ in range(num_perks):
        pick = random.choices(weighted_perks, weights=weights)[0]
        idx = weighted_perks.index(pick)
        chosen.append(pick)
        weighted_perks.pop(idx)
        weights.pop(idx)

    return chosen