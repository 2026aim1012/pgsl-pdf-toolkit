"""
main.py
-------
Application entry point for PGSL PDF Toolkit.
Initializes the Qt Application, loads stylesheets and resources,
and displays the integrated MainWindow.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# Ensure gui directory is in sys.path
_gui_dir = str(Path(__file__).resolve().parent / "gui")
if _gui_dir not in sys.path:
    sys.path.insert(0, _gui_dir)

from pdf_toolkit.gui.main_window import MainWindow, ensure_application_fonts
from pdf_toolkit.gui.session import Session


def load_stylesheet(dark_mode: bool = False) -> str:
    """Load application QSS stylesheet for light or dark mode."""
    resources_dir = Path(__file__).resolve().parent / "resources"
    filename = "style_dark.qss" if dark_mode else "style.qss"
    qss_path = resources_dir / filename
    if qss_path.is_file():
        try:
            return qss_path.read_text(encoding="utf-8")
        except OSError:
            pass
    if dark_mode:
        fallback = resources_dir / "style.qss"
        if fallback.is_file():
            try:
                return fallback.read_text(encoding="utf-8")
            except OSError:
                pass
    return ""


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PGSL PDF Toolkit")
    app.setApplicationDisplayName("PGSL PDF Toolkit — IIT Ropar")
    app.setOrganizationName("IIT Ropar")

    # Load embedded application fonts
    ensure_application_fonts()

    # Set accessible default UI font (12pt minimum)
    font = QFont(
        "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif"
    )
    font.setPointSize(12)
    app.setFont(font)

    # Apply stylesheet based on persisted theme setting
    settings = QSettings("PGSL", "PDF Toolkit")
    dark_mode = settings.value("dark_mode", False, type=bool)
    stylesheet = load_stylesheet(dark_mode=dark_mode)
    if stylesheet:
        app.setStyleSheet(stylesheet)

    # Initialize shared Session hub and MainWindow
    session = Session()
    window = MainWindow(session=session)
    window.show()

    exit_code = app.exec()
    session.cleanup()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
