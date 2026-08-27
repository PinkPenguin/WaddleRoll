# WaddleRoll

A single desktop launcher hosting build randomizers for multiple ARPGs.
Pick a game from the launcher screen, hit Roll, get a randomized
build seed to theorycraft around — no more juggling a separate tool
per game.

## Why this exists

Randomized/theorycrafted challenge runs across PoE, Grim Dawn, Last
Epoch, Hero Siege, Fallout 4, and whatever's next, without needing a
different standalone script or tool open for each one.

## How it's organized

This is a plugin architecture: one shell, N game modules.

```
randomizer-launcher/
├── main.py                   # entry point
├── core/
│   ├── plugin_base.py        # the contract every game module implements
│   └── discovery.py          # auto-finds modules/<game>/module.py on startup
├── ui/
│   ├── main_window.py        # shell: picker <-> module page, per-module sizing
│   ├── game_picker.py        # the "choose a game" screen
│   ├── editable_table.py     # generic in-app CRUD editor (search included),
│   │                         #   reused by every module's Manage X dialogs
│   └── version_badge.py      # generic "game version I last checked against" field
└── modules/
    ├── fallout4/
    ├── hero_siege/
    ├── grim_dawn/
    └── last_epoch/
        ├── module.py          # plugin wrapper: id, palette, window size, icon
        ├── roller.py          # pure roll logic, no UI code
        ├── ui.py               # that module's screen -- own palette/font/layout
        ├── editor.py           # wires editable_table.py to this module's data shape
        └── config/
            ├── *.yaml          # classes/skills/relics/etc -- hand- or app-editable
            ├── settings.yaml   # per-module toggles (wildcard chance, etc.)
            └── version.yaml    # hand-tracked game version, via the version badge

```

Each module owns its **entire visual identity** — palette, font, window
size, panel style — independently. The shell (`core/`, `ui/`) has zero
game-specific knowledge; it just discovers modules and mounts whatever
widget each one returns.

## Adding a new game

1. Create `modules/<game>/` with `__init__.py`, `roller.py`, `ui.py`, `module.py`
2. `module.py` needs a class named `Module(GameModule)` with `id`,
   `display_name`, `description`, `background_color`, `accent_color`,
   `icon`, `default_size`, `min_size`, and `get_widget()`
3. That's it — restart the app and it shows up on the picker automatically.
   Nothing in `core/` or `ui/` needs to change.

Tip: measure `default_size`/`min_size` off the widget's actual
`sizeHint()` rather than guessing pixel values — windows should only
be as large as their content actually needs.

## Editing game data (classes, skills, relics, etc.)

Every module's data lives in `modules/<game>/config/*.yaml`. Two ways
to edit it:

- **In-app**: each module has "Manage X" buttons that open a searchable,
  editable table (add/remove/edit rows, including nested sub-lists like
  a class's skills or a skill's tree nodes). Saves straight back to the
  YAML.
- **By hand**: the YAML is plain and commented. If a name contains a
  colon, wrap it in double quotes (`"Warpath: Onslaught"`) or the file
  will fail to parse entirely.

"Excluded" flags (per class/skill/relic/node) control what's eligible
to roll without deleting the entry — useful for curating out things you
wouldn't build around.

## Setup

```
pip install -r requirements.txt
python main.py
```

## Notes

- Game version tracking (the small field under each module's title) is
  entirely manual for now — no automatic SteamDB/patch-note checking.
  It's just a place to record what you last verified your data against.
- Windows-only right now (uses `os.startfile` for "Open Config Folder");
  easy to extend if that ever needs to change.