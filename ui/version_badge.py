"""
ui/version_badge.py

Small reusable widget: a hand-maintained "game version" string per module,
so you can tell at a glance whether your compiled skill/relic/etc. lists
might be stale after a game update. Purely manual for now -- no automatic
version checking (e.g. against SteamDB) is done; that's a possible future
upgrade, this just gives you a place to record what you last checked
against.

Backed by a tiny version.yaml living in that module's own config folder,
independent of whatever other config files that module has.
"""

from pathlib import Path

import yaml
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit
from PySide6.QtCore import Qt


def load_game_version(config_dir: Path) -> str:
    path = Path(config_dir) / "version.yaml"
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("game_version", "")


def save_game_version(config_dir: Path, version: str) -> None:
    path = Path(config_dir) / "version.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"game_version": version}, f, sort_keys=False)


class VersionBadge(QWidget):
    """Label + editable text field for a module's hand-tracked game
    version. Saves automatically when you press Enter or click away."""

    def __init__(self, config_dir: Path, text_color: str, accent_color: str,
                 bg_color: str, font_family: str, parent=None):
        super().__init__(parent)
        self.config_dir = Path(config_dir)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel("Data compiled for game version:")
        label.setStyleSheet(f"color: {text_color}; font-family: '{font_family}'; font-size: 10px;")
        layout.addWidget(label)

        self.edit = QLineEdit(load_game_version(self.config_dir))
        self.edit.setPlaceholderText("e.g. 1.2.1.0")
        self.edit.setFixedWidth(110)
        self.edit.setStyleSheet(f"""
            QLineEdit {{
                color: {text_color}; background-color: {bg_color};
                border: 1px solid {accent_color}; padding: 3px 6px;
                font-family: '{font_family}'; font-size: 10px;
            }}
        """)
        self.edit.editingFinished.connect(self._save)
        layout.addWidget(self.edit)

    def _save(self):
        save_game_version(self.config_dir, self.edit.text().strip())