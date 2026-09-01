"""
ui/toggle_grid.py

Generic reusable grid editor for large flat lists where a normal
row-per-item table (EditableTableDialog) would be too tall to
comfortably browse -- shows items in a fixed-column grid instead, each
cell a clickable name plus an "excluded" checkbox. Built for Dota's
~120-hero roster; general enough for any future module with a big flat
list (a full Pokemon species list, say).

Same sharing boundary as EditableTableDialog: this owns the generic
"browse/toggle a big flat list, optionally act on a clicked name"
mechanism, nothing about what the items actually mean. A caller wires
up on_name_click to do something specific (e.g. Dota's per-hero notes)
without this file knowing anything about what that specific thing is --
same relationship EditableTableDialog's extra_action already has with
every module that nests through it. Palette is fixed and neutral, same
reasoning as EditableTableDialog's: a shared editing dialog isn't part
of any module's visual identity.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QWidget,
    QPushButton, QCheckBox, QLineEdit, QLabel,
)
from PySide6.QtCore import Qt

DIALOG_BG = "#1c1c1c"
DIALOG_TEXT = "#eaeaea"
DIALOG_BORDER = "#444"
CHECK_ON = "#5ec26a"

DIALOG_QSS = f"""
    QDialog {{ background-color: {DIALOG_BG}; }}
    QScrollArea {{ background-color: {DIALOG_BG}; border: 1px solid {DIALOG_BORDER}; }}
    QPushButton {{
        background-color: #2a2a2a; color: {DIALOG_TEXT};
        border: 1px solid {DIALOG_BORDER}; padding: 5px 12px;
    }}
    QPushButton:hover {{ background-color: #383838; }}
    QLineEdit {{
        background-color: #2a2a2a; color: {DIALOG_TEXT};
        border: 1px solid {DIALOG_BORDER}; padding: 5px 8px;
    }}
"""

CELL_NAME_QSS = f"""
    QPushButton {{
        background-color: transparent; color: {DIALOG_TEXT};
        border: none; text-align: left; padding: 2px 0px;
        font-size: 12px;
    }}
    QPushButton:hover {{ color: {CHECK_ON}; text-decoration: underline; }}
"""

CHECKBOX_QSS = f"""
    QCheckBox {{ color: #aaaaaa; font-size: 10px; }}
    QCheckBox::indicator {{
        width: 14px; height: 14px;
        border: 1px solid {DIALOG_TEXT}; border-radius: 2px;
        background: transparent;
    }}
    QCheckBox::indicator:checked {{
        background-color: {CHECK_ON}; border: 1px solid {CHECK_ON};
    }}
"""


class _GridCell(QWidget):
    """One item: a clickable name (if on_name_click was given) stacked
    above an 'Excluded' checkbox."""

    def __init__(self, row: dict, on_name_click, parent=None):
        super().__init__(parent)
        self.row = row

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        if on_name_click:
            name_btn = QPushButton(row.get("name", ""))
            name_btn.setStyleSheet(CELL_NAME_QSS)
            name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            name_btn.clicked.connect(lambda: on_name_click(self.row))
            layout.addWidget(name_btn)
        else:
            name_lbl = QLabel(row.get("name", ""))
            name_lbl.setStyleSheet(f"color: {DIALOG_TEXT}; font-size: 12px;")
            layout.addWidget(name_lbl)

        self.checkbox = QCheckBox("Excluded")
        self.checkbox.setChecked(bool(row.get("excluded", False)))
        self.checkbox.setStyleSheet(CHECKBOX_QSS)
        layout.addWidget(self.checkbox)

    @property
    def name(self) -> str:
        return self.row.get("name", "")


class ToggleGridDialog(QDialog):
    """
    rows: list[dict] -- each needs at least 'name'; 'excluded' read/
          written, everything else in the dict passes through untouched.
    columns: how many cells per row of the grid.
    on_name_click: optional callable(row_dict) -- if given, each cell's
                   name becomes a clickable button that calls this
                   instead of just displaying plain text. Doesn't touch
                   the checkbox/excluded state at all -- purely a hook
                   for the caller to do something else (open notes,
                   whatever) when a name is clicked.

    get_result() returns the edited rows on Save, or None if cancelled
    -- same contract as EditableTableDialog.
    """

    def __init__(self, title, rows: list[dict], columns: int = 5,
                 on_name_click=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(DIALOG_QSS)
        self.resize(720, 560)
        self.columns = columns
        self.rows = [dict(r) for r in rows]
        self._saved_rows = None

        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(4)
        scroll.setWidget(grid_widget)
        layout.addWidget(scroll, stretch=1)

        self._cells = [_GridCell(row, on_name_click) for row in self.rows]
        self._layout_cells(self._cells)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _layout_cells(self, cells):
        """Rebuilds the grid from scratch with just these cells --
        removeWidget/takeAt don't delete the widgets, just detach them
        from the layout, so this is safe to call repeatedly on filter
        changes without losing checkbox state."""
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)
        for i, cell in enumerate(cells):
            row, col = divmod(i, self.columns)
            self.grid_layout.addWidget(cell, row, col)
            cell.setVisible(True)
        for cell in self._cells:
            if cell not in cells:
                cell.setVisible(False)

    def _apply_filter(self, query: str):
        query = query.strip().lower()
        if not query:
            self._layout_cells(self._cells)
            return
        matches = [c for c in self._cells if query in c.name.lower()]
        self._layout_cells(matches)

    def _save_and_close(self):
        for cell in self._cells:
            cell.row["excluded"] = cell.checkbox.isChecked()
        self._saved_rows = self.rows
        self.accept()

    def get_result(self):
        return self._saved_rows