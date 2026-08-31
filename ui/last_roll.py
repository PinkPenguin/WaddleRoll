"""
ui/last_roll.py

Generic "remember what was last rolled" persistence -- a plain YAML
load/save pair, deliberately living here rather than duplicated into
every module's roller.py. This follows the same precedent
ui/version_badge.py already set: app-usage state (not actual game roll
logic) belongs in ui/, self-contained, imported directly by each
module's ui.py.

The logic itself has zero per-module variation -- it's just "load a
dict from a file, or None if missing" / "save a dict, or delete the
file if given None." What actually goes IN that dict, and how it gets
rendered back on screen (SlotMachine.set_static() vs. a module's own
_update_display(), etc.), stays entirely module-specific -- this file
only ever touches the byte on disk, nothing else.
"""

from pathlib import Path

import yaml


def load_last_roll(path: Path) -> dict | None:
    """Returns the saved roll-result dict, or None if nothing's saved
    (file doesn't exist, or is empty)."""
    if not Path(path).exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or None


def save_last_roll(path: Path, data: dict | None) -> None:
    """Pass None to clear -- deletes the file rather than writing an
    empty one, so a fresh module load has nothing to find."""
    if data is None:
        if Path(path).exists():
            Path(path).unlink()
        return
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)