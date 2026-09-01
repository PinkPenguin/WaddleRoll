"""
modules/torchlight_infinite/roller.py

Pure roll logic for Torchlight Infinite. No UI code here.

Roll shape: a flat skill roll by default, plus an optional (off by
default) independent hero-trait roll -- same "two flat, independent
rolls" shape as PoE1/PoE2's skill + ascendancy.

Skills carry tags (e.g. "Spell", "Attack") -- most don't matter for
rolling, but stored anyway since a future hero-trait-scaling match
will need them. No filtering logic on tags here: whether a skill deals
damage at all (Spell/Attack) is handled via excluded=true on the
non-damage skills, not a second filter dimension alongside it (see
CONVENTIONS.md's rule on this).

Heroes carry traits (2-3 each, 12 base heroes), and traits carry tags
too (e.g. an "Attack"-tagged trait presumably scales Attack-tagged
skills) -- same status as skill tags: stored, not yet used for any
matching logic. The roll flattens every non-excluded trait across every
non-excluded hero into one pool and picks directly from that -- hero
grouping is purely how the data's organized/edited, not a two-step
"pick hero then pick trait" roll. Excluding a whole hero removes all
its traits from the pool at once.
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


def load_heroes(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("heroes", [])


def save_heroes(path: Path, heroes: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"heroes": heroes}, f, sort_keys=False, allow_unicode=True)


def load_settings(path: Path) -> dict:
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return {
        "hero_trait_roll_enabled": data.get("hero_trait_roll_enabled", False),
        "remember_last_roll": data.get("remember_last_roll", True),
    }


def save_settings(path: Path, settings: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, sort_keys=False)


# ── Roll logic ───────────────────────────────────────────────────────────

def eligible_skill_pool(skills: list[dict]) -> list[dict]:
    return [s for s in skills if not s.get("excluded", False)]


def roll_skill(skills: list[dict], locked_skill: str | None = None) -> dict:
    """Returns {"skill": str|None, "warning": str|None}."""
    pool = eligible_skill_pool(skills)
    pool_names = [s["name"] for s in pool]

    if not pool_names:
        return {"skill": None, "warning": "No eligible skills -- check exclusions."}

    if locked_skill and locked_skill in pool_names:
        chosen = locked_skill
    else:
        chosen = random.choice(pool_names)

    return {"skill": chosen, "warning": None}


def roll_hero_trait(
    heroes: list[dict],
    locked_hero: str | None = None,
    locked_trait: str | None = None,
) -> dict:
    """
    Returns {"hero": str|None, "trait": str|None, "warning": str|None}.

    Flattens every non-excluded trait across every non-excluded hero
    into one (hero_name, trait_name) pool and picks directly from it --
    not a two-step "pick hero, then pick trait within it" roll. Lock
    matches on the exact (hero, trait) pair from the last result,
    falling back to a fresh random pick if that pair's no longer
    eligible (e.g. excluded since the last roll).
    """
    pool = []
    for hero in heroes:
        if hero.get("excluded", False):
            continue
        for trait in hero.get("traits", []):
            if trait.get("excluded", False):
                continue
            pool.append((hero["name"], trait["name"]))

    if not pool:
        return {"hero": None, "trait": None, "warning": "No eligible hero traits -- check exclusions."}

    if locked_hero and locked_trait and (locked_hero, locked_trait) in pool:
        hero_name, trait_name = locked_hero, locked_trait
    else:
        hero_name, trait_name = random.choice(pool)

    return {"hero": hero_name, "trait": trait_name, "warning": None}