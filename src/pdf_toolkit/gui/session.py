"""
session.py: Central communication hub and shared state for PGSL PDF Toolkit.

Notes from our team discussion (Day 1 & Day 2):
------------------------------------------------
We decided to split the GUI into 4 main parts so the four of us can work on our
own panels in parallel without merge conflicts or stepping on each other's code:

  1. Explorer (Left Panel - explorer.py):
     - Role: File tree and directory browsing; lets user pick files for batch operations
       (like Merge PDFs or Images -> PDF).
     - Calls into session:
         * session.open(path)               -> open selected PDF in preview
         * session.set_folder(path)         -> update current working directory
         * session.set_picked_files(files)  -> list of files checked for batch tools
     - Listens to:
         * session.folderChanged, session.pickedFilesChanged, session.busyChanged

  2. Preview (Center Panel - preview.py):
     - Role: Renders the active PDF page and thumbnail strip.
     - Calls into session:
         * session.set_page(idx)             -> user clicked next/prev or a thumbnail
         * session.set_selected_pages(list)  -> user multi-selected thumbnails
     - Listens to:
         * session.documentChanged          -> reload doc from session.current
         * session.documentClosed           -> clear page view and thumbnails
         * session.pageChanged              -> update displayed page
         * session.pageCountChanged         -> update total page count / slider bounds
         * session.pageSelectionChanged     -> update thumbnail highlights

  3. Toolkit (Right Panel - toolkit.py):
     - Role: Action buttons for PDF tools (Rotate, Reverse, Delete, Merge, Watermark, OCR, etc.).
       Toolkit manages its own inputs (spinboxes, sliders, dialogs) and gets page bounds
       from session.pageCountChanged.
     - Calls into session:
         * session.apply(op, ...)           -> runs modifying tool with undo support
         * session.run(fn, ...)             -> runs read-only tool (OCR, export text)
         * session.undo()                   -> reverts last applied operation
     - Listens to:
         * session.undoAvailable, session.busyChanged, session.pageCountChanged,
           session.pickedFilesChanged, session.pageSelectionChanged

  4. Main Window & Bottom Bar (main_window.py):
     - Role: Main window frame, menu bar, status bar, and progress indicator.
     - Calls into session:
         * session.cancel()                 -> user hit cancel button during task
         * session.save() / save_as(path)   -> Save / Save As menu actions
         * session.cleanup()                -> called on window close to clean temp files
     - Listens to:
         * session.fileInfoChanged          -> updates filename & size in status bar
         * session.progress, session.progressPercent -> drives progress bar widget
         * session.statusMessage, session.errorMessage -> shows status/error labels
         * session.busyChanged              -> toggles progress bar visibility

Design Rule:
  Panels must NEVER import or call each other directly! Everything goes through
  this Session hub using Qt signals so we keep things cleanly decoupled.

Backend Contract with core/:
  - Modifying tools: op(src_path: Path, out_path: Path, reporter: Reporter, **opts) -> None
  - Read-only tools: fn(reporter: Reporter, *args, **kwargs) -> Any
"""

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from PySide6.QtCore import QObject, QThread, Signal

# Keep last 10 versions in temp folder so user can undo changes
MAX_UNDO = 10


class Cancelled(Exception):
    """Raised inside a background worker when the user clicks Cancel."""


def format_size(size_bytes: int) -> str:
    """Helper to convert bytes into human-readable string for the status bar."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def count_pages(path: Path) -> int:
    """Get total page count using pypdfium2."""
    doc = pdfium.PdfDocument(str(path))
    count = len(doc)
    doc.close()
    return count


# ── Background Worker & Progress Reporter ─────────────────────────────

class Reporter:
    """
    Passed into core tools so they can report progress and check if user clicked Cancel.
    """

    def __init__(self, worker: "WorkerThread") -> None:
        self.worker = worker

    def __call__(self, done: int, total: int, msg: str = "") -> None:
        self.check_cancelled()
        self.worker.report_progress(done, total, msg)

    @property
    def is_cancelled(self) -> bool:
        return self.worker.is_cancelled

    def check_cancelled(self) -> None:
        if self.worker.is_cancelled:
            raise Cancelled("Operation cancelled by user")

    def set_message(self, msg: str) -> None:
        self.check_cancelled()
        self.worker.status.emit(msg)


class WorkerThread(QThread):
    """Runs long tasks off the main GUI thread so the UI stays responsive."""

    progress = Signal(int, int)
    percentage = Signal(int)
    status = Signal(str)
    done = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, job: Callable[[Reporter], Any]) -> None:
        super().__init__()
        self.job = job
        self.is_cancelled = False

    def cancel(self) -> None:
        self.is_cancelled = True

    def report_progress(self, done: int, total: int, msg: str = "") -> None:
        self.progress.emit(done, total)
        if total > 0:
            pct = int((done / total) * 100)
            self.percentage.emit(min(100, max(0, pct)))
        if msg:
            self.status.emit(msg)

    def run(self) -> None:
        try:
            reporter = Reporter(self)
            result = self.job(reporter)
            self.done.emit(result)
        except Cancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


# ── Central Session Hub ──────────────────────────────────────────────

class Session(QObject):
    # Document state signals
    documentChanged = Signal(object)      # Path | None (current working copy)
    documentClosed = Signal()
    modifiedChanged = Signal(bool)
    fileInfoChanged = Signal(str)         # e.g. "Lecture1.pdf · 2.4 MB"
    undoAvailable = Signal(bool)

    # Explorer signals
    folderChanged = Signal(object)        # Path | None
    pickedFilesChanged = Signal(list)     # list[Path] for batch tools

    # Preview signals
    pageChanged = Signal(int)             # 0-based page index
    pageCountChanged = Signal(int)        # total pages
    pageSelectionChanged = Signal(list)   # list[int] selected thumbnails

    # Worker & status signals (bottom bar)
    busyChanged = Signal(bool)            # True while worker is running
    progress = Signal(int, int)           # (done, total)
    progressPercent = Signal(int)         # 0..100
    statusMessage = Signal(str)
    errorMessage = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Working directory for temp files
        self.temp_dir = tempfile.TemporaryDirectory(prefix="pgsl_")
        self.temp_path = Path(self.temp_dir.name)
        self._temp_counter = 0

        # Document state
        self.source: Path | None = None       # Original file on disk
        self.current: Path | None = None      # Working copy in temp dir
        self._saved_copy: Path | None = None  # Reference to compare if modified
        self.page_count: int = 0
        self.page: int = 0                    # 0-based active page index
        self.selected_pages: list[int] = []   # 0-based selected thumbnails

        # Explorer state
        self.folder: Path | None = None
        self.picked_files: list[Path] = []

        # Undo stack (list of temp file paths)
        self.undo_stack: list[Path] = []

        # Worker management
        self.worker: WorkerThread | None = None
        self._on_done: Callable[[Any], None] | None = None

    # ── Properties ───────────────────────────────────────────────────

    @property
    def has_document(self) -> bool:
        return self.current is not None and self.page_count > 0

    @property
    def busy(self) -> bool:
        return self.worker is not None

    @property
    def modified(self) -> bool:
        return self.current is not None and self.current != self._saved_copy

    @property
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0 and not self.busy

    @property
    def file_info(self) -> str:
        """Formatted string for the status bar (e.g. 'Report.pdf · 1.50 MB')."""
        if not self.source:
            return ""
        try:
            target = self.current or self.source
            size = target.stat().st_size
            return f"{self.source.name} · {format_size(size)}"
        except OSError:
            return self.source.name

    # ── State Setters (Called by Panels) ─────────────────────────────

    def set_folder(self, path: Path | str | None) -> None:
        """Called by Explorer when the user changes directory."""
        self.folder = Path(path) if path else None
        self.folderChanged.emit(self.folder)

    def set_picked_files(self, files: list[Path | str]) -> None:
        """Called by Explorer when user selects multiple files for batch ops."""
        self.picked_files = [Path(f) for f in files]
        self.pickedFilesChanged.emit(self.picked_files)

    def set_page(self, index: int) -> bool:
        """Called by Preview when user navigates to another page."""
        if not self.has_document:
            return False
        clamped = max(0, min(index, self.page_count - 1))
        if clamped == self.page:
            return False
        self.page = clamped
        self.pageChanged.emit(clamped)
        return True

    def set_selected_pages(self, pages: list[int]) -> None:
        """Called by Preview when thumbnail selections change."""
        valid_pages = sorted({p for p in pages if 0 <= p < self.page_count})
        if valid_pages != self.selected_pages:
            self.selected_pages = valid_pages
            self.pageSelectionChanged.emit(valid_pages)

    # ── Document Lifecycle ───────────────────────────────────────────

    def open(self, path: Path | str) -> bool:
        """Open a PDF by making a temp copy so we never touch the original file directly."""
        if self.busy:
            self.statusMessage.emit("Please wait for the current task to finish.")
            return False

        path = Path(path)
        if not path.is_file():
            self.errorMessage.emit(f"File not found: {path}")
            return False

        work_copy = self._new_temp(path.suffix or ".pdf")
        try:
            shutil.copy2(path, work_copy)
            pages = count_pages(work_copy)
        except Exception as e:  # noqa: BLE001
            if work_copy.exists():
                work_copy.unlink(missing_ok=True)
            self.errorMessage.emit(f"Could not open {path.name}: {e}")
            return False

        # Reset undo history for the new document
        self._clear_undo()
        self.source = path
        self._saved_copy = work_copy
        self._set_current(work_copy, page_count=pages)
        self.statusMessage.emit(f"Opened {path.name}")
        return True

    def save(self) -> bool:
        """Save changes back to the original source file."""
        if not self.source or not self.current:
            return False
        return self.save_as(self.source)

    def save_as(self, path: Path | str) -> bool:
        """Save current document to a target file."""
        if not self.current:
            return False
        target = Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.current, target)
            self.source = target
            self._saved_copy = self.current
            self.modifiedChanged.emit(False)
            self.fileInfoChanged.emit(self.file_info)
            self.statusMessage.emit(f"Saved to {target.name}")
            return True
        except OSError as e:
            self.errorMessage.emit(f"Failed to save {target.name}: {e}")
            return False

    def close(self) -> None:
        """Close current document and clear working state."""
        if self.busy:
            return
        self._clear_undo()
        self.source = None
        self._saved_copy = None
        self._set_current(None)
        self.documentClosed.emit()

    # ── Running Operations ───────────────────────────────────────────

    def apply(self, op: Callable[..., Any], keep_page: bool = True,
              description: str = "", **opts: Any) -> bool:
        """
        Run a modifying PDF operation in the background and push current state
        to the undo stack.
        """
        if self.busy:
            self.statusMessage.emit("Please wait for the current task to finish.")
            return False
        if not self.has_document:
            self.errorMessage.emit("No document open.")
            return False

        src = self.current
        out = self._new_temp(".pdf")
        if description:
            self.statusMessage.emit(description)

        def job(reporter: Reporter) -> Path:
            try:
                op(src, out, reporter, **opts)
            except Exception:
                if out.exists():
                    out.unlink(missing_ok=True)
                raise
            return out

        return self._start_worker(job, lambda new_doc: self._applied(new_doc, keep_page))

    def run(self, fn: Callable[..., Any], on_done: Callable[[Any], None] | None = None,
              description: str = "", *args: Any, **kwargs: Any) -> bool:
        """Run a read-only background task (OCR, export text, etc.)."""
        if self.busy:
            self.statusMessage.emit("Please wait for the current task to finish.")
            return False

        if description:
            self.statusMessage.emit(description)

        return self._start_worker(lambda rpt: fn(rpt, *args, **kwargs), on_done)

    def undo(self) -> bool:
        """Revert document to the state before the last applied operation."""
        if not self.can_undo:
            return False

        prev = self.undo_stack.pop()
        # Clean up the undone file if it wasn't saved
        if self.current and self.current != self._saved_copy:
            self.current.unlink(missing_ok=True)

        self._set_current(prev, keep_page=True)
        self.statusMessage.emit("Undone")
        return True

    def cancel(self) -> None:
        """Cancel current background job."""
        if self.worker:
            self.worker.cancel()
            self.statusMessage.emit("Cancelling...")

    def cleanup(self) -> None:
        """Called when closing the app: stops worker and removes temp directory."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    # ── Helpers ──────────────────────────────────────────────────────

    def _start_worker(self, job: Callable[[Reporter], Any],
                      on_done: Callable[[Any], None] | None) -> bool:
        w = WorkerThread(job)
        w.progress.connect(self.progress)
        w.percentage.connect(self.progressPercent)
        w.status.connect(self.statusMessage)
        w.done.connect(self._task_done)
        w.failed.connect(self._task_failed)
        w.cancelled.connect(self._task_cancelled)

        self.worker = w
        self._on_done = on_done

        self.busyChanged.emit(True)
        self.undoAvailable.emit(False)
        self.progress.emit(0, 0)
        self.progressPercent.emit(0)

        w.start()
        return True

    def _finish_worker(self) -> None:
        if self.worker:
            self.worker.wait()
            self.worker.deleteLater()
            self.worker = None

        self.busyChanged.emit(False)
        self.undoAvailable.emit(self.can_undo)
        self.progress.emit(0, 0)
        self.progressPercent.emit(0)

    def _task_done(self, result: Any) -> None:
        callback = self._on_done
        self._on_done = None
        self._finish_worker()
        if callback:
            callback(result)

    def _task_failed(self, err_msg: str) -> None:
        self._on_done = None
        self._finish_worker()
        self.errorMessage.emit(err_msg)

    def _task_cancelled(self) -> None:
        self._on_done = None
        self._finish_worker()
        self.statusMessage.emit("Cancelled")

    def _applied(self, out: Path, keep_page: bool) -> None:
        if self.current:
            self.undo_stack.append(self.current)
            if len(self.undo_stack) > MAX_UNDO:
                evicted = self.undo_stack.pop(0)
                if evicted != self._saved_copy:
                    evicted.unlink(missing_ok=True)

        self._set_current(out, keep_page=keep_page)

    def _set_current(self, path: Path | None, page_count: int | None = None,
                     keep_page: bool = False) -> None:
        self.current = path
        if path is None:
            self.page_count = 0
            self.page = 0
            self.selected_pages = []
        else:
            self.page_count = page_count if page_count is not None else count_pages(path)
            self.page = min(self.page, max(0, self.page_count - 1)) if keep_page else 0
            self.selected_pages = []

        # Broadcast updates to panels
        self.documentChanged.emit(self.current)
        self.pageCountChanged.emit(self.page_count)
        self.pageChanged.emit(self.page)
        self.pageSelectionChanged.emit(self.selected_pages)
        self.modifiedChanged.emit(self.modified)
        self.fileInfoChanged.emit(self.file_info)
        self.undoAvailable.emit(self.can_undo)

    def _clear_undo(self) -> None:
        for p in self.undo_stack:
            if p != self._saved_copy:
                p.unlink(missing_ok=True)
        self.undo_stack.clear()
        if self.current and self.current != self._saved_copy:
            self.current.unlink(missing_ok=True)

    def _new_temp(self, suffix: str) -> Path:
        self._temp_counter += 1
        return self.temp_path / f"temp_{self._temp_counter:03d}{suffix}"
