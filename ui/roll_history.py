"""
ui/roll_history.py

Shared roll-history machinery -- generic dict-in-list-out, so any
module can keep a capped, timestamped list of past results without
reimplementing the same logic per module. Mirrors ui/last_roll.py's
own shape (one file per module, not a global cross-module log) --
this just keeps more than the single most recent entry.

Deliberately per-module, not a shared cross-module log -- matches the
project's existing "settings.yaml/last_roll.yaml are per-module data,
not global state" convention, and every module's result shape is
different enough that a single combined log would need to know about
every module's own data anyway.

Display uses the same "generic machinery, module supplies its own
shape" split as EditableTableDialog: this dialog knows nothing about
what's INSIDE an entry dict. The caller supplies a small
format_entry(entry) -> str function turning one entry into whatever
single line of text makes sense for that module's own result shape --
that's the one bit of code each module actually needs to write, not a
whole feature reimplemented per module.

Double-click restores rather than showing full detail per entry: a
history entry showing everything (all SPECIAL stats, full weapon
detail, every perk, for FO4's own three-part result) scales badly --
by 20 entries the dialog is unreadable. A summary line plus "double-
click to load this back into the UI" is both more usable and more
useful (a log you can only look at is weaker than one you can act on),
and it costs the caller nothing new -- restoring a past entry works
through the exact same set_static()/_show_static() mechanism a module
already has for restoring its single most recent roll on launch.
"""

from datetime import datetime
from pathlib import Path

import yaml

from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QLabel

# Neutral, explicit dark styling -- deliberately not tied to any one
# module's own palette (this dialog is shared across all of them), but
# explicit regardless of system theme. Leaving colors unset let Qt's
# default system palette decide, which on a dark-mode OS could render
# white text while the dialog's own background defaulted to white --
# unreadable, and not something any module's own styling could fix
# since none of them touch this dialog's internals.
_BG = "#1c1c1e"
_BG_ITEM = "#28282a"
_TEXT = "#e8e8e8"
_TEXT_DIM = "#9a9a9a"
_ACCENT = "#5a8fd6"


def load_roll_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("history", [])


def append_roll_history(path: Path, entry: dict, max_entries: int = 20) -> None:
    """Prepends the new entry (most recent first), caps the list at
    max_entries, dropping the oldest once exceeded. Stamps a
    "rolled_at" timestamp onto a shallow copy of entry -- the caller's
    own result dict isn't mutated."""
    history = load_roll_history(path)
    stamped = dict(entry)
    stamped["rolled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history.insert(0, stamped)
    history = history[:max_entries]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"history": history}, f, sort_keys=False, allow_unicode=True)


def open_roll_history_dialog(parent, title: str, history: list[dict], format_entry,
                              on_restore=None) -> None:
    """format_entry: callable taking one entry dict, returning the
    single line of text to show for it. This dialog is otherwise
    entirely opaque to what a module's own result shape looks like.

    on_restore: optional callable taking one entry dict, called on
    double-click and expected to apply that entry back to the module's
    own UI (typically by handing it straight to whatever set_static()/
    _show_static() call already restores the last roll on launch).
    Closes the dialog afterward. Omit for a purely read-only list."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(420, 480)
    dlg.setStyleSheet(f"QDialog {{ background-color: {_BG}; }}")

    layout = QVBoxLayout(dlg)

    label_style = f"color: {_TEXT_DIM}; background: transparent; font-size: 11px; padding: 2px;"

    if not history:
        empty_lbl = QLabel("No rolls yet.")
        empty_lbl.setStyleSheet(f"color: {_TEXT}; background: transparent; padding: 8px;")
        layout.addWidget(empty_lbl)
    else:
        if on_restore is not None:
            hint_lbl = QLabel("Double-click an entry to load it back in.")
            hint_lbl.setStyleSheet(label_style)
            layout.addWidget(hint_lbl)

        list_widget = QListWidget()
        list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {_BG_ITEM}; color: {_TEXT};
                border: 1px solid #3a3a3c; border-radius: 4px;
                font-size: 12px; padding: 4px;
            }}
            QListWidget::item {{ padding: 5px 4px; }}
            QListWidget::item:selected {{ background-color: {_ACCENT}; color: #ffffff; }}
            QListWidget::item:hover {{ background-color: #3a3a3c; }}
        """)
        for entry in history:
            timestamp = entry.get("rolled_at", "")
            line = format_entry(entry)
            list_widget.addItem(f"{timestamp}  —  {line}" if timestamp else line)

        if on_restore is not None:
            def handle_double_click(item):
                index = list_widget.row(item)
                on_restore(history[index])
                dlg.accept()
            list_widget.itemDoubleClicked.connect(handle_double_click)

        layout.addWidget(list_widget)

    close_btn = QPushButton("Close")
    close_btn.setStyleSheet(f"""
        QPushButton {{
            color: {_TEXT}; background-color: {_BG_ITEM};
            border: 1px solid #3a3a3c; border-radius: 4px; padding: 6px 16px;
        }}
        QPushButton:hover {{ background-color: #3a3a3c; }}
    """)
    close_btn.clicked.connect(dlg.accept)
    layout.addWidget(close_btn)

    dlg.exec()