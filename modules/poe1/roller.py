"""
modules/poe1/roller.py

Pure roll logic for PoE1. No UI code here.

Same engine, same skill-roll mechanics as PoE2's roller.py -- PoE1
skills carry is_vaal_skill, is_item_skill, and is_ascendancy_skill flags,
same three flags as PoE2. Unlike PoE2, there's no separate
classes.yaml/roll_ascendancy() -- PoE1 has no independent ascendancy
*class* roll here, only the skill-level flag.
"""

import random
from pathlib import Path

import yaml


# ── Loading / saving ────────────────────────────────────────────────────

def load_skills(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("skills", [])


def save_skills(path: Path, skills: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"skills": skills}, f, sort_keys=False, allow_unicode=True)


def load_classes(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("classes", [])


def save_classes(path: Path, classes: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"classes": classes}, f, sort_keys=False, allow_unicode=True)


def load_settings(path: Path) -> dict:
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return {
        "allow_vaal_skills": data.get("allow_vaal_skills", True),
        "allow_item_skills": data.get("allow_item_skills", True),
        "allow_ascendancy_skills": data.get("allow_ascendancy_skills", True),
        "ascendancy_roll_enabled": data.get("ascendancy_roll_enabled", False),
        "remember_last_roll": data.get("remember_last_roll", True),
    }


def save_settings(path: Path, settings: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, sort_keys=False)


# ── Roll logic ───────────────────────────────────────────────────────────

def eligible_skill_pool(
    skills: list[dict],
    allow_vaal_skills: bool = True,
    allow_item_skills: bool = True,
    allow_ascendancy_skills: bool = True,
) -> list[dict]:
    pool = []
    for s in skills:
        if s.get("excluded", False):
            continue
        if s.get("is_vaal_skill", False) and not allow_vaal_skills:
            continue
        if s.get("is_item_skill", False) and not allow_item_skills:
            continue
        if s.get("is_ascendancy_skill", False) and not allow_ascendancy_skills:
            continue
        pool.append(s)
    return pool


def roll_skill(
    skills: list[dict],
    allow_vaal_skills: bool = True,
    allow_item_skills: bool = True,
    allow_ascendancy_skills: bool = True,
    locked_skill: str | None = None,
) -> dict:
    """
    Returns {"skill": str|None, "pool_names": list[str], "warning": str|None}.
    pool_names is the full eligible pool at roll time -- kept for parity
    with PoE2's return shape even though ui.py recomputes colored entries
    separately (same pattern PoE2 uses, for the same reason: this stays
    UI-agnostic).
    """
    pool = eligible_skill_pool(skills, allow_vaal_skills, allow_item_skills, allow_ascendancy_skills)
    pool_names = [s["name"] for s in pool]

    if not pool_names:
        return {"skill": None, "pool_names": [], "warning": "No eligible skills -- check filters/exclusions."}

    if locked_skill and locked_skill in pool_names:
        chosen = locked_skill
    else:
        chosen = random.choice(pool_names)

    return {"skill": chosen, "pool_names": pool_names, "warning": None}


def roll_ascendancy(classes: list[dict], locked_class: str | None = None, locked_ascendancy: str | None = None) -> dict:
    """
    Returns {"class": str, "ascendancy": str|None, "warning": str|None}
    or {"error": str} if no classes are enabled. Identical logic to
    PoE2's roll_ascendancy() -- same game engine, same class/ascendancy
    relationship.
    """
    enabled = [c for c in classes if not c.get("excluded", False)]
    if not enabled:
        return {"error": "No classes enabled. Check Manage Classes."}

    by_name = {c["name"]: c for c in enabled}
    if locked_class and locked_class in by_name:
        chosen_class = by_name[locked_class]
    else:
        chosen_class = random.choice(enabled)

    enabled_asc = [a for a in chosen_class.get("ascendancies", []) if not a.get("excluded", False)]
    if not enabled_asc:
        return {"class": chosen_class["name"], "ascendancy": None, "warning": f"No non-excluded ascendancies for {chosen_class['name']}."}

    asc_names = {a["name"] for a in enabled_asc}
    if locked_ascendancy and locked_ascendancy in asc_names:
        ascendancy = locked_ascendancy
    else:
        ascendancy = random.choice(enabled_asc)["name"]

    return {"class": chosen_class["name"], "ascendancy": ascendancy, "warning": None}