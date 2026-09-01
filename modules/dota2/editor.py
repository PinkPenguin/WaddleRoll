"""
modules/dota2/editor.py

Wires the shared ToggleGridDialog to Dota's hero roster (too large --
~120 entries -- for a normal row-per-item EditableTableDialog to be
comfortable to browse), plus per-hero notes.

Notes are a *list* of named builds per hero (e.g. "Support",
"Core"), not one blob -- browsable via EditableTableDialog (a plain
flat table: build name + an "Edit Notes..." extra_action drilling into
a small two-field general/item dialog per build), same nesting
mechanism every other nested editor in this project already uses.
That two-field dialog itself isn't built on EditableTableDialog or
ToggleGridDialog -- neither fits free-text fields -- so it's its own
small dialog, styled to match the other shared dialogs' neutral palette.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton

from ui.toggle_grid import ToggleGridDialog
from ui.editable_table import EditableTableDialog

DIALOG_BG = "#1c1c1c"
DIALOG_TEXT = "#eaeaea"
DIALOG_BORDER = "#444"


def open_heroes_grid(parent, heroes: list[dict], on_name_click=None):
    dlg = ToggleGridDialog(
        "Manage Heroes", heroes, columns=5,
        on_name_click=on_name_click, parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None


def open_builds_editor(parent, hero_name: str, builds: list[dict]):
    """List of this hero's named builds -- 'Edit Notes...' drills into
    the general+item dialog for one specific build. Returns the edited
    builds list on Save, or None if cancelled -- same contract as every
    other editor here."""
    def edit_build_notes(build_row: dict):
        result = open_build_notes_dialog(parent, hero_name, build_row.get("name", ""), build_row)
        if result is not None:
            build_row["general_notes"] = result["general_notes"]
            build_row["item_notes"] = result["item_notes"]

    columns = [("name", "Build Name", "text")]
    dlg = EditableTableDialog(
        f"Builds — {hero_name}", columns, builds,
        extra_action=("Edit Notes...", edit_build_notes),
        extra_row_defaults={"general_notes": str, "item_notes": str},
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None


def open_build_notes_dialog(parent, hero_name: str, build_name: str, notes_entry: dict):
    """Two plain text fields -- general notes and item notes -- for one
    specific named build. Returns {"general_notes": str, "item_notes": str}
    on Save, None on Cancel."""
    dlg = QDialog(parent)
    title = f"Notes — {hero_name} ({build_name})" if build_name else f"Notes — {hero_name}"
    dlg.setWindowTitle(title)
    dlg.setStyleSheet(f"background-color: {DIALOG_BG};")
    dlg.resize(480, 420)

    layout = QVBoxLayout(dlg)

    general_label = QLabel("General Notes")
    general_label.setStyleSheet(f"color: {DIALOG_TEXT};")
    layout.addWidget(general_label)

    general_edit = QTextEdit(notes_entry.get("general_notes", ""))
    general_edit.setStyleSheet(f"background-color: #2a2a2a; color: {DIALOG_TEXT}; border: 1px solid {DIALOG_BORDER};")
    layout.addWidget(general_edit, stretch=1)

    item_label = QLabel("Item Notes")
    item_label.setStyleSheet(f"color: {DIALOG_TEXT};")
    layout.addWidget(item_label)

    item_edit = QTextEdit(notes_entry.get("item_notes", ""))
    item_edit.setStyleSheet(f"background-color: #2a2a2a; color: {DIALOG_TEXT}; border: 1px solid {DIALOG_BORDER};")
    layout.addWidget(item_edit, stretch=1)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setStyleSheet(f"background-color: #2a2a2a; color: {DIALOG_TEXT}; border: 1px solid {DIALOG_BORDER}; padding: 5px 12px;")
    cancel_btn.clicked.connect(dlg.reject)
    save_btn = QPushButton("Save")
    save_btn.setStyleSheet(f"background-color: #2a2a2a; color: {DIALOG_TEXT}; border: 1px solid {DIALOG_BORDER}; padding: 5px 12px;")
    save_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(save_btn)
    layout.addLayout(btn_row)

    if dlg.exec():
        return {
            "general_notes": general_edit.toPlainText(),
            "item_notes": item_edit.toPlainText(),
        }
    return None