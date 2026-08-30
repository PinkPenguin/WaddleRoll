"""
ui/editable_table.py

Generic reusable table editor for lists of dicts -- add/remove/edit rows,
with a text/bool/tags column model. Not game-specific: any module can use
this to give itself an in-app CRUD editor instead of requiring hand-edited
config files. Hero Siege is the first user; PoE/others can reuse it.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QCheckBox, QHeaderView, QLineEdit,
)
from PySide6.QtCore import Qt

# Neutral dark theme, independent of whichever module opened this dialog --
# guarantees checkbox/text contrast regardless of OS theme (the original
# bug: unstyled QCheckBox indicators can render nearly invisible against
# a dark OS theme).
DIALOG_BG = "#1c1c1c"
DIALOG_TEXT = "#eaeaea"
DIALOG_BORDER = "#444"
CHECK_ON = "#5ec26a"  # bright, unambiguous "on" color independent of any module's palette

DIALOG_QSS = f"""
    QDialog {{ background-color: {DIALOG_BG}; }}
    QTableWidget {{
        background-color: {DIALOG_BG}; color: {DIALOG_TEXT};
        gridline-color: {DIALOG_BORDER}; border: 1px solid {DIALOG_BORDER};
    }}
    QHeaderView::section {{
        background-color: #2a2a2a; color: {DIALOG_TEXT};
        border: 1px solid {DIALOG_BORDER}; padding: 4px;
    }}
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

CHECKBOX_QSS = f"""
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {DIALOG_TEXT}; border-radius: 2px;
        background: transparent;
    }}
    QCheckBox::indicator:checked {{
        background-color: {CHECK_ON}; border: 1px solid {CHECK_ON};
    }}
"""


class EditableTableDialog(QDialog):
    """
    columns: list of (field_key, header_label, field_type) tuples.
             field_type is one of "text", "bool", "tags" (tags is stored
             as a list[str], edited as a comma-separated string).
    rows: list[dict] -- a working copy is made; originals aren't mutated
          unless you use the returned result.
    extra_action: optional (button_label, callback(row_dict)) -- adds an
                  extra per-row button, e.g. "Edit Skills..." to drill into
                  nested data that doesn't fit in a flat table.
    extra_row_defaults: optional dict[str, callable] for fields not shown
                        as columns but needed on new rows (e.g. a nested
                        "skills": list factory).
    """

    def __init__(self, title, columns, rows, extra_action=None,
                 extra_row_defaults=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(DIALOG_QSS)
        self.resize(680, 480)
        self.columns = columns
        self.rows = [dict(r) for r in rows]
        self.extra_action = extra_action
        self.extra_row_defaults = extra_row_defaults or {}
        self._saved_rows = None

        # 'excluded' is a convention followed at every level of every
        # module's data, but this dialog doesn't assume it's there --
        # only offers the "show excluded only" filter when a caller
        # actually included that column.
        self._excluded_col_index = next(
            (i for i, (key, _label, _ftype) in enumerate(columns) if key == "excluded"), None
        )

        layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.search_box, 1)

        if self._excluded_col_index is not None:
            self.excluded_only_cb = QCheckBox("Show Excluded Only")
            self.excluded_only_cb.setStyleSheet(f"QCheckBox {{ color: {DIALOG_TEXT}; }}\n{CHECKBOX_QSS}")
            self.excluded_only_cb.toggled.connect(self._apply_filter)
            filter_row.addWidget(self.excluded_only_cb)
        else:
            self.excluded_only_cb = None

        layout.addLayout(filter_row)

        self.table = QTableWidget()
        col_count = len(columns) + (1 if extra_action else 0)
        self.table.setColumnCount(col_count)
        headers = [c[1] for c in columns] + ([extra_action[0]] if extra_action else [])
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self._populate()

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Row")
        add_btn.clicked.connect(self._add_row)
        remove_btn = QPushButton("- Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _populate(self):
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            self._populate_row(r, row)

    def _populate_row(self, r, row):
        for c, (key, _label, ftype) in enumerate(self.columns):
            if ftype == "bool":
                cb = QCheckBox()
                cb.setChecked(bool(row.get(key, False)))
                cb.setStyleSheet(CHECKBOX_QSS)
                if c == self._excluded_col_index:
                    # Live-reactive: unchecking "excluded" while "Show
                    # Excluded Only" is active should drop the row out of
                    # view immediately, not just after Save+reopen -- this
                    # is specifically what makes "browse and fix mistakes"
                    # workable in one pass.
                    cb.toggled.connect(self._apply_filter)
                self.table.setCellWidget(r, c, cb)
            elif ftype == "tags":
                text = ", ".join(row.get(key, []) or [])
                self.table.setItem(r, c, QTableWidgetItem(text))
            elif ftype == "stats":
                pairs = row.get(key, {}) or {}
                text = ", ".join(f"{k}:{v}" for k, v in pairs.items())
                self.table.setItem(r, c, QTableWidgetItem(text))
            else:
                self.table.setItem(r, c, QTableWidgetItem(str(row.get(key, ""))))

        if self.extra_action:
            label, callback = self.extra_action
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked=False, row=row: callback(row))
            self.table.setCellWidget(r, len(self.columns), btn)

    def _add_row(self):
        new_row = {}
        for key, _label, ftype in self.columns:
            new_row[key] = [] if ftype == "tags" else ({} if ftype == "stats" else (False if ftype == "bool" else ""))
        for key, factory in self.extra_row_defaults.items():
            new_row[key] = factory()

        self.rows.append(new_row)
        self.table.setRowCount(len(self.rows))
        self._populate_row(len(self.rows) - 1, new_row)
        self._apply_filter()

    def _remove_selected(self):
        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for r in selected_rows:
            del self.rows[r]
            self.table.removeRow(r)

    def _apply_filter(self, *_args):
        """Re-applies both active filters together: the text search (still
        read from self.rows, same as before -- doesn't reflect an unsaved
        text edit mid-session, matching existing behavior) and "Show
        Excluded Only" (read live from each row's actual checkbox widget,
        not the stale self.rows snapshot, so toggling excluded off while
        filtered updates the view immediately)."""
        query = self.search_box.text().strip().lower()
        show_excluded_only = bool(self.excluded_only_cb and self.excluded_only_cb.isChecked())

        for r, row in enumerate(self.rows):
            matches_query = True
            if query:
                haystack_parts = []
                for key, _label, ftype in self.columns:
                    if ftype == "tags":
                        haystack_parts.append(", ".join(row.get(key, []) or []))
                    elif ftype == "stats":
                        haystack_parts.append(", ".join(f"{k}:{v}" for k, v in (row.get(key, {}) or {}).items()))
                    elif ftype == "text":
                        haystack_parts.append(str(row.get(key, "")))
                haystack = " ".join(haystack_parts).lower()
                matches_query = query in haystack

            matches_excluded = True
            if show_excluded_only:
                cb = self.table.cellWidget(r, self._excluded_col_index)
                matches_excluded = bool(cb.isChecked()) if cb else bool(row.get("excluded", False))

            self.table.setRowHidden(r, not (matches_query and matches_excluded))

    def _harvest(self):
        """Pulls current widget/item values back into self.rows before saving."""
        for r, row in enumerate(self.rows):
            for c, (key, _label, ftype) in enumerate(self.columns):
                if ftype == "bool":
                    cb = self.table.cellWidget(r, c)
                    row[key] = cb.isChecked() if cb else False
                elif ftype == "tags":
                    item = self.table.item(r, c)
                    text = item.text() if item else ""
                    row[key] = [t.strip() for t in text.split(",") if t.strip()]
                elif ftype == "stats":
                    item = self.table.item(r, c)
                    text = item.text() if item else ""
                    parsed = {}
                    for chunk in text.split(","):
                        chunk = chunk.strip()
                        if not chunk or ":" not in chunk:
                            continue
                        stat, _, val = chunk.partition(":")
                        stat = stat.strip()
                        val = val.strip()
                        try:
                            parsed[stat] = int(val)
                        except ValueError:
                            try:
                                parsed[stat] = float(val)
                            except ValueError:
                                continue
                    row[key] = parsed
                else:
                    item = self.table.item(r, c)
                    row[key] = item.text() if item else ""

    def _save_and_close(self):
        self._harvest()
        self._saved_rows = self.rows
        self.accept()

    def get_result(self):
        """Returns the edited rows if Save was clicked, else None (Cancel/closed)."""
        return self._saved_rows