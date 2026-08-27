# Build Randomizer Launcher

A single desktop app that hosts randomizers for multiple games, chosen
from one launcher screen.

## Setup (in PyCharm or terminal)

```
pip install -r requirements.txt
python main.py
```

## How it's organized

- `main.py` — entry point, boots the app
- `ui/` — the shell: game picker screen + main window (generic, no game-specific code)
- `core/plugin_base.py` — the contract every game module must implement
- `core/discovery.py` — auto-finds any `modules/<game>/module.py` on startup
- `modules/fallout4/` — the first module:
  - `roller.py` — pure roll logic (ported from the original `fo4_randomizer.py`, unchanged logic)
  - `ui.py` — the Pip-Boy themed screen (ported from Tkinter to PySide6)
  - `module.py` — the small wrapper connecting it to the launcher

## Adding a new game (e.g. Path of Exile)

1. Create `modules/poe/` with `__init__.py`, `roller.py`, `ui.py`, `module.py`
2. `module.py` needs a class named `Module(GameModule)` with `id`, `display_name`,
   `description`, and `get_widget()` — copy `modules/fallout4/module.py` as a template
3. That's it — restart the app and it shows up on the picker automatically.
   Nothing in `core/` or `ui/` needs to change.
