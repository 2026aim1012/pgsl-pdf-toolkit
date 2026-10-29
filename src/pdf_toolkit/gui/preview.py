from bisect import bisect_left
from pathlib import Path

import pypdfium2 as pdfium
from PySide6.QtCore import QMimeData, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pdf_toolkit.core.page_ops import move_pages_order, reorder_pages

THUMB_SIZE = QSize(60, 80)  # box each thumbnail picture fits into
DRAWN = Qt.ItemDataRole.UserRole  # marks thumbnails already rendered
PAGES_MIME = "application/x-pgsl-pages"  # tags our own thumbnail drags


def render_page(pdf, index: int, box_w: int, box_h: int, dpr: float = 1.0) -> QPixmap:
    """Render page `index` of `pdf` so it fits inside box_w x box_h pixels."""
    page = pdf[index]
    try:
        width_pt, height_pt = page.get_size()  # PDF units (1/72 inch)
        scale = min(box_w / width_pt, box_h / height_pt)
        # dpr is 2 on high-DPI screens: draw extra pixels so the page stays sharp
        image = page.render(scale=scale * dpr).to_pil().convert("RGB")
    finally:
        page.close()

    # Pillow image -> Qt image -> Qt pixmap (what a QLabel can display)
    qimage = QImage(
        image.tobytes(),
        image.width,
        image.height,
        image.width * 3,
        QImage.Format.Format_RGB888,
    ).copy()
    pixmap = QPixmap.fromImage(qimage)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def drop_index(centers: list[float], x: float) -> int:
    """Where a drop lands in the strip: the number of thumbnails whose
    centre is left of the mouse. 0 = before the first page,
    len(centers) = after the last page.

        drop_index([10, 30, 50], 5)   -> 0
        drop_index([10, 30, 50], 35)  -> 2
        drop_index([10, 30, 50], 99)  -> 3
    """
    return bisect_left(centers, x)


# ----------------------------------------------------------------------
#  Thumbnail strip with drag-to-reorder
# ----------------------------------------------------------------------


class ThumbStrip(QListWidget):
    """A one-row list of page thumbnails. Dragging thumbnails to a new place
    does NOT move them itself: it emits `pagesDropped(pages, position)` and
    the panel asks the Session to really reorder the PDF (so Undo works).
    After that the strip is simply rebuilt from the new file."""

    pagesDropped = Signal(list, int)  # pages dragged (0-based), drop position

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("thumbs")
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)  # a single row
        self.setMovement(QListWidget.Movement.Static)  # Qt must not move items
        self.setIconSize(THUMB_SIZE)
        self.setSpacing(6)
        self.setUniformItemSizes(True)
        self.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )  # Ctrl / Shift
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(THUMB_SIZE.height() + 50)

        # Turn dragging on AFTER setMovement(Static): setMovement switches
        # drag and drop off again.
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(False)  # we draw our own line instead

        self._drop_at = None  # where the blue line is drawn while dragging

    # ----- starting a drag -----

    def startDrag(self, supported_actions):
        """Called by Qt when the mouse moves with a thumbnail held down."""
        items = self.selectedItems()
        if not items:
            return
        mime = QMimeData()
        mime.setData(PAGES_MIME, b"pages")  # only the content type matters
        drag = QDrag(self)
        drag.setMimeData(mime)
        icon = self.currentItem().icon() if self.currentItem() else items[0].icon()
        drag.setPixmap(icon.pixmap(THUMB_SIZE))
        drag.setHotSpot(drag.pixmap().rect().center())
        # We started the drag ourselves, so Qt never deletes items when it
        # ends, whatever the drop does.
        drag.exec(Qt.DropAction.MoveAction)
        self._set_drop_at(None)

    # ----- while dragging over the strip -----

    def _is_our_drag(self, event) -> bool:
        return event.source() is self and event.mimeData().hasFormat(PAGES_MIME)

    def _position_for(self, x: int) -> int:
        centers = [
            self.visualItemRect(self.item(row)).center().x()
            for row in range(self.count())
        ]
        return drop_index(centers, x)

    def _set_drop_at(self, position):
        if position != self._drop_at:
            self._drop_at = position
            self.viewport().update()  # redraw the blue line

    def dragEnterEvent(self, event):
        if self._is_our_drag(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self._is_our_drag(event):
            event.ignore()
            return
        x = event.position().toPoint().x()
        # Scroll the strip when the mouse is near its left or right edge
        bar = self.horizontalScrollBar()
        if x < 40:
            bar.setValue(bar.value() - 20)
        elif x > self.viewport().width() - 40:
            bar.setValue(bar.value() + 20)
        self._set_drop_at(self._position_for(x))
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_drop_at(None)
        event.accept()

    def dropEvent(self, event):
        if not self._is_our_drag(event):
            event.ignore()
            return
        position = self._position_for(event.position().toPoint().x())
        pages = sorted(self.row(item) for item in self.selectedItems())
        self._set_drop_at(None)
        event.acceptProposedAction()
        if pages:
            self.pagesDropped.emit(pages, position)

    # ----- the blue "drop here" line -----

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drop_at is None or self.count() == 0:
            return
        if self._drop_at < self.count():
            rect = self.visualItemRect(self.item(self._drop_at))
            x = rect.left() - 4  # just left of that thumbnail
        else:
            rect = self.visualItemRect(self.item(self.count() - 1))
            x = rect.right() + 4  # just right of the last one
        painter = QPainter(self.viewport())
        painter.setPen(QPen(QColor("#2f6fdc"), 3))
        painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.end()


class PreviewPanel(QWidget):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.pdf = None  # the open pdfium.PdfDocument (None = nothing open)
        self.index = 0  # page currently shown (0-based)
        # After a drag-reorder: (page count, page to show, pages to select)
        # once the reordered file arrives. None = nothing waiting.
        self._after_move = None

        self._build_ui()
        self._connect_signals()
        self._show_empty()

    # ------------------------------------------------------------------
    #  Building the widgets
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        title = QLabel("PREVIEW")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 1) The big page
        self.page_label = QLabel()
        self.page_label.setObjectName("pageView")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # "Ignored" = the layout decides the size. Without it, a big page
        # picture would stop the window from being made smaller.
        self.page_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        layout.addWidget(self.page_label, stretch=1)

        # 2) Navigation row:  ‹  [ 1 ]  / 391  ›
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        for button in (self.prev_btn, self.next_btn):
            button.setObjectName("navButton")
            button.setFixedWidth(36)

        self.page_box = QSpinBox()
        self.page_box.setFixedWidth(60)
        self.page_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.page_box.setKeyboardTracking(False)  # jump on Enter, not every key

        self.total_label = QLabel("/ 0")

        nav = QHBoxLayout()
        nav.addStretch(1)  # stretches on both sides
        nav.addWidget(self.prev_btn)  # keep the row centred
        nav.addWidget(self.page_box)
        nav.addWidget(self.total_label)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        layout.addLayout(nav)

        # 3) Thumbnail strip: one row of page pictures; drag them to reorder
        self.thumbs = ThumbStrip()

        strip = QFrame()  # dashed box around the strip (style.qss)
        strip.setObjectName("thumbStrip")
        strip_layout = QVBoxLayout(strip)
        strip_layout.setContentsMargins(6, 4, 6, 2)
        strip_layout.addWidget(self.thumbs)
        layout.addWidget(strip)

        hint = QLabel(
            "Click a thumbnail to jump · Ctrl + click to select "
            "several · Drag to move pages"
        )
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Timers that wait a moment before redrawing, so resizing or scrolling
        # quickly doesn't redraw 100 times a second.
        self._page_timer = QTimer(self)
        self._page_timer.setSingleShot(True)
        self._page_timer.setInterval(50)
        self._page_timer.timeout.connect(self._draw_page)

        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.setInterval(50)
        self._thumb_timer.timeout.connect(self._draw_visible_thumbs)

    def _connect_signals(self):
        s = self.session

        # Session -> this panel
        s.documentChanged.connect(self.load_document)
        s.pageChanged.connect(self.show_page)
        s.pageSelectionChanged.connect(self._select_thumbs)
        # Optional signals: only connected if your session.py has them
        if hasattr(s, "documentClosed"):
            s.documentClosed.connect(lambda: self.load_document(None))
        if hasattr(s, "pageCountChanged"):
            s.pageCountChanged.connect(self._set_page_count)

        # This panel -> Session
        self.prev_btn.clicked.connect(s.prev_page)
        self.next_btn.clicked.connect(s.next_page)
        self.page_box.valueChanged.connect(lambda number: s.set_page(number - 1))
        self.thumbs.currentRowChanged.connect(self._on_thumb_clicked)
        self.thumbs.itemSelectionChanged.connect(self._on_thumb_selection)
        self.thumbs.pagesDropped.connect(self._on_pages_dropped)

        # No dragging while another job runs (the Session refuses it anyway)
        if hasattr(s, "busyChanged"):
            s.busyChanged.connect(self._on_busy_changed)

        # Thumbnails are only drawn when visible, so check again after scrolling.
        # (lambda *_ throws away the scroll value: timer.start(value) would
        #  wrongly use it as the delay in milliseconds)
        bar = self.thumbs.horizontalScrollBar()
        bar.valueChanged.connect(lambda *_: self._thumb_timer.start())
        bar.rangeChanged.connect(lambda *_: self._thumb_timer.start())

    # ------------------------------------------------------------------
    #  Session -> panel
    # ------------------------------------------------------------------

    def load_document(self, path):
        """A new working file (or None). Happens after open, every edit and undo."""
        if self.pdf is not None:
            self.pdf.close()
            self.pdf = None

        if path is not None:
            try:
                # Read the file into memory, so the file on disk isn't kept open.
                # The Session deletes old temp files, and Windows can't delete
                # a file that is still open.
                self.pdf = pdfium.PdfDocument(Path(path).read_bytes())
            except Exception as e:  # noqa: BLE001 - any unreadable file shows a message
                self._show_empty(f"Could not display this file:\n{e}")
                return

        count = len(self.pdf) if self.pdf else 0
        self._set_page_count(count)
        self._fill_thumbs(count)

        if count == 0:
            self._show_empty()
        else:
            self.page_box.setEnabled(True)
            self.show_page(self.session.page)

        # Just reordered by a drag? Then follow the moved pages. Done a moment
        # later (singleShot 0), after the Session has finished announcing the
        # new file, so its own "page / selection reset" doesn't undo this.
        waiting, self._after_move = self._after_move, None
        if waiting is not None and waiting[0] == count:
            QTimer.singleShot(0, lambda: self._follow_moved_pages(waiting))

    def _set_page_count(self, count: int):
        """Update '/ 391' and the highest number the page box accepts."""
        self.page_box.blockSignals(True)  # don't trigger set_page here
        self.page_box.setRange(1, max(1, count))
        self.page_box.blockSignals(False)
        self.total_label.setText(f"/ {count}")

    def show_page(self, index: int):
        """Show page `index` (0-based) and keep the controls in sync."""
        if self.pdf is None:
            return
        count = len(self.pdf)
        self.index = max(0, min(index, count - 1))

        # Update the number box without it calling set_page again
        self.page_box.blockSignals(True)
        self.page_box.setValue(self.index + 1)
        self.page_box.blockSignals(False)

        self.prev_btn.setEnabled(self.index > 0)
        self.next_btn.setEnabled(self.index < count - 1)

        # Highlight the matching thumbnail. Skipped when it is already the
        # current one, so a Ctrl+click multi-selection is not wiped out.
        if self.thumbs.currentRow() != self.index:
            self.thumbs.setCurrentRow(self.index)
        self.thumbs.scrollToItem(self.thumbs.item(self.index))

        self._draw_page()

    def _select_thumbs(self, pages: list):
        """The Session changed the page selection (e.g. cleared after an edit)."""
        if self._selected_rows() == list(pages):
            return  # already showing this selection
        self.thumbs.blockSignals(True)  # don't report it back again
        self.thumbs.clearSelection()
        for row in pages:
            item = self.thumbs.item(row)
            if item is not None:
                item.setSelected(True)
        self.thumbs.blockSignals(False)

    # ------------------------------------------------------------------
    #  Panel -> Session (things the user did)
    # ------------------------------------------------------------------

    def _on_thumb_clicked(self, row: int):
        if row >= 0:  # -1 means "no thumbnail"
            self.session.set_page(row)

    def _on_thumb_selection(self):
        self.session.set_selected_pages(self._selected_rows())

    def _selected_rows(self) -> list:
        return sorted(self.thumbs.row(item) for item in self.thumbs.selectedItems())

    # ----- drag to reorder -----

    def _on_pages_dropped(self, pages: list, position: int):
        """Thumbnails `pages` were dropped in front of `position`."""
        if self.pdf is None or self.session.busy:
            return
        count = len(self.pdf)
        order = move_pages_order(count, pages, position)
        if order == list(range(count)):
            return  # dropped where they already were

        # Where the moved pages end up, so we can show them afterwards
        new_places = sorted(order.index(p) for p in pages)
        self._after_move = (count, new_places[0], new_places)

        moved = "1 page" if len(pages) == 1 else f"{len(pages)} pages"
        started = self.session.apply(
            reorder_pages, order=order, description=f"Moving {moved}..."
        )
        if not started:
            self._after_move = None

    def _follow_moved_pages(self, waiting):
        """Show and select the pages the user just moved."""
        _count, first, selected = waiting
        self.session.set_page(first)
        self.session.set_selected_pages(selected)

    def _on_busy_changed(self, busy: bool):
        self.thumbs.setDragEnabled(not busy)
        if not busy:
            # The job is over. If it failed or was cancelled, no new file
            # arrives, so forget the pages we were waiting to show. (When it
            # succeeded, load_document already used them before this runs.)
            QTimer.singleShot(0, self._forget_pending_move)

    def _forget_pending_move(self):
        self._after_move = None

    # ------------------------------------------------------------------
    #  Drawing
    # ------------------------------------------------------------------

    def _show_empty(self, text="No document open\nPick a PDF in the Explorer"):
        self.page_label.clear()
        self.page_label.setText(text)
        self.total_label.setText("/ 0")
        self.thumbs.clear()
        for widget in (self.prev_btn, self.next_btn, self.page_box):
            widget.setEnabled(False)

    def _draw_page(self):
        """Render the current page as large as fits, centred in the label."""
        if self.pdf is None:
            return
        box_w = self.page_label.width() - 40  # small margin around the page
        box_h = self.page_label.height() - 20
        if box_w < 20 or box_h < 20:
            return  # not on screen yet / too small
        pixmap = render_page(
            self.pdf, self.index, box_w, box_h, self.devicePixelRatioF()
        )
        self.page_label.setPixmap(pixmap)

    def _fill_thumbs(self, count: int):
        """Add one blank thumbnail per page; real pictures are drawn later."""
        self.thumbs.blockSignals(True)  # rebuilding, not a user action
        self.thumbs.clear()
        blank = QPixmap(THUMB_SIZE)
        blank.fill(QColor("white"))
        for i in range(count):
            self.thumbs.addItem(QListWidgetItem(QIcon(blank), str(i + 1)))
        self.thumbs.blockSignals(False)
        self._thumb_timer.start()

    def _draw_visible_thumbs(self):
        """Render only the thumbnails currently on screen.
        Drawing all pages of a 400-page PDF at once would freeze the app."""
        if self.pdf is None:
            return
        visible_area = self.thumbs.viewport().rect()
        for row in range(self.thumbs.count()):
            item = self.thumbs.item(row)
            if item.data(DRAWN):
                continue
            if self.thumbs.visualItemRect(item).intersects(visible_area):
                pixmap = render_page(
                    self.pdf,
                    row,
                    THUMB_SIZE.width(),
                    THUMB_SIZE.height(),
                    self.devicePixelRatioF(),
                )
                item.setIcon(QIcon(pixmap))
                item.setData(DRAWN, True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._page_timer.start()  # redraw the page to fit the new size
        self._thumb_timer.start()  # more thumbnails may be visible now


# ----------------------------------------------------------------------
#  Try this panel on its own:
#      uv run python -m pdf_toolkit.gui.preview  path/to/some.pdf
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    from pdf_toolkit.gui.session import Session

    app = QApplication(sys.argv)
    session = Session()
    session.errorMessage.connect(print)
    app.aboutToQuit.connect(session.cleanup)

    panel = PreviewPanel(session)
    panel.setWindowTitle("Preview panel test")
    panel.resize(900, 720)
    panel.show()

    if len(sys.argv) > 1:
        session.open(sys.argv[1])
    sys.exit(app.exec())
