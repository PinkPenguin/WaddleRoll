"""
modules/last_epoch/editor.py

Wires the generic EditableTableDialog to Last Epoch's data shape, three
levels deep: classes -> skills -> nodes. Each level reuses the same
generic dialog, just nested via extra_action.
"""

from ui.editable_table import EditableTableDialog


def open_classes_editor(parent, classes: list[dict]):
    def edit_skills(class_row: dict):
        def edit_nodes(skill_row: dict):
            node_columns = [
                ("name", "Node", "text"),
                ("notable", "Notable", "bool"),
                ("excluded", "Excluded", "bool"),
            ]
            node_dlg = EditableTableDialog(
                f"Nodes — {skill_row.get('name', '(unnamed skill)')}",
                node_columns,
                skill_row.get("nodes", []),
                parent=parent,
            )
            if node_dlg.exec():
                skill_row["nodes"] = node_dlg.get_result()

        skill_columns = [
            ("name", "Skill", "text"),
            ("excluded", "Excluded", "bool"),
        ]
        skill_dlg = EditableTableDialog(
            f"Skills — {class_row.get('name', '(unnamed class)')}",
            skill_columns,
            class_row.get("skills", []),
            extra_action=("Edit Nodes...", edit_nodes),
            extra_row_defaults={"nodes": list},
            parent=parent,
        )
        if skill_dlg.exec():
            class_row["skills"] = skill_dlg.get_result()

    columns = [
        ("name", "Class", "text"),
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