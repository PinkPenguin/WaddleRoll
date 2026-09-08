"""
main.py

Entry point for the launcher shell. Run this file to start the app.
"""

import sys
from PySide6.QtWidgets import QApplication

from core.paths import ensure_resources_extracted
from ui.main_window import MainWindow


def main():
    ensure_resources_extracted()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()