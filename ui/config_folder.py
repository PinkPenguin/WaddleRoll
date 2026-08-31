"""
ui/config_folder.py

Cross-platform "open this folder in the OS file browser" -- the exact
same three-branch os.startfile/subprocess dispatch every module needed,
byte-for-byte identical across all six. Zero game-specific knowledge,
so it lives here once instead of being copy-pasted per module.
"""

import os
import platform
import subprocess


def open_config_folder(path) -> None:
    path = str(path)
    system = platform.system()
    if system == "Windows":
        os.startfile(path)  # noqa: S606 -- Windows-only call, deliberate
    elif system == "Darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])