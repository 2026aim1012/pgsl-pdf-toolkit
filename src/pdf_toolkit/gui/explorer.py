from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QAbstractItemView, QMenu, QFileDialog,
    QSizePolicy, QFrame,
)

from session import Session


PDF_EXT = {".pdf"}
IMG_EXT = {".png", ".jpg", ".jpeg"}

PATH_ROLE = Qt.ItemDataRole.UserRole
KIND_ROLE = Qt.ItemDataRole.UserRole + 1        # "dir" | "pdf" | "img"


# Small helper function

class ElidedLabel(QLabel):
    """QLabel that shortens long paths with '…' instead of widening the panel."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = text
        self.setMinimumWidth(10)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,
                           QSizePolicy.Policy.Preferred)
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
        elided = fm.elidedText(self._full,
                               Qt.TextElideMode.ElideMiddle,
                               max(20, self.width()))
        super().setText(elided)


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
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.list, stretch=1)

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

    def _connect_session(self) -> None:
        self.session.folderChanged.connect(self._on_folder_changed)
        self.session.busyChanged.connect(self._on_busy_changed)

    # Session callbacks

    def _on_folder_changed(self, folder) -> None:
        self.path_label.setFullText(
            folder.as_posix() if folder else "No folder opened")
        self._populate(folder)

    def _on_busy_changed(self, busy: bool) -> None:
        # While a background task runs, freeze file picking
        self.open_btn.setEnabled(not busy)
        self.list.setEnabled(not busy)

    # Widget callbacks

    def _on_open_folder(self) -> None:
        start = (str(self.session.folder) if self.session.folder
                 else str(Path.home()))
        folder = QFileDialog.getExistingDirectory(
            self, "Open folder", start)
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
        # A checkbox was ticked/unticked — tell the session which files
        # are currently picked, so Merge / Image → PDF can use them.
        picked = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if (it.data(KIND_ROLE) in ("pdf", "img")
                    and it.checkState() == Qt.CheckState.Checked):
                picked.append(Path(it.data(PATH_ROLE)))
        self.session.set_picked_files(picked)

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
            new_state = (Qt.CheckState.Unchecked
                         if item.checkState() == Qt.CheckState.Checked
                         else Qt.CheckState.Checked)
            for it in self.list.selectedItems():
                if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    it.setCheckState(new_state)
        elif chosen is act_refresh:
            self._populate(self.session.folder)

    # Population

    def _populate(self, folder: Path | None) -> None:
        self.list.blockSignals(True)   # avoid a storm of itemChanged
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