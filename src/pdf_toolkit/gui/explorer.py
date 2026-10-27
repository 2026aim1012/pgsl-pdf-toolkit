from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from pdf_toolkit.gui.session import Session

PDF_EXT = {".pdf"}
IMG_EXT = {".png", ".jpg", ".jpeg"}

PATH_ROLE = Qt.ItemDataRole.UserRole
KIND_ROLE = Qt.ItemDataRole.UserRole + 1  # "dir" | "pdf" | "img"

def move_item(items: list, index: int, delta: int) -> tuple[list, int]:
    """Move items[index] by delta (-1 up, +1 down). Returns (new_list, new_index)."""
    new = index + delta
    if not 0 <= new < len(items):
        return list(items), index
    out = list(items)
    out[index], out[new] = out[new], out[index]
    return out, new

# Small helper function


class ElidedLabel(QLabel):
    """QLabel that shortens long paths with '…' instead of widening the panel."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = text
        self.setMinimumWidth(10)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._refresh()

    def setFullText(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(
            self._full, Qt.TextElideMode.ElideMiddle, max(20, self.width())
        )
        super().setText(elided)

class MergeOrderDialog(QDialog):
    """Lets the user arrange files (top = first) before merging or converting."""

    def __init__(self, files, parent=None, title="Choose file order"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._files = [Path(f) for f in files]

        self.list = QListWidget()
        up, down = QPushButton("Move up"), QPushButton("Move down")
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(+1))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        side = QVBoxLayout()
        side.addWidget(up)
        side.addWidget(down)
        side.addStretch()
        row = QHBoxLayout()
        row.addWidget(self.list, 1)
        row.addLayout(side)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Files are used from top to bottom."))
        root.addLayout(row)
        root.addWidget(buttons)
        self.resize(420, 320)
        self._refill(0)

    def _refill(self, current: int) -> None:
        self.list.clear()
        for p in self._files:
            item = QListWidgetItem(p.name)
            item.setToolTip(str(p))
            self.list.addItem(item)
        self.list.setCurrentRow(current)

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        self._files, new_row = move_item(self._files, row, delta)
        self._refill(new_row)

    def ordered_files(self) -> list[Path]:
        return list(self._files)

# The panel


class ExplorerPanel(QFrame):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setObjectName("sidePanel")
        self.setMinimumWidth(230)

        self._build_ui()
        self._connect_widgets()
        self._connect_session()

        # If a folder is already known (session was restored), show it
        if self.session.folder:
            self._on_folder_changed(self.session.folder)

    # Construction

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        title = QLabel("EXPLORER")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.open_btn = QPushButton("Open folder…")
        self.open_btn.setObjectName("openFolder")
        layout.addWidget(self.open_btn)

        self.path_label = ElidedLabel("No folder opened")
        self.path_label.setObjectName("pathLabel")
        layout.addWidget(self.path_label)

        self.list = QListWidget()
        self.list.setObjectName("explorer")
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.list, stretch=1)

        btn_row = QHBoxLayout()
        self.order_btn = QPushButton("Order…")
        self.order_btn.setToolTip("Choose the order of ticked files")
        btn_row.addWidget(self.order_btn)
        layout.addLayout(btn_row)
        self._update_buttons()

        hint = QLabel("Ctrl + click or drag to select multiple files")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def _connect_widgets(self) -> None:
        self.open_btn.clicked.connect(self._on_open_folder)
        self.list.itemClicked.connect(self._on_item_clicked)
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        self.order_btn.clicked.connect(self._on_choose_order)

    def _connect_session(self) -> None:
        self.session.folderChanged.connect(self._on_folder_changed)
        self.session.busyChanged.connect(self._on_busy_changed)
        self.session.pickedFilesChanged.connect(lambda _files: self._update_buttons())

    # Session callbacks

    def _on_folder_changed(self, folder) -> None:
        self.path_label.setFullText(folder.as_posix() if folder else "No folder opened")
        self._populate(folder)

    def _on_busy_changed(self, busy: bool) -> None:
        # While a background task runs, freeze file picking
        self.open_btn.setEnabled(not busy)
        self.list.setEnabled(not busy)
        self._update_buttons()

    def _update_buttons(self) -> None:
        idle = not self.session.busy
        self.order_btn.setEnabled(idle and len(self.session.picked_files) >= 2)

    def _on_choose_order(self) -> None:
        dlg = MergeOrderDialog(self.session.picked_files, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.session.set_picked_files(dlg.ordered_files())
            self.session.statusMessage.emit("Merge order updated.")

    # Widget callbacks

    def _on_open_folder(self) -> None:
        start = str(self.session.folder) if self.session.folder else str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Open folder", start)
        if folder:
            self.session.set_folder(Path(folder))

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        # Single click only selects. Do not open — that would prevent
        # Ctrl + click multi-selection for batch tools.
        pass

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        kind = item.data(KIND_ROLE)
        path = Path(item.data(PATH_ROLE))
        if kind == "dir":
            self.session.set_folder(path)
        elif kind == "pdf":
            self.session.open(path)

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        # Keep already-picked files in their current order; new ticks go at the end.
        ticked = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if (
                it.data(KIND_ROLE) in ("pdf", "img")
                and it.checkState() == Qt.CheckState.Checked
            ):
                ticked.append(Path(it.data(PATH_ROLE)))
        kept = [p for p in self.session.picked_files if p in ticked]
        added = [p for p in ticked if p not in kept]
        self.session.set_picked_files(kept + added)

    def _on_context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        menu = QMenu(self)
        act_open = act_tick = None

        if item is not None and item.data(KIND_ROLE) in ("pdf", "img"):
            act_open = menu.addAction("Open preview")
        if item is not None and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
            act_tick = menu.addAction("Tick / untick selected")
        act_refresh = menu.addAction("Refresh folder")

        chosen = menu.exec(self.list.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_open:
            self._on_item_clicked(item)
        elif chosen is act_tick:
            new_state = (
                Qt.CheckState.Unchecked
                if item.checkState() == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
            for it in self.list.selectedItems():
                if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    it.setCheckState(new_state)
        elif chosen is act_refresh:
            self._populate(self.session.folder)

    # Population

    def _populate(self, folder: Path | None) -> None:
        self.list.blockSignals(True)  # avoid a storm of itemChanged
        self.list.clear()

        if folder is None or not Path(folder).is_dir():
            self.list.blockSignals(False)
            return

        folder = Path(folder)

        # Up-one-level entry
        if folder.parent != folder:
            up = QListWidgetItem("↑  ../")
            up.setData(PATH_ROLE, str(folder.parent))
            up.setData(KIND_ROLE, "dir")
            up.setToolTip("Up one folder (double-click)")
            self.list.addItem(up)

        try:
            entries = sorted(folder.iterdir(), key=self._sort_key)
        except OSError as e:
            self.session.errorMessage.emit(f"Cannot read folder: {e}")
            self.list.blockSignals(False)
            return

        for p in entries:
            if p.name.startswith("."):
                continue
            try:
                if p.is_dir():
                    kind, label = "dir", p.name + "/"
                elif p.suffix.lower() in PDF_EXT:
                    kind, label = "pdf", p.name
                elif p.suffix.lower() in IMG_EXT:
                    kind, label = "img", p.name
                else:
                    continue
            except OSError:
                continue

            item = QListWidgetItem(label)
            item.setData(PATH_ROLE, str(p))
            item.setData(KIND_ROLE, kind)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item)

        self.list.blockSignals(False)

    @staticmethod
    def _sort_key(p: Path):
        """Directories first, then alphabetical (case-insensitive)."""
        try:
            is_dir = p.is_dir()
        except OSError:
            is_dir = False
        return (not is_dir, p.name.lower())
