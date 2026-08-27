"""
modules/last_epoch/roller.py

Pure roll logic for Last Epoch. No UI code here.

Roll shape (per your current manual process):
  - Roll a class from the enabled pool (no mastery step for now).
  - Roll 1 main skill, evenly, from that class's curated non-excluded
    skill list.
  - Optionally (on by default) roll a "Notable" -- a tree node tagged
    notable: true from the skill's own node list. Notables are the ones
    that fundamentally reshape how a skill behaves. All tree nodes (not
    just notables) can be nested under a skill via "nodes" -- only ones
    tagged notable: true are ever eligible to roll, so dumping a skill's
    entire tree in is fine; nothing needs curating out except which
    notables you don't want to build around (via excluded: true).

No unique-item wildcard for now, per your call -- the data model doesn't
need to anticipate it structurally since it'd be a separate, independent
roll step if added later (same shape as Hero Siege's relic wildcard).
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


def load_settings(path: Path) -> dict:
    if not Path(path).exists():
        return {"notables_enabled": True}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {"notables_enabled": data.get("notables_enabled", True)}


def save_settings(path: Path, settings: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings, f, sort_keys=False)


# ── Roll logic ───────────────────────────────────────────────────────────

def roll(
    classes: list[dict],
    include_notable: bool = True,
    locked_class: str | None = None,
    locked_skill: str | None = None,
    locked_notable: str | None = None,
) -> dict:
    """
    Returns:
      {"class": str, "skill": str|None, "notable": str|None, "warning": str|None}
    or {"error": str} if no classes are enabled.

    locked_* params let the UI pin any of the three results across a
    re-roll, same pattern as Grim Dawn.
    """
    enabled_classes = [c for c in classes if not c.get("excluded", False)]
    if not enabled_classes:
        return {"error": "No classes enabled. Check Manage Classes."}

    classes_by_name = {c["name"]: c for c in enabled_classes}
    if locked_class and locked_class in classes_by_name:
        chosen_class = classes_by_name[locked_class]
    else:
        chosen_class = random.choice(enabled_classes)

    enabled_skills = [s for s in chosen_class.get("skills", []) if not s.get("excluded", False)]
    if not enabled_skills:
        return {
            "class": chosen_class["name"], "skill": None, "notable": None,
            "warning": f"No non-excluded skills available for {chosen_class['name']}.",
        }

    skills_by_name = {s["name"]: s for s in enabled_skills}
    if locked_skill and locked_skill in skills_by_name:
        skill = skills_by_name[locked_skill]
    else:
        skill = random.choice(enabled_skills)

    notable = None
    warning = None

    if include_notable:
        eligible_notables = [
            sp for sp in skill.get("nodes", [])
            if sp.get("notable", False) and not sp.get("excluded", False)
        ]
        notable_names = {sp["name"] for sp in eligible_notables}
        if locked_notable and locked_notable in notable_names:
            notable = locked_notable
        elif eligible_notables:
            notable = random.choice(eligible_notables)["name"]
        else:
            warning = f"No notables tagged for {skill['name']} yet."

    return {
        "class": chosen_class["name"],
        "skill": skill["name"],
        "notable": notable,
        "warning": warning,
    }