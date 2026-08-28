"""
modules/fallout4/editor.py

Wires the generic EditableTableDialog to FO4's data shapes: weapon
groups (nested: group -> weapons), named weapons (flat), utility perks
(flat), and weapon-type tags (flat).
"""

from ui.editable_table import EditableTableDialog


def open_weapon_groups_editor(parent, groups: list[dict]):
    def edit_weapons(group_row: dict):
        weapon_columns = [
            ("name", "Weapon", "text"),
            ("min_stats", "Min Stats (e.g. PER:3, INT:2)", "stats"),
            ("excluded", "Excluded", "bool"),
        ]
        weapon_dlg = EditableTableDialog(
            f"Weapons — {group_row.get('name', '(unnamed group)')}",
            weapon_columns,
            group_row.get("weapons", []),
            parent=parent,
        )
        if weapon_dlg.exec():
            group_row["weapons"] = weapon_dlg.get_result()

    columns = [("name", "Group", "text")]
    dlg = EditableTableDialog(
        "Manage Weapon Groups", columns, groups,
        extra_action=("Edit Weapons...", edit_weapons),
        extra_row_defaults={"weapons": list},
        parent=parent,
    )
    if dlg.exec():
        return dlg.get_result()
    return None


def open_named_weapons_editor(parent, named_weapons: list[dict]):
    columns = [
        ("name", "Weapon", "text"),
        ("type", "Type", "text"),
        ("dlc", "DLC (blank = base game)", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog("Manage Named Weapons", columns, named_weapons, parent=parent)
    if dlg.exec():
        return dlg.get_result()
    return None


def open_utility_perks_editor(parent, perks: list[dict]):
    columns = [
        ("name", "Perk", "text"),
        ("min_stats", "Min Stats (e.g. STR:1)", "stats"),
        ("requires", "Requires Tags", "tags"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog("Manage Perks", columns, perks, parent=parent)
    if dlg.exec():
        return dlg.get_result()
    return None


def open_weapon_tags_editor(parent, weapon_tags: list[dict]):
    columns = [
        ("name", "Weapon Type", "text"),
        ("tags", "Tags", "tags"),
    ]
    dlg = EditableTableDialog("Manage Weapon Tags", columns, weapon_tags, parent=parent)
    if dlg.exec():
        return dlg.get_result()
    return None