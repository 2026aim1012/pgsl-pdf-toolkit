"""
Unit tests for MainWindow, StatusBarWidget, and GUI integration.
"""

import pikepdf

from pdf_toolkit.gui.main_window import APP_TITLE, MainWindow
from pdf_toolkit.gui.session import Session
from pdf_toolkit.gui.widgets.status_bar import StatusBarWidget


def test_status_bar_initial_state(qapp):
    session = Session()
    bar = StatusBarWidget(session)

    assert "No document open" in bar.file_info_label.text()
    assert bar.status_message_label.text() == "Ready"
    assert not bar.progress_container.isVisible()
    assert bar.progress_bar.value() == 0
    assert bar.percent_label.text() == "0%"

    session.cleanup()


def test_status_bar_updates(qapp):
    session = Session()
    bar = StatusBarWidget(session)
    bar.show()

    # File info update
    session.fileInfoChanged.emit("TestFile.pdf · 1.20 MB")
    assert bar.file_info_label.text() == "TestFile.pdf · 1.20 MB"

    # Status message update
    session.statusMessage.emit("Rotating pages...")
    assert bar.status_message_label.text() == "Rotating pages..."

    # Error message update
    session.errorMessage.emit("File not found")
    assert "Error: File not found" in bar.status_message_label.text()

    # Progress bar and percent
    session.busyChanged.emit(True)
    assert bar.progress_container.isVisible()

    session.progressPercent.emit(45)
    assert bar.progress_bar.value() == 45
    assert bar.percent_label.text() == "45%"

    session.busyChanged.emit(False)
    assert not bar.progress_container.isVisible()

    session.cleanup()


def test_session_navigation_helpers(qapp, tmp_path):
    # Create sample 3-page PDF
    pdf_path = tmp_path / "nav_test.pdf"
    pdf = pikepdf.new()
    for _ in range(3):
        pdf.add_blank_page(page_size=(100, 100))
    pdf.save(pdf_path)

    session = Session()
    assert session.open(pdf_path)
    assert session.page == 0
    assert session.page_count == 3

    # Next page
    assert session.next_page()
    assert session.page == 1

    assert session.next_page()
    assert session.page == 2

    # Clamped at last page
    assert not session.next_page()
    assert session.page == 2

    # Prev page
    assert session.prev_page()
    assert session.page == 1

    assert session.prev_page()
    assert session.page == 0

    # Clamped at first page
    assert not session.prev_page()
    assert session.page == 0

    session.close()
    session.cleanup()


def test_main_window_creation(qapp):
    from PySide6.QtCore import QSettings

    settings = QSettings("PGSL", "PDF Toolkit")
    settings.clear()

    session = Session()
    window = MainWindow(session=session)

    # Title & dimensions
    assert window.windowTitle() == APP_TITLE
    assert window.width() == 1280
    assert window.height() == 720
    assert window.minimumWidth() == 960
    assert window.minimumHeight() == 540

    # 3-Panel splitter
    assert window.splitter.count() == 3
    assert window.explorer_panel is not None
    assert window.preview_panel is not None
    assert window.toolkit_panel is not None
    assert window.toolkit_panel.number_start.value() == 1
    assert window.toolkit_panel.number_start_page.value() == 1
    assert window.status_bar_widget is not None

    # Actions
    assert window.act_save is not None
    assert window.act_save_as is not None
    assert window.act_undo is not None
    assert not window.act_undo.isEnabled()
    assert window.act_shortcuts is not None
    assert window.act_about is not None
    assert window.act_shortcuts.shortcut().toString() == "F1"

    # Title bar icon removed per design
    assert window.windowIcon().isNull()

    window.close()
    session.cleanup()


def test_main_window_document_lifecycle(qapp, tmp_path):
    # Create test PDF
    pdf_path = tmp_path / "sample.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(100, 100))
    pdf.save(pdf_path)

    session = Session()
    window = MainWindow(session=session)

    # Open document
    assert session.open(pdf_path)
    assert window.toolkit_panel.number_start_page.maximum() == 1
    assert pdf_path.name in window.windowTitle()
    assert window.act_save.isEnabled()
    assert window.act_save_as.isEnabled()
    assert window.act_close_doc.isEnabled()

    # Close document
    session.close()
    assert window.windowTitle() == APP_TITLE
    assert not window.act_save.isEnabled()

    window.close()
    session.cleanup()


def test_help_menu_dialogs(qapp, monkeypatch):
    session = Session()
    window = MainWindow(session=session)

    shortcuts_shown = []
    about_shown = []

    monkeypatch.setattr(
        "pdf_toolkit.gui.main_window.QMessageBox.information",
        lambda parent, title, text: shortcuts_shown.append((title, text)),
    )
    monkeypatch.setattr(
        "pdf_toolkit.gui.main_window.QMessageBox.about",
        lambda parent, title, text: about_shown.append((title, text)),
    )

    window.act_shortcuts.trigger()
    assert len(shortcuts_shown) == 1
    assert "Keyboard Shortcuts" in shortcuts_shown[0][0]
    assert "Ctrl + O" in shortcuts_shown[0][1]

    window.act_about.trigger()
    assert len(about_shown) == 1
    assert "About" in about_shown[0][0]
    assert "0.2.0" in about_shown[0][1]

    window.close()
    session.cleanup()


def test_ensure_application_fonts(qapp):
    from PySide6.QtGui import QFontDatabase

    from pdf_toolkit.gui.main_window import ensure_application_fonts

    ensure_application_fonts()
    families = QFontDatabase.families()
    assert any("Devanagari" in f for f in families)


def test_window_geometry_persistence(qapp):
    from PySide6.QtCore import QSettings

    settings = QSettings("PGSL", "PDF Toolkit")
    settings.clear()

    s1 = Session()
    w1 = MainWindow(session=s1)
    w1.show()
    w1.resize(1150, 680)
    w1.splitter.setSizes([240, 500, 350])
    expected_splitter = w1.splitter.sizes()
    w1.close()
    s1.cleanup()

    # Reopen to verify restore
    s2 = Session()
    w2 = MainWindow(session=s2)
    w2.show()
    assert w2.width() == 1150
    assert w2.height() == 680
    assert w2.splitter.sizes() == expected_splitter
    w2.close()
    s2.cleanup()

    settings.clear()


def test_dark_mode_toggle(qapp):
    from PySide6.QtCore import QSettings

    settings = QSettings("PGSL", "PDF Toolkit")
    settings.clear()

    session = Session()
    window = MainWindow(session=session)

    # Initial state should be light mode
    assert not window._dark_mode
    assert window.theme_btn.text() == "Dark Mode"
    assert not window.theme_btn.icon().isNull()
    assert window.act_toggle_theme is not None
    assert "Dark Mode" in window.act_toggle_theme.text()
    assert not window.act_save.icon().isNull()
    assert not window.act_shortcuts.icon().isNull()

    # Click theme switch button to switch to dark mode
    window.theme_btn.click()
    assert window._dark_mode
    assert window.theme_btn.text() == "Light Mode"
    assert not window.theme_btn.icon().isNull()
    assert "Light Mode" in window.act_toggle_theme.text()

    # Trigger action to switch back to light mode
    window.act_toggle_theme.trigger()
    assert not window._dark_mode
    assert window.theme_btn.text() == "Dark Mode"
    assert not window.theme_btn.icon().isNull()

    # Persist and reopen
    window.set_dark_mode(True)
    window._save_settings()
    window.close()
    session.cleanup()

    # Verify saved state is restored on next window instantiation
    session2 = Session()
    window2 = MainWindow(session=session2)
    assert window2._dark_mode
    assert "Light Mode" in window2.theme_btn.text()
    window2.close()
    session2.cleanup()

    settings.clear()


def test_ui_interaction_and_focus_revert(qapp):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QPushButton

    from pdf_toolkit.gui.preview import SmoothPageLabel

    session = Session()
    window = MainWindow(session=session)
    window.show()

    # 1. Window icon should be removed (empty)
    assert window.windowIcon().isNull()

    # 2. Clicking a button should NOT leave permanent focus
    window.theme_btn.click()
    assert not window.theme_btn.hasFocus()

    # 3. All buttons should have TabFocus policy (keyboard navigation works, mouse click doesn't stick)
    buttons = window.findChildren(QPushButton)
    assert len(buttons) >= 15
    for btn in buttons:
        assert btn.focusPolicy() == Qt.FocusPolicy.TabFocus

    # 4. Menubar actions exist and top menus are managed
    assert window.menuBar() is not None
    assert len(window.menuBar().actions()) >= 4
    assert hasattr(window, "_app_menus")
    assert len(window._app_menus) == 4
    for menu in window._app_menus:
        assert menu.parent() is window.menuBar()

    # 5. Opening one menu closes any previously open menu
    m0, m1 = window._app_menus[0], window._app_menus[1]
    m0.show()
    assert m0.isVisible()
    m1.aboutToShow.emit()
    assert not m0.isVisible()

    # 6. Clicking empty area in window reverts active UI state and closes open menus
    m1.show()
    assert m1.isVisible()
    press_ev = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(window.rect().center()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mousePressEvent(press_ev)
    assert not m1.isVisible()

    # 7. Smooth preview scaling label is active
    assert isinstance(window.preview_panel.page_label, SmoothPageLabel)

    window.close()
    session.cleanup()
