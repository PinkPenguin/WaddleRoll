"""
ui/module_visibility.py

Small dialog letting the person choose which discovered modules show
up on the picker screen. A plain checkbox per module, not a full
EditableTableDialog -- there's nothing to add or remove here, just
toggle a fixed, known set (whatever discover_modules() actually found),
so the generic list-editor's add/remove affordances would just be
confusing UI that doesn't do anything meaningful in this context.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QScrollArea,
    QWidget, QLabel,
)

DIALOG_BG = "#1c1c1c"
DIALOG_TEXT = "#eaeaea"
DIALOG_BORDER = "#444"


def open_module_visibility_dialog(parent, modules: list, hidden_ids: set):
    """
    modules: every discovered GameModule instance, not just the
             currently-visible ones -- this dialog is how a hidden one
             gets shown again.
    hidden_ids: set of module ids currently hidden.

    Returns the new set of hidden ids on Save, or None if cancelled.
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle("Manage Visible Games")
    dlg.setStyleSheet(f"background-color: {DIALOG_BG};")
    dlg.resize(360, 480)

    layout = QVBoxLayout(dlg)

    label = QLabel("Choose which games show up on the picker screen:")
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {DIALOG_TEXT};")
    layout.addWidget(label)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(f"QScrollArea {{ background-color: {DIALOG_BG}; border: 1px solid {DIALOG_BORDER}; }}")

    inner = QWidget()
    inner.setStyleSheet(f"background-color: {DIALOG_BG};")
    inner_layout = QVBoxLayout(inner)

    checkboxes = {}
    for module in sorted(modules, key=lambda m: m.display_name):
        cb = QCheckBox(f"{module.icon}  {module.display_name}")
        cb.setChecked(module.id not in hidden_ids)
        cb.setStyleSheet(f"color: {DIALOG_TEXT}; padding: 4px;")
        inner_layout.addWidget(cb)
        checkboxes[module.id] = cb
    inner_layout.addStretch(1)

    scroll.setWidget(inner)
    layout.addWidget(scroll, stretch=1)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setStyleSheet(f"background-color: #2a2a2a; color: {DIALOG_TEXT}; border: 1px solid {DIALOG_BORDER}; padding: 6px 14px;")
    cancel_btn.clicked.connect(dlg.reject)
    save_btn = QPushButton("Save")
    save_btn.setStyleSheet(f"background-color: #2a2a2a; color: {DIALOG_TEXT}; border: 1px solid {DIALOG_BORDER}; padding: 6px 14px;")
    save_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(save_btn)
    layout.addLayout(btn_row)

    if dlg.exec():
        return {module_id for module_id, cb in checkboxes.items() if not cb.isChecked()}
    return None