"""
modules/rimworld/editor.py

Wires the generic EditableTableDialog to RimWorld's three flat data
shapes: structures, memes (with an axis field for mutual-exclusivity
grouping), and precepts (issue/precept/requirement/associated).
"""

from ui.editable_table import EditableTableDialog


def open_structures_editor(parent, structures: list[dict]):
    columns = [
        ("name", "Structure", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog("Manage Structures", columns, structures, parent=parent)
    if dlg.exec():
        return dlg.get_result()
    return None


def open_memes_editor(parent, memes: list[dict]):
    columns = [
        ("name", "Meme", "text"),
        ("axis", "Axis (blank = standalone)", "text"),
        ("impact", "Impact (low/medium/high)", "text"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog("Manage Memes", columns, memes, parent=parent)
    if dlg.exec():
        return dlg.get_result()
    return None


def open_precepts_editor(parent, precepts: list[dict]):
    columns = [
        ("issue", "Issue", "text"),
        ("precept", "Precept", "text"),
        ("requirement", "Requirement (comma-separated, 'Not X' allowed)", "tags"),
        ("associated", "Associated Memes", "tags"),
        ("required", "Issue Required (must always resolve)", "bool"),
        ("extreme", "Extreme Option", "bool"),
        ("excluded", "Excluded", "bool"),
    ]
    dlg = EditableTableDialog("Manage Precepts", columns, precepts, parent=parent)
    if dlg.exec():
        return dlg.get_result()
    return None