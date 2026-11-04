"""Opening a file must never silently throw away unsaved changes.

Bug seen in testing: pages were inserted, then the same PDF was
double-clicked in the Explorer. It was re-read from disk, so the inserted
pages and the Undo history disappeared without any warning.

Run with:  uv run pytest tests/unit/test_session_open.py -v
"""

from pathlib import Path

import pikepdf

from pdf_toolkit.core.page_ops import insert_pages
from pdf_toolkit.gui.session import Session
from pdf_toolkit.gui.toolkit import Toolkit


def make_pdf(path: Path, pages: int) -> Path:
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(200, 300))
    pdf.save(path)
    return path


def open_and_change(session: Session, tmp_path: Path) -> Path:
    """Open an 8-page PDF and insert 3 pages, as the Toolkit would."""
    doc = make_pdf(tmp_path / "doc.pdf", 8)
    extra = make_pdf(tmp_path / "extra.pdf", 3)
    assert session.open(doc)
    out = session._new_temp(".pdf")
    insert_pages(session.current, out, None, insert_path=extra, at=2)
    session._applied(out, keep_page=True)  # what Session.apply does when done
    assert session.page_count == 11 and session.modified
    return doc


def test_opening_the_same_file_keeps_the_changes(qapp, tmp_path):
    session = Session()
    doc = open_and_change(session, tmp_path)

    assert session.open(doc)  # e.g. double-clicked in the Explorer

    assert session.page_count == 11  # inserted pages still there
    assert session.modified
    assert session.can_undo  # Undo history kept
    session.cleanup()


def test_cancel_keeps_the_changed_document(qapp, tmp_path):
    session = Session()
    open_and_change(session, tmp_path)
    other = make_pdf(tmp_path / "other.pdf", 2)
    session.confirm_discard = lambda: False  # user pressed Cancel

    assert not session.open(other)

    assert session.page_count == 11
    assert session.source.name == "doc.pdf"
    session.cleanup()


def test_discard_opens_the_other_file(qapp, tmp_path):
    session = Session()
    open_and_change(session, tmp_path)
    other = make_pdf(tmp_path / "other.pdf", 2)
    asked = []
    session.confirm_discard = lambda: asked.append(True) or True  # Discard

    assert session.open(other)

    assert asked == [True]
    assert session.page_count == 2
    assert session.source.name == "other.pdf"
    session.cleanup()


def test_no_question_when_nothing_changed(qapp, tmp_path):
    session = Session()
    assert session.open(make_pdf(tmp_path / "a.pdf", 1))
    session.confirm_discard = lambda: (_ for _ in ()).throw(AssertionError("asked"))

    assert session.open(make_pdf(tmp_path / "b.pdf", 2))
    session.cleanup()


def test_insert_reports_what_it_did(qapp, tmp_path):
    session = Session()
    toolkit = Toolkit(session, operations={})
    messages = []
    toolkit.requestStatus.connect(messages.append)
    doc = make_pdf(tmp_path / "doc.pdf", 8)
    extra = make_pdf(tmp_path / "ABC.pdf", 3)
    assert session.open(doc)

    toolkit._insert_pending = (session.current, 8, 2, "ABC.pdf", "before page 3")
    out = session._new_temp(".pdf")
    insert_pages(session.current, out, None, insert_path=extra, at=2)
    session._applied(out, keep_page=True)  # the Toolkit hears documentChanged

    assert messages == ["Inserted 3 pages from ABC.pdf before page 3 (now 11 pages)."]
    session.cleanup()
