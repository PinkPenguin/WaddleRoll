"""
ui/manage_menu.py

Shared small picker dialog: replaces a growing row of "Manage X"
buttons (one per config data file/editor -- classes, races, perks,
weapon groups, whatever a given module has) with a single "Manage
Config" entry point that opens a short list of what's actually
available to edit, with "Open Config Folder" as just one more item in
that same list rather than its own separate button.

Generalizes the exact same small-chooser pattern WoW's own
_open_class_detail_chooser used for its races/specs split (needed
there because EditableTableDialog only supports one action per row) --
this is that same idea, applied to a module's whole top-level set of
"things to manage," not just one nested row's two choices.

Explicit dark styling, not left to the OS system palette -- the same
lesson already learned once this session with ui/roll_history.py's own
dialog (white text on a white background on a dark-mode OS, since
nothing there set either color explicitly).
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel

# Same neutral, explicit dark palette as ui/roll_history.py's own
# dialog -- deliberately not tied to any one module's palette (this is
# shared across all of them), but explicit regardless of system theme.
_BG = "#1c1c1e"
_BG_ITEM = "#28282a"
_TEXT = "#e8e8e8"
_TEXT_DIM = "#9a9a9a"


def open_manage_menu(parent, title: str, actions: list) -> None:
    """actions: list of (label, callback) pairs. callback takes no
    arguments and is called once this picker has fully closed.

    Closes this dialog completely (dlg.exec() returns) before running
    the chosen action, rather than firing it from inside the button's
    own click handler while this dialog is still tearing itself down
    -- opening a new modal mid-teardown of another one is the kind of
    thing worth avoiding rather than assuming is safe, same reasoning
    WoW's own class-detail chooser already used."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setStyleSheet(f"QDialog {{ background-color: {_BG}; }}")

    layout = QVBoxLayout(dlg)
    hint = QLabel("What would you like to manage?")
    hint.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent; font-size: 11px; padding: 2px;")
    layout.addWidget(hint)

    choice = {"value": None}

    def pick(callback):
        choice["value"] = callback
        dlg.accept()

    for label, callback in actions:
        btn = QPushButton(label)
        btn.setStyleSheet(f"""
            QPushButton {{
                color: {_TEXT}; background-color: {_BG_ITEM};
                border: 1px solid #3a3a3c; border-radius: 4px; padding: 8px 16px;
                text-align: left;
            }}
            QPushButton:hover {{ background-color: #3a3a3c; }}
        """)
        # Default-bind callback (cb=callback) -- otherwise every button's
        # lambda would share the SAME late-bound reference to the loop
        # variable and all fire the LAST action in the list regardless
        # of which button was actually clicked, a classic closure-over-
        # loop-variable bug.
        btn.clicked.connect(lambda checked=False, cb=callback: pick(cb))
        layout.addWidget(btn)

    dlg.exec()

    if choice["value"] is not None:
        choice["value"]()