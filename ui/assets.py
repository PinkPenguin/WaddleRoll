"""
ui/assets.py

Generic named-asset lookup, used both for per-module assets
(modules/<name>/assets/) and launcher-wide ones (the top-level assets/
folder -- background/logo for the picker screen itself, not tied to
any specific game).

Convention: fixed, predictable base names -- same "generic name for a
fixed slot" pattern already used for config files (settings.yaml,
last_roll.yaml, etc.) -- so no lookup table is ever needed, and adding
art later is just dropping a correctly-named file in place, not
touching any code.

Per-module (modules/<name>/assets/):
  card.png / card.jpg              -- picker screen thumbnail
  background.png / background.jpg  -- module UI's full background
  title.png / title.jpg            -- reserved, not decided whether this happens at all

Launcher-wide (top-level assets/, not under any module):
  background.png / background.jpg  -- picker screen's own background
  logo.png / logo.jpg              -- replaces the "WADDLEROLL" text title when present

Either extension works: PNG checked first (better for line art or
anything needing transparency), falling back to JPG/JPEG. Returns None
if neither exists -- these are being added one at a time, so callers
must fall back to their existing plain rendering in that case, not
crash or show a broken image.

find_module_background()/find_module_card() additionally respect the
per-module ignore_background/ignore_card settings in
core/launcher_settings.py -- these derive the module id directly from
assets_dir's own path shape (modules/<id>/assets), so a module's ui.py
doesn't need to pass its id separately just for this.
"""

from pathlib import Path

from core.launcher_settings import load_module_visual_settings


def find_asset(assets_dir: Path, base_name: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg"):
        candidate = assets_dir / f"{base_name}{ext}"
        if candidate.exists():
            return candidate
    return None


def find_module_background(assets_dir: Path | None) -> Path | None:
    if not assets_dir:
        return None
    module_id = assets_dir.parent.name
    if load_module_visual_settings(module_id)["ignore_background"]:
        return None
    return find_asset(assets_dir, "background")


def find_module_card(assets_dir: Path | None) -> Path | None:
    if not assets_dir:
        return None
    module_id = assets_dir.parent.name
    if load_module_visual_settings(module_id)["ignore_card"]:
        return None
    return find_asset(assets_dir, "card")