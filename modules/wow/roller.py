"""
modules/wow/roller.py

Rolls: Class -> Race, filtered to whichever races are actually eligible
for the rolled class. Not a symmetric class<->race relationship --
some classes have more eligible races than others (real WoW mechanics:
e.g. Paladins were Alliance-only for years, Shaman Horde-only), so each
class in the data owns its own race list rather than there being one
shared race pool with a separate class-eligibility flag per race.

Ruleset-aware: WoW has meaningfully different class/race availability
across versions (Classic vs Retail vs a private server) -- different
classes existing at all, not just different availability. Rather than
one shared dataset with per-version overrides (which gets messy fast
given how much can differ), each ruleset is a complete, self-contained
YAML file. This module has zero opinion about *which* ruleset is
active -- that's UI state, loaded once and passed in here like any
other data, matching every other module's roller.py/ui.py split.

No real class/race/ruleset data ships with this -- same policy as
every other module (PoE2's empty ascendancy roster, Last Epoch's empty
skill trees): never fabricate plausible-looking game data as a
placeholder.
"""

import random
from pathlib import Path

import yaml


def discover_rulesets(rulesets_dir: Path) -> list[str]:
    """Bare ruleset names (no .yaml extension), sorted. Just drop a new
    .yaml file into rulesets_dir to add a ruleset -- no code changes
    needed, matching the project's usual 'just drop a file in'
    philosophy (same as module discovery itself)."""
    if not rulesets_dir.exists():
        return []
    return sorted(p.stem for p in rulesets_dir.glob("*.yaml"))


def load_ruleset(rulesets_dir: Path, ruleset_name: str) -> list[dict]:
    path = rulesets_dir / f"{ruleset_name}.yaml"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("classes", [])


def save_ruleset(rulesets_dir: Path, ruleset_name: str, classes: list[dict]) -> None:
    rulesets_dir.mkdir(parents=True, exist_ok=True)
    path = rulesets_dir / f"{ruleset_name}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"classes": classes}, f, sort_keys=False)


def race_factions(race: dict) -> list[str]:
    """Faction is always stored as a list, even for the common single-
    faction case (["Alliance"]) -- one shape, no ambiguity about which
    format a given race entry uses. Costs a little hand-editing
    verbosity for the common case in exchange for removing a whole
    branch of format-checking, and it lines up with EditableTableDialog's
    existing "tags" field type (comma-separated, already used elsewhere
    in this project for exactly this kind of field) rather than needing
    a workaround for the single-value case."""
    return [f.lower() for f in (race.get("faction") or []) if f]


def roll(classes: list[dict], faction_filter: str = "any",
         locked_class: str = None, locked_race: str = None) -> dict:
    """
    faction_filter: "any" | "alliance" | "horde" -- restricts the
    ELIGIBLE RACE POOL for whichever class gets picked, not the class
    pool itself, since a class's own availability doesn't depend on
    faction -- only which specific races within it do. A race whose
    faction list includes the requested filter is eligible even if it
    ALSO belongs to the other faction -- this is a membership check,
    not an equality check, specifically to support dual-faction races.

    Returns {"class", "race", "warning"} or {"error"} if nothing's
    enabled. "race" is None (with a warning, not an error) if the
    rolled class has no races eligible under the current faction
    filter -- distinguishes "this class+faction combo is genuinely
    empty" from "nothing is enabled at all."
    """
    eligible_classes = [c for c in classes if not c.get("excluded", False)]
    if not eligible_classes:
        return {"error": "No classes are enabled."}

    if locked_class:
        chosen_class = next((c for c in eligible_classes if c["name"] == locked_class), None) \
            or random.choice(eligible_classes)
    else:
        chosen_class = random.choice(eligible_classes)

    faction_filter = (faction_filter or "any").lower()
    eligible_races = [
        r for r in chosen_class.get("races", [])
        if not r.get("excluded", False)
        and (faction_filter == "any" or faction_filter in race_factions(r))
    ]

    if not eligible_races:
        return {
            "class": chosen_class["name"],
            "race": None,
            "warning": f"No eligible races for {chosen_class['name']} under the current faction filter.",
        }

    if locked_race:
        chosen_race = next((r for r in eligible_races if r["name"] == locked_race), None) \
            or random.choice(eligible_races)
    else:
        chosen_race = random.choice(eligible_races)

    return {"class": chosen_class["name"], "race": chosen_race["name"], "warning": None}