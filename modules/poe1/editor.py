"""
modules/poe1/editor.py

Thin wiring layer connecting PoE1's skills.yaml/classes.yaml to the
shared EditableTableDialog. Two entry points: skills (flat) and classes
(nested one level into ascendancies) -- same shape as PoE2's editor.py.
"""

from ui.editable_table import EditableTableDialog


def open_skills_editor(parent, skills: list[dict]):
    dlg = EditableTableDialog(
        title="Manage Skills",
        columns=[
            ("name", "Name", "text"),
            ("is_vaal_skill", "Vaal", "bool"),
            ("is_item_skill", "Item", "bool"),
            ("is_ascendancy_skill", "Ascendancy", "bool"),
            ("excluded", "Excluded", "bool"),
        ],
        rows=skills,
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None


def open_classes_editor(parent, classes: list[dict]):
    """Classes -> ascendancies, one level of nesting via extra_action --
    same mechanism as every other nested editor in the project. The
    callback receives the actual class dict (not a copy) and mutates its
    'ascendancies' key in place on save."""

    def edit_ascendancies(class_row):
        dlg = EditableTableDialog(
            title=f"Manage Ascendancies — {class_row.get('name', '')}",
            columns=[
                ("name", "Name", "text"),
                ("excluded", "Excluded", "bool"),
            ],
            rows=class_row.get("ascendancies", []),
            parent=parent,
        )
        if dlg.exec():
            class_row["ascendancies"] = dlg.get_result()

    dlg = EditableTableDialog(
        title="Manage Classes",
        columns=[
            ("name", "Name", "text"),
            ("excluded", "Excluded", "bool"),
        ],
        rows=classes,
        extra_action=("Edit Ascendancies...", edit_ascendancies),
        extra_row_defaults={"ascendancies": list},
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None