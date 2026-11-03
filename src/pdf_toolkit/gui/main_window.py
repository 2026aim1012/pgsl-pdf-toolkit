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

from PySide6.QtCore import QPoint, QSettings, QSize, Qt
from PySide6.QtGui import QAction, QFontDatabase, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

# Ensure this directory is in sys.path so direct imports within panels resolve
_gui_dir = str(Path(__file__).resolve().parent)
if _gui_dir not in sys.path:
    sys.path.insert(0, _gui_dir)

from pdf_toolkit import __version__
from pdf_toolkit.gui.explorer import ExplorerPanel
from pdf_toolkit.gui.preview import PreviewPanel
from pdf_toolkit.gui.session import Session
from pdf_toolkit.gui.toolkit import Toolkit
from pdf_toolkit.gui.widgets.status_bar import StatusBarWidget

if TYPE_CHECKING:
    from collections.abc import Callable

APP_TITLE = "PGSL PDF Toolkit — IIT Ropar"

_FONTS_LOADED = False


def ensure_application_fonts() -> None:
    """Register embedded fonts such as Devanagari into the global font database."""
    global _FONTS_LOADED
    if _FONTS_LOADED:
        return
    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    deva_font = resources_dir / "NotoSansDevanagari-Regular.ttf"
    if deva_font.is_file():
        QFontDatabase.addApplicationFont(str(deva_font))
    _FONTS_LOADED = True


def load_stylesheet(dark_mode: bool = False) -> str:
    """Load application QSS stylesheet for light or dark mode."""
    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    filename = "style_dark.qss" if dark_mode else "style.qss"
    qss_path = resources_dir / filename
    if qss_path.is_file():
        try:
            return qss_path.read_text(encoding="utf-8")
        except OSError:
            pass
    if dark_mode:
        fallback = resources_dir / "style.qss"
        if fallback.is_file():
            try:
                return fallback.read_text(encoding="utf-8")
            except OSError:
                pass
    return ""


def get_resource_icon(name: str) -> QIcon:
    """Load an icon by name from the application resources/icons directory."""
    icon_path = (
        Path(__file__).resolve().parent.parent / "resources" / "icons" / f"{name}.png"
    )
    if icon_path.is_file():
        return QIcon(str(icon_path))
    return QIcon()


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
        ensure_application_fonts()
        self.session = session or Session(self)

        # Built-in or injected operations from operations registry
        self.operations = (
            operations
            if operations is not None
            else get_default_registry().bind_session(self.session)
        )

        settings = QSettings("PGSL", "PDF Toolkit")
        saved_dark = settings.value("dark_mode", False, type=bool)
        self._dark_mode = False

        self._setup_window()
        self._build_layout()
        self._create_menus()
        self.set_dark_mode(saved_dark)
        self._connect_session()
        self._update_window_title()

    # ── Window Setup ─────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(960, 540)

        # Restore window geometry (size & position) from QSettings
        self._restore_window_geometry()

        # Set application / window icon
        icons_dir = Path(__file__).resolve().parent.parent / "resources" / "icons"
        for icon_name in ("app_icon.png", "icon.png", "app_icon.ico", "icon.ico"):
            icon_path = icons_dir / icon_name
            if icon_path.is_file():
                self.setWindowIcon(QIcon(str(icon_path)))
                break

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
        self.explorer_panel.setObjectName("sidePanel")
        self.explorer_panel.setMinimumWidth(220)
        self.splitter.addWidget(self.explorer_panel)

        # 2. Center: Preview Panel
        self.preview_panel = PreviewPanel(self.session, parent=self.splitter)
        self.preview_panel.setObjectName("previewContainer")
        self.splitter.addWidget(self.preview_panel)

        # 3. Right: Toolkit Panel
        self.toolkit_panel = Toolkit(
            self.session, operations=self.operations, parent=self.splitter
        )
        self.toolkit_panel.setObjectName("toolkitContainer")
        self.toolkit_panel.setMinimumWidth(330)
        self.splitter.addWidget(self.toolkit_panel)

        # Proportions: Explorer ~250px, Toolkit ~340px, Preview occupies rest
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self._restore_splitter_sizes()

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
        act_open_pdf.setIcon(get_resource_icon("file-pdf"))
        act_open_pdf.setShortcut(QKeySequence("Ctrl+O"))
        act_open_pdf.setStatusTip("Open a PDF file for preview and editing")
        act_open_pdf.triggered.connect(self._on_open_pdf_dialog)
        file_menu.addAction(act_open_pdf)

        act_open_folder = QAction("Open &Folder...", self)
        act_open_folder.setIcon(get_resource_icon("folder-open"))
        act_open_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_folder.setStatusTip("Browse a folder in the Explorer panel")
        act_open_folder.triggered.connect(self._on_open_folder_dialog)
        file_menu.addAction(act_open_folder)

        file_menu.addSeparator()

        self.act_save = QAction("&Save", self)
        self.act_save.setIcon(get_resource_icon("save"))
        self.act_save.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save.setStatusTip("Save changes back to the original PDF")
        self.act_save.triggered.connect(self._on_save)
        file_menu.addAction(self.act_save)

        self.act_save_as = QAction("Save &As...", self)
        self.act_save_as.setIcon(get_resource_icon("save-as"))
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.setStatusTip("Save current PDF to a new file location")
        self.act_save_as.triggered.connect(self._on_save_as)
        file_menu.addAction(self.act_save_as)

        self.act_close_doc = QAction("&Close Document", self)
        self.act_close_doc.setIcon(get_resource_icon("close"))
        self.act_close_doc.setShortcut(QKeySequence("Ctrl+W"))
        self.act_close_doc.setStatusTip("Close the current document")
        self.act_close_doc.triggered.connect(self._on_close_document)
        file_menu.addAction(self.act_close_doc)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setIcon(get_resource_icon("exit"))
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.setStatusTip("Exit the application")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # ── Edit Menu ──
        edit_menu = menubar.addMenu("&Edit")

        self.act_undo = QAction("&Undo", self)
        self.act_undo.setIcon(get_resource_icon("undo"))
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_undo.setStatusTip("Undo the last modifying operation")
        self.act_undo.triggered.connect(self.session.undo)
        self.act_undo.setEnabled(False)
        edit_menu.addAction(self.act_undo)

        # ── View Menu ──
        view_menu = menubar.addMenu("&View")

        act_prev_page = QAction("&Previous Page", self)
        act_prev_page.setIcon(get_resource_icon("chevron-left"))
        act_prev_page.setShortcuts([QKeySequence("Left"), QKeySequence("Page Up")])
        act_prev_page.triggered.connect(self.session.prev_page)
        view_menu.addAction(act_prev_page)

        act_next_page = QAction("&Next Page", self)
        act_next_page.setIcon(get_resource_icon("chevron-right"))
        act_next_page.setShortcuts([QKeySequence("Right"), QKeySequence("Page Down")])
        act_next_page.triggered.connect(self.session.next_page)
        view_menu.addAction(act_next_page)

        view_menu.addSeparator()

        act_toggle_explorer = QAction("Toggle &Explorer Panel", self)
        act_toggle_explorer.setIcon(get_resource_icon("panel-explorer"))
        act_toggle_explorer.setShortcut(QKeySequence("F8"))
        act_toggle_explorer.setCheckable(True)
        act_toggle_explorer.setChecked(True)
        act_toggle_explorer.toggled.connect(self.explorer_panel.setVisible)
        view_menu.addAction(act_toggle_explorer)

        act_toggle_toolkit = QAction("Toggle &Toolkit Panel", self)
        act_toggle_toolkit.setIcon(get_resource_icon("panel-toolkit"))
        act_toggle_toolkit.setShortcut(QKeySequence("F9"))
        act_toggle_toolkit.setCheckable(True)
        act_toggle_toolkit.setChecked(True)
        act_toggle_toolkit.toggled.connect(self.toolkit_panel.setVisible)
        view_menu.addAction(act_toggle_toolkit)

        act_reset_layout = QAction("&Reset Panel Layout", self)
        act_reset_layout.setIcon(get_resource_icon("reset-layout"))
        act_reset_layout.setShortcut(QKeySequence("Ctrl+0"))
        act_reset_layout.triggered.connect(
            lambda: self.splitter.setSizes([250, 690, 340])
        )
        view_menu.addAction(act_reset_layout)

        self.act_toggle_theme = QAction("Toggle &Dark Mode", self)
        self.act_toggle_theme.setIcon(get_resource_icon("moon"))
        self.act_toggle_theme.setShortcut(QKeySequence("Ctrl+D"))
        self.act_toggle_theme.setStatusTip("Toggle between light and dark appearance")
        self.act_toggle_theme.setToolTip("Toggle dark mode (Ctrl+D)")
        self.act_toggle_theme.triggered.connect(self.toggle_theme)
        view_menu.addAction(self.act_toggle_theme)

        # ── Help Menu ──
        help_menu = menubar.addMenu("&Help")

        self.act_shortcuts = QAction("&Keyboard Shortcuts", self)
        self.act_shortcuts.setIcon(get_resource_icon("keyboard"))
        self.act_shortcuts.setShortcut(QKeySequence("F1"))
        self.act_shortcuts.setStatusTip("View accessible keyboard shortcuts guide")
        self.act_shortcuts.setToolTip("View keyboard shortcuts (F1)")
        self.act_shortcuts.triggered.connect(self._show_shortcuts_dialog)
        help_menu.addAction(self.act_shortcuts)

        self.act_about = QAction("&About PGSL PDF Toolkit", self)
        self.act_about.setIcon(get_resource_icon("info"))
        self.act_about.setStatusTip("View application version and credits")
        self.act_about.setToolTip("About PGSL PDF Toolkit")
        self.act_about.triggered.connect(self._show_about_dialog)
        help_menu.addAction(self.act_about)

        # ── Corner Widget: Dark/Light Mode Switch Button ──
        menubar.setNativeMenuBar(False)
        self.theme_btn = QPushButton("Dark Mode", self)
        self.theme_btn.setObjectName("themeToggleBtn")
        self.theme_btn.setIcon(get_resource_icon("moon"))
        self.theme_btn.setToolTip("Switch to dark appearance (Ctrl+D)")
        self.theme_btn.setAccessibleName("Toggle light or dark appearance")
        self.theme_btn.clicked.connect(self.toggle_theme)
        menubar.setCornerWidget(self.theme_btn, Qt.Corner.TopRightCorner)

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
            "<h3>Keyboard Shortcuts</h3>"
            "<table cellpadding='4' cellspacing='2'>"
            "<tr><th align='left'>Shortcut</th><th align='left'>Action</th></tr>"
            "<tr><td><b>Ctrl + O</b></td><td>Open PDF document</td></tr>"
            "<tr><td><b>Ctrl + Shift + O</b></td><td>Open folder in explorer</td></tr>"
            "<tr><td><b>Ctrl + S</b></td><td>Save document</td></tr>"
            "<tr><td><b>Ctrl + Shift + S</b></td><td>Save document as...</td></tr>"
            "<tr><td><b>Ctrl + W</b></td><td>Close current document</td></tr>"
            "<tr><td><b>Ctrl + Q</b></td><td>Exit application</td></tr>"
            "<tr><td><b>Ctrl + Z</b></td><td>Undo last operation</td></tr>"
            "<tr><td><b>Left / Right</b></td><td>Previous / Next page</td></tr>"
            "<tr><td><b>Page Up / Down</b></td><td>Previous / Next page</td></tr>"
            "<tr><td><b>Tab / Shift + Tab</b></td><td>Move focus between controls</td></tr>"
            "<tr><td><b>Space</b></td><td>Toggle selection / Activate focused button</td></tr>"
            "<tr><td><b>Enter</b></td><td>Open selected file in Explorer</td></tr>"
            "<tr><td><b>F8</b></td><td>Toggle Explorer panel</td></tr>"
            "<tr><td><b>F9</b></td><td>Toggle Toolkit panel</td></tr>"
            "<tr><td><b>Ctrl + 0</b></td><td>Reset panel layout</td></tr>"
            "<tr><td><b>Ctrl + D</b></td><td>Toggle dark / light appearance mode</td></tr>"
            "<tr><td><b>Escape</b></td><td>Cancel running operation</td></tr>"
            "<tr><td><b>F1</b></td><td>Show this keyboard shortcuts guide</td></tr>"
            "</table>"
        )
        QMessageBox.information(self, "Keyboard Shortcuts", msg)

    def _show_about_dialog(self) -> None:
        msg = (
            "<h3>PGSL PDF Toolkit</h3>"
            f"<p><b>Version {__version__}</b></p>"
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

        # Persist window geometry and splitter sizes
        self._save_settings()

        # Clean up temporary files and cancel running workers
        self.session.cleanup()
        event.accept()

    def toggle_theme(self) -> None:
        """Toggle between light and dark appearance modes."""
        self.set_dark_mode(not self._dark_mode)

    def set_dark_mode(self, enabled: bool) -> None:
        """Apply light or dark theme and update button / action text."""
        self._dark_mode = bool(enabled)
        if hasattr(self, "theme_btn") and self.theme_btn is not None:
            self.theme_btn.setText("Light Mode" if self._dark_mode else "Dark Mode")
            self.theme_btn.setIcon(
                get_resource_icon("sun")
                if self._dark_mode
                else get_resource_icon("moon")
            )
            self.theme_btn.setToolTip(
                "Switch to light appearance (Ctrl+D)"
                if self._dark_mode
                else "Switch to dark appearance (Ctrl+D)"
            )
        if hasattr(self, "act_toggle_theme") and self.act_toggle_theme is not None:
            self.act_toggle_theme.setText(
                "Toggle &Light Mode" if self._dark_mode else "Toggle &Dark Mode"
            )
            self.act_toggle_theme.setIcon(
                get_resource_icon("sun")
                if self._dark_mode
                else get_resource_icon("moon")
            )

        stylesheet = load_stylesheet(dark_mode=self._dark_mode)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)

    # ── Settings Persistence ─────────────────────────────────────────

    def _save_settings(self) -> None:
        """Persist window geometry and splitter sizes using standard QSettings key."""
        settings = QSettings("PGSL", "PDF Toolkit")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("window_size", self.size())
        settings.setValue("window_pos", self.pos())
        settings.setValue("dark_mode", self._dark_mode)
        if hasattr(self, "splitter") and self.splitter is not None:
            sizes = self.splitter.sizes()
            if sum(sizes) > 150:
                settings.setValue("splitter_sizes", sizes)

    def _restore_window_geometry(self) -> None:
        """Restore window geometry and size from QSettings, falling back to default 1280x720."""
        settings = QSettings("PGSL", "PDF Toolkit")
        geo = settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        size = settings.value("window_size")
        if isinstance(size, QSize) and size.isValid():
            self.resize(size)
        elif isinstance(size, (tuple, list)) and len(size) == 2:
            try:
                self.resize(int(size[0]), int(size[1]))
            except (ValueError, TypeError):
                pass
        elif not geo:
            self.resize(1280, 720)

        pos = settings.value("window_pos")
        if isinstance(pos, QPoint):
            self.move(pos)
        elif isinstance(pos, (tuple, list)) and len(pos) == 2:
            try:
                self.move(int(pos[0]), int(pos[1]))
            except (ValueError, TypeError):
                pass

    def _restore_splitter_sizes(self) -> None:
        """Restore splitter sizes from QSettings, falling back to default [250, 690, 340]."""
        settings = QSettings("PGSL", "PDF Toolkit")
        saved = settings.value("splitter_sizes")
        if saved and isinstance(saved, list) and len(saved) == 3:
            try:
                sizes = [int(x) for x in saved]
                if all(s > 0 for s in sizes):
                    self.splitter.setSizes(sizes)
                    return
            except (ValueError, TypeError):
                pass
        self.splitter.setSizes([250, 690, 340])
