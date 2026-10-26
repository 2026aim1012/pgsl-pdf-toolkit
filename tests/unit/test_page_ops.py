"""Tests for core/page_ops.py (FR-02: reorder and insert pages).

Run with:  uv run pytest tests/unit/test_page_ops.py -v

Each test PDF is built on the fly: page i is (100 + i) points wide, so a
page's width tells us which original page it is.
"""

from pathlib import Path

import pikepdf
import pytest

from pdf_toolkit.core.page_ops import insert_pages, move_pages_order, reorder_pages

# ---------- helpers ----------

def make_pdf(path: Path, count: int, first_width: int = 100) -> Path:
    """A PDF whose page i is (first_width + i) points wide."""
    pdf = pikepdf.new()
    for i in range(count):
        pdf.add_blank_page(page_size=(first_width + i, 200))
    pdf.save(path)
    return path


def widths(path: Path) -> list[int]:
    """Page widths, in page order."""
    with pikepdf.open(path) as pdf:
        return [int(page.mediabox[2]) for page in pdf.pages]


class Recorder:
    """A fake reporter that remembers every (done, total) it was given."""

    def __init__(self):
        self.calls = []

    def __call__(self, done, total, msg=""):
        self.calls.append((done, total))


# ---------- reorder_pages ----------

def test_reorder_puts_pages_in_the_new_order(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", 4)
    out = tmp_path / "out.pdf"

    reorder_pages(src, out, None, order=[3, 0, 1, 2])

    assert widths(out) == [103, 100, 101, 102]


def test_reorder_leaves_the_source_untouched(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", 3)

    reorder_pages(src, tmp_path / "out.pdf", None, order=[2, 1, 0])

    assert widths(src) == [100, 101, 102]


def test_reorder_reports_progress_for_every_page(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", 3)
    rec = Recorder()

    reorder_pages(src, tmp_path / "out.pdf", rec, order=[2, 1, 0])

    assert rec.calls == [(1, 3), (2, 3), (3, 3)]


@pytest.mark.parametrize("bad_order", [
    [0, 1],          # a page missing
    [0, 1, 1],       # a page twice
    [0, 1, 3],       # a page that does not exist
])
def test_reorder_rejects_an_order_that_is_not_every_page_once(tmp_path, bad_order):
    src = make_pdf(tmp_path / "in.pdf", 3)

    with pytest.raises(ValueError):
        reorder_pages(src, tmp_path / "out.pdf", None, order=bad_order)


def test_reorder_keeps_bookmarks_on_the_right_page(tmp_path):
    src = tmp_path / "in.pdf"
    pdf = pikepdf.new()
    for i in range(3):
        pdf.add_blank_page(page_size=(100 + i, 200))
    with pdf.open_outline() as outline:
        outline.root.append(pikepdf.OutlineItem("Chapter", 2))   # -> 3rd page
    pdf.save(src)
    out = tmp_path / "out.pdf"

    reorder_pages(src, out, None, order=[2, 0, 1])

    with pikepdf.open(out) as result, result.open_outline() as outline:
        target = outline.root[0].destination[0]
        moved_to = [i for i, page in enumerate(result.pages)
                    if page.obj.objgen == target.objgen]
    assert moved_to == [0]          # the old 3rd page is now first


def test_reorder_writes_nothing_when_cancelled(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", 3)
    out = tmp_path / "out.pdf"

    def cancel_at_once(done, total, msg=""):
        raise RuntimeError("Cancelled")

    with pytest.raises(RuntimeError):
        reorder_pages(src, out, cancel_at_once, order=[2, 1, 0])
    assert not out.exists()


# ---------- move_pages_order ----------

@pytest.mark.parametrize("count, moving, to, expected", [
    (5, [3], 0, [3, 0, 1, 2, 4]),        # drag page 4 to the front
    (5, [0], 5, [1, 2, 3, 4, 0]),        # drag page 1 to the end
    (5, [0, 1], 5, [2, 3, 4, 0, 1]),     # drag two pages to the end
    (5, [4, 1], 3, [0, 2, 1, 4, 3]),     # selection order does not matter
    (3, [1], 1, [0, 1, 2]),              # dropped where it already is
])
def test_move_pages_order(count, moving, to, expected):
    assert move_pages_order(count, moving, to) == expected


@pytest.mark.parametrize("moving, to", [([], 0), ([5], 0), ([0], 6), ([0], -1)])
def test_move_pages_order_rejects_bad_input(moving, to):
    with pytest.raises(ValueError):
        move_pages_order(5, moving, to)


# ---------- insert_pages ----------

@pytest.mark.parametrize("at, expected", [
    (0, [500, 501, 100, 101, 102]),      # before the first page
    (1, [100, 500, 501, 101, 102]),      # in the middle
    (3, [100, 101, 102, 500, 501]),      # after the last page
])
def test_insert_all_pages_at_a_position(tmp_path, at, expected):
    src = make_pdf(tmp_path / "in.pdf", 3)
    other = make_pdf(tmp_path / "other.pdf", 2, first_width=500)
    out = tmp_path / "out.pdf"

    insert_pages(src, out, None, insert_path=other, at=at)

    assert widths(out) == expected


def test_insert_only_chosen_pages_in_the_given_order(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", 2)
    other = make_pdf(tmp_path / "other.pdf", 4, first_width=500)
    out = tmp_path / "out.pdf"

    insert_pages(src, out, None, insert_path=other, at=1, pages=[3, 0])

    assert widths(out) == [100, 503, 500, 101]


def test_insert_from_the_same_file(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", 2)
    out = tmp_path / "out.pdf"

    insert_pages(src, out, None, insert_path=src, at=2)

    assert widths(out) == [100, 101, 100, 101]


def test_insert_reports_progress_and_leaves_inputs_untouched(tmp_path):
    src = make_pdf(tmp_path / "in.pdf", 2)
    other = make_pdf(tmp_path / "other.pdf", 3, first_width=500)
    rec = Recorder()

    insert_pages(src, tmp_path / "out.pdf", rec, insert_path=other, at=0)

    assert rec.calls == [(1, 3), (2, 3), (3, 3)]
    assert widths(src) == [100, 101]
    assert widths(other) == [500, 501, 502]


@pytest.mark.parametrize("at, pages", [
    (-1, None),      # position before the start
    (3, None),       # position past the end (2-page file)
    (0, [5]),        # a page the other file does not have
    (0, []),         # nothing chosen
])
def test_insert_rejects_bad_input(tmp_path, at, pages):
    src = make_pdf(tmp_path / "in.pdf", 2)
    other = make_pdf(tmp_path / "other.pdf", 2, first_width=500)

    with pytest.raises(ValueError):
        insert_pages(src, tmp_path / "out.pdf", None,
                     insert_path=other, at=at, pages=pages)