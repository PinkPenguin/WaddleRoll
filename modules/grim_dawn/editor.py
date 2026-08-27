"""
modules/grim_dawn/editor.py

Wires the generic EditableTableDialog to Grim Dawn's data shape:
masteries (name, excluded, + nested skills).
"""

from ui.editable_table import EditableTableDialog


def open_masteries_editor(parent, masteries: list[dict]):
    def edit_skills(mastery_row: dict):
        skill_columns = [
            ("name", "Skill", "text"),
            ("excluded", "Excluded", "bool"),
        ]
        skill_dlg = EditableTableDialog(
            f"Skills — {mastery_row.get('name', '(unnamed mastery)')}",
            skill_columns,
            mastery_row.get("skills", []),
            parent=parent,
        )
        if skill_dlg.exec():
            mastery_row["skills"] = skill_dlg.get_result()

    columns = [
        ("name", "Mastery", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog(
        "Manage Masteries", columns, masteries,
        extra_action=("Edit Skills...", edit_skills),
        extra_row_defaults={"skills": list},
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None