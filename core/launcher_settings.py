"""
core/launcher_settings.py

Small persisted launcher-wide settings file, at the app root, not
nested under any specific module -- these are launcher-level concerns,
not game-specific ones. Holds three independent things:

1. hidden_modules -- which discovered modules are hidden from the
   picker screen (toggled via the in-app "Manage Visible Games" dialog).
2. launcher_visuals -- ignore_background/ignore_logo for the picker
   screen's own art.
3. module_visuals -- per-module ignore_background/ignore_card,
   keyed by module id.

All three default to the inclusive/visible side when absent -- same
"missing = safe default" polarity used everywhere else in this project
(excluded: false, required: false, etc.). For (1), this means a
brand-new module shows up automatically without being added to an
"enabled" list anywhere; for (2)/(3), it means art shows by default
once it exists, not the other way around.

(2) and (3) are deliberately hand-edit-only -- no in-app UI for them,
by explicit request ("doesn't have to be easily accessible, just don't
want to juggle files to turn it off"). Same convention as
remember_last_roll elsewhere in this project: a real setting, just not
one that needs a checkbox.

Since this one file now holds multiple independent settings sections,
every save function here reads the whole file first and only updates
its own key -- overwriting the whole file would silently destroy
hand-edited sections a save function doesn't know about.
"""

from pathlib import Path

import yaml

from core.paths import get_app_root


def _settings_path() -> Path:
    return get_app_root() / "launcher_settings.yaml"


def _load_all() -> dict:
    path = _settings_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_key(key: str, value) -> None:
    data = _load_all()
    data[key] = value
    with open(_settings_path(), "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def load_hidden_module_ids() -> set:
    return set(_load_all().get("hidden_modules", []))


def save_hidden_module_ids(hidden_ids: set) -> None:
    _save_key("hidden_modules", sorted(hidden_ids))


def load_launcher_visual_settings() -> dict:
    """{"ignore_background": bool, "ignore_logo": bool} for the picker
    screen's own art. Hand-edit launcher_settings.yaml directly:

        launcher_visuals:
          ignore_background: true
          ignore_logo: true
    """
    lv = _load_all().get("launcher_visuals", {})
    return {
        "ignore_background": lv.get("ignore_background", False),
        "ignore_logo": lv.get("ignore_logo", False),
    }


def load_module_visual_settings(module_id: str) -> dict:
    """{"ignore_background": bool, "ignore_card": bool} for one module.
    Hand-edit launcher_settings.yaml directly:

        module_visuals:
          poe1:
            ignore_background: true
    """
    mv = _load_all().get("module_visuals", {}).get(module_id, {})
    return {
        "ignore_background": mv.get("ignore_background", False),
        "ignore_card": mv.get("ignore_card", False),
    }