"""
toolkit.py
---------
Right-side toolkit panel for the PGSL PDF Toolkit.

Architecture:
    Toolkit -> Session -> core/

The Toolkit panel NEVER calls another GUI panel directly.
All document-changing operations go through:

    session.apply(op, ...)

All read-only operations go through:

    session.run(fn, ...)

Expected backend contract:

    Modifying:
        op(src_path, out_path, reporter, **opts) -> None

    Read-only:
        fn(reporter, *args, **kwargs) -> Any

The actual core function names are intentionally injected through
the `operations` dictionary because the backend API is not defined
by session.py.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

Operation = Callable[..., Any]

# The five groups of tools, shown as big buttons at the top of the panel:
# (button text, what it is for - read out by screen readers and shown on hover)
CATEGORIES = [
    ("Pages", "Rotate, reorder, delete, insert and merge pages"),
    ("Compress", "Make the PDF file smaller"),
    ("Convert", "Turn images into a PDF, or PDF pages into images"),
    ("Stamp", "Add page numbers or a watermark"),
    ("Text", "Read the text in a PDF, even a scanned one"),
]
OPEN_KEY = "\u2318O" if sys.platform == "darwin" else "Ctrl+O"


class Toolkit(QWidget):
    """
    Right-side PDF toolkit panel.

    Parameters
    ----------
    session:
        Shared Session instance from session.py.

    operations:
        Mapping containing backend functions.

        Expected keys:

            "rotate"
            "reverse"
            "delete"
            "merge"
            "watermark"
            "ocr"
            "export_text"
            "compress"
            "insert"
            "page_numbers"
            "images_to_pdf"
            "pdf_to_images"

        Only operations that are supplied will be enabled.
    """

    # Optional signal for the main window if it wants to know that
    # the toolkit has requested an external action.
    requestStatus = Signal(str)

    def __init__(
        self,
        session: Any,
        operations: dict[str, Operation] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.session = session
        self.operations = operations or {}

        self.page_count = 0
        self.picked_files: list[Path] = []
        self.selected_pages: list[int] = []
        self._compression_before_size: int | None = None
        self._compression_pending = False
        # The control that had keyboard focus when a job started (see
        # _on_busy_changed); it gets focus back when the job is done.
        self._focus_to_restore: QWidget | None = None
        # Set while an insert runs:
        # (working file before, pages before, insert position, file name)
        self._insert_pending: tuple[Any, int, int, str] | None = None

        self._build_ui()
        self._setup_accessibility()
        self._connect_session()
        self._refresh_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _show_category(self, index: int) -> None:
        """Show the tools of one group (0 = Pages ... 4 = Text) and remember it."""
        for number, section in enumerate(self.sections):
            section.setVisible(number == index)
        button = self.category_group.button(index)
        if button is not None and not button.isChecked():
            button.setChecked(True)
        self.category_hint.setText(CATEGORIES[index][1] + ".")
        QSettings("PGSL", "PDF Toolkit").setValue("toolkit_category", index)

    def _setup_accessibility(self) -> None:
        """Add tooltips, accessible names, and a predictable tab sequence."""
        # Give every visible widget a useful tooltip, including labels and
        # controls that are not currently enabled. More specific tips below
        # override these defaults.
        for widget in self.findChildren(QWidget):
            if widget.toolTip().strip():
                continue
            name = widget.accessibleName().strip()
            if not name:
                name = widget.text().strip() if hasattr(widget, "text") else ""
            if not name and hasattr(widget, "placeholderText"):
                name = widget.placeholderText().strip()
            if name:
                widget.setToolTip(name)

        self.compress_quality.setAccessibleName("Compression quality")
        self.compress_quality.setAccessibleDescription(
            "Choose the requested compression quality from 1 to 100 percent."
        )
        self.convert_dpi.setAccessibleName("Image resolution in DPI")
        self.convert_dpi.setAccessibleDescription(
            "Choose the resolution used when rendering PDF pages as images."
        )
        self.insert_at.setAccessibleName("Insert before page number")
        self.number_start.setAccessibleName("First page number to print")
        self.number_start_page.setAccessibleName("Document page where numbering starts")
        self.watermark_opacity.setAccessibleName("Watermark opacity percentage")
        self.watermark_rotation.setAccessibleName("Watermark rotation in degrees")

        # Controls in visual top-to-bottom order. setTabOrder() establishes
        # an explicit chain instead of relying on widget construction order.
        order = [
            *self.category_group.buttons(),
            self.scope_combo,
            self.rotate_angle,
            self.rotate_button,
            self.reverse_button,
            self.delete_button,
            self.merge_button,
            self.insert_pick_button,
            self.insert_at,
            self.insert_button,
            self.number_position,
            self.number_start,
            self.number_start_page,
            self.number_numerals,
            self.number_button,
            self.undo_button,
            self.compress_quality,
            self.compress_button,
            self.images_to_pdf_button,
            self.pdf_to_images_button,
            self.convert_dpi,
            self.watermark_text,
            self.watermark_opacity,
            self.watermark_rotation,
            self.watermark_button,
            self.ocr_button,
            self.export_text_button,
        ]
        for first, second in pairwise(order):
            QWidget.setTabOrder(first, second)

    def _build_ui(self) -> None:
        """Construct the complete toolkit panel."""

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("PDF Toolkit")
        title.setObjectName("toolkitTitle")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding-bottom: 4px;")
        root.addWidget(title)

        # Shown while no PDF is open, so nobody wonders why the buttons are grey
        self.start_hint = QLabel(
            "Open a PDF to start.\n"
            "Click \u201cOpen folder\u2026\u201d on the left and pick a PDF, "
            f"or press {OPEN_KEY}."
        )
        self.start_hint.setObjectName("startHint")
        self.start_hint.setWordWrap(True)
        self.start_hint.setAccessibleName("How to start")
        root.addWidget(self.start_hint)

        # Big category buttons that are always visible: no hidden dropdowns,
        # no tabs with cut-off names. Exactly one is chosen at a time.
        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(True)
        category_grid = QGridLayout()
        category_grid.setSpacing(6)
        for index, (name, purpose) in enumerate(CATEGORIES):
            button = QPushButton(name)
            button.setObjectName("categoryButton")
            button.setCheckable(True)
            button.setMinimumHeight(40)
            button.setToolTip(purpose)
            button.setAccessibleName(f"{name} tools")
            button.setAccessibleDescription(purpose)
            self.category_group.addButton(button, index)
            category_grid.addWidget(button, index // 3, index % 3)
        root.addLayout(category_grid)

        # One sentence saying what the chosen group does
        self.category_hint = QLabel()
        self.category_hint.setObjectName("hint")
        self.category_hint.setWordWrap(True)
        root.addWidget(self.category_hint)

        # The tools of the chosen group, in one column that scrolls, so no
        # control is ever cut off on a small screen or with large text.
        sections = QWidget()
        sections_layout = QVBoxLayout(sections)
        sections_layout.setContentsMargins(0, 0, 4, 0)
        sections_layout.setSpacing(0)
        self.sections: list[QWidget] = []
        layouts: list[QVBoxLayout] = []
        for _name, _purpose in CATEGORIES:
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(8)
            sections_layout.addWidget(section)
            self.sections.append(section)
            layouts.append(section_layout)
        sections_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(sections)
        root.addWidget(scroll, 1)

        # Where each tool goes (names kept from the earlier tab layout)
        self.pages_layout = layouts[0]
        self.insert_tab_layout = layouts[0]
        self.optimise_layout = layouts[1]
        self.convert_layout = layouts[2]
        self.numbers_tab_layout = layouts[3]
        self.stamp_layout = layouts[3]
        self.text_layout = layouts[4]
        # Undo is always visible at the bottom, whatever group is chosen
        self.history_tab_layout = QVBoxLayout()
        root.addLayout(self.history_tab_layout)

        self.category_group.idClicked.connect(self._show_category)

        # --------------------------------------------------------------
        # Page scope
        # --------------------------------------------------------------

        scope_group = QGroupBox("Page Scope")
        scope_layout = QFormLayout(scope_group)

        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Entire document", "all")
        self.scope_combo.addItem("Current page", "current")
        self.scope_combo.addItem("Selected pages", "selected")

        scope_layout.addRow("Apply to:", self.scope_combo)

        # Page count line, e.g. "4 pages · 1 selected".
        # It gets its own full-width row (addRow with one widget spans both
        # columns). Squeezed into the narrow right column next to a
        # "Pages:" label, the text wrapped onto a second line that the form
        # layout did not make room for, so it was cut off.
        self.page_info_label = QLabel("No document open")
        self.page_info_label.setObjectName("pageInfo")
        self.page_info_label.setWordWrap(True)

        scope_layout.addRow(self.page_info_label)

        self.pages_layout.addWidget(scope_group)

        # --------------------------------------------------------------
        # Rotate
        # --------------------------------------------------------------

        rotate_group = QGroupBox("Rotate")
        rotate_layout = QVBoxLayout(rotate_group)

        rotate_controls = QHBoxLayout()

        self.rotate_angle = QComboBox()
        self.rotate_angle.addItem("90° clockwise", 90)
        self.rotate_angle.addItem("180°", 180)
        self.rotate_angle.addItem("270° clockwise", 270)

        self.rotate_button = QPushButton("Rotate")
        self.rotate_button.clicked.connect(self._rotate)

        rotate_controls.addWidget(self.rotate_angle)
        rotate_controls.addWidget(self.rotate_button)

        rotate_layout.addLayout(rotate_controls)
        self.pages_layout.addWidget(rotate_group)

        # --------------------------------------------------------------
        # Reverse
        # --------------------------------------------------------------

        reverse_group = QGroupBox("Page Order")
        reverse_layout = QVBoxLayout(reverse_group)

        self.reverse_button = QPushButton("Reverse Page Order")
        self.reverse_button.clicked.connect(self._reverse)

        reverse_layout.addWidget(self.reverse_button)

        self.pages_layout.addWidget(reverse_group)

        # --------------------------------------------------------------
        # Delete
        # --------------------------------------------------------------

        delete_group = QGroupBox("Delete Pages")
        delete_layout = QVBoxLayout(delete_group)

        delete_hint = QLabel("Delete the pages selected in the preview.")
        delete_hint.setWordWrap(True)

        self.delete_button = QPushButton("Delete Selected Pages")
        self.delete_button.clicked.connect(self._delete)

        delete_layout.addWidget(delete_hint)
        delete_layout.addWidget(self.delete_button)

        self.pages_layout.addWidget(delete_group)

        # --------------------------------------------------------------
        # Merge
        # --------------------------------------------------------------

        merge_group = QGroupBox("Merge PDFs")
        merge_layout = QVBoxLayout(merge_group)

        self.merge_info_label = QLabel(
            "Select files in Explorer for a batch operation."
        )
        self.merge_info_label.setWordWrap(True)

        self.merge_button = QPushButton("Merge Picked PDFs")
        self.merge_button.clicked.connect(self._merge)

        merge_layout.addWidget(self.merge_info_label)
        merge_layout.addWidget(self.merge_button)

        self.pages_layout.addWidget(merge_group)

        # --------------------------------------------------------------
        # Compress
        # --------------------------------------------------------------

        compress_group = QGroupBox("Compress PDF")
        compress_layout = QVBoxLayout(compress_group)

        self.compress_quality_label = QLabel("Quality: 70%")
        self.compress_quality = QSlider(Qt.Orientation.Horizontal)
        self.compress_quality.setRange(1, 100)
        self.compress_quality.setValue(70)
        self.compress_quality.setToolTip(
            "Higher quality usually preserves more detail but may reduce file size less."
        )
        self.compress_quality.valueChanged.connect(
            lambda value: self.compress_quality_label.setText(f"Quality: {value}%")
        )

        self.compress_size_label = QLabel("Before: —    After: —")
        self.compress_size_label.setWordWrap(True)
        self.compress_button = QPushButton("Compress PDF")
        self.compress_button.clicked.connect(self._compress)

        compress_layout.addWidget(self.compress_quality_label)
        compress_layout.addWidget(self.compress_quality)
        compress_layout.addWidget(self.compress_size_label)
        compress_layout.addWidget(self.compress_button)
        self.optimise_layout.addWidget(compress_group)

        # --------------------------------------------------------------
        # Convert
        # --------------------------------------------------------------

        convert_group = QGroupBox("Convert")
        convert_layout = QVBoxLayout(convert_group)

        self.images_to_pdf_button = QPushButton("Images → PDF")
        self.images_to_pdf_button.clicked.connect(self._images_to_pdf)
        self.pdf_to_images_button = QPushButton("PDF → Images")
        self.pdf_to_images_button.clicked.connect(self._pdf_to_images)

        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("Image DPI:"))
        self.convert_dpi = QSpinBox()
        self.convert_dpi.setRange(72, 600)
        self.convert_dpi.setSingleStep(24)
        self.convert_dpi.setValue(150)
        dpi_row.addWidget(self.convert_dpi)

        convert_layout.addWidget(self.images_to_pdf_button)
        convert_layout.addWidget(self.pdf_to_images_button)
        convert_layout.addLayout(dpi_row)
        self.convert_layout.addWidget(convert_group)

        # --------------------------------------------------------------
        # Insert pages
        # --------------------------------------------------------------

        insert_group = QGroupBox("Insert Pages")
        insert_layout = QFormLayout(insert_group)

        self.insert_path_label = QLabel("No PDF selected")
        self.insert_path_label.setWordWrap(True)
        self.insert_pick_button = QPushButton("Choose PDF to insert")
        self.insert_pick_button.clicked.connect(self._choose_insert_pdf)
        self.insert_at = QSpinBox()
        self.insert_at.setRange(1, 1)
        self.insert_at.setPrefix("Before page ")
        self.insert_button = QPushButton("Insert Pages")
        self.insert_button.clicked.connect(self._insert_pages)

        insert_layout.addRow(self.insert_pick_button)
        insert_layout.addRow("Selected file:", self.insert_path_label)
        insert_layout.addRow("Position:", self.insert_at)
        insert_layout.addRow(self.insert_button)
        self.insert_tab_layout.addWidget(insert_group)

        # --------------------------------------------------------------
        # Page numbers
        # --------------------------------------------------------------

        numbers_group = QGroupBox("Page Numbers")
        numbers_layout = QFormLayout(numbers_group)
        self.number_position = QComboBox()
        self.number_position.addItem("Bottom centre", "bottom")
        self.number_position.addItem("Bottom right", "bottom_right")
        self.number_position.addItem("Bottom left", "bottom_left")
        self.number_position.addItem("Top centre", "top")
        self.number_start = QSpinBox()
        self.number_start.setRange(1, 999999)
        self.number_start.setValue(1)
        self.number_start_page = QSpinBox()
        self.number_start_page.setRange(1, 999999)
        self.number_start_page.setValue(1)
        self.number_numerals = QComboBox()
        self.number_numerals.addItem("Latin (1, 2, 3)", "latin")
        self.number_numerals.addItem("Devanagari (१, २, ३)", "devanagari")
        self.number_button = QPushButton("Add Page Numbers")
        self.number_button.clicked.connect(self._page_numbers)

        numbers_layout.addRow("Position:", self.number_position)
        numbers_layout.addRow("Start number:", self.number_start)
        numbers_layout.addRow("Start page:", self.number_start_page)
        numbers_layout.addRow("Numerals:", self.number_numerals)
        numbers_layout.addRow(self.number_button)
        self.numbers_tab_layout.addWidget(numbers_group)

        # --------------------------------------------------------------
        # Watermark
        # --------------------------------------------------------------

        watermark_group = QGroupBox("Watermark")
        watermark_layout = QVBoxLayout(watermark_group)

        self.watermark_text = QLineEdit()
        self.watermark_text.setPlaceholderText("Watermark text...")
        # Re-check the Apply button while typing; otherwise it stays
        # greyed out until some other event refreshes the panel.
        self.watermark_text.textChanged.connect(lambda _: self._refresh_ui())

        watermark_options = QFormLayout()

        self.watermark_opacity = QSpinBox()
        self.watermark_opacity.setRange(1, 100)
        self.watermark_opacity.setValue(30)
        self.watermark_opacity.setSuffix("%")

        self.watermark_rotation = QSpinBox()
        self.watermark_rotation.setRange(-180, 180)
        self.watermark_rotation.setValue(45)
        self.watermark_rotation.setSuffix("°")

        watermark_options.addRow("Opacity:", self.watermark_opacity)
        watermark_options.addRow("Rotation:", self.watermark_rotation)

        self.watermark_button = QPushButton("Apply Watermark")
        self.watermark_button.clicked.connect(self._watermark)

        watermark_layout.addWidget(self.watermark_text)
        watermark_layout.addLayout(watermark_options)
        watermark_layout.addWidget(self.watermark_button)

        self.stamp_layout.addWidget(watermark_group)

        # --------------------------------------------------------------
        # OCR
        # --------------------------------------------------------------

        ocr_group = QGroupBox("OCR")
        ocr_layout = QVBoxLayout(ocr_group)

        ocr_hint = QLabel(
            "Run OCR on the current document and return the extracted text."
        )
        ocr_hint.setWordWrap(True)

        self.ocr_button = QPushButton("Run OCR")
        self.ocr_button.clicked.connect(self._ocr)

        ocr_layout.addWidget(ocr_hint)
        ocr_layout.addWidget(self.ocr_button)

        self.text_layout.addWidget(ocr_group)

        # --------------------------------------------------------------
        # Export text
        # --------------------------------------------------------------

        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout(export_group)

        self.export_text_button = QPushButton("Export Text")
        self.export_text_button.clicked.connect(self._export_text)

        export_layout.addWidget(self.export_text_button)

        self.text_layout.addWidget(export_group)

        # --------------------------------------------------------------
        # Undo
        # --------------------------------------------------------------

        undo_group = QGroupBox("History")
        undo_layout = QVBoxLayout(undo_group)

        self.undo_button = QPushButton("Undo Last Operation")
        self.undo_button.clicked.connect(self._undo)

        undo_layout.addWidget(self.undo_button)

        self.history_tab_layout.addWidget(undo_group)

        # Open on the group used last time (Pages the first time)
        saved = QSettings("PGSL", "PDF Toolkit").value("toolkit_category", 0)
        try:
            saved = int(saved)
        except (TypeError, ValueError):
            saved = 0
        self._show_category(saved if 0 <= saved < len(CATEGORIES) else 0)

        # Helpful descriptions for fields whose labels alone are ambiguous.
        self.scope_combo.setToolTip(
            "Choose whether page operations affect the whole PDF, the current page, or preview-selected pages."
        )
        self.rotate_angle.setToolTip("Choose the clockwise rotation angle.")
        self.compress_quality.setToolTip(
            "Set the requested compression quality. Higher values preserve more detail."
        )
        self.convert_dpi.setToolTip(
            "Set the image resolution in dots per inch (DPI). Higher values create larger images."
        )
        self.insert_at.setToolTip(
            "Choose the page number before which the selected PDF will be inserted."
        )
        self.number_position.setToolTip(
            "Choose where page numbers appear on each page."
        )
        self.number_start.setToolTip(
            "Choose the number printed on the first numbered page."
        )
        self.number_start_page.setToolTip(
            "Choose which document page receives the first page number."
        )
        self.number_numerals.setToolTip(
            "Choose the numeral style used for page numbers."
        )
        self.watermark_text.setToolTip("Enter the text to place over the PDF pages.")
        self.watermark_opacity.setToolTip("Choose how visible the watermark will be.")
        self.watermark_rotation.setToolTip("Choose the angle of the watermark.")

    # ------------------------------------------------------------------
    # Session connections
    # ------------------------------------------------------------------

    def _connect_session(self) -> None:
        """Connect Session signals to toolkit state/UI."""

        self.session.busyChanged.connect(self._on_busy_changed)
        self.session.undoAvailable.connect(self._on_undo_available)
        self.session.pageCountChanged.connect(self._on_page_count_changed)
        self.session.pickedFilesChanged.connect(self._on_picked_files_changed)
        self.session.pageSelectionChanged.connect(self._on_page_selection_changed)
        self.session.documentChanged.connect(self._on_document_changed)
        self.session.errorMessage.connect(self._on_operation_error)

    # ------------------------------------------------------------------
    # Session signal handlers
    # ------------------------------------------------------------------

    def _on_busy_changed(self, busy: bool) -> None:
        """Enable/disable controls while a background operation runs.

        If the focused control (say the Rotate button just clicked) is about
        to be greyed out, Qt would move focus to the next control and the
        scroll area would jump to show it, often all the way to the bottom.
        So focus is parked on the chosen category button at the top (outside
        the scroll area) during the job, then handed back afterwards.
        """
        if busy:
            focused = QApplication.focusWidget()
            if focused is not None and self.isAncestorOf(focused):
                self._focus_to_restore = focused
                parking = self.category_group.checkedButton()
                if parking is not None:
                    parking.setFocus(Qt.FocusReason.OtherFocusReason)
        self._refresh_ui()
        if not busy and self._focus_to_restore is not None:
            widget, self._focus_to_restore = self._focus_to_restore, None
            if widget.isEnabled() and widget.isVisible():
                widget.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_undo_available(self, available: bool) -> None:
        """Update Undo button state."""
        self.undo_button.setEnabled(available and not self.session.busy)

    def _on_page_count_changed(self, count: int) -> None:
        """Receive page count from Session."""
        self.page_count = count
        self._update_page_info()
        self._refresh_ui()

    def _on_document_changed(self, path: Path | None) -> None:
        """Feedback after an insert or a compression finishes."""
        if self._insert_pending is not None and path is not None:
            self._report_insert()
        if not self._compression_pending:
            return
        self._compression_pending = False
        if path is None or self._compression_before_size is None:
            return
        after_size = path.stat().st_size if path.exists() else 0
        before_size = self._compression_before_size
        self.compress_size_label.setText(
            f"Before: {self._format_size(before_size)}    "
            f"After: {self._format_size(after_size)}"
        )
        if after_size < before_size:
            saved = before_size - after_size
            percent = saved / before_size * 100 if before_size else 0
            self.requestStatus.emit(
                f"Compression saved {self._format_size(saved)} ({percent:.1f}%)."
            )
        else:
            self.requestStatus.emit(
                "Compression did not reduce the file size; the original size was retained."
            )

    def _report_insert(self) -> None:
        """Say how many pages were inserted and jump to the first of them."""
        old_file, before, at, name = self._insert_pending
        self._insert_pending = None
        # Only if this new document really is the insert's result (and not,
        # say, another file opened after the insert was cancelled)
        undo_stack = getattr(self.session, "undo_stack", [])
        if not undo_stack or undo_stack[-1] != old_file:
            return
        added = self.session.page_count - before
        if added <= 0:
            return
        pages = "1 page" if added == 1 else f"{added} pages"
        self.requestStatus.emit(
            f"Inserted {pages} from {name} before page {at + 1} "
            f"(now {self.session.page_count} pages)."
        )
        # A moment later, after every panel has loaded the new file
        QTimer.singleShot(0, lambda: self.session.set_page(at))

    def _on_operation_error(self, message: str) -> None:
        """Show a short, plain-language explanation when an operation fails."""
        self._insert_pending = None
        if self._compression_pending:
            self._compression_pending = False
            self.compress_size_label.setText("Compression did not finish.")

        raw = str(message or "").strip()
        lower = raw.lower()
        if "permission" in lower or "access is denied" in lower:
            friendly = "The file could not be changed because access was denied. Check that you have permission and that it is not open in another app."
        elif "no space" in lower or "disk full" in lower:
            friendly = "There is not enough free space to finish this task."
        elif "password" in lower or "encrypted" in lower:
            friendly = "This PDF is password-protected. Unlock it before trying again."
        elif "not found" in lower or "no such file" in lower:
            friendly = "The file could not be found. It may have been moved or deleted."
        elif "invalid pdf" in lower or "malformed" in lower or "damaged" in lower:
            friendly = "This PDF appears to be damaged or is not a valid PDF file."
        else:
            # Avoid dumping tracebacks or implementation details into the UI.
            friendly = (
                "The task could not be completed. Please check the file and try again."
            )
        self._show_warning("Could not complete the task", friendly)

    def _on_picked_files_changed(self, files: list[Path]) -> None:
        """Receive Explorer's picked-file list."""
        self.picked_files = list(files)

        pdfs = [p for p in self.picked_files if p.suffix.lower() == ".pdf"]
        count = len(pdfs)

        if count == 0:
            self.merge_info_label.setText(
                "No PDFs selected in Explorer. Select at least 2 PDFs to merge."
            )
        elif count == 1:
            self.merge_info_label.setText(
                "1 PDF selected. Select at least 2 PDFs to merge."
            )
        else:
            self.merge_info_label.setText(f"{count} PDFs selected for merging.")

        self._refresh_ui()

    def _on_page_selection_changed(self, pages: list[int]) -> None:
        """Receive thumbnail selections from Preview."""
        self.selected_pages = list(pages)
        self._update_page_info()
        self._refresh_ui()

    # ------------------------------------------------------------------
    # UI state
    # ------------------------------------------------------------------

    def _refresh_ui(self) -> None:
        """Refresh enabled/disabled state of toolkit controls."""

        busy = bool(self.session.busy)
        has_document = bool(self.session.has_document)
        self.start_hint.setVisible(not has_document)

        has_selection = len(self.selected_pages) > 0
        pdfs = [p for p in self.picked_files if p.suffix.lower() == ".pdf"]
        has_merge_files = len(pdfs) >= 2

        # General document operations.
        self.scope_combo.setEnabled(has_document and not busy)

        self.rotate_button.setEnabled(
            has_document and not busy and self._has_operation("rotate")
        )

        self.reverse_button.setEnabled(
            has_document and not busy and self._has_operation("reverse")
        )

        self.delete_button.setEnabled(
            has_document
            and not busy
            and has_selection
            and self._has_operation("delete")
        )

        self.watermark_button.setEnabled(
            has_document
            and not busy
            and bool(self.watermark_text.text().strip())
            and self._has_operation("watermark")
        )

        self.ocr_button.setEnabled(
            has_document and not busy and self._has_operation("ocr")
        )

        self.export_text_button.setEnabled(
            has_document and not busy and self._has_operation("export_text")
        )

        self.merge_button.setEnabled(
            has_document
            and not busy
            and has_merge_files
            and self._has_operation("merge")
        )

        self.compress_button.setEnabled(
            has_document and not busy and self._has_operation("compress")
        )
        self.images_to_pdf_button.setEnabled(
            not busy and self._has_operation("images_to_pdf")
        )
        self.pdf_to_images_button.setEnabled(
            has_document and not busy and self._has_operation("pdf_to_images")
        )
        self.insert_pick_button.setEnabled(not busy)
        self.insert_at.setEnabled(has_document and not busy)
        self.insert_button.setEnabled(
            has_document
            and not busy
            and bool(self.insert_path_label.property("insert_path"))
            and self._has_operation("insert")
        )
        self.number_button.setEnabled(
            has_document and not busy and self._has_operation("page_numbers")
        )
        self.insert_at.setMaximum(max(1, self.page_count + 1))
        self.number_start_page.setMaximum(max(1, self.page_count))

        # Undo has its own Session signal, but busy still takes precedence.
        self.undo_button.setEnabled(not busy and bool(self.session.can_undo))
        self._refresh_button_tooltips(
            busy, has_document, has_selection, has_merge_files
        )

    def _refresh_button_tooltips(
        self, busy: bool, has_document: bool, has_selection: bool, has_merge_files: bool
    ) -> None:
        """Explain both the purpose and disabled reason for every action."""
        states = {
            self.rotate_button: (
                "Rotate pages by the selected angle.",
                has_document and self._has_operation("rotate"),
                "Open a PDF first, or this tool is not available.",
            ),
            self.reverse_button: (
                "Reverse the page order in the open PDF.",
                has_document and self._has_operation("reverse"),
                "Open a PDF first, or this tool is not available.",
            ),
            self.delete_button: (
                "Delete pages selected in the preview.",
                has_selection and self._has_operation("delete"),
                "Select pages in the preview first, or this tool is not available.",
            ),
            self.merge_button: (
                "Merge the PDFs selected in Explorer.",
                has_merge_files and has_document and self._has_operation("merge"),
                "Open a PDF and select at least two PDFs in Explorer; this tool must also be available.",
            ),
            self.compress_button: (
                "Reduce the size of the open PDF.",
                has_document and self._has_operation("compress"),
                "Open a PDF first, or this tool is not available.",
            ),
            self.images_to_pdf_button: (
                "Create a PDF from selected image files.",
                self._has_operation("images_to_pdf"),
                "Image-to-PDF conversion is not available.",
            ),
            self.pdf_to_images_button: (
                "Save each page of the open PDF as an image.",
                has_document and self._has_operation("pdf_to_images"),
                "Open a PDF first, or this tool is not available.",
            ),
            self.insert_pick_button: (
                "Choose another PDF whose pages will be inserted.",
                True,
                "",
            ),
            self.insert_button: (
                "Insert the chosen PDF before the selected page.",
                bool(self.insert_path_label.property("insert_path")) and has_document,
                "Choose an insert PDF and open a document first.",
            ),
            self.number_button: (
                "Add page numbers to the open PDF.",
                has_document and self._has_operation("page_numbers"),
                "Open a PDF first, or this tool is not available.",
            ),
            self.watermark_button: (
                "Apply the watermark text to the open PDF.",
                has_document
                and bool(self.watermark_text.text().strip())
                and self._has_operation("watermark"),
                "Open a PDF, enter watermark text, and make sure this tool is available.",
            ),
            self.ocr_button: (
                "Recognise text in the open PDF.",
                has_document and self._has_operation("ocr"),
                "Open a PDF first, or this tool is not available.",
            ),
            self.export_text_button: (
                "Extract text from the open PDF.",
                has_document and self._has_operation("export_text"),
                "Open a PDF first, or this tool is not available.",
            ),
            self.undo_button: (
                "Undo the most recent document change.",
                bool(self.session.can_undo),
                "There is no operation to undo.",
            ),
        }
        for button, (purpose, prerequisite, reason) in states.items():
            if busy:
                button.setToolTip(
                    f"{purpose} Temporarily unavailable while another task is running."
                )
            elif not prerequisite:
                button.setToolTip(f"{purpose} {reason}")
            elif not button.isEnabled():
                button.setToolTip(f"{purpose} This action is currently unavailable.")
            else:
                button.setToolTip(purpose)

    def _update_page_info(self) -> None:
        """Update the human-readable page information label."""

        if self.page_count <= 0:
            self.page_info_label.setText("No document open")
            return

        selected = len(self.selected_pages)

        # Short text so it fits on one line, e.g. "4 pages · 1 selected"
        pages = "1 page" if self.page_count == 1 else f"{self.page_count} pages"
        if selected:
            self.page_info_label.setText(f"{pages} · {selected} selected")
        else:
            self.page_info_label.setText(f"{pages} · none selected")

    def _has_operation(self, name: str) -> bool:
        """Return True if a backend operation has been supplied."""
        return callable(self.operations.get(name))

    # ------------------------------------------------------------------
    # Scope handling
    # ------------------------------------------------------------------

    def _scope_options(self) -> dict[str, Any]:
        """
        Build the common page-scope options passed to core operations.

        The exact interpretation of these options belongs to core/.
        """

        scope = self.scope_combo.currentData()

        if scope == "current":
            return {
                "scope": "current",
                "pages": [self.session.page],
            }

        if scope == "selected":
            return {
                "scope": "selected",
                "pages": list(self.selected_pages),
            }

        return {
            "scope": "all",
            "pages": list(range(self.page_count)),
        }

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format a byte count compactly for the Toolkit panel."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.2f} MB"

    def _compress(self) -> None:
        """Compress the current PDF with the selected quality."""
        operation = self.operations.get("compress")
        if not callable(operation) or not self.session.current:
            return
        self._compression_before_size = self.session.current.stat().st_size
        self._compression_pending = True
        self.compress_size_label.setText(
            f"Before: {self._format_size(self._compression_before_size)}    After: working…"
        )
        started = self.session.apply(
            operation,
            description="Compressing PDF...",
            quality=self.compress_quality.value(),
        )
        if not started:
            self._compression_pending = False

    def _choose_insert_pdf(self) -> None:
        """Choose the PDF whose pages should be inserted."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose PDF to insert", "", "PDF files (*.pdf)"
        )
        if not path:
            return
        selected = Path(path)
        self.insert_path_label.setText(selected.name)
        self.insert_path_label.setToolTip(str(selected))
        self.insert_path_label.setProperty("insert_path", str(selected))
        self._refresh_ui()

    def _insert_pages(self) -> None:
        """Insert pages from the chosen PDF before the selected page."""
        operation = self.operations.get("insert")
        raw_path = self.insert_path_label.property("insert_path")
        if not callable(operation) or not raw_path:
            return
        insert_path = Path(str(raw_path))
        if not insert_path.is_file():
            self._show_warning("Insert Pages", "The selected PDF no longer exists.")
            return
        # The UI is 1-based; the page operation contract uses zero-based indices.
        at = self.insert_at.value() - 1
        self._insert_pending = (
            self.session.current,
            self.session.page_count,
            at,
            insert_path.name,
        )
        started = self.session.apply(
            operation,
            description=f"Inserting pages before page {self.insert_at.value()}...",
            insert_path=insert_path,
            at=at,
        )
        if not started:
            self._insert_pending = None

    def _page_numbers(self) -> None:
        """Apply page numbers with the chosen placement and numeral system."""
        operation = self.operations.get("page_numbers")
        if not callable(operation):
            return
        self.session.apply(
            operation,
            description="Adding page numbers...",
            position=self.number_position.currentData(),
            start=self.number_start.value(),
            start_page=self.number_start_page.value(),
            numerals=self.number_numerals.currentData(),
        )

    def _images_to_pdf(self) -> None:
        """Convert selected images to PDF and open the result."""
        operation = self.operations.get("images_to_pdf")
        if not callable(operation):
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose images to convert",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)",
        )
        if not paths:
            return
        output, _ = QFileDialog.getSaveFileName(
            self, "Save converted PDF", "images.pdf", "PDF files (*.pdf)"
        )
        if not output:
            return
        out_path = Path(output)
        if out_path.suffix.lower() != ".pdf":
            out_path = out_path.with_suffix(".pdf")
        self.session.run(
            operation,
            on_done=lambda result: self._images_to_pdf_finished(result, out_path),
            description="Converting images to PDF...",
            images=[Path(path) for path in paths],
            out_path=out_path,
        )

    def _images_to_pdf_finished(self, result: Any, fallback_path: Path) -> None:
        """Open the converted PDF returned by the engine."""
        result_path = Path(result) if result else fallback_path
        if result_path.is_file():
            self.session.open(result_path)
            self.requestStatus.emit(f"Created PDF: {result_path.name}")
        else:
            self._show_warning(
                "Images to PDF", "Conversion finished, but no output PDF was found."
            )

    def _pdf_to_images(self) -> None:
        """Render the open PDF into images in the selected output folder."""
        operation = self.operations.get("pdf_to_images")
        if not callable(operation) or not self.session.current:
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "Choose output folder for images"
        )
        if not out_dir:
            return
        self.session.run(
            operation,
            on_done=self._pdf_to_images_finished,
            description="Converting PDF pages to images...",
            pdf=self.session.current,
            out_dir=Path(out_dir),
            dpi=self.convert_dpi.value(),
        )

    def _pdf_to_images_finished(self, result: Any) -> None:
        """Report the number of images created by the conversion engine."""
        files = list(result or [])
        self.requestStatus.emit(f"Created {len(files)} image(s).")
        if not files:
            self._show_warning("PDF to Images", "No images were created.")

    def _rotate(self) -> None:
        """Request a rotate operation from Session."""

        operation = self.operations.get("rotate")

        if not callable(operation):
            return

        angle = int(self.rotate_angle.currentData())
        options = self._scope_options()
        options["angle"] = angle

        self.session.apply(
            operation,
            description=f"Rotating pages by {angle}°...",
            **options,
        )

    def _reverse(self) -> None:
        """Request a page-order reversal from Session."""

        operation = self.operations.get("reverse")

        if not callable(operation):
            return

        self.session.apply(
            operation,
            description="Reversing page order...",
        )

    def _delete(self) -> None:
        """Delete pages selected in the Preview panel."""

        operation = self.operations.get("delete")

        if not callable(operation):
            return

        if not self.selected_pages:
            self._show_warning(
                "Delete Pages",
                "Select one or more pages in the preview first.",
            )
            return

        pages = list(self.selected_pages)

        reply = QMessageBox.question(
            self,
            "Delete Pages",
            (f"Delete {len(pages)} selected page{'' if len(pages) == 1 else 's'}?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.session.apply(
            operation,
            description=f"Deleting {len(pages)} page(s)...",
            pages=pages,
        )

    def _merge(self) -> None:
        """Merge files selected by Explorer."""

        operation = self.operations.get("merge")

        if not callable(operation):
            return

        if not self.session.has_document:
            self._show_warning(
                "Merge PDFs",
                "Open a PDF document before merging files.",
            )
            return

        files = [p for p in self.picked_files if p.suffix.lower() == ".pdf"]
        if len(files) < 2:
            self._show_warning(
                "Merge PDFs",
                "Select at least two PDF files in Explorer.",
            )
            return

        self.session.apply(
            operation,
            description=f"Merging {len(files)} PDF files...",
            files=files,
        )

    def _watermark(self) -> None:
        """Apply a text watermark."""

        operation = self.operations.get("watermark")

        if not callable(operation):
            return

        text = self.watermark_text.text().strip()

        if not text:
            self._show_warning(
                "Watermark",
                "Enter watermark text first.",
            )
            return

        options = self._scope_options()

        options.update(
            {
                "text": text,
                "opacity": self.watermark_opacity.value() / 100.0,
                "rotation": self.watermark_rotation.value(),
            }
        )

        self.session.apply(
            operation,
            description="Applying watermark...",
            **options,
        )

    def _ocr(self) -> None:
        """Run OCR as a read-only background operation."""

        operation = self.operations.get("ocr")

        if not callable(operation):
            return

        self.session.run(
            operation,
            on_done=self._ocr_finished,
            description="Running OCR...",
        )

    def _ocr_finished(self, result: Any) -> None:
        """Handle OCR result returned by Session."""

        if result is None:
            self.requestStatus.emit("OCR completed.")
            return

        # Do not assume that the backend returns a particular structure.
        # Convert the result to text only for display/status purposes.
        if isinstance(result, str):
            text = result
        else:
            text = str(result)

        self.requestStatus.emit(f"OCR completed ({len(text)} characters).")

        # Keep the full result available without imposing a backend
        # result structure on the Session layer.
        self._show_text_result("OCR Result", text)

    def _export_text(self) -> None:
        """Run text extraction/export as a read-only operation."""

        operation = self.operations.get("export_text")

        if not callable(operation):
            return

        self.session.run(
            operation,
            on_done=self._export_text_finished,
            description="Extracting text...",
        )

    def _export_text_finished(self, result: Any) -> None:
        """Handle extracted text."""

        if result is None:
            self.requestStatus.emit("Text extraction completed.")
            return

        if isinstance(result, str):
            text = result
        else:
            text = str(result)

        self.requestStatus.emit(f"Text extraction completed ({len(text)} characters).")

        self._show_text_result("Extracted Text", text)

    def _undo(self) -> None:
        """Undo the most recent modifying operation."""

        if not self.session.can_undo:
            return

        self.session.undo()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_warning(self, title: str, message: str) -> None:
        """Display a non-destructive warning."""
        QMessageBox.warning(
            self,
            title,
            message,
        )

    def _show_text_result(self, title: str, text: str) -> None:
        """
        Display text returned by a read-only operation.

        This deliberately uses a simple dialog so Toolkit remains
        independent of Preview/MainWindow.
        """

        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText(text[:4000] if text else "(No text returned.)")

        if len(text) > 4000:
            dialog.setInformativeText(
                "The result is longer than the preview shown here."
            )

        dialog.exec()

    # ------------------------------------------------------------------
    # Public helper
    # ------------------------------------------------------------------

    def set_operations(
        self,
        operations: dict[str, Operation],
    ) -> None:
        """
        Replace the backend operation mapping.

        Useful if core/ is initialized after the GUI.
        """
        self.operations = dict(operations)
        self._refresh_ui()
