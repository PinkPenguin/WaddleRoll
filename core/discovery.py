"""
core/discovery.py

Scans modules/<game>/module.py for anything that subclasses GameModule
and returns instances of them. This is what lets you add a new game by
just dropping a folder in modules/ -- nothing in the shell needs to change.

Convention: each modules/<game>/module.py must define a class named
`Module` that subclasses GameModule. Keeping the class name fixed makes
discovery trivial (no need to hunt through every class in the file).
"""

import importlib
import pkgutil

from core.plugin_base import GameModule

import modules as modules_pkg


def discover_modules() -> list[GameModule]:
    found = []

    for _, name, is_pkg in pkgutil.iter_modules(modules_pkg.__path__):
        if not is_pkg:
            continue

        try:
            mod = importlib.import_module(f"modules.{name}.module")
        except ModuleNotFoundError:
            # This game folder doesn't have a module.py yet -- skip it
            # instead of crashing the whole launcher.
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
