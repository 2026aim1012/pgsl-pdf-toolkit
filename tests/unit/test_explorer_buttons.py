from pathlib import Path

from pdf_toolkit.gui.explorer import ExplorerPanel
from pdf_toolkit.gui.session import Session


def test_order_button_needs_two_files(qapp):
    session = Session()
    panel = ExplorerPanel(session)
    assert not panel.order_btn.isEnabled()

    session.set_picked_files([Path("a.pdf"), Path("b.pdf")])
    assert panel.order_btn.isEnabled()

    session.cleanup()