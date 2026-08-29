"""
modules/poe2/editor.py

Wires the generic EditableTableDialog to PoE2's data shapes: skills
(flat, with vaal/item/ascendancy tag columns) and classes (nested:
class -> ascendancies).
"""

from ui.editable_table import EditableTableDialog


def open_skills_editor(parent, skills: list[dict]):
    columns = [
        ("name", "Skill", "text"),
        ("is_vaal_skill", "Vaal Skill", "bool"),
        ("is_item_skill", "Item Skill", "bool"),
        ("is_ascendancy_skill", "Ascendancy Skill", "bool"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog("Manage Skills", columns, skills, parent=parent)
    if dlg.exec():
        return dlg.get_result()
    return None


def open_classes_editor(parent, classes: list[dict]):
    def edit_ascendancies(class_row: dict):
        asc_columns = [
            ("name", "Ascendancy", "text"),
            ("excluded", "Excluded", "bool"),
        ]
        asc_dlg = EditableTableDialog(
            f"Ascendancies — {class_row.get('name', '(unnamed class)')}",
            asc_columns,
            class_row.get("ascendancies", []),
            parent=parent,
        )
        if asc_dlg.exec():
            class_row["ascendancies"] = asc_dlg.get_result()

    columns = [
        ("name", "Class", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog(
        "Manage Classes", columns, classes,
        extra_action=("Edit Ascendancies...", edit_ascendancies),
        extra_row_defaults={"ascendancies": list},
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None