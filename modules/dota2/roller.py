"""
modules/dota2/roller.py

Pure roll logic for Dota 2. No UI code here.

Roll shape: a single flat hero roll -- no secondary role roll, since
the person already has a roll-off mechanic with friends for that. A
1-5 (+ maybe jungle) viable-roles list per hero is a real future idea,
not built yet -- would need real data and a design pass of its own
when it happens.

Per-hero notes are a separate, persistent concept from the roll itself
-- a hero can have several *named* builds (e.g. "Support", "Core"),
each with its own general + item notes, not just one blob per hero.
See load_notes/save_notes/get_builds_for_hero/save_builds_for_hero
below. Lazily populated at both levels: a hero only gets an entry once
they have at least one saved build, and builds are just a plain list
the person names and edits themselves.
"""

import random
from pathlib import Path

import yaml


# ── Loading / saving ────────────────────────────────────────────────────

def load_heroes(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("heroes", [])


def save_heroes(path: Path, heroes: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"heroes": heroes}, f, sort_keys=False, allow_unicode=True)


def load_notes(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("notes", [])


def save_notes(path: Path, notes: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"notes": notes}, f, sort_keys=False, allow_unicode=True)


def get_builds_for_hero(notes: list[dict], hero_name: str) -> list[dict]:
    """Returns this hero's list of named builds, or an empty list if
    they have none saved yet -- callers don't need to special-case
    'first time'."""
    for n in notes:
        if n.get("hero") == hero_name:
            return n.get("builds", [])
    return []


def save_builds_for_hero(notes: list[dict], hero_name: str, builds: list[dict]) -> list[dict]:
    """Updates the existing hero entry's build list in place, or
    creates a new hero entry if this is their first saved build -- a
    hero only ever appears in notes.yaml once they actually have at
    least one build, same lazy-population idea as before, just one
    level deeper now (hero -> list of named builds, not hero -> one
    blob)."""
    for n in notes:
        if n.get("hero") == hero_name:
            n["builds"] = builds
            return notes
    notes.append({"hero": hero_name, "builds": builds})
    return notes


def load_settings(path: Path) -> dict:
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return {
        "remember_last_roll": data.get("remember_last_roll", True),
    }


def save_settings(path: Path, settings: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, sort_keys=False)


# ── Roll logic ───────────────────────────────────────────────────────────

def roll_hero(heroes: list[dict], locked_hero: str | None = None) -> dict:
    """Returns {"hero": str|None, "warning": str|None}."""
    pool = [h["name"] for h in heroes if not h.get("excluded", False)]

    if not pool:
        return {"hero": None, "warning": "No eligible heroes -- check exclusions."}

    if locked_hero and locked_hero in pool:
        chosen = locked_hero
    else:
        chosen = random.choice(pool)

    return {"hero": chosen, "warning": None}