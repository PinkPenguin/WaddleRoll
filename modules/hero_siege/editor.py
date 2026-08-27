"""
modules/hero_siege/editor.py

Wires the generic EditableTableDialog to Hero Siege's specific data shape:
classes (name, tags, excluded, + nested skills) and relics (name, tags,
excluded). Returns edited data on Save, or None if the dialog was cancelled.
"""

from ui.editable_table import EditableTableDialog


def open_relics_editor(parent, relics: list[dict]):
    columns = [
        ("name", "Relic", "text"),
        ("tags", "Tags (comma-separated)", "tags"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog("Manage Relics", columns, relics, parent=parent)
    if dlg.exec():
        return dlg.get_result()
    return None


def open_classes_editor(parent, classes: list[dict]):
    def edit_skills(class_row: dict):
        skill_columns = [
            ("name", "Skill", "text"),
            ("tree", "Tree", "text"),
            ("excluded", "Excluded", "bool"),
        ]
        skill_dlg = EditableTableDialog(
            f"Skills — {class_row.get('name', '(unnamed class)')}",
            skill_columns,
            class_row.get("skills", []),
            parent=parent,
        )
        if skill_dlg.exec():
            # Mutates the same dict object that lives in the outer table's
            # row list, so the parent editor picks this up automatically.
            class_row["skills"] = skill_dlg.get_result()

    columns = [
        ("name", "Class", "text"),
        ("tags", "Tags (comma-separated)", "tags"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog(
        "Manage Classes", columns, classes,
        extra_action=("Edit Skills...", edit_skills),
        extra_row_defaults={"skills": list},
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None