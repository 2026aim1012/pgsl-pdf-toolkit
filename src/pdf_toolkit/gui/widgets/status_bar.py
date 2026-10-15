"""
status_bar.py
-------------
Dedicated, accessible bottom status bar widget for PGSL PDF Toolkit.
Displays document details, task status messages, and background job progress
with Cancel support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QWidget,
)

if TYPE_CHECKING:
    from pdf_toolkit.gui.session import Session


class StatusBarWidget(QFrame):
    """
    Bottom status bar component as depicted in the project wireframe.

    Layout:
        [ Document info (e.g. "Lecture 3.pdf · 3.46 MB") ] | [ Status message ]
        ... (spacer) ...
        [ ===== Progress Bar ===== ] [ 45% ] [ Cancel ]
    """

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.setObjectName("statusBarWidget")
        self.setFixedHeight(38)

        self._build_ui()
        self._connect_signals()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # ── Left: Document info ──────────────────────────────────────────
        self.file_info_label = QLabel("No document open")
        self.file_info_label.setObjectName("fileInfoLabel")
        self.file_info_label.setToolTip("Active document name and file size")
        self.file_info_label.setAccessibleName("Active document information")
        layout.addWidget(self.file_info_label)

        # Divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("color: #cbd5e1; max-height: 18px;")
        layout.addWidget(divider)

        # ── Left-Center: Status / message label ──────────────────────────
        self.status_message_label = QLabel("Ready")
        self.status_message_label.setObjectName("statusMessageLabel")
        self.status_message_label.setAccessibleName("Application status message")
        self.status_message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.status_message_label, stretch=1)

        # ── Right: Progress section (visible only during tasks) ──────────
        self.progress_container = QWidget()
        self.progress_container.setObjectName("progressContainer")
        prog_layout = QHBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("statusBarProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(240)
        self.progress_bar.setAccessibleName("Task progress bar")
        prog_layout.addWidget(self.progress_bar)

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("percentLabel")
        self.percent_label.setAccessibleName("Task completion percentage")
        self.percent_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        prog_layout.addWidget(self.percent_label)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelButton")
        self.cancel_btn.setToolTip("Cancel the ongoing operation")
        self.cancel_btn.setAccessibleName("Cancel ongoing operation")
        self.cancel_btn.clicked.connect(self.session.cancel)
        prog_layout.addWidget(self.cancel_btn)

        layout.addWidget(self.progress_container)

        # Initially idle
        self.progress_container.setVisible(False)

    def _connect_signals(self) -> None:
        self.session.fileInfoChanged.connect(self._on_file_info_changed)
        self.session.statusMessage.connect(self._on_status_message)
        self.session.errorMessage.connect(self._on_error_message)
        self.session.progressPercent.connect(self._on_progress_percent)
        self.session.busyChanged.connect(self._on_busy_changed)
        self.session.documentClosed.connect(self._on_document_closed)

    def _refresh(self) -> None:
        if self.session.file_info:
            self.file_info_label.setText(self.session.file_info)
        else:
            self.file_info_label.setText("No document open")
        self.progress_container.setVisible(self.session.busy)

    def _on_file_info_changed(self, text: str) -> None:
        self.file_info_label.setText(text if text else "No document open")

    def _on_document_closed(self) -> None:
        self.file_info_label.setText("No document open")
        self.status_message_label.setText("Document closed")
        self.status_message_label.setStyleSheet("color: #4b5563;")

    def _on_status_message(self, text: str) -> None:
        self.status_message_label.setText(text)
        self.status_message_label.setStyleSheet("color: #4b5563;")

    def _on_error_message(self, text: str) -> None:
        self.status_message_label.setText(f"Error: {text}")
        self.status_message_label.setStyleSheet("color: #dc2626; font-weight: 600;")

    def _on_progress_percent(self, pct: int) -> None:
        clamped = max(0, min(100, pct))
        self.progress_bar.setValue(clamped)
        self.percent_label.setText(f"{clamped}%")

    def _on_busy_changed(self, busy: bool) -> None:
        self.progress_container.setVisible(busy)
        if not busy:
            self.progress_bar.setValue(0)
            self.percent_label.setText("0%")
