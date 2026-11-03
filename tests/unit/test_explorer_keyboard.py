from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from pdf_toolkit.gui.explorer import ExplorerPanel
from pdf_toolkit.gui.session import Session


def _panel(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"")
    session = Session()
    panel = ExplorerPanel(session)
    session.set_folder(tmp_path)
    return session, panel


def test_enter_emits_current_item(qapp, tmp_path):
    session, panel = _panel(tmp_path)
    got = []
    panel.list.enterPressed.connect(got.append)
    panel.list.setCurrentRow(1)  # row 0 is "../"
    QTest.keyClick(panel.list, Qt.Key.Key_Return)
    assert len(got) == 1
    session.cleanup()


def test_space_ticks_current_file(qapp, tmp_path):
    session, panel = _panel(tmp_path)
    panel.list.setCurrentRow(1)
    QTest.keyClick(panel.list, Qt.Key.Key_Space)
    assert session.picked_files == [tmp_path / "a.pdf"]
    session.cleanup()


def test_controls_have_accessible_names(qapp):
    session = Session()
    panel = ExplorerPanel(session)
    for widget in (panel.open_btn, panel.list, panel.order_btn, panel.img_pdf_btn):
        assert widget.accessibleName()
    session.cleanup()


def test_disabled_button_explains_itself(qapp):
    session = Session()
    panel = ExplorerPanel(session)
    assert not panel.order_btn.isEnabled()
    assert "two files" in panel.order_btn.toolTip()
    session.cleanup()
