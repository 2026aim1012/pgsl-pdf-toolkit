"""Keyboard and screen-reader support in gui/preview.py.

Run with:  uv run pytest tests/unit/test_preview_keyboard.py -v
"""

import pytest

pytest.importorskip("PySide6")  # preview.py needs Qt installed to import

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from pdf_toolkit.core.page_ops import move_pages_order
from pdf_toolkit.gui.preview import PreviewPanel, ThumbStrip, keyboard_move_target
from pdf_toolkit.gui.session import Session

CTRL_SHIFT = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier


# ----- where Ctrl+Shift+arrow moves pages (plain Python) -----


@pytest.mark.parametrize(
    ("pages", "step", "new_order"),
    [
        ([2], -1, [0, 2, 1, 3, 4]),  # page 3 one place left
        ([2], +1, [0, 1, 3, 2, 4]),  # page 3 one place right
        ([3], +1, [0, 1, 2, 4, 3]),  # next to last -> last
        ([1, 2], +1, [0, 3, 1, 2, 4]),  # a block moves together
        ([1, 2], -1, [1, 2, 0, 3, 4]),
    ],
)
def test_keyboard_move_gives_expected_order(pages, step, new_order):
    target = keyboard_move_target(5, pages, step)
    assert move_pages_order(5, pages, target) == new_order


@pytest.mark.parametrize(
    ("pages", "step"),
    [([0], -1), ([4], +1), ([0, 1], -1), ([], +1)],
)
def test_keyboard_move_stops_at_the_ends(pages, step):
    assert keyboard_move_target(5, pages, step) is None


# ----- the shortcut itself -----


def make_strip(count=4):
    strip = ThumbStrip()
    for i in range(count):
        strip.addItem(str(i + 1))
    moves = []
    strip.pagesDropped.connect(lambda pages, pos: moves.append((list(pages), pos)))
    return strip, moves


def test_ctrl_shift_right_moves_selected_page(qapp):
    strip, moves = make_strip()
    strip.item(1).setSelected(True)  # page 2

    QTest.keyClick(strip, Qt.Key.Key_Right, CTRL_SHIFT)

    assert moves == [([1], 3)]  # page 2 goes in front of page 4


def test_ctrl_shift_left_moves_selected_page(qapp):
    strip, moves = make_strip()
    strip.item(2).setSelected(True)  # page 3

    QTest.keyClick(strip, Qt.Key.Key_Left, CTRL_SHIFT)

    assert moves == [([2], 1)]


def test_plain_arrow_does_not_move_pages(qapp):
    strip, moves = make_strip()
    strip.item(1).setSelected(True)

    QTest.keyClick(strip, Qt.Key.Key_Right)

    assert moves == []


def test_no_keyboard_move_while_busy(qapp):
    strip, moves = make_strip()
    strip.item(1).setSelected(True)
    strip.setDragEnabled(False)  # what the panel does while a job runs

    QTest.keyClick(strip, Qt.Key.Key_Right, CTRL_SHIFT)

    assert moves == []


# ----- names for screen readers -----


def test_controls_have_screen_reader_names(qapp):
    session = Session()
    panel = PreviewPanel(session)

    assert panel.prev_btn.accessibleName() == "Previous page"
    assert panel.next_btn.accessibleName() == "Next page"
    assert panel.page_box.accessibleName() == "Page number"
    assert panel.thumbs.accessibleName() == "Page thumbnails"
    assert panel.prev_btn.toolTip()  # every button explains itself

    session.cleanup()


def test_thumbnails_are_read_as_page_numbers(qapp):
    session = Session()
    panel = PreviewPanel(session)

    panel._fill_thumbs(3)

    item = panel.thumbs.item(2)
    assert item.data(Qt.ItemDataRole.AccessibleTextRole) == "Page 3"
    assert item.toolTip() == "Page 3"

    session.cleanup()
