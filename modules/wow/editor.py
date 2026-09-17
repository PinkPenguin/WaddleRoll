"""
modules/wow/editor.py

Thin wiring layer, matching every other module's editor.py shape:
one EditableTableDialog for classes, with races nested via
extra_action (a class's races are edited via their own child dialog,
opened from the parent row -- same mechanism Last Epoch's 3-level
class->skill->node nesting uses, just one level deep here).
"""

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


def open_classes_editor(parent, classes: list[dict]):
    columns = [
        ("name", "Class", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog(
        title="Manage Classes",
        columns=columns,
        rows=classes,
        extra_action=("Edit Races...", lambda row: open_races_editor(parent, row)),
        extra_row_defaults={"races": list},
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None