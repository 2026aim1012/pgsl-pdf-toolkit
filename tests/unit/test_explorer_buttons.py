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

def test_images_button_needs_an_image(qapp):
    session = Session()
    panel = ExplorerPanel(session)

    session.set_picked_files([Path("a.pdf")])
    assert not panel.img_pdf_btn.isEnabled()

    session.set_picked_files([Path("a.pdf"), Path("pic.png")])
    assert panel.img_pdf_btn.isEnabled()

    session.cleanup()

def test_refresh_clears_picked_files(qapp, tmp_path):
    session = Session()
    panel = ExplorerPanel(session)
    session.set_picked_files([Path("a.png"), Path("b.png")])
    assert panel.img_pdf_btn.isEnabled()

    session.set_folder(tmp_path)  # rebuilds the list
    assert session.picked_files == []
    assert not panel.img_pdf_btn.isEnabled()

    session.cleanup()