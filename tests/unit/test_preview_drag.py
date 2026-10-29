"""Tests for the drag-to-reorder logic in gui/preview.py.

Run with:  uv run pytest tests/unit/test_preview_drag.py -v

Only the plain-Python parts are tested here (no window is opened):
where a drop lands, and the page order it produces.
"""

import pytest

pytest.importorskip("PySide6")   # preview.py needs Qt installed to import

from pdf_toolkit.core.page_ops import move_pages_order  # noqa: E402
from pdf_toolkit.gui.preview import drop_index          # noqa: E402

# Centres (x, in pixels) of four thumbnails, 70 px apart
CENTERS = [40, 110, 180, 250]


@pytest.mark.parametrize("x, expected", [
    (0, 0),      # far left: before page 1
    (39, 0),     # just left of page 1's centre
    (41, 1),     # just right of page 1's centre: between pages 1 and 2
    (175, 2),    # left half of page 3
    (300, 4),    # past the last page: at the end
])
def test_drop_index(x, expected):
    assert drop_index(CENTERS, x) == expected


def test_drop_index_on_an_empty_strip():
    assert drop_index([], 50) == 0


@pytest.mark.parametrize("pages, x, expected_order", [
    ([3], 0, [3, 0, 1, 2]),        # drag page 4 to the far left
    ([0], 300, [1, 2, 3, 0]),      # drag page 1 past the last page
    ([0, 1], 200, [2, 0, 1, 3]),   # drag pages 1-2 between pages 3 and 4
])
def test_a_drop_gives_the_expected_page_order(pages, x, expected_order):
    position = drop_index(CENTERS, x)
    assert move_pages_order(len(CENTERS), pages, position) == expected_order