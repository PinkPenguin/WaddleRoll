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
PyInstaller normally packs .py code into a compiled archive (a PYZ blob)
rather than leaving it as individually-listable files, so pkgutil can't
"see into" it once frozen, even though the code is genuinely there and
perfectly importable. --collect-submodules controls what gets *bundled*;
it doesn't change *how* frozen code gets *discovered*, which is the step
that actually fails. The fix reuses the same mechanism already proven to
work for extracting bundled config (core/paths.get_bundled_resource_root())
-- every module ships a config/ folder, and that folder DOES exist as a
real, listable file on disk under sys._MEIPASS (added via --add-data),
so its presence there is a reliable stand-in for "this module exists,"
without ever needing to hardcode a module list anywhere.
"""

import importlib
import pkgutil
import sys

from core.plugin_base import GameModule
from core.paths import get_bundled_resource_root

import modules as modules_pkg


def _candidate_module_names() -> list[str]:
    is_frozen = getattr(sys, "frozen", False)
    print(f"[discovery] sys.frozen = {is_frozen}")

    if not is_frozen:
        names = [name for _, name, is_pkg in pkgutil.iter_modules(modules_pkg.__path__) if is_pkg]
        print(f"[discovery] non-frozen path, pkgutil found: {names}")
        return names

    bundled_root = get_bundled_resource_root()
    bundled_modules_dir = bundled_root / "modules"
    print(f"[discovery] bundled_root = {bundled_root}")
    print(f"[discovery] bundled_modules_dir = {bundled_modules_dir}")
    print(f"[discovery] bundled_modules_dir.exists() = {bundled_modules_dir.exists()}")

    if not bundled_modules_dir.exists():
        return []

    names = [
        d.name for d in bundled_modules_dir.iterdir()
        if d.is_dir() and (d / "config").exists()
    ]
    print(f"[discovery] frozen path, found module folders: {names}")
    return names


def discover_modules() -> list[GameModule]:
    found = []
    names = _candidate_module_names()
    print(f"[discovery] about to attempt {len(names)} module(s): {names}")

    for name in names:
        print(f"[discovery] >>> attempting '{name}'")
        try:
            mod = importlib.import_module(f"modules.{name}.module")
        except ModuleNotFoundError as e:
            # This game folder doesn't have a module.py yet -- skip it
            # instead of crashing the whole launcher.
            print(f"[discovery] '{name}': ModuleNotFoundError: {e}  (e.name={e.name!r})")
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
            print(f"[discovery] '{name}': mod.Module is None (getattr found nothing named 'Module')")
            continue

        is_type = isinstance(module_class, type)
        is_subclass = is_type and issubclass(module_class, GameModule)
        if not (is_type and is_subclass):
            print(f"[discovery] '{name}': isinstance(module_class, type) = {is_type}, "
                  f"issubclass(module_class, GameModule) = {is_subclass if is_type else 'N/A'}")
            print(f"[discovery] '{name}': module_class = {module_class!r}, "
                  f"id(GameModule imported here) = {id(GameModule)}, "
                  f"GameModule module = {GameModule.__module__}")
            if is_type:
                print(f"[discovery] '{name}': module_class.__mro__ = {module_class.__mro__}")
            continue

        try:
            instance = module_class()
        except Exception as e:
            print(f"[discovery] Failed to instantiate module '{name}': {e}")
            continue

        print(f"[discovery] '{name}': OK, instantiated successfully (id={instance.id})")
        found.append(instance)

    print(f"[discovery] final result: {len(found)} module(s) found")
    return found