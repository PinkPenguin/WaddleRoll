"""
modules/wow/roller.py

Rolls: Class -> Race, filtered to whichever races are actually eligible
for the rolled class. Not a symmetric class<->race relationship --
some classes have more eligible races than others (real WoW mechanics:
e.g. Paladins were Alliance-only for years, Shaman Horde-only), so each
class in the data owns its own race list rather than there being one
shared race pool with a separate class-eligibility flag per race.

Also rolls a Spec (talent tree) from the chosen class's own spec list
-- purely class-dependent, entirely independent of race/faction, same
relationship Last Epoch's class->skill->notable chain has once the
class itself is fixed.

Professions are a separate, unrelated roll (roll_professions) -- any
class can learn any profession in real WoW, so there's no dependency
on the class/race/spec roll at all. Only ever rolls exactly 2 PRIMARY
professions (the real in-game constraint -- you can only know 2 at
once), uniform random, no attempt to balance gathering vs crafting.
Secondary professions (Cooking, First Aid, Fishing, etc.) are never
part of the roll since every character can learn all of them regardless
-- they still live in the same professions list/schema for
completeness, just filtered out here by category.

Ruleset-aware: WoW has meaningfully different class/race availability
across versions (Classic vs Retail vs a private server) -- different
classes existing at all, not just different availability. Rather than
one shared dataset with per-version overrides (which gets messy fast
given how much can differ), each ruleset is a complete, self-contained
YAML file. This module has zero opinion about *which* ruleset is
active -- that's UI state, loaded once and passed in here like any
other data, matching every other module's roller.py/ui.py split.

No real class/race/spec/profession data ships with this -- same policy
as every other module (PoE2's empty ascendancy roster, Last Epoch's
empty skill trees): never fabricate plausible-looking game data as a
placeholder, even for something as generally stable as WoW's standard
profession list -- "Forever" is a private server, and private servers
routinely deviate from standard rules in ways that can't be verified
from general knowledge alone.
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


def load_ruleset(rulesets_dir: Path, ruleset_name: str) -> dict:
    """Returns the full parsed ruleset -- {"classes": [...], "professions": [...]}
    -- rather than just the classes list, so a caller can pull out
    whichever top-level keys it needs without this function's return
    shape needing to change again if more get added later."""
    path = rulesets_dir / f"{ruleset_name}.yaml"
    if not path.exists():
        return {"classes": [], "professions": []}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        "classes": data.get("classes", []),
        "professions": data.get("professions", []),
    }


def save_ruleset(rulesets_dir: Path, ruleset_name: str, classes: list[dict], professions: list[dict]) -> None:
    """Both classes and professions are required, always written
    together -- this is a single YAML file with two top-level keys, so
    saving one without the other would silently drop it. The caller
    already holds both in memory as instance state once a ruleset is
    loaded, so passing both here is simpler and safer than a read-
    modify-write from disk (same lesson as an earlier bug elsewhere in
    this project, where a settings save was overwriting the whole file
    instead of preserving keys it wasn't touching)."""
    rulesets_dir.mkdir(parents=True, exist_ok=True)
    path = rulesets_dir / f"{ruleset_name}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"classes": classes, "professions": professions}, f, sort_keys=False)


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

    Locking is symmetric: locking class rolls race from whatever's
    valid for that class; locking race rolls class from whatever
    classes actually have that race as an eligible option (not just
    "whichever class happens to already be active" -- a fresh random
    pick among the compatible ones, matching how an unlocked class
    normally behaves). Locking both keeps both fixed (falling back to a
    random race if the two locked values genuinely aren't compatible
    with each other, same as a stale/invalid single lock already did).

    This replaced an earlier, asymmetric version that always picked
    class first, independently of any race lock, then tried to find the
    locked race WITHIN whatever class had just been randomly chosen.
    That silently failed most of the time a race was locked without
    class also being locked: a freshly-randomized class often simply
    doesn't have the locked race as an option at all, so the lock
    quietly got discarded in favor of an unrelated random race instead
    of actually being honored.

    "spec" is rolled purely from the chosen class's own spec list --
    entirely independent of race/faction, so it's computed right after
    the class and included in BOTH return paths below (with or without
    an eligible race), since a missing race doesn't mean spec should be
    skipped too -- they're unrelated concerns once the class is fixed,
    same as Last Epoch treats each level of its own class->skill->
    notable chain independently. None (not a warning, not an error) if
    the class simply has no specs defined yet.

    Returns {"class", "race", "spec", "warning"} or {"error"} if
    nothing's enabled. "race" is None (with a warning, not an error) if
    the rolled class has no races eligible under the current faction
    filter -- distinguishes "this class+faction combo is genuinely
    empty" from "nothing is enabled at all."
    """
    eligible_classes = [c for c in classes if not c.get("excluded", False)]
    if not eligible_classes:
        return {"error": "No classes are enabled."}

    faction_filter = (faction_filter or "any").lower()

    def eligible_races_for(cls: dict) -> list[dict]:
        return [
            r for r in cls.get("races", [])
            if not r.get("excluded", False)
            and (faction_filter == "any" or faction_filter in race_factions(r))
        ]

    if locked_race and not locked_class:
        # Restrict the class pool to only those that actually have this
        # race as an eligible option, then pick freely among THOSE --
        # "roll available classes," not just keep whichever class
        # happened to already be active.
        compatible_classes = [
            c for c in eligible_classes
            if any(r["name"] == locked_race for r in eligible_races_for(c))
        ]
        if not compatible_classes:
            return {"error": f'No enabled class has "{locked_race}" as an eligible race under the current faction filter.'}
        chosen_class = random.choice(compatible_classes)
    elif locked_class:
        chosen_class = next((c for c in eligible_classes if c["name"] == locked_class), None) \
            or random.choice(eligible_classes)
    else:
        chosen_class = random.choice(eligible_classes)

    eligible_specs = [s["name"] for s in chosen_class.get("specs", []) if not s.get("excluded", False)]
    chosen_spec = random.choice(eligible_specs) if eligible_specs else None

    eligible_races = eligible_races_for(chosen_class)

    if not eligible_races:
        return {
            "class": chosen_class["name"],
            "race": None,
            "spec": chosen_spec,
            "warning": f"No eligible races for {chosen_class['name']} under the current faction filter.",
        }

    if locked_race:
        chosen_race = next((r for r in eligible_races if r["name"] == locked_race), None) \
            or random.choice(eligible_races)
    else:
        chosen_race = random.choice(eligible_races)

    return {"class": chosen_class["name"], "race": chosen_race["name"], "spec": chosen_spec, "warning": None}


def roll_professions(professions: list[dict], locked_profession_a: str = None,
                      locked_profession_b: str = None) -> dict:
    """
    Rolls exactly 2 PRIMARY professions, uniform random, no duplicates
    -- purely by chance which mix comes up (2 gathering, 2 crafting, or
    one of each), deliberately no attempt to balance the pair, per the
    request ("almost like a challenge"). Secondary professions are
    never part of this roll -- every character can learn all of them
    regardless of what's rolled here, so there's no real choice to
    randomize; they still live in the same professions list/schema for
    completeness even though this function filters them out by
    category.

    Independently lockable per slot (profession_a / profession_b),
    matching how every other multi-result roll in this project treats
    each result as its own separately lockable thing rather than a
    single "lock both" toggle -- same shape as Grim Dawn's
    mastery_a/mastery_b.

    Returns {"professions": [name_a, name_b]} or {"error"} if fewer
    than 2 non-excluded primary professions exist at all.
    """
    eligible = [
        p["name"] for p in professions
        if not p.get("excluded", False) and p.get("category") == "primary"
    ]
    if len(eligible) < 2:
        return {"error": "Fewer than 2 primary professions are enabled."}

    profession_a = locked_profession_a if locked_profession_a in eligible else random.choice(eligible)
    remaining = [p for p in eligible if p != profession_a]

    if locked_profession_b and locked_profession_b != profession_a and locked_profession_b in remaining:
        profession_b = locked_profession_b
    else:
        profession_b = random.choice(remaining)

    return {"professions": [profession_a, profession_b]}