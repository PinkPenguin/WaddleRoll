"""
modules/torchlight_infinite/editor.py

Wires the generic EditableTableDialog to Torchlight Infinite's data
shapes: skills (flat, with tags) and heroes (nested: hero -> traits).
"""

from ui.editable_table import EditableTableDialog


def open_skills_editor(parent, skills: list[dict]):
    columns = [
        ("name", "Skill", "text"),
        ("tags", "Tags (comma-separated)", "tags"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog("Manage Skills", columns, skills, parent=parent)
    if dlg.exec():
        return dlg.get_result()
    return None


def open_heroes_editor(parent, heroes: list[dict]):
    def edit_traits(hero_row: dict):
        trait_columns = [
            ("name", "Trait", "text"),
            ("tags", "Tags (comma-separated)", "tags"),
            ("excluded", "Excluded", "bool"),
        ]
        trait_dlg = EditableTableDialog(
            f"Traits — {hero_row.get('name', '(unnamed hero)')}",
            trait_columns,
            hero_row.get("traits", []),
            parent=parent,
        )
        if trait_dlg.exec():
            hero_row["traits"] = trait_dlg.get_result()

    columns = [
        ("name", "Hero", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog(
        "Manage Heroes", columns, heroes,
        extra_action=("Edit Traits...", edit_traits),
        extra_row_defaults={"traits": list},
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None