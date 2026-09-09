"""
core/launcher_settings.py

Small persisted launcher-wide setting: which discovered modules are
hidden from the picker screen. Lives at the app root, not nested under
any specific module -- this is a launcher-level concern, not a
game-specific one.

Default (a module's id absent from hidden_modules) is VISIBLE -- same
"missing = safe/inclusive default" polarity used everywhere else in
this project (excluded: false, required: false, etc.). Specifically
means a brand-new module shows up automatically without needing to be
added to an "enabled" list anywhere, preserving the plugin
architecture's "just drop a folder in modules/" promise even with this
feature in place.
"""

from pathlib import Path

import yaml

from core.paths import get_app_root


def _settings_path() -> Path:
    return get_app_root() / "launcher_settings.yaml"


def load_hidden_module_ids() -> set:
    path = _settings_path()
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return set(data.get("hidden_modules", []))


def save_hidden_module_ids(hidden_ids: set) -> None:
    with open(_settings_path(), "w", encoding="utf-8") as f:
        yaml.safe_dump({"hidden_modules": sorted(hidden_ids)}, f, sort_keys=False)