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
