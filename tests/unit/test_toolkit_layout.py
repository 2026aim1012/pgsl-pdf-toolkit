"""The Toolkit's layout: big category buttons, nothing hidden or cut off.

Run with:  uv run pytest tests/unit/test_toolkit_layout.py -v
"""

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
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


def test_scroll_stays_put_when_a_job_starts(qapp, monkeypatch):
    """Bug seen in testing: clicking Rotate made the Toolkit jump to the
    bottom, because the focused button was greyed out during the job and
    focus (and the scroll area with it) moved on to another control."""
    session, toolkit = make_toolkit()
    toolkit.resize(360, 320)  # small, so the tools need scrolling
    toolkit.show()
    QTest.qWaitForWindowExposed(toolkit)
    toolkit.activateWindow()

    toolkit.rotate_button.setEnabled(True)
    toolkit.rotate_button.setFocus()
    if not toolkit.rotate_button.hasFocus():
        pytest.skip("no keyboard focus available on this test platform")
    bar = toolkit.findChildren(QScrollArea)[0].verticalScrollBar()
    bar.setValue(0)

    monkeypatch.setattr(type(session), "busy", property(lambda self: True))
    toolkit._on_busy_changed(True)  # a job starts: buttons grey out

    assert not toolkit.rotate_button.isEnabled()
    assert bar.value() == 0  # did not jump
    assert toolkit.category_group.checkedButton().hasFocus()  # focus parked

    toolkit.close()
    session.cleanup()


def test_insert_position_before_or_after(qapp, tmp_path, monkeypatch):
    """Position = a Before/After choice plus a separate page-number box."""
    import pikepdf

    session, toolkit = make_toolkit()
    extra = tmp_path / "extra.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page()
    pdf.save(extra)

    calls = []
    monkeypatch.setattr(session, "apply", lambda op, **kw: calls.append(kw) or True)
    toolkit.operations = {"insert": lambda *a, **k: None}
    toolkit.insert_path_label.setProperty("insert_path", str(extra))
    toolkit.insert_at.setMaximum(8)
    toolkit.insert_at.setValue(5)

    assert toolkit.insert_where is not toolkit.insert_at  # two fields
    assert toolkit.insert_at.prefix() == ""  # just the number

    toolkit.insert_where.setCurrentIndex(toolkit.insert_where.findData("after"))
    toolkit._insert_pages()
    assert calls[-1]["at"] == 5  # new pages start right after page 5
    assert "after page 5" in calls[-1]["description"]

    toolkit.insert_where.setCurrentIndex(toolkit.insert_where.findData("before"))
    toolkit._insert_pages()
    assert calls[-1]["at"] == 4  # new pages start where page 5 was
    assert "before page 5" in calls[-1]["description"]

    session.cleanup()


def test_new_pdf_defaults_to_after_the_last_page(qapp):
    session, toolkit = make_toolkit()

    toolkit._on_page_count_changed(8)  # a PDF with 8 pages was opened

    assert toolkit.insert_where.currentData() == "after"
    assert toolkit.insert_at.value() == 8
    assert toolkit.insert_at.maximum() == 8
    session.cleanup()
