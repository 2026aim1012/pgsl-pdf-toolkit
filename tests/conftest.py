import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

# Run headless in test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Ensure src and src/pdf_toolkit/gui are in sys.path
root_dir = Path(__file__).resolve().parent.parent
gui_dir = root_dir / "src" / "pdf_toolkit" / "gui"
for p in [str(root_dir / "src"), str(gui_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
