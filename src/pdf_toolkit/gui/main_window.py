"""
main_window.py
--------------
Main application window for PGSL PDF Toolkit (IIT Ropar).
Acts as the central UI integrator connecting the 3 primary panels:
  1. ExplorerPanel (Left - explorer.py)
  2. PreviewPanel (Center - preview.py)
  3. Toolkit (Right - toolkit.py)
along with the bottom status and progress bar, and system menu.

All panels communicate exclusively through the shared Session hub.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

# Ensure this directory is in sys.path so direct imports within panels resolve
_gui_dir = str(Path(__file__).resolve().parent)
if _gui_dir not in sys.path:
    sys.path.insert(0, _gui_dir)

from pdf_toolkit.gui.explorer import ExplorerPanel
from pdf_toolkit.gui.preview import PreviewPanel
from pdf_toolkit.gui.session import Session
from pdf_toolkit.gui.toolkit import Toolkit
from pdf_toolkit.gui.widgets.status_bar import StatusBarWidget

if TYPE_CHECKING:
    from collections.abc import Callable

APP_TITLE = "PGSL PDF Toolkit — IIT Ropar"


from pdf_toolkit.core import (
    delete_pages,
    export_text,
    get_default_registry,
    images_to_pdf,
    merge_pdfs,
    ocr_document,
    pdf_to_images,
    reverse_pages,
    rotate_pages,
)

# Aliases for backwards compatibility
default_rotate = rotate_pages
default_reverse = reverse_pages
default_delete = delete_pages
default_merge = merge_pdfs
default_export_text = export_text
default_ocr = ocr_document
default_images_to_pdf = images_to_pdf
default_pdf_to_images = pdf_to_images


# ── MainWindow Class ─────────────────────────────────────────────────


class MainWindow(QMainWindow):
    """
    Main application window implementing the 3-panel architecture
    and status bar specified in the UI Wireframe and Guidelines.
    """

    def __init__(
        self,
        session: Session | None = None,
        operations: dict[str, Callable[..., Any]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.session = session or Session(self)

        # Built-in or injected operations from operations registry
        self.operations = (
            operations
            if operations is not None
            else get_default_registry().bind_session(self.session)
        )

        self._setup_window()
        self._build_layout()
        self._create_menus()
        self._connect_session()
        self._update_window_title()

    # ── Window Setup ─────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_TITLE)
        # Default 1280x720, minimum 960x540 (fits >= 720p screens)
        self.resize(1280, 720)
        self.setMinimumSize(960, 540)

        # Global Esc shortcut to cancel background worker
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self._on_escape_pressed)

    def _build_layout(self) -> None:
        central_container = QWidget(self)
        self.setCentralWidget(central_container)

        root_layout = QVBoxLayout(central_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 3-Column horizontal splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setObjectName("mainSplitter")
        self.splitter.setChildrenCollapsible(False)

        # 1. Left: Explorer Panel
        self.explorer_panel = ExplorerPanel(self.session, parent=self.splitter)
        self.splitter.addWidget(self.explorer_panel)

        # 2. Center: Preview Panel
        self.preview_panel = PreviewPanel(self.session, parent=self.splitter)
        self.splitter.addWidget(self.preview_panel)

        # 3. Right: Toolkit Panel
        self.toolkit_panel = Toolkit(
            self.session, operations=self.operations, parent=self.splitter
        )
        self.splitter.addWidget(self.toolkit_panel)

        # Proportions: Explorer ~250px, Toolkit ~280px, Preview occupies rest
        self.splitter.setSizes([260, 740, 280])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)

        root_layout.addWidget(self.splitter, stretch=1)

        # Bottom: Status & Progress Bar
        self.status_bar_widget = StatusBarWidget(self.session, parent=self)
        root_layout.addWidget(self.status_bar_widget)

    # ── Menus & Actions ──────────────────────────────────────────────

    def _create_menus(self) -> None:
        menubar = self.menuBar()
        menubar.setNativeMenuBar(True)

        # ── File Menu ──
        file_menu = menubar.addMenu("&File")

        act_open_pdf = QAction("&Open PDF...", self)
        act_open_pdf.setShortcut(QKeySequence("Ctrl+O"))
        act_open_pdf.setStatusTip("Open a PDF file for preview and editing")
        act_open_pdf.triggered.connect(self._on_open_pdf_dialog)
        file_menu.addAction(act_open_pdf)

        act_open_folder = QAction("Open &Folder...", self)
        act_open_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_folder.setStatusTip("Browse a folder in the Explorer panel")
        act_open_folder.triggered.connect(self._on_open_folder_dialog)
        file_menu.addAction(act_open_folder)

        file_menu.addSeparator()

        self.act_save = QAction("&Save", self)
        self.act_save.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save.setStatusTip("Save changes back to the original PDF")
        self.act_save.triggered.connect(self._on_save)
        file_menu.addAction(self.act_save)

        self.act_save_as = QAction("Save &As...", self)
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.setStatusTip("Save current PDF to a new file location")
        self.act_save_as.triggered.connect(self._on_save_as)
        file_menu.addAction(self.act_save_as)

        self.act_close_doc = QAction("&Close Document", self)
        self.act_close_doc.setShortcut(QKeySequence("Ctrl+W"))
        self.act_close_doc.setStatusTip("Close the current document")
        self.act_close_doc.triggered.connect(self._on_close_document)
        file_menu.addAction(self.act_close_doc)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.setStatusTip("Exit the application")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # ── Edit Menu ──
        edit_menu = menubar.addMenu("&Edit")

        self.act_undo = QAction("&Undo", self)
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_undo.setStatusTip("Undo the last modifying operation")
        self.act_undo.triggered.connect(self.session.undo)
        self.act_undo.setEnabled(False)
        edit_menu.addAction(self.act_undo)

        # ── View Menu ──
        view_menu = menubar.addMenu("&View")

        act_prev_page = QAction("&Previous Page", self)
        act_prev_page.setShortcuts([QKeySequence("Left"), QKeySequence("Page Up")])
        act_prev_page.triggered.connect(self.session.prev_page)
        view_menu.addAction(act_prev_page)

        act_next_page = QAction("&Next Page", self)
        act_next_page.setShortcuts([QKeySequence("Right"), QKeySequence("Page Down")])
        act_next_page.triggered.connect(self.session.next_page)
        view_menu.addAction(act_next_page)

        view_menu.addSeparator()

        act_toggle_explorer = QAction("Toggle &Explorer Panel", self)
        act_toggle_explorer.setShortcut(QKeySequence("F8"))
        act_toggle_explorer.setCheckable(True)
        act_toggle_explorer.setChecked(True)
        act_toggle_explorer.toggled.connect(self.explorer_panel.setVisible)
        view_menu.addAction(act_toggle_explorer)

        act_toggle_toolkit = QAction("Toggle &Toolkit Panel", self)
        act_toggle_toolkit.setShortcut(QKeySequence("F9"))
        act_toggle_toolkit.setCheckable(True)
        act_toggle_toolkit.setChecked(True)
        act_toggle_toolkit.toggled.connect(self.toolkit_panel.setVisible)
        view_menu.addAction(act_toggle_toolkit)

        act_reset_layout = QAction("&Reset Panel Layout", self)
        act_reset_layout.setShortcut(QKeySequence("Ctrl+0"))
        act_reset_layout.triggered.connect(
            lambda: self.splitter.setSizes([260, 740, 280])
        )
        view_menu.addAction(act_reset_layout)

        # ── Help Menu ──
        help_menu = menubar.addMenu("&Help")

        act_shortcuts = QAction("&Keyboard Shortcuts", self)
        act_shortcuts.setShortcut(QKeySequence("F1"))
        act_shortcuts.triggered.connect(self._show_shortcuts_dialog)
        help_menu.addAction(act_shortcuts)

        act_about = QAction("&About PGSL PDF Toolkit", self)
        act_about.triggered.connect(self._show_about_dialog)
        help_menu.addAction(act_about)

    # ── Session Connections ──────────────────────────────────────────

    def _connect_session(self) -> None:
        self.session.documentChanged.connect(self._on_document_changed)
        self.session.modifiedChanged.connect(self._on_modified_changed)
        self.session.undoAvailable.connect(self.act_undo.setEnabled)
        self.session.busyChanged.connect(self._on_busy_changed)

    def _update_window_title(self) -> None:
        if self.session.has_document and self.session.source:
            mod = "● " if self.session.modified else ""
            self.setWindowTitle(f"{mod}{self.session.source.name} — {APP_TITLE}")
        else:
            self.setWindowTitle(APP_TITLE)

    def _on_document_changed(self, _path: Path | None) -> None:
        has_doc = self.session.has_document
        self.act_save.setEnabled(has_doc and not self.session.busy)
        self.act_save_as.setEnabled(has_doc and not self.session.busy)
        self.act_close_doc.setEnabled(has_doc and not self.session.busy)
        self._update_window_title()

    def _on_modified_changed(self, _modified: bool) -> None:
        self._update_window_title()

    def _on_busy_changed(self, busy: bool) -> None:
        has_doc = self.session.has_document
        self.act_save.setEnabled(has_doc and not busy)
        self.act_save_as.setEnabled(has_doc and not busy)
        self.act_close_doc.setEnabled(has_doc and not busy)
        self.act_undo.setEnabled(self.session.can_undo and not busy)

    # ── User Actions ─────────────────────────────────────────────────

    def _on_open_pdf_dialog(self) -> None:
        start_dir = str(self.session.folder or Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF Document",
            start_dir,
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if file_path:
            self.session.open(file_path)

    def _on_open_folder_dialog(self) -> None:
        start_dir = str(self.session.folder or Path.home())
        folder = QFileDialog.getExistingDirectory(
            self,
            "Open Folder in Explorer",
            start_dir,
        )
        if folder:
            self.session.set_folder(folder)

    def _on_save(self) -> None:
        if not self.session.has_document:
            return
        if self.session.source:
            self.session.save()
        else:
            self._on_save_as()

    def _on_save_as(self) -> None:
        if not self.session.has_document:
            return
        default_name = (
            self.session.source.name if self.session.source else "document.pdf"
        )
        start_dir = str(
            self.session.source.parent
            if self.session.source
            else (self.session.folder or Path.home())
        )
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF As",
            str(Path(start_dir) / default_name),
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if dest:
            self.session.save_as(dest)

    def _on_close_document(self) -> None:
        if not self.session.has_document:
            return
        if self.session.modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "The active document has unsaved edits.\nDo you want to save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.session.close()

    def _on_escape_pressed(self) -> None:
        if self.session.busy:
            self.session.cancel()

    # ── Dialogs ──────────────────────────────────────────────────────

    def _show_shortcuts_dialog(self) -> None:
        msg = (
            "<b>Keyboard Shortcuts:</b><br><br>"
            "<table>"
            "<tr><td><b>Ctrl + O</b></td><td>Open PDF document</td></tr>"
            "<tr><td><b>Ctrl + Shift + O</b></td><td>Open folder in explorer</td></tr>"
            "<tr><td><b>Ctrl + S</b></td><td>Save document</td></tr>"
            "<tr><td><b>Ctrl + Shift + S</b></td><td>Save document as...</td></tr>"
            "<tr><td><b>Ctrl + W</b></td><td>Close current document</td></tr>"
            "<tr><td><b>Ctrl + Z</b></td><td>Undo last operation</td></tr>"
            "<tr><td><b>Left / Right</b></td><td>Previous / Next page</td></tr>"
            "<tr><td><b>F8 / F9</b></td><td>Toggle Explorer / Toolkit panel</td></tr>"
            "<tr><td><b>Ctrl + 0</b></td><td>Reset panel layout</td></tr>"
            "<tr><td><b>Escape</b></td><td>Cancel running operation</td></tr>"
            "</table>"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", msg)

    def _show_about_dialog(self) -> None:
        msg = (
            "<h3>PGSL PDF Toolkit</h3>"
            "<p><b>Version 0.1.0 (Milestone 2)</b></p>"
            "<p>Developed for IIT Ropar Store & Purchase and Student Affairs sections.</p>"
            "<p>A safe, fully offline desktop application for PDF manipulation:</p>"
            "<ul>"
            "<li>Merge, split, reorder, rotate and delete pages</li>"
            "<li>Image &lt;-&gt; PDF conversions</li>"
            "<li>Lossless & lossy PDF compression</li>"
            "<li>Bilingual Latin & Devanagari page numbering</li>"
            "<li>Completely offline OCR</li>"
            "<li>Safe multi-step Undo with isolated temporary copies</li>"
            "</ul>"
            "<p><i>Team: Piyush · Harsh · Johan · Chiranton</i></p>"
        )
        QMessageBox.about(self, "About PGSL PDF Toolkit", msg)

    # ── Lifecycle ────────────────────────────────────────────────────

    def closeEvent(self, event: Any) -> None:
        """Prompt to save if modified, then cleanup temporary session state."""
        if self.session.modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes in your document.\nDo you want to save before exiting?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        # Clean up temporary files and cancel running workers
        self.session.cleanup()
        event.accept()
