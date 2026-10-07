"""
preview.py: the centre panel.

    PREVIEW
    ┌────────────┐
    │    page    │      big page, centred, redrawn when the window resizes
    └────────────┘
    ‹  [ 1 ]  / 391  ›   page navigation
    ┌ [1][2][3][4]… ┐    thumbnail strip (Ctrl+click / Shift+click / drag
    └───────────────┘    selects several pages)

This panel never changes any file. It only talks to the Session:
    listens to:  documentChanged, pageChanged, pageSelectionChanged
    calls:       set_page(i), next_page(), prev_page(), set_selected_pages([...])
"""

from pathlib import Path

import pypdfium2 as pdfium
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget,
)

THUMB_SIZE = QSize(60, 80)          # box each thumbnail picture fits into
DRAWN = Qt.ItemDataRole.UserRole    # marks thumbnails already rendered


def render_page(pdf, index: int, box_w: int, box_h: int, dpr: float = 1.0) -> QPixmap:
    """Render page `index` of `pdf` so it fits inside box_w x box_h pixels."""
    page = pdf[index]
    try:
        width_pt, height_pt = page.get_size()      # PDF units (1/72 inch)
        scale = min(box_w / width_pt, box_h / height_pt)
        # dpr is 2 on high-DPI screens: draw extra pixels so the page stays sharp
        image = page.render(scale=scale * dpr).to_pil().convert("RGB")
    finally:
        page.close()

    # Pillow image -> Qt image -> Qt pixmap (what a QLabel can display)
    qimage = QImage(image.tobytes(), image.width, image.height,
                    image.width * 3, QImage.Format.Format_RGB888).copy()
    pixmap = QPixmap.fromImage(qimage)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


class PreviewPanel(QWidget):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.pdf = None        # the open pdfium.PdfDocument (None = nothing open)
        self.index = 0         # page currently shown (0-based)

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
        self.page_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                      QSizePolicy.Policy.Ignored)
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
        self.page_box.setKeyboardTracking(False)   # jump on Enter, not every key

        self.total_label = QLabel("/ 0")

        nav = QHBoxLayout()
        nav.addStretch(1)                          # stretches on both sides
        nav.addWidget(self.prev_btn)               # keep the row centred
        nav.addWidget(self.page_box)
        nav.addWidget(self.total_label)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        layout.addLayout(nav)

        # 3) Thumbnail strip (a list shown as one horizontal row of icons)
        self.thumbs = QListWidget()
        self.thumbs.setObjectName("thumbs")
        self.thumbs.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumbs.setFlow(QListWidget.Flow.LeftToRight)
        self.thumbs.setWrapping(False)                       # a single row
        self.thumbs.setMovement(QListWidget.Movement.Static) # items can't be dragged
        self.thumbs.setIconSize(THUMB_SIZE)
        self.thumbs.setSpacing(6)
        self.thumbs.setUniformItemSizes(True)
        self.thumbs.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)  # Ctrl / Shift / drag
        self.thumbs.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.thumbs.setFixedHeight(THUMB_SIZE.height() + 50)

        strip = QFrame()                  # dashed box around the strip (style.qss)
        strip.setObjectName("thumbStrip")
        strip_layout = QVBoxLayout(strip)
        strip_layout.setContentsMargins(6, 4, 6, 2)
        strip_layout.addWidget(self.thumbs)
        layout.addWidget(strip)

        hint = QLabel("Click a thumbnail to jump · Ctrl + click or drag "
                      "to select multiple pages")
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

        # This panel -> Session
        self.prev_btn.clicked.connect(s.prev_page)
        self.next_btn.clicked.connect(s.next_page)
        self.page_box.valueChanged.connect(lambda number: s.set_page(number - 1))
        self.thumbs.currentRowChanged.connect(self._on_thumb_clicked)
        self.thumbs.itemSelectionChanged.connect(self._on_thumb_selection)

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
            except Exception as e:
                self._show_empty(f"Could not display this file:\n{e}")
                return

        count = len(self.pdf) if self.pdf else 0
        self.page_box.blockSignals(True)       # don't trigger set_page here
        self.page_box.setRange(1, max(1, count))
        self.page_box.blockSignals(False)
        self.total_label.setText(f"/ {count}")
        self._fill_thumbs(count)

        if count == 0:
            self._show_empty()
        else:
            self.page_box.setEnabled(True)
            self.show_page(self.session.page)

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
            return                              # already showing this selection
        self.thumbs.blockSignals(True)          # don't report it back again
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
        if row >= 0:                            # -1 means "no thumbnail"
            self.session.set_page(row)

    def _on_thumb_selection(self):
        self.session.set_selected_pages(self._selected_rows())

    def _selected_rows(self) -> list:
        return sorted(self.thumbs.row(item) for item in self.thumbs.selectedItems())

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
        box_w = self.page_label.width() - 40    # small margin around the page
        box_h = self.page_label.height() - 20
        if box_w < 20 or box_h < 20:
            return                              # not on screen yet / too small
        pixmap = render_page(self.pdf, self.index, box_w, box_h,
                             self.devicePixelRatioF())
        self.page_label.setPixmap(pixmap)

    def _fill_thumbs(self, count: int):
        """Add one blank thumbnail per page; real pictures are drawn later."""
        self.thumbs.blockSignals(True)          # rebuilding, not a user action
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
                pixmap = render_page(self.pdf, row, THUMB_SIZE.width(),
                                     THUMB_SIZE.height(), self.devicePixelRatioF())
                item.setIcon(QIcon(pixmap))
                item.setData(DRAWN, True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._page_timer.start()    # redraw the page to fit the new size
        self._thumb_timer.start()   # more thumbnails may be visible now


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
    session.error.connect(print)
    app.aboutToQuit.connect(session.cleanup)

    panel = PreviewPanel(session)
    panel.setWindowTitle("Preview panel test")
    panel.resize(900, 720)
    panel.show()

    if len(sys.argv) > 1:
        session.open(sys.argv[1])
    sys.exit(app.exec())