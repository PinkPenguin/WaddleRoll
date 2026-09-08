"""
core/discovery.py

Scans modules/<game>/module.py for anything that subclasses GameModule
and returns instances of them. This is what lets you add a new game by
just dropping a folder in modules/ -- nothing in the shell needs to change.

Convention: each modules/<game>/module.py must define a class named
`Module` that subclasses GameModule. Keeping the class name fixed makes
discovery trivial (no need to hunt through every class in the file).

Enumeration is frozen-aware. pkgutil.iter_modules() enumerates submodules
by scanning real filesystem directories -- fine running from source, but
PyInstaller normally packs .py code into a compiled archive rather than
leaving it as individually-listable files, so pkgutil can't "see into"
it once frozen, even though the code is genuinely there and importable
(WaddleRoll.spec explicitly lists each module.py as a hiddenimport for
exactly this reason). The fix below reuses the same mechanism already
proven to work for extracting bundled config
(core/paths.get_bundled_resource_root()) -- every module ships a
config/ folder, and that folder exists as a real, listable file on disk
under sys._MEIPASS (bundled via WaddleRoll.spec's datas list), so its
presence there is a reliable stand-in for "this module exists," without
ever needing to hardcode a module list anywhere.
"""

import importlib
import pkgutil
import sys

from core.plugin_base import GameModule
from core.paths import get_bundled_resource_root

import modules as modules_pkg


def _candidate_module_names() -> list[str]:
    if not getattr(sys, "frozen", False):
        return [name for _, name, is_pkg in pkgutil.iter_modules(modules_pkg.__path__) if is_pkg]

    bundled_modules_dir = get_bundled_resource_root() / "modules"
    if not bundled_modules_dir.exists():
        return []
    return [
        d.name for d in bundled_modules_dir.iterdir()
        if d.is_dir() and (d / "config").exists()
    ]


def discover_modules() -> list[GameModule]:
    found = []

    for name in _candidate_module_names():
        try:
            mod = importlib.import_module(f"modules.{name}.module")
        except ModuleNotFoundError:
            # This game folder doesn't have a module.py yet -- skip it
            # instead of crashing the whole launcher.
            continue
        except Exception as e:
            # Anything else (a missing dependency, a bundling issue,
            # whatever) shouldn't be able to take down the whole
            # launcher either -- log it and keep going, same as an
            # instantiation failure below.
            print(f"[discovery] Failed to import module '{name}': {e}")
            continue

        module_class = getattr(mod, "Module", None)
        if module_class is None:
            continue

        if not (isinstance(module_class, type) and issubclass(module_class, GameModule)):
            continue

        try:
            instance = module_class()
        except Exception as e:
            print(f"[discovery] Failed to instantiate module '{name}': {e}")
            continue

        found.append(instance)

    return found