"""
modules/fallout4/roller.py

Pure roll logic for the Fallout 4 module -- ported unchanged from the
original fo4_randomizer.py. No UI code lives here, same as before.
The only thing removed is the CLI main() loop, since the GUI is now
the only way this gets driven.
"""

import random

STATS = ["STR", "PER", "END", "CHA", "INT", "AGI", "LCK"]

WEAPON_GROUPS = {
    "Ballistic": [
        {"name": "Semi-automatic Rifle", "min_stats": {"PER": 3}},
        {"name": "Automatic Rifle",       "min_stats": {"PER": 3}},
        {"name": "Pistol",                "min_stats": {"PER": 2}},
        {"name": "Semi-automatic Shotgun","min_stats": {"STR": 2}},
        {"name": "Automatic Shotgun",     "min_stats": {"STR": 3}},
    ],
    "Energy": [
        {"name": "Semi-auto Energy Rifle", "min_stats": {"PER": 3, "INT": 2}},
        {"name": "Automatic Energy Rifle", "min_stats": {"PER": 3, "INT": 2}},
        {"name": "Energy Pistol",          "min_stats": {"PER": 2, "INT": 2}},
    ],
    "Melee": [
        {"name": "Light Melee", "min_stats": {"STR": 2, "AGI": 3}},
        {"name": "Heavy Melee", "min_stats": {"STR": 4, "END": 2}},
        {"name": "Unarmed",     "min_stats": {"STR": 3, "AGI": 2, "END": 2}},
    ],
    "Heavy": [
        {"name": "Heavy Ballistic", "min_stats": {"STR": 5}},
        {"name": "Heavy Energy",    "min_stats": {"STR": 5, "INT": 2}},
        {"name": "Flamer",          "min_stats": {"STR": 4, "END": 2}},
    ],
    "Explosives": [
        {"name": "Thrown Explosives", "min_stats": {"PER": 2}},
        {"name": "Heavy Rocket",      "min_stats": {"STR": 4, "PER": 2}},
        {"name": "Fat Man",           "min_stats": {"STR": 5}},
    ],
}

SPECIAL_CATEGORIES = {
    "Named":        0.7,
    "UltraHeavy":   0.1,
    "Pipe Weapons": 0.2,
}

NAMED_WEAPONS = [
    {"name": "Deliverer",               "type": "Pistol",                 "dlc": None},
    {"name": "Cryolator",               "type": "Energy Pistol",          "dlc": None},
    {"name": "Tesla Rifle",             "type": "Automatic Energy Rifle", "dlc": "Automatron"},
    {"name": "Broadsider",              "type": "Heavy Ballistic",        "dlc": None},
    {"name": "Lorenzo's Artifact",      "type": "Energy Pistol",          "dlc": None},
    {"name": "Prototype UP77",          "type": "Semi-auto Energy Rifle", "dlc": None},
    {"name": "Good Intentions",         "type": "Semi-auto Energy Rifle", "dlc": None},
    {"name": "Aeternus",                "type": "Heavy Energy",           "dlc": "Nuka-World"},
    {"name": "Death From Above",        "type": "Heavy Rocket",           "dlc": None},
    {"name": "2076 World Series Bat",   "type": "Heavy Melee",            "dlc": None},
    {"name": "Kremvh's Tooth",          "type": "Light Melee",            "dlc": None},
    {"name": "Shem Drowne Sword",       "type": "Light Melee",            "dlc": None},
    {"name": "Tinker Tom Special",      "type": "Semi-automatic Rifle",   "dlc": None},
    {"name": "The Problem Solver",      "type": "Automatic Rifle",        "dlc": "Nuka-World"},
    {"name": "December's Child",        "type": "Automatic Rifle",        "dlc": "Far Harbor"},
    {"name": "Salvaged Assaultron Head","type": "Heavy Energy",           "dlc": "Automatron"},
    {"name": "Flare Gun",               "type": "Semi-auto Energy Rifle", "dlc": None},
    {"name": "Junk Jet",                "type": "Heavy Ballistic",        "dlc": None},
    {"name": "Syringer",                "type": "Pistol",                 "dlc": None},
    {"name": "Railway Rifle",           "type": "Semi-automatic Rifle",   "dlc": None},
    {"name": "Ripper",                  "type": "Light Melee",            "dlc": None},
]

ULTRA_HEAVY = [
    {"name": "Fat Man", "type": "Fat Man"},
]

WEAPON_TAGS = {
    "Semi-automatic Rifle":  ["gun", "non-auto rifle", "suppressor"],
    "Automatic Rifle":       ["gun", "suppressor"],
    "Pistol":                ["gun", "suppressor"],
    "Semi-automatic Shotgun":["gun", "suppressor"],
    "Automatic Shotgun":     ["gun", "suppressor"],

    "Semi-auto Energy Rifle":["gun", "non-auto rifle"],
    "Automatic Energy Rifle":["gun"],
    "Energy Pistol":         ["gun"],

    "Light Melee":  ["melee"],
    "Heavy Melee":  ["melee"],
    "Unarmed":      ["melee"],

    "Heavy Ballistic": ["gun"],
    "Heavy Energy":    ["gun"],
    "Flamer":          ["gun"],

    "Thrown Explosives": ["explosive"],
    "Heavy Rocket":      ["explosive"],
    "Fat Man":           ["explosive"],

    "Pipe Weapons": ["gun", "suppressor"],
}

UTILITY_PERKS = {
    "Armorer":     {"STR": 1},
    "Strong Back": {"STR": 3},
    "Steady Aim":  {"STR": 4},
    "Basher":      {"STR": 5},
    "Rooted":      {"STR": 6},
    "Pain Train":  {"STR": 7},

    "Pickpocket":        {"PER": 1},
    "Awareness":         {"PER": 1},
    "Locksmith":         {"PER": 1},
    "Night Person":      {"PER": 3},
    "Sniper":            {"PER": 5},
    "Penetrator":        {"PER": 6},
    "Concentrated Fire": {"PER": 7},

    "Life Giver":          {"END": 1},
    "Toughness":           {"END": 1},
    "Lead Belly":          {"END": 1},
    "Chem Resistant":      {"END": 1},
    "Aquaboy":             {"END": 2},
    "Rad Resistant":       {"END": 3},
    "Adamantium Skeleton": {"END": 4},
    "Cannibal":            {"END": 5},
    "Ghoulish":            {"END": 6},
    "Solar Powered":       {"END": 7},

    "Lone Wanderer": {"CHA": 1},
    "Cap Collector": {"CHA": 1},
    "Attack Dog":    {"CHA": 1},
    "Animal Friend": {"CHA": 2},
    "Local Leader":  {"CHA": 3},
    "Inspiration":   {"CHA": 5},

    "Idiot Savant":      {"INT": 1},
    "Gun Nut":           {"INT": 1},
    "Hacker":            {"INT": 1},
    "Medic":             {"INT": 1},
    "Scrapper":          {"INT": 2},
    "Science":           {"INT": 3},
    "Chemist":           {"INT": 4},
    "Robotics Expert":   {"INT": 5},
    "Nuclear Physicist": {"INT": 6},
    "Nerd Rage":         {"INT": 7},

    "Sneak":           {"AGI": 1},
    "Mister Sandman":  {"AGI": 1},
    "Action Boy/Girl": {"AGI": 2},
    "Moving Target":   {"AGI": 3},
    "Ninja":           {"AGI": 4},
    "Quick Hands":     {"AGI": 5},
    "Gun Fu":          {"AGI": 7},

    "Mysterious Stranger":  {"LCK": 1},
    "Four Leaf Clover":     {"LCK": 6},
    "Ricochet":             {"LCK": 7},
    "Fortune Finder":       {"LCK": 1},
    "Scrounger":            {"LCK": 1},
    "Better Criticals":     {"LCK": 3},
    "Critical Banker":      {"LCK": 4},
    "Grim Reaper's Sprint": {"LCK": 5},
}

PERK_REQUIRES = {
    "Mister Sandman":    ["suppressor"],
    "Sniper":            ["non-auto rifle"],
    "Penetrator":        ["gun"],
    "Concentrated Fire": ["gun"],
    "Steady Aim":        ["gun"],
    "Basher":            ["gun"],
    "Gun Fu":            ["gun"],
    "Quick Hands":       ["gun"],
    "Rooted":            ["gun", "melee"],
}

SPECIAL_WEIGHT = 1.01
WEIGHT_PENALTY = 0.5
WEIGHT_BONUS = 0.4
SPECIAL_ROLL_CHANCE = 0.1

POINTS_TO_DISTRIBUTE = 21
MAX_STAT = 10


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


def _normalize_weapon(weapon):
    if isinstance(weapon, str):
        return {"name": weapon, "type": weapon}
    weapon = dict(weapon)
    if "type" not in weapon:
        weapon["type"] = weapon["name"]
    return weapon


def roll_weapon(special, named_weapons=None, weapon_groups=None, allow_special=True):
    """
    weapon_groups: optional dict restricting which groups can be rolled
                   (defaults to the full WEAPON_GROUPS).
    allow_special: if False, forces a normal group roll (0% special chance)
                   instead of mutating SPECIAL_ROLL_CHANCE globally.
    """
    pool = named_weapons if named_weapons is not None else NAMED_WEAPONS
    groups = weapon_groups if weapon_groups is not None else WEAPON_GROUPS
    special_chance = SPECIAL_ROLL_CHANCE if allow_special else 0.0

    if random.random() < special_chance:
        category = random.choices(
            list(SPECIAL_CATEGORIES.keys()),
            weights=list(SPECIAL_CATEGORIES.values()),
        )[0]

        if category == "Named" and pool:
            weapon = random.choice(pool)
            return {
                "category": category,
                "group": None,
                "weapon": _normalize_weapon(weapon),
            }
        elif category == "Pipe Weapons":
            weapon = {"name": "Pipe Weapon Only", "type": "Pipe Weapons"}
        else:
            weapon = random.choice(ULTRA_HEAVY)

        return {
            "category": category,
            "group": None,
            "weapon": _normalize_weapon(weapon),
        }

    group = random.choice(list(groups.keys()))
    weapons = groups[group]

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
        "group": group,
        "weapon": _normalize_weapon(chosen),
    }


def _weapon_tags_for(weapon_type):
    return WEAPON_TAGS.get(weapon_type, [])


def _perk_weight(perk, min_stats, special):
    weight = 1.0
    for stat, min_val in min_stats.items():
        surplus = special.get(stat, 0) - min_val
        weight *= max(0.05, 1.0 + WEIGHT_BONUS * surplus)
    return weight


def roll_utility_perks(special, weapon_type, num_perks=1):
    weapon_tags = _weapon_tags_for(weapon_type)

    weighted_perks = []
    weights = []

    for perk, min_stats in UTILITY_PERKS.items():
        if perk in PERK_REQUIRES:
            required = PERK_REQUIRES[perk]
            if not any(tag in weapon_tags for tag in required):
                continue

        weight = _perk_weight(perk, min_stats, special)
        weighted_perks.append(perk)
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
