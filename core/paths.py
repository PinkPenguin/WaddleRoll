"""
core/paths.py

Resolves the "app root" -- where config data should actually live --
correctly whether running from source (python main.py) or as a
PyInstaller-frozen executable.

This matters specifically for packaging: __file__ inside a frozen app
resolves to a TEMPORARY extraction directory (--onefile mode, a fresh
one every single launch) or a bundle-internal path (--onedir mode),
neither of which is a stable place to read/write config, settings, or
last_roll data. sys.executable, by contrast, always points to the
real, stable executable location in both frozen and normal execution.
Using it keeps the whole "portable, no-install" experience working
correctly: copy the folder anywhere, config travels with the .exe
rather than disappearing into a temp directory that gets wiped on exit.

ensure_resources_extracted() handles the other half of this: a fresh
install (or a newer version's .exe) needs its default config data to
actually exist at that persistent location the first time it's ever
launched, without ever overwriting config/settings/last_roll data a
returning user already has. Only files genuinely missing get copied in
-- this is what makes "download an update" safe rather than something
that quietly resets everyone's rolls and exclusions back to defaults.
"""

import shutil
import sys
from pathlib import Path


def get_app_root() -> Path:
    """Directory config data should live under.

    Frozen (PyInstaller): the folder containing the actual .exe, not
    wherever the bundle happens to extract itself to internally.

    Not frozen: the project root (this file lives at
    <project_root>/core/paths.py, so its grandparent is project root) --
    identical to what every module already computed via
    Path(__file__).parent before this existed, so dev-mode behavior is
    unchanged.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def get_bundled_resource_root() -> Path:
    """Where PyInstaller actually put the bundled default config data
    (the read-only originals, built into the package via --add-data),
    as opposed to get_app_root()'s persistent, mutable location. In
    both --onefile and --onedir modes, PyInstaller sets sys._MEIPASS to
    this. Not frozen: same as get_app_root() -- running from source,
    "bundled defaults" and "the real config" are just the same tree.

    Also reused by core/discovery.py as a reliable way to enumerate
    which modules exist when frozen -- see that file for why
    pkgutil.iter_modules() doesn't work for this once packaged."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


RESOURCE_SUBFOLDERS = ["config", "assets"]  # per-module subfolders that get extracted from bundled defaults to the persistent location


def _extract_missing_files(bundled_subfolder: Path, bundled_root: Path, persistent_root: Path) -> None:
    """Copies every file under bundled_subfolder to its equivalent
    persistent path, skipping anything that already exists there."""
    if not bundled_subfolder.exists():
        return
    for bundled_file in bundled_subfolder.rglob("*"):
        if bundled_file.is_dir():
            continue
        relative = bundled_file.relative_to(bundled_root)
        target = persistent_root / relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled_file, target)


def ensure_resources_extracted() -> None:
    """
    Copies each bundled default resource file -- per-module config/
    assets (see RESOURCE_SUBFOLDERS) and the top-level launcher-wide
    assets/ folder (background/logo for the picker itself, not tied to
    any module) -- to its persistent location, but ONLY if it doesn't
    already exist there -- never overwrites anything a returning user
    already has. Safe to call on every single launch; a no-op once
    everything's already extracted. Must run before any module tries
    to load its config (i.e. before MainWindow/discover_modules()).
    """
    bundled_root = get_bundled_resource_root()
    persistent_root = get_app_root()

    if bundled_root == persistent_root:
        return  # running from source -- same tree, nothing to extract

    _extract_missing_files(bundled_root / "assets", bundled_root, persistent_root)

    bundled_modules_dir = bundled_root / "modules"
    if not bundled_modules_dir.exists():
        return

    for module_dir in bundled_modules_dir.iterdir():
        if not module_dir.is_dir():
            continue

        for subfolder_name in RESOURCE_SUBFOLDERS:
            _extract_missing_files(module_dir / subfolder_name, bundled_root, persistent_root)