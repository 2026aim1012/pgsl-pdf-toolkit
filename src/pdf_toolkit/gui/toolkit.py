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

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


Operation = Callable[..., Any]


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

        self._build_ui()
        self._connect_session()
        self._refresh_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the complete toolkit panel."""

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("PDF Toolkit")
        title.setObjectName("toolkitTitle")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; padding-bottom: 4px;"
        )
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(2, 2, 2, 2)
        self.content_layout.setSpacing(8)

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

        self.page_info_label = QLabel("No document open")
        self.page_info_label.setWordWrap(True)

        scope_layout.addRow("Pages:", self.page_info_label)

        self.content_layout.addWidget(scope_group)

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
        self.content_layout.addWidget(rotate_group)

        # --------------------------------------------------------------
        # Reverse
        # --------------------------------------------------------------

        reverse_group = QGroupBox("Page Order")
        reverse_layout = QVBoxLayout(reverse_group)

        self.reverse_button = QPushButton("Reverse Page Order")
        self.reverse_button.clicked.connect(self._reverse)

        reverse_layout.addWidget(self.reverse_button)

        self.content_layout.addWidget(reverse_group)

        # --------------------------------------------------------------
        # Delete
        # --------------------------------------------------------------

        delete_group = QGroupBox("Delete Pages")
        delete_layout = QVBoxLayout(delete_group)

        delete_hint = QLabel(
            "Delete the pages selected in the preview."
        )
        delete_hint.setWordWrap(True)

        self.delete_button = QPushButton("Delete Selected Pages")
        self.delete_button.clicked.connect(self._delete)

        delete_layout.addWidget(delete_hint)
        delete_layout.addWidget(self.delete_button)

        self.content_layout.addWidget(delete_group)

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

        self.content_layout.addWidget(merge_group)

        # --------------------------------------------------------------
        # Watermark
        # --------------------------------------------------------------

        watermark_group = QGroupBox("Watermark")
        watermark_layout = QVBoxLayout(watermark_group)

        self.watermark_text = QLineEdit()
        self.watermark_text.setPlaceholderText("Watermark text...")

        watermark_options = QFormLayout()

        self.watermark_opacity = QSpinBox()
        self.watermark_opacity.setRange(1, 100)
        self.watermark_opacity.setValue(30)
        self.watermark_opacity.setSuffix("%")

        self.watermark_rotation = QSpinBox()
        self.watermark_rotation.setRange(-180, 180)
        self.watermark_rotation.setValue(45)
        self.watermark_rotation.setSuffix("°")

        watermark_options.addRow(
            "Opacity:", self.watermark_opacity
        )
        watermark_options.addRow(
            "Rotation:", self.watermark_rotation
        )

        self.watermark_button = QPushButton("Apply Watermark")
        self.watermark_button.clicked.connect(self._watermark)

        watermark_layout.addWidget(self.watermark_text)
        watermark_layout.addLayout(watermark_options)
        watermark_layout.addWidget(self.watermark_button)

        self.content_layout.addWidget(watermark_group)

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

        self.content_layout.addWidget(ocr_group)

        # --------------------------------------------------------------
        # Export text
        # --------------------------------------------------------------

        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout(export_group)

        self.export_text_button = QPushButton("Export Text")
        self.export_text_button.clicked.connect(self._export_text)

        export_layout.addWidget(self.export_text_button)

        self.content_layout.addWidget(export_group)

        # --------------------------------------------------------------
        # Undo
        # --------------------------------------------------------------

        undo_group = QGroupBox("History")
        undo_layout = QVBoxLayout(undo_group)

        self.undo_button = QPushButton("Undo Last Operation")
        self.undo_button.clicked.connect(self._undo)

        undo_layout.addWidget(self.undo_button)

        self.content_layout.addWidget(undo_group)

        # Spacer
        self.content_layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)

    # ------------------------------------------------------------------
    # Session connections
    # ------------------------------------------------------------------

    def _connect_session(self) -> None:
        """Connect Session signals to toolkit state/UI."""

        self.session.busyChanged.connect(self._on_busy_changed)
        self.session.undoAvailable.connect(self._on_undo_available)
        self.session.pageCountChanged.connect(self._on_page_count_changed)
        self.session.pickedFilesChanged.connect(self._on_picked_files_changed)
        self.session.pageSelectionChanged.connect(
            self._on_page_selection_changed
        )

    # ------------------------------------------------------------------
    # Session signal handlers
    # ------------------------------------------------------------------

    def _on_busy_changed(self, busy: bool) -> None:
        """Enable/disable controls while a background operation runs."""
        self._refresh_ui()

    def _on_undo_available(self, available: bool) -> None:
        """Update Undo button state."""
        self.undo_button.setEnabled(
            available and not self.session.busy
        )

    def _on_page_count_changed(self, count: int) -> None:
        """Receive page count from Session."""
        self.page_count = count
        self._update_page_info()
        self._refresh_ui()

    def _on_picked_files_changed(self, files: list[Path]) -> None:
        """Receive Explorer's picked-file list."""
        self.picked_files = list(files)

        count = len(self.picked_files)

        if count == 0:
            self.merge_info_label.setText(
                "No files selected in Explorer."
            )
        elif count == 1:
            self.merge_info_label.setText(
                "1 file selected. Select at least 2 PDFs to merge."
            )
        else:
            self.merge_info_label.setText(
                f"{count} files selected for merging."
            )

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

        has_selection = len(self.selected_pages) > 0
        has_merge_files = len(self.picked_files) >= 2

        # General document operations.
        self.scope_combo.setEnabled(
            has_document and not busy
        )

        self.rotate_button.setEnabled(
            has_document
            and not busy
            and self._has_operation("rotate")
        )

        self.reverse_button.setEnabled(
            has_document
            and not busy
            and self._has_operation("reverse")
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
            has_document
            and not busy
            and self._has_operation("ocr")
        )

        self.export_text_button.setEnabled(
            has_document
            and not busy
            and self._has_operation("export_text")
        )

        self.merge_button.setEnabled(
            not busy
            and has_merge_files
            and self._has_operation("merge")
        )

        # Undo has its own Session signal, but busy still takes precedence.
        self.undo_button.setEnabled(
            not busy
            and bool(self.session.can_undo)
        )

    def _update_page_info(self) -> None:
        """Update the human-readable page information label."""

        if self.page_count <= 0:
            self.page_info_label.setText("No document open.")
            return

        selected = len(self.selected_pages)

        if selected:
            self.page_info_label.setText(
                f"{self.page_count} pages total; "
                f"{selected} selected."
            )
        else:
            self.page_info_label.setText(
                f"{self.page_count} pages total; "
                "no thumbnail selection."
            )

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
            (
                f"Delete {len(pages)} selected page"
                f"{'' if len(pages) == 1 else 's'}?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
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

        if len(self.picked_files) < 2:
            self._show_warning(
                "Merge PDFs",
                "Select at least two PDF files in Explorer.",
            )
            return

        files = list(self.picked_files)

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

        self.requestStatus.emit(
            f"OCR completed ({len(text)} characters)."
        )

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

        self.requestStatus.emit(
            f"Text extraction completed ({len(text)} characters)."
        )

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
        dialog.setText(
            text[:4000] if text else "(No text returned.)"
        )

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
