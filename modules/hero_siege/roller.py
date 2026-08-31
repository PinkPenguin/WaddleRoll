"""
modules/hero_siege/roller.py

Pure roll logic for Hero Siege. No UI code here.

Roll shape:
  - Pick a random enabled class.
  - Normal mode: pick 1 non-excluded skill from that class's full skill
    list (all 18, tree number is just metadata for display).
  - Wildcard mode (chance-based, toggleable): roll a relic instead. The
    relic pool is filtered to relics sharing at least one tag with the
    chosen class. If no enabled class among all of them has a tag-matching
    relic, falls back to a normal skill roll and reports which classes
    were tried, so tagging mistakes are easy to spot.

No passive/buff-style category flags -- deliberately kept to one signal
(excluded) for what should or shouldn't come up, plus an optional
ignore_exclusions override for an occasional "roll from everything"
pass, rather than proliferating separate category tags to maintain.
"""

import random
from pathlib import Path

import yaml


# ── Loading / saving ────────────────────────────────────────────────────

def load_classes(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("classes", [])


def save_classes(path: Path, classes: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"classes": classes}, f, sort_keys=False, allow_unicode=True)


def load_relics(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("relics", [])


def save_relics(path: Path, relics: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"relics": relics}, f, sort_keys=False, allow_unicode=True)


def load_settings(path: Path) -> dict:
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return {
        "wildcard_enabled": data.get("wildcard_enabled", True),
        "wildcard_chance": data.get("wildcard_chance", 0.12),
        "ignore_exclusions": data.get("ignore_exclusions", False),
        "remember_last_roll": data.get("remember_last_roll", True),
    }


def save_settings(path: Path, settings: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, sort_keys=False)


# ── Roll logic ───────────────────────────────────────────────────────────

def _roll_skill(chosen_class: dict, ignore_exclusions: bool = False) -> str | None:
    pool = [
        s["name"] for s in chosen_class.get("skills", [])
        if ignore_exclusions or not s.get("excluded", False)
    ]
    if not pool:
        return None
    return random.choice(pool)


UNIVERSAL_TAG = "universal"  # relics with this tag fit every class (pure stat sticks, no element)


def _norm_tags(tags: list[str]) -> set[str]:
    """Lowercases and trims tags before comparing, so 'Fire' and 'fire'
    (or a stray trailing space from hand-editing) still match instead of
    silently never overlapping."""
    return {t.strip().lower() for t in tags if t.strip()}


def _roll_relic(chosen_class: dict, relics: list[dict], ignore_exclusions: bool = False) -> str | None:
    class_tags = _norm_tags(chosen_class.get("tags", []))
    pool = [
        r["name"] for r in relics
        if (ignore_exclusions or not r.get("excluded", False))
        and (UNIVERSAL_TAG in _norm_tags(r.get("tags", [])) or _norm_tags(r.get("tags", [])) & class_tags)
    ]
    if not pool:
        return None
    return random.choice(pool)


def roll(classes: list[dict], relics: list[dict], wildcard_enabled: bool, wildcard_chance: float, ignore_exclusions: bool = False) -> dict:
    """
    Returns a dict:
      {"class": str, "mode": "skill"|"relic", "result": str|None,
       "warning": str|None, "skipped_classes": list[str]}
    or {"error": str} if nothing is rollable at all.

    ignore_exclusions bypasses every excluded=true check uniformly --
    classes, skills, and relics alike -- for an occasional "roll from
    everything" pass, e.g. rediscovering something you'd previously
    excluded.
    """
    enabled_classes = classes if ignore_exclusions else [c for c in classes if not c.get("excluded", False)]
    if not enabled_classes:
        return {"error": "No classes enabled. Check Manage Classes."}

    do_wildcard = wildcard_enabled and random.random() < wildcard_chance

    if not do_wildcard:
        chosen_class = random.choice(enabled_classes)
        skill = _roll_skill(chosen_class, ignore_exclusions)
        warning = None if skill else f"No non-excluded skills available for {chosen_class['name']}."
        return {
            "class": chosen_class["name"], "mode": "skill", "result": skill,
            "warning": warning, "skipped_classes": [],
        }

    # Wildcard: try every enabled class (in random order) until one has a
    # tag-matching relic. This is "re-roll a different class until one
    # matches" rather than randomly repeating classes forever.
    shuffled = enabled_classes[:]
    random.shuffle(shuffled)
    skipped = []
    for chosen_class in shuffled:
        relic = _roll_relic(chosen_class, relics, ignore_exclusions)
        if relic is not None:
            return {
                "class": chosen_class["name"], "mode": "relic", "result": relic,
                "warning": None, "skipped_classes": skipped,
            }
        skipped.append(chosen_class["name"])

    # No enabled class had a matching relic anywhere -- fall back to a
    # normal skill roll and report every class that was tried, so a
    # tagging mistake is easy to track down.
    chosen_class = random.choice(enabled_classes)
    skill = _roll_skill(chosen_class, ignore_exclusions)
    return {
        "class": chosen_class["name"], "mode": "skill", "result": skill,
        "warning": (
            f"No relic tag matches found for any of the {len(shuffled)} enabled "
            f"class(es) — rolled a normal skill for {chosen_class['name']} instead. "
            f"Check your relic/class tags."
        ),
        "skipped_classes": skipped,
    }