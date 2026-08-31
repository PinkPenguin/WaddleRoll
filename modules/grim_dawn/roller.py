"""
modules/grim_dawn/roller.py

Pure roll logic for Grim Dawn. No UI code here.

Roll shape:
  - Roll mastery A from the enabled pool.
  - Roll 1 non-excluded "main skill" from mastery A's curated skill list
    (the build-defining active you commit to).
  - Roll mastery B from the remaining enabled pool (can't repeat A).
    No skill is rolled for B -- it's the secondary/support mastery,
    skills there are picked manually in-game around A's build.

No devotion/constellation system here per your call -- masteries + one
main skill only.
"""

import random
from pathlib import Path

import yaml


# ── Loading / saving ────────────────────────────────────────────────────

def load_masteries(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("masteries", [])


def save_masteries(path: Path, masteries: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"masteries": masteries}, f, sort_keys=False, allow_unicode=True)


def load_settings(path: Path) -> dict:
    """Grim Dawn had no persisted settings before this -- every toggle
    just reset on launch. This introduces the file for remember_last_roll
    specifically; nothing else got retrofitted to persist."""
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

def _roll_skill(mastery: dict) -> str | None:
    pool = [s["name"] for s in mastery.get("skills", []) if not s.get("excluded", False)]
    if not pool:
        return None
    return random.choice(pool)


def roll(
    masteries: list[dict],
    locked_mastery_a: str | None = None,
    locked_skill: str | None = None,
    locked_mastery_b: str | None = None,
) -> dict:
    """
    Returns:
      {"mastery_a": str, "skill": str|None, "mastery_b": str, "warning": str|None}
    or {"error": str} if fewer than 2 masteries are enabled, or the locked
    mastery has no other enabled mastery left to pair with.

    locked_* params let the UI pin any of the three results across a
    re-roll (e.g. "Lock Mastery A" keeps rolling B and the skill fresh).
    """
    enabled = [m for m in masteries if not m.get("excluded", False)]
    if len(enabled) < 2:
        return {"error": "Need at least 2 enabled masteries. Check Manage Masteries."}

    by_name = {m["name"]: m for m in enabled}

    if locked_mastery_a and locked_mastery_a in by_name:
        mastery_a = by_name[locked_mastery_a]
    else:
        mastery_a = random.choice(enabled)

    if locked_skill:
        skill = locked_skill
    else:
        skill = _roll_skill(mastery_a)

    remaining = [m for m in enabled if m["name"] != mastery_a["name"]]
    if not remaining:
        return {"error": f"No other enabled mastery available to pair with {mastery_a['name']}."}

    if locked_mastery_b and locked_mastery_b in {m["name"] for m in remaining}:
        mastery_b = by_name[locked_mastery_b]
    else:
        mastery_b = random.choice(remaining)

    warning = None if skill else f"No non-excluded skills available for {mastery_a['name']}."

    return {
        "mastery_a": mastery_a["name"],
        "skill": skill,
        "mastery_b": mastery_b["name"],
        "warning": warning,
    }