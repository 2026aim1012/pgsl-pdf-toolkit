"""The Toolkit's layout: big category buttons, nothing hidden or cut off.

Run with:  uv run pytest tests/unit/test_toolkit_layout.py -v
"""

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QScrollArea

from pdf_toolkit.gui.main_window import MainWindow
from pdf_toolkit.gui.preview import PreviewPanel
from pdf_toolkit.gui.session import Session
from pdf_toolkit.gui.toolkit import CATEGORIES, Toolkit

SETTINGS_KEY = "toolkit_category"


def make_toolkit():
    session = Session()
    return session, Toolkit(session, operations={})


def test_five_category_buttons_with_names(qapp):
    session, toolkit = make_toolkit()

    buttons = toolkit.category_group.buttons()
    assert [b.text() for b in buttons] == [name for name, _ in CATEGORIES]
    assert sum(b.isChecked() for b in buttons) == 1  # exactly one chosen
    for button in buttons:
        assert button.accessibleName().endswith("tools")
        assert button.toolTip()  # says what the group is for

    session.cleanup()


def test_choosing_a_category_shows_only_its_tools(qapp):
    settings = QSettings("PGSL", "PDF Toolkit")
    saved = settings.value(SETTINGS_KEY)
    session, toolkit = make_toolkit()

    toolkit.category_group.button(3).click()  # Stamp

    shown = [not section.isHidden() for section in toolkit.sections]
    assert shown == [False, False, False, True, False]
    # Page numbers and watermark both live under Stamp
    assert toolkit.sections[3].isAncestorOf(toolkit.number_button)
    assert toolkit.sections[3].isAncestorOf(toolkit.watermark_button)
    assert "page numbers" in toolkit.category_hint.text().lower()

    session.cleanup()
    if saved is None:
        settings.remove(SETTINGS_KEY)
    else:
        settings.setValue(SETTINGS_KEY, saved)


def test_tools_scroll_instead_of_being_cut_off(qapp):
    session, toolkit = make_toolkit()

    scroll_areas = toolkit.findChildren(QScrollArea)
    assert scroll_areas
    assert scroll_areas[0].widget().isAncestorOf(toolkit.merge_button)

    session.cleanup()


def test_undo_is_always_visible(qapp):
    session, toolkit = make_toolkit()

    for section in toolkit.sections:
        assert not section.isAncestorOf(toolkit.undo_button)

    session.cleanup()


def test_start_hint_shows_until_a_pdf_is_open(qapp):
    session, toolkit = make_toolkit()

    assert not toolkit.start_hint.isHidden()
    assert "Open a PDF" in toolkit.start_hint.text()

    session.cleanup()


def test_toolkit_messages_reach_the_status_bar(qapp):
    session = Session()
    window = MainWindow(session=session)

    window.toolkit_panel.requestStatus.emit("Compression saved 1.0 MB (40.0%).")

    label = window.status_bar_widget.status_message_label
    assert "Compression saved" in label.text()

    window.close()
    session.cleanup()


def test_empty_preview_shows_a_dash_not_page_zero(qapp):
    session = Session()
    panel = PreviewPanel(session)

    assert panel.page_box.specialValueText() == "–"
    assert panel.page_box.value() == panel.page_box.minimum()
    assert panel.total_label.text() == "/ –"

    session.cleanup()
