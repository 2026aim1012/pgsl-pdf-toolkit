"""
page_ops.py: page-level operations for FR-02 (reorder and insert pages).

Every operation follows the team's engine contract, so the Toolkit can run it
through ``session.apply(...)``:

    op(src, out, reporter, **options) -> None

    src       Path of the current working PDF (never modified)
    out       Path where the result must be written
    reporter  called as reporter(done, total) to move the progress bar;
              it raises Cancelled when the user presses Cancel.
              May be None (handy in tests).

Register them in the operations registry as:

    "reorder": reorder_pages,
    "insert":  insert_pages,
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pikepdf

Reporter = Callable[..., None]


def _report(reporter: Reporter | None, done: int, total: int) -> None:
    """Move the progress bar (and let Cancel stop us) if there is a reporter."""
    if reporter is not None:
        reporter(done, total)


# ----------------------------------------------------------------------
#  Reorder
# ----------------------------------------------------------------------

def reorder_pages(src: Path, out: Path, reporter: Reporter | None = None, *,
                  order: Sequence[int]) -> None:
    """Write `src` to `out` with its pages in a new order.

    `order` lists the old page numbers (0-based) in their new order, and must
    use every page exactly once. Example for a 4-page PDF:

        order = [3, 0, 1, 2]   ->  old page 4 becomes the first page
    """
    order = list(order)

    with pikepdf.open(src) as pdf:
        count = len(pdf.pages)
        if sorted(order) != list(range(count)):
            raise ValueError(
                f"order must list every page from 0 to {count - 1} exactly once, "
                f"got {order}"
            )

        # Keep a handle on every page, take them all out, then put them back
        # in the new order. Moving the pages themselves (instead of copying
        # them) keeps bookmarks and links pointing at the right page.
        pages = list(pdf.pages)
        while len(pdf.pages) > 0:
            del pdf.pages[0]

        for done, old_index in enumerate(order, start=1):
            pdf.pages.append(pages[old_index])
            _report(reporter, done, count)

        pdf.save(out)


def move_pages_order(page_count: int, moving: Sequence[int], to: int) -> list[int]:
    """Build the `order` for reorder_pages when pages are dragged somewhere.

    `moving` = the pages being dragged (0-based, any order), `to` = the
    position in the ORIGINAL document they are dropped in front of
    (0 = before the first page, page_count = after the last page).
    The moved pages keep their relative order.

        move_pages_order(5, [3], 0)     -> [3, 0, 1, 2, 4]
        move_pages_order(5, [0, 1], 5)  -> [2, 3, 4, 0, 1]
    """
    if not 0 <= to <= page_count:
        raise ValueError(f"to must be between 0 and {page_count}, got {to}")
    moving_set = set(moving)
    if not moving_set or not all(0 <= p < page_count for p in moving_set):
        raise ValueError(f"moving must hold page numbers from 0 to {page_count - 1}")

    moved = sorted(moving_set)
    before = [p for p in range(to) if p not in moving_set]
    after = [p for p in range(to, page_count) if p not in moving_set]
    return before + moved + after


# ----------------------------------------------------------------------
#  Insert
# ----------------------------------------------------------------------

def insert_pages(src: Path, out: Path, reporter: Reporter | None = None, *,
                 insert_path: Path, at: int,
                 pages: Sequence[int] | None = None) -> None:
    """Write `src` to `out` with pages from another PDF inserted.

    insert_path  the PDF to take pages from (may be the same file as src)
    at           position for the first inserted page, 0-based:
                 0 = before page 1, len(src) = after the last page
    pages        which pages of insert_path to insert (0-based);
                 None = all of them, in order
    """
    with pikepdf.open(src) as pdf, pikepdf.open(insert_path) as other:
        count = len(pdf.pages)
        if not 0 <= at <= count:
            raise ValueError(f"at must be between 0 and {count}, got {at}")

        other_count = len(other.pages)
        chosen = list(range(other_count)) if pages is None else list(pages)
        if not chosen:
            raise ValueError("no pages chosen to insert")
        bad = [p for p in chosen if not 0 <= p < other_count]
        if bad:
            raise ValueError(
                f"{Path(insert_path).name} has {other_count} pages; "
                f"cannot insert page(s) {bad}"
            )

        # pikepdf copies each page (and what it uses: fonts, images) over
        # from the other file when it is inserted.
        for done, page_index in enumerate(chosen, start=1):
            pdf.pages.insert(at + done - 1, other.pages[page_index])
            _report(reporter, done, len(chosen))

        pdf.save(out)