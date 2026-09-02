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
    QPushButton, QCheckBox, QLineEdit, QLabel, QComboBox,
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
    """One item: a clickable name (if on_name_click was given) --
    prefixed with '#<dex_id>' when the row has that field, plain name
    otherwise -- above a bare checkbox with an 'Excluded' caption below
    it. Stacked vertically on purpose: an inline 'Excluded' checkbox
    label made every column wide enough that a handful of columns
    filled an entire monitor. This way the checkbox itself carries no
    text at all, so columns can actually stay narrow."""

    def __init__(self, row: dict, on_name_click, parent=None):
        super().__init__(parent)
        self.row = row

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        display_name = row.get("name", "")
        dex_id = row.get("dex_id")
        if dex_id is not None:
            display_name = f"#{dex_id} {display_name}"

        if on_name_click:
            name_btn = QPushButton(display_name)
            name_btn.setStyleSheet(CELL_NAME_QSS)
            name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            name_btn.clicked.connect(lambda: on_name_click(self.row))
            layout.addWidget(name_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        else:
            name_lbl = QLabel(display_name)
            name_lbl.setStyleSheet(f"color: {DIALOG_TEXT}; font-size: 12px;")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(name_lbl)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(bool(row.get("excluded", False)))
        self.checkbox.setStyleSheet(CHECKBOX_QSS)
        layout.addWidget(self.checkbox, alignment=Qt.AlignmentFlag.AlignHCenter)

        excluded_caption = QLabel("Excluded")
        excluded_caption.setStyleSheet(f"color: #999999; font-size: 9px;")
        excluded_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(excluded_caption)

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
    sort_options: optional dict[label, callable(row_dict) -> sort_key]
                  -- if given, a small combo box lets the person switch
                  sort order (e.g. {"Dex #": lambda r: r["dex_id"],
                  "Name": lambda r: r["name"]}). Composes with the
                  search filter -- both apply together, not one or the
                  other. Omit entirely for a plain unsorted grid
                  (original list order), same as before this existed.

    get_result() returns the edited rows on Save, or None if cancelled
    -- same contract as EditableTableDialog.
    """

    def __init__(self, title, rows: list[dict], columns: int = 5,
                 on_name_click=None, sort_options: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(DIALOG_QSS)
        self.resize(720, 560)
        self.columns = columns
        self.rows = [dict(r) for r in rows]
        self.sort_options = sort_options or {}
        self._saved_rows = None

        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self._apply_filter)
        top_row.addWidget(self.search_box, 1)

        if self.sort_options:
            sort_label = QLabel("Sort:")
            sort_label.setStyleSheet(f"color: {DIALOG_TEXT};")
            top_row.addWidget(sort_label)
            self.sort_combo = QComboBox()
            self.sort_combo.addItems(list(self.sort_options.keys()))
            self.sort_combo.setStyleSheet(f"background-color: #2a2a2a; color: {DIALOG_TEXT}; border: 1px solid {DIALOG_BORDER}; padding: 4px 8px;")
            self.sort_combo.currentTextChanged.connect(self._apply_filter)
            top_row.addWidget(self.sort_combo)
        else:
            self.sort_combo = None

        layout.addLayout(top_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_widget = QWidget()
        # Same gotcha GameCard already had to work around: a plain QWidget
        # with only a stylesheet, no WA_StyledBackground, doesn't actually
        # paint its background -- without this, the grid's content area
        # falls back to a light system default regardless of DIALOG_BG,
        # leaving light DIALOG_TEXT effectively invisible against it.
        grid_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        grid_widget.setStyleSheet(f"background-color: {DIALOG_BG};")
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(4)
        scroll.setWidget(grid_widget)
        layout.addWidget(scroll, stretch=1)

        self._cells = [_GridCell(row, on_name_click) for row in self.rows]

        # If a sort was given, apply its first option immediately so the
        # initial grid matches what the combo visually shows as selected
        # -- otherwise it'd look sorted but not actually be, until the
        # person interacts with the combo at least once.
        if self.sort_combo:
            self._apply_filter()
        else:
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

    def _apply_filter(self, *_args):
        query = self.search_box.text().strip().lower()
        cells = self._cells
        if query:
            cells = [c for c in cells if query in c.name.lower()]
        if self.sort_combo:
            key_func = self.sort_options.get(self.sort_combo.currentText())
            if key_func:
                cells = sorted(cells, key=lambda c: key_func(c.row))
        self._layout_cells(cells)

    def _save_and_close(self):
        for cell in self._cells:
            cell.row["excluded"] = cell.checkbox.isChecked()
        self._saved_rows = self.rows
        self.accept()

    def get_result(self):
        return self._saved_rows