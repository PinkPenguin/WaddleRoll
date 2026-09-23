"""
modules/wow/editor.py

Thin wiring layer, matching every other module's editor.py shape:
EditableTableDialog for classes, with races AND specs both nested
under a class row, plus a separate top-level editor for professions
(unrelated to class/race/spec -- any class can learn any profession in
real WoW, so this isn't nested under anything).

EditableTableDialog only supports one extra_action per row (a single
label+callback), but a class row here has TWO things worth drilling
into -- races and specs. Rather than guessing at extending that shared
component (its current source isn't in this session to safely modify),
_open_class_detail_chooser is a small, self-contained picker dialog
that routes to whichever child editor the user actually wants; the
classes table's own extra_action just opens this chooser instead of
either child editor directly.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel

from ui.editable_table import EditableTableDialog


def open_races_editor(parent, class_row: dict):
    columns = [
        ("name", "Race", "text"),
        ("faction", "Faction", "tags"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog(
        title=f"Races — {class_row.get('name', '(unnamed class)')}",
        columns=columns,
        rows=class_row.get("races", []),
        parent=parent,
    )
    if dlg.exec():
        class_row["races"] = dlg.get_result()


def open_specs_editor(parent, class_row: dict):
    columns = [
        ("name", "Spec", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog(
        title=f"Specs — {class_row.get('name', '(unnamed class)')}",
        columns=columns,
        rows=class_row.get("specs", []),
        parent=parent,
    )
    if dlg.exec():
        class_row["specs"] = dlg.get_result()


def _open_class_detail_chooser(parent, class_row: dict):
    """Small picker routing to races or specs -- see module docstring
    for why this exists instead of a second extra_action."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Edit — {class_row.get('name', '(unnamed class)')}")
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("What would you like to edit?"))

    choice = {"value": None}

    def pick(which):
        choice["value"] = which
        dlg.accept()

    races_btn = QPushButton("Races...")
    races_btn.clicked.connect(lambda: pick("races"))
    layout.addWidget(races_btn)

    specs_btn = QPushButton("Specs...")
    specs_btn.clicked.connect(lambda: pick("specs"))
    layout.addWidget(specs_btn)

    # Fully close the chooser (dlg.exec() returns) before opening
    # either child editor -- opening a new modal from inside a button's
    # own click handler, while this dialog is still tearing itself
    # down, is the kind of thing worth avoiding rather than assuming
    # is safe.
    dlg.exec()

    if choice["value"] == "races":
        open_races_editor(parent, class_row)
    elif choice["value"] == "specs":
        open_specs_editor(parent, class_row)


def open_classes_editor(parent, classes: list[dict]):
    columns = [
        ("name", "Class", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog(
        title="Manage Classes",
        columns=columns,
        rows=classes,
        extra_action=("Edit Races/Specs...", lambda row: _open_class_detail_chooser(parent, row)),
        extra_row_defaults={"races": list, "specs": list},
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None


def open_professions_editor(parent, professions: list[dict]):
    """Flat, top-level list -- professions aren't nested under class,
    race, or anything else, since any class can learn any profession.

    "category" expects exactly "primary" or "secondary" (case-
    sensitive, matching roll_professions()'s own check) -- this is a
    plain text field, not a dropdown, since EditableTableDialog doesn't
    have a constrained-choice field type; nothing here enforces the
    value, same as everywhere else in this project that has this
    limitation. "type" ("gathering" or "crafting") only meaningfully
    applies to primary professions -- leave it blank for secondary
    ones, roll_professions() never reads it for those anyway."""
    columns = [
        ("name", "Profession", "text"),
        ("category", "Category (primary/secondary)", "text"),
        ("type", "Type (gathering/crafting)", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog(
        title="Manage Professions",
        columns=columns,
        rows=professions,
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None