"""
modules/rimworld/roller.py

Pure roll logic for RimWorld ideology generation. No UI code here.

Roll shape: Structure (flat roll) -> 3 ordered Memes -> every applicable
Precept, all derived from those 3 memes. Deliberately generates the
*destination* ideology, not a simulation of evolving toward it -- all 3
memes are treated as simultaneously active for every downstream roll,
regardless of which meme slot "unlocks" them in the actual game.

Meme rolling is axis-fair, not flat-with-exclusion: a naive flat pool
with post-hoc removal of the excluded side would give every exclusive
pair (e.g. Individualist/Collectivist) double the chance of a standalone
meme (e.g. Raider), purely because two competing options share one slot.
Instead, mutually exclusive memes are grouped by `axis` first, and the
top-level roll picks a *group* (Structure-axis, Primacy-axis, Raider by
itself, etc.) uniformly -- only then rolling within that group for the
specific side. See _group_memes_by_axis()/roll_memes() below.

Slot 1 (the starting meme) additionally excludes anything with
`impact: high` -- those can't actually be picked as a starting meme
during fluid ideology creation in the real game, only gained later
through evolution. `low` and `medium` impact are both valid starting
picks. Slots 2+ have no such restriction regardless of impact.

Precepts use a two-stage gate-then-weight, same shape FO4's weapon/perk
weighting already established elsewhere in this project:
  1. Gate (hard): an entry's `requirement` list must be fully satisfied
     against the 3 active memes, including negated entries like
     "Not Blindsight" -- anything that fails is excluded outright, not
     just down-weighted.
  2. Weight (soft): among gate-survivors, entries whose `associated`
     list overlaps the active memes get a multiplier boost over
     baseline -- still possible either way, just favored.
An issue with zero gate-survivors simply doesn't appear in the result at
all (not applicable under these memes) -- no special-casing needed,
that's just what falls out of the algorithm. An issue with exactly one
survivor also needs no special-casing -- the weighted pick trivially
always returns it, which is "this precept got locked in by your memes."
"""

import random
from pathlib import Path

import yaml

ASSOCIATED_WEIGHT_MULTIPLIER = 4.0  # tune once real data shows how often this should actually win


# ── Loading / saving ────────────────────────────────────────────────────

def load_structures(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("structures", [])


def save_structures(path: Path, structures: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"structures": structures}, f, sort_keys=False, allow_unicode=True)


def load_memes(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("memes", [])


def save_memes(path: Path, memes: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"memes": memes}, f, sort_keys=False, allow_unicode=True)


def load_precepts(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("precepts", [])


def save_precepts(path: Path, precepts: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"precepts": precepts}, f, sort_keys=False, allow_unicode=True)


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


# ── Structure roll ───────────────────────────────────────────────────────

def roll_structure(structures: list[dict], locked_structure: str | None = None) -> dict:
    """Returns {"structure": str|None, "warning": str|None}."""
    pool = [s["name"] for s in structures if not s.get("excluded", False)]

    if not pool:
        return {"structure": None, "warning": "No eligible structures -- check exclusions."}

    if locked_structure and locked_structure in pool:
        chosen = locked_structure
    else:
        chosen = random.choice(pool)

    return {"structure": chosen, "warning": None}


# ── Meme roll (axis-fair) ────────────────────────────────────────────────

def _group_memes_by_axis(memes: list[dict]) -> dict:
    """Groups eligible memes by their `axis` field -- memes with no axis
    (None/absent) are grouped under their own name, so they end up as a
    single-member group, same as a real axis group with 2+ members."""
    groups: dict[str, list[dict]] = {}
    for meme in memes:
        if meme.get("excluded", False):
            continue
        key = meme.get("axis") or meme["name"]
        groups.setdefault(key, []).append(meme)
    return groups


def roll_memes(memes: list[dict], count: int = 3) -> dict:
    """
    Returns {"memes": list[str], "warning": str|None} -- an ORDERED list
    of up to `count` meme names, fair at the axis level: an exclusive
    pair competes as one unit against a standalone meme, not two units
    against one. Once an axis (or standalone meme) is chosen for a slot,
    it's fully removed from contention for every later slot -- no repeat
    memes, and never both sides of the same axis.

    Slot 1 specifically (the starting meme) excludes anything with
    impact: high -- those genuinely can't be picked as a starting meme
    during fluid ideology creation in the real game, only gained later
    through evolution. low/medium impact (or impact omitted entirely,
    defaulting to low) are both valid starting picks. Slots 2+ draw
    from the full remaining pool regardless of impact, since evolution
    is exactly where high-impact memes are supposed to come from. If a
    whole axis is entirely high-impact members, that axis simply isn't
    eligible for slot 1 at all -- no lower-impact side exists to fall
    back to.
    """
    groups = _group_memes_by_axis(memes)
    result = []

    for slot_index in range(count):
        if not groups:
            break

        if slot_index == 0:
            # Starting slot: only axes with at least one non-high-impact
            # member are eligible at all.
            eligible_keys = [
                key for key, candidates in groups.items()
                if any(c.get("impact", "low") != "high" for c in candidates)
            ]
        else:
            eligible_keys = list(groups.keys())

        if not eligible_keys:
            break

        axis_key = random.choice(eligible_keys)
        candidates = groups.pop(axis_key)

        if slot_index == 0:
            # Within that axis, only non-high-impact members are a
            # valid starting pick -- matters if one side of an axis is
            # high impact and the other isn't.
            candidates = [c for c in candidates if c.get("impact", "low") != "high"]

        chosen = random.choice(candidates)
        result.append(chosen["name"])

    warning = None
    if len(result) < count:
        warning = f"Only {len(result)} meme(s) available (needed {count})."

    return {"memes": result, "warning": warning}


# ── Precept roll (gate + weight) ─────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase + strip -- same normalization Hero Siege's relic/class
    tag matching already established elsewhere in this project, after
    a real bug there ('Fire' vs 'fire' silently matching nothing).
    Applied here too so a precept referencing 'Pain is virtue' still
    correctly matches a meme actually named 'Pain Is Virtue'."""
    return s.strip().lower()


def _requirement_satisfied(requirement: list[str], active_memes_normalized: set) -> bool:
    """Every entry in requirement must hold. A "Not X" entry (case-
    insensitive on the "Not" itself, same as the meme name after it)
    means X must NOT be among the active memes; anything else must be.
    active_memes_normalized must already be pre-normalized via _norm()."""
    for req in requirement:
        req = req.strip()
        if req[:4].lower() == "not ":
            if _norm(req[4:]) in active_memes_normalized:
                return False
        else:
            if _norm(req) not in active_memes_normalized:
                return False
    return True


OPTIONAL_ISSUE_INCLUSION_CHANCE = 0.5  # non-required issues have this base chance of getting any precept at all


def roll_precepts(precepts: list[dict], active_memes: list[str]) -> dict:
    """
    Groups precept entries by `issue`, gates each issue's entries by
    `requirement` against active_memes, then weighted-picks among the
    survivors -- entries whose `associated` overlaps active_memes get
    ASSOCIATED_WEIGHT_MULTIPLIER, everything else that passed the gate
    stays at baseline weight 1.0.

    Two mechanics layer on top of that base gate+weight, addressing
    "every colony feels the same" -- forcing a pick on every single
    issue, including ones that are effectively binary on/off or have no
    real positive option at all, drowns out the few issues that
    actually reflect the 3 active memes:

    1. `required` (per-entry, resolved per-issue as "required if ANY
       entry for that issue says so"): a required issue always gets a
       precept if it has any gate-survivors, same as before this
       existed. A non-required issue instead first rolls a coin-flip
       (OPTIONAL_ISSUE_INCLUSION_CHANCE) on whether it's addressed by
       this ideology at all -- on failure, the issue is simply absent
       from the result, same as if it had been gated out entirely.

    2. `extreme` (per-entry): options flagged extreme participate in a
       running, WHOLE-IDEOLOGY tally, not a per-issue one -- each time
       an extreme option actually gets chosen, a shared extreme_count
       increments, and every subsequent extreme option (on a different
       issue) gets progressively less likely (weight divided by
       1+extreme_count) relative to non-extreme options on that same
       issue. This is why issues are processed in RANDOMIZED order,
       not dict/list order -- otherwise whichever issues happened to
       iterate first would systematically bear a lower penalty than
       whichever iterated last, a bias from arbitrary ordering, not
       genuine randomness.
    """
    active_set = {_norm(m) for m in active_memes}

    by_issue: dict[str, list[dict]] = {}
    for entry in precepts:
        if entry.get("excluded", False):
            continue
        by_issue.setdefault(entry["issue"], []).append(entry)

    issue_order = list(by_issue.keys())
    random.shuffle(issue_order)

    extreme_count = 0
    resolved = {}

    for issue in issue_order:
        entries = by_issue[issue]
        eligible = [e for e in entries if _requirement_satisfied(e.get("requirement", []), active_set)]
        if not eligible:
            continue

        is_required = any(e.get("required", False) for e in entries)
        if not is_required and random.random() > OPTIONAL_ISSUE_INCLUSION_CHANCE:
            continue

        weights = []
        for e in eligible:
            w = ASSOCIATED_WEIGHT_MULTIPLIER if {_norm(a) for a in e.get("associated", [])} & active_set else 1.0
            if e.get("extreme", False):
                w = w / (1 + extreme_count)
            weights.append(w)

        chosen = random.choices(eligible, weights=weights)[0]
        resolved[issue] = chosen["precept"]

        if chosen.get("extreme", False):
            extreme_count += 1

    return {"precepts": resolved}