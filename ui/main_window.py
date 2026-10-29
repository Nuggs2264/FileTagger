import os
import re

from PySide6.QtCore import (
    QEventLoop,
    QRegularExpression,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTableView,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.media_item import SUPPORTED_EXTENSIONS, MediaItem
from core.tagger import normalize_cover_image, read_media_item, save_media_item
from ui.acoustic_id_dialog import AcousticIdDialog
from ui.file_table_model import COLUMNS, FileTableModel
from ui.icons import get_icon, get_pixmap
from ui.lyrics_dialog import LyricsDialog
from ui.music_fetcher_dialog import MusicFetcherDialog
from ui.online_fetcher_dialog import OnlineFetcherDialog
from ui.rename_dialog import RenameDialog
from ui.replay_gain_dialog import ReplayGainDialog
from ui.tag_editor_panel import TagEditorPanel
from ui.thumbnail_panel import ThumbnailPanel


class SaveWorker(QThread):
    progress = Signal(int, int, str)
    finished_save = Signal(int, list, bool)

    def __init__(self, items: list[MediaItem], parent=None):
        super().__init__(parent)
        self.items = items
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        saved_count = 0
        error_items = []
        total = len(self.items)
        cancelled = False
        for idx, item in enumerate(self.items, 1):
            if self._is_cancelled:
                cancelled = True
                break
            self.progress.emit(idx, total, item.file_name)
            if save_media_item(item):
                saved_count += 1
            else:
                error_items.append(
                    (item.file_name, item.error or "Unknown save error", getattr(item, "detailed_error", ""))
                )
        self.finished_save.emit(saved_count, error_items, cancelled)


class LoadWorker(QThread):
    progress = Signal(int, int, str)
    finished_load = Signal(list, bool)

    def __init__(self, file_paths: list[str], parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        import concurrent.futures

        total = len(self.file_paths)
        results: list[MediaItem | None] = [None] * total
        max_workers = min(4, max(1, total))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(read_media_item, fp): (idx, fp)
                for idx, fp in enumerate(self.file_paths)
            }
            for completed, future in enumerate(concurrent.futures.as_completed(future_to_idx), 1):
                if self._is_cancelled:
                    break
                idx, fp = future_to_idx[future]
                try:
                    item = future.result()
                    results[idx] = item
                except Exception as e:
                    item = MediaItem(file_path=fp)
                    item.error = f"Read error: {e}"
                    results[idx] = item
                self.progress.emit(completed, total, os.path.basename(fp))

        items = [it for it in results if it is not None]
        self.finished_load.emit(items, self._is_cancelled)


class FileSearchFilterProxyModel(QSortFilterProxyModel):
    """Filters table rows across multiple columns (Filename, Title, Artist, Album)."""

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        regex = self.filterRegularExpression()
        if not regex.pattern():
            return True

        model = self.sourceModel()
        # Search in Filename (col 1), Title (col 3), Artist (col 4), Album (col 5)
        for col in [1, 3, 4, 5]:
            idx = model.index(source_row, col, source_parent)
            text = str(model.data(idx, Qt.ItemDataRole.DisplayRole) or "")
            if regex.match(text).hasMatch():
                return True
        return False


class TableEmptyStateWidget(QWidget):
    """Interactive card overlay shown in the table viewport when no media files are loaded."""

    add_files_requested = Signal()
    add_folder_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(20, 20, 20, 20)

        card = QFrame()
        card.setObjectName("EmptyStateCard")
        card.setFixedWidth(440)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(12)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Vector Icon badge
        lbl_icon = QLabel()
        lbl_icon.setPixmap(get_pixmap("disc", "#3b82f6", 42))
        lbl_icon.setStyleSheet("background: transparent;")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_icon)

        # Title
        lbl_title = QLabel("No Media Files Loaded")
        lbl_title.setObjectName("EmptyStateTitle")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_title)

        # Subtitle
        lbl_sub = QLabel("Drag & drop audio or video files here, or browse from disk.")
        lbl_sub.setObjectName("EmptyStateSub")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setWordWrap(True)
        lbl_sub.setMinimumHeight(24)
        card_layout.addWidget(lbl_sub)

        card_layout.addSpacing(4)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_files = QPushButton("Add Files...")
        self.btn_files.setObjectName("PrimaryButton")
        self.btn_files.setIcon(get_icon("file-plus", "#ffffff", 15))
        self.btn_files.setIconSize(QSize(15, 15))
        self.btn_files.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_files.setStyleSheet("padding: 8px 18px; font-weight: 600; font-size: 9.5pt;")
        self.btn_files.clicked.connect(self.add_files_requested.emit)
        btn_row.addWidget(self.btn_files)

        self.btn_folder = QPushButton("Add Folder...")
        self.btn_folder.setIcon(get_icon("folder-plus", "#cbd5e1", 15))
        self.btn_folder.setIconSize(QSize(15, 15))
        self.btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_folder.setStyleSheet("padding: 8px 18px; font-weight: 600; font-size: 9.5pt;")
        self.btn_folder.clicked.connect(self.add_folder_requested.emit)
        btn_row.addWidget(self.btn_folder)

        card_layout.addLayout(btn_row)

        # Keyboard shortcuts hint
        kbd_row = QHBoxLayout()
        kbd_row.setSpacing(10)
        kbd_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        kbd_f = QLabel("Ctrl+O  (Files)")
        kbd_f.setObjectName("EmptyStateKbd")
        kbd_row.addWidget(kbd_f)

        kbd_d = QLabel("Ctrl+Shift+O  (Folder)")
        kbd_d.setObjectName("EmptyStateKbd")
        kbd_row.addWidget(kbd_d)

        card_layout.addLayout(kbd_row)
        layout.addWidget(card)

    def dragEnterEvent(self, event: QDragEnterEvent):
        win = self.window()
        if win and hasattr(win, "dragEnterEvent"):
            win.dragEnterEvent(event)
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        win = self.window()
        if win and hasattr(win, "dropEvent"):
            win.dropEvent(event)
        else:
            event.ignore()


class FileTableView(QTableView):
    """QTableView with an interactive empty-state overlay card when no files are loaded."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.empty_state = TableEmptyStateWidget(self.viewport())
        self.empty_state.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "empty_state") and self.empty_state:
            self.empty_state.setGeometry(self.viewport().rect())

    def update_empty_state(self):
        model = self.model()
        if model is None or model.rowCount() == 0:
            self.empty_state.setGeometry(self.viewport().rect())
            self.empty_state.show()
        else:
            self.empty_state.hide()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileTagger — Media Tag & Artwork Studio")
        self.resize(1260, 780)
        self.setAcceptDrops(True)

        self.table_model = FileTableModel(self)
        self.proxy_model = FileSearchFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._init_ui()
        self._create_actions_and_menus()
        self._update_status_bar()
        self.table_view.update_empty_state()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)

        # Main horizontal splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)

        # Left side: Borderless Studio Tracklist
        self.table_view = FileTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.empty_state.add_files_requested.connect(self.add_files_dialog)
        self.table_view.empty_state.add_folder_requested.connect(self.add_folder_dialog)
        self.proxy_model.modelReset.connect(self.table_view.update_empty_state)
        self.proxy_model.rowsInserted.connect(lambda *_: self.table_view.update_empty_state())
        self.proxy_model.rowsRemoved.connect(lambda *_: self.table_view.update_empty_state())
        self.table_view.setShowGrid(False)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(34)
        self.table_view.setWordWrap(False)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setHighlightSections(False)

        # Set default column widths and hide redundant full Path column (shown in Filename tooltip & Specs)
        for col_idx, (_name, width) in enumerate(COLUMNS):
            self.table_view.setColumnWidth(col_idx, width)
        self.table_view.setColumnHidden(11, True)

        self.table_view.setEditTriggers(
            QTableView.EditTrigger.DoubleClicked
            | QTableView.EditTrigger.EditKeyPressed
            | QTableView.EditTrigger.SelectedClicked
        )

        self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table_model.item_edited.connect(self._on_table_item_edited)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_table_context_menu)
        self.main_splitter.addWidget(self.table_view)

        # Right side: Cohesive Inspector Sidebar (Compact Cover Header Card on top + Full-Height Tag Inspector below)
        self.inspector_sidebar = QFrame()
        self.inspector_sidebar.setObjectName("RightInspectorSidebar")
        self.inspector_sidebar.setMinimumWidth(400)
        sidebar_layout = QVBoxLayout(self.inspector_sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        self.thumbnail_panel = ThumbnailPanel()
        self.thumbnail_panel.cover_updated.connect(self._on_cover_updated)
        self.thumbnail_panel.fetch_online_requested.connect(self.open_online_fetcher)
        sidebar_layout.addWidget(self.thumbnail_panel, 0)

        self.tag_editor = TagEditorPanel()
        self.tag_editor.tags_applied.connect(self._on_tags_applied)
        self.tag_editor.save_requested.connect(self.save_selected)
        self.tag_editor.revert_requested.connect(self.revert_selected)
        sidebar_layout.addWidget(self.tag_editor, 1)

        self.main_splitter.addWidget(self.inspector_sidebar)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([810, 430])

        main_layout.addWidget(self.main_splitter, 1)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _create_actions_and_menus(self):
        # Menu Bar
        menu_bar = self.menuBar()

        # --- File Menu ---
        file_menu = menu_bar.addMenu("&File")

        act_add_files = QAction(get_icon("file-plus", "#cbd5e1", 16), "Add Files...", self)
        act_add_files.setShortcut(QKeySequence.StandardKey.Open)
        act_add_files.triggered.connect(self.add_files_dialog)
        file_menu.addAction(act_add_files)

        act_add_folder = QAction(get_icon("folder-plus", "#cbd5e1", 16), "Add Folder...", self)
        act_add_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_add_folder.triggered.connect(self.add_folder_dialog)
        file_menu.addAction(act_add_folder)

        file_menu.addSeparator()

        self.act_save_sel = QAction(get_icon("save", "#60a5fa", 16), "Save Selected", self)
        self.act_save_sel.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save_sel.triggered.connect(self.save_selected)
        file_menu.addAction(self.act_save_sel)

        self.act_save_all = QAction(get_icon("save", "#cbd5e1", 16), "Save All Modified", self)
        self.act_save_all.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_all.triggered.connect(self.save_all)
        file_menu.addAction(self.act_save_all)

        file_menu.addSeparator()

        act_remove_sel = QAction(get_icon("trash", "#cbd5e1", 16), "Remove Selected from List", self)
        act_remove_sel.setShortcut(QKeySequence("Del"))
        act_remove_sel.triggered.connect(self.remove_selected)
        file_menu.addAction(act_remove_sel)

        act_clear_all = QAction(get_icon("x", "#cbd5e1", 16), "Clear List", self)
        act_clear_all.triggered.connect(self.clear_all)
        file_menu.addAction(act_clear_all)

        file_menu.addSeparator()

        act_exit = QAction("Exit", self)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # --- Tools Menu ---
        tools_menu = menu_bar.addMenu("&Tools")

        act_rename = QAction(get_icon("edit", "#cbd5e1", 16), "Batch Rename Files...", self)
        act_rename.setShortcut(QKeySequence("Ctrl+R"))
        act_rename.triggered.connect(self.open_rename_dialog)
        tools_menu.addAction(act_rename)

        act_fetch_online = QAction(get_icon("film", "#cbd5e1", 16), "Fetch Movie/TV Info (TMDb / IMDb)...", self)
        act_fetch_online.setShortcut(QKeySequence("Ctrl+F"))
        act_fetch_online.triggered.connect(self.open_online_fetcher)
        tools_menu.addAction(act_fetch_online)

        act_autonum = QAction(get_icon("hash", "#cbd5e1", 16), "Auto-Number Tracks (1..N)", self)
        act_autonum.triggered.connect(self.auto_number_tracks)
        tools_menu.addAction(act_autonum)

        act_guess_tags = QAction(get_icon("tag", "#cbd5e1", 16), "Guess Tags from Filename (Artist - Title)", self)
        act_guess_tags.triggered.connect(self.guess_tags_from_filename)
        tools_menu.addAction(act_guess_tags)

        # --- Audio Superpowers Menu ---
        audio_menu = menu_bar.addMenu("&Audio")

        self.act_music_fetch = QAction(
            get_icon("image", "#cbd5e1", 16), "Fetch Album Art && Tags (iTunes / Deezer / Discogs)...", self
        )
        self.act_music_fetch.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.act_music_fetch.triggered.connect(self.open_music_fetcher)
        audio_menu.addAction(self.act_music_fetch)

        self.act_acoustic_id = QAction(get_icon("fingerprint", "#cbd5e1", 16), "Identify Track (Acoustic ID)...", self)
        self.act_acoustic_id.setShortcut(QKeySequence("Ctrl+I"))
        self.act_acoustic_id.triggered.connect(self.open_acoustic_id)
        audio_menu.addAction(self.act_acoustic_id)

        self.act_lyrics = QAction(get_icon("mic", "#cbd5e1", 16), "Download Lyrics (LRCLIB)...", self)
        self.act_lyrics.setShortcut(QKeySequence("Ctrl+L"))
        self.act_lyrics.triggered.connect(self.open_lyrics_dialog)
        audio_menu.addAction(self.act_lyrics)

        self.act_replay_gain = QAction(get_icon("sliders", "#cbd5e1", 16), "Scan ReplayGain (EBU R128)...", self)
        self.act_replay_gain.setShortcut(QKeySequence("Ctrl+G"))
        self.act_replay_gain.triggered.connect(self.open_replay_gain)
        audio_menu.addAction(self.act_replay_gain)

        # --- Help Menu ---
        help_menu = menu_bar.addMenu("&Help")
        act_about = QAction("About FileTagger", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

        # --- Unified Studio Action Bar (Toolbar + Integrated Search) ---
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(15, 15))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(self.toolbar)

        act_add_files.setIconText("Files")
        act_add_folder.setIconText("Folder")
        self.act_save_sel.setIconText("Save")
        act_remove_sel.setIconText("Remove")
        self.act_music_fetch.setIconText("Artwork")
        self.act_music_fetch.setToolTip("Fetch Album Art & Tags (iTunes / Deezer / Discogs) [Ctrl+Shift+F]")
        self.act_acoustic_id.setIconText("AcoustID")
        self.act_acoustic_id.setToolTip("Identify Track via Acoustic Fingerprint (AcoustID) [Ctrl+I]")
        self.act_lyrics.setIconText("Lyrics")
        self.act_lyrics.setToolTip("Download Synchronized & Plain Lyrics (LRCLIB) [Ctrl+L]")
        self.act_replay_gain.setIconText("Gain")
        self.act_replay_gain.setToolTip("Scan ReplayGain / EBU R128 Loudness [Ctrl+G]")
        act_fetch_online.setIconText("Movie/TV")
        act_fetch_online.setToolTip("Fetch Movie/TV Info & Posters (TMDb / IMDb) [Ctrl+F]")
        act_rename.setIconText("Rename")
        act_rename.setToolTip("Batch Rename Files from Tags [Ctrl+R]")
        act_autonum.setIconText("Track #")
        act_autonum.setToolTip("Auto-Number Tracks (1..N)")

        # Group 1: Library
        self.toolbar.addAction(act_add_files)
        self.toolbar.addAction(act_add_folder)
        self.toolbar.addAction(self.act_save_sel)
        self.toolbar.addAction(act_remove_sel)
        self.toolbar.addSeparator()

        # Group 2: Auto-Tag Fetchers
        self.toolbar.addAction(self.act_music_fetch)
        self.toolbar.addAction(self.act_acoustic_id)
        self.toolbar.addAction(self.act_lyrics)
        self.toolbar.addAction(self.act_replay_gain)
        self.toolbar.addAction(act_fetch_online)
        self.toolbar.addSeparator()

        # Group 3: Batch Tools
        self.toolbar.addAction(act_rename)
        self.toolbar.addAction(act_autonum)

        # Expanding Spacer + Integrated Right-Aligned Search Input & Count Pill
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        self.toolbar.addWidget(spacer)

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("ToolbarSearchInput")
        self.txt_search.addAction(get_icon("search", "#64748b", 14), QLineEdit.ActionPosition.LeadingPosition)
        self.txt_search.setPlaceholderText("Filter tracks, artist, album...")
        self.txt_search.setFixedWidth(210)
        self.txt_search.textChanged.connect(self._on_search_changed)
        self.txt_search.setClearButtonEnabled(True)
        self.toolbar.addWidget(self.txt_search)

        self.lbl_count_badge = QLabel("0 files")
        self.lbl_count_badge.setObjectName("ToolbarCountBadge")
        self.toolbar.addWidget(self.lbl_count_badge)

    # ---------------------------------------------------------
    # Drag and Drop
    # ---------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if os.path.exists(local_path):
                paths.append(local_path)
        if paths:
            self.load_paths(paths)
            event.acceptProposedAction()

    # ---------------------------------------------------------
    # File Loading
    # ---------------------------------------------------------
    def add_files_dialog(self):
        ext_filter = "Media Files (*.mp3 *.flac *.m4a *.mp4 *.mkv *.wav *.ogg *.opus *.webm *.avi);;All Files (*)"
        files, _ = QFileDialog.getOpenFileNames(self, "Add Audio / Video Files", "", ext_filter)
        if files:
            self.load_paths(files)

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Add Folder Containing Media")
        if folder:
            self.load_paths([folder])

    def load_paths(self, paths: list[str]):
        if getattr(self, "_is_loading", False):
            return

        has_dirs = any(os.path.isdir(p) for p in paths)
        progress = None
        if has_dirs or len(paths) > 20:
            progress = QProgressDialog("Scanning for media files...", "Cancel", 0, 0, self)
            progress.setWindowTitle("Loading Media")
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setMinimumDuration(200)
            progress.setMinimumWidth(440)
            progress.show()
            QApplication.processEvents()

        all_files: list[str] = []
        seen_norm: set[str] = set()
        cancelled = False
        for path in paths:
            if progress and progress.wasCanceled():
                cancelled = True
                break
            abs_p = os.path.abspath(path)
            if os.path.isfile(abs_p):
                ext = os.path.splitext(abs_p)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    norm = os.path.normcase(abs_p)
                    if norm not in seen_norm:
                        seen_norm.add(norm)
                        all_files.append(abs_p)
            elif os.path.isdir(abs_p):
                for root, _, filenames in os.walk(abs_p):
                    if progress and progress.wasCanceled():
                        cancelled = True
                        break
                    for fname in filenames:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            file_p = os.path.abspath(os.path.join(root, fname))
                            norm = os.path.normcase(file_p)
                            if norm not in seen_norm:
                                seen_norm.add(norm)
                                all_files.append(file_p)
                    if progress:
                        progress.setLabelText(f"Found {len(all_files)} files... Scanning: {os.path.basename(root)}")
                        QApplication.processEvents()

        if cancelled or not all_files:
            if progress:
                progress.close()
            return

        # Avoid duplicates (normalized on Windows)
        existing_norms = {os.path.normcase(os.path.abspath(item.file_path)) for item in self.table_model.items}
        new_files = [f for f in all_files if os.path.normcase(f) not in existing_norms]

        if not new_files:
            if progress:
                progress.close()
            return

        self._is_loading = True
        try:
            if progress is None:
                progress = QProgressDialog("Reading metadata and covers...", "Cancel", 0, len(new_files), self)
                progress.setWindowTitle("Loading Media")
                progress.setWindowModality(Qt.WindowModality.ApplicationModal)
                progress.setMinimumDuration(0)
                progress.setMinimumWidth(440)
                progress.show()
            else:
                progress.setRange(0, len(new_files))

            loop = QEventLoop(self)
            result_holder = {"items": [], "cancelled": False}

            worker = LoadWorker(new_files, self)
            progress.canceled.connect(worker.cancel)

            def _on_load_progress(curr: int, total: int, fname: str):
                progress.setValue(curr)
                progress.setLabelText(f"Reading ({curr}/{total}): {fname}")

            def _on_load_done(items: list, was_cancelled: bool):
                result_holder["items"] = items
                result_holder["cancelled"] = was_cancelled
                loop.quit()

            worker.progress.connect(_on_load_progress)
            worker.finished_load.connect(_on_load_done)
            worker.start()
            loop.exec()
            worker.wait()
            progress.close()

            items_to_add = result_holder["items"]
            if items_to_add:
                self.table_model.add_items(items_to_add)
                self._update_status_bar()
        finally:
            if progress:
                progress.close()
            self._is_loading = False

    # ---------------------------------------------------------
    # Selection & Editing
    # ---------------------------------------------------------
    def _get_selected_source_rows(self) -> list[int]:
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes:
            # Fallback to selectedIndexes when individual cells are clicked/focused
            seen_rows = set()
            source_rows = []
            for idx in self.table_view.selectionModel().selectedIndexes():
                if idx.row() not in seen_rows:
                    seen_rows.add(idx.row())
                    src_idx = self.proxy_model.mapToSource(idx)
                    source_rows.append(src_idx.row())
            return sorted(source_rows)

        source_rows = []
        for idx in selected_indexes:
            src_idx = self.proxy_model.mapToSource(idx)
            source_rows.append(src_idx.row())
        return sorted(source_rows)

    def _get_selected_items(self) -> list[MediaItem]:
        rows = self._get_selected_source_rows()
        return [self.table_model.get_item(r) for r in rows]

    def _on_selection_changed(self):
        items = self._get_selected_items()
        self.tag_editor.set_selected_items(items)
        if len(items) == 1:
            self.thumbnail_panel.set_media_item(items[0])
        elif len(items) > 1:
            # Multi selection: show first item's cover or common
            self.thumbnail_panel.set_media_item(items[0])
        else:
            self.thumbnail_panel.set_media_item(None)

        self._update_status_bar()

    def _on_tags_applied(self, changed_tags: dict):
        selected_rows = self._get_selected_source_rows()
        for r in selected_rows:
            item = self.table_model.get_item(r)
            for k, v in changed_tags.items():
                if k in item.tags:
                    item.tags[k] = v
                else:
                    if v:
                        item.extra_tags[k] = v
                    elif k in item.extra_tags:
                        del item.extra_tags[k]
            self.table_model.notify_item_changed(r)
        self._update_status_bar()

    def _on_cover_updated(self, data, mime):
        selected_rows = self._get_selected_source_rows()
        for r in selected_rows:
            item = self.table_model.get_item(r)
            item.set_cover(data, mime)
            self.table_model.notify_item_changed(r)
        self._update_status_bar()

    def _on_search_changed(self, text: str):
        regex = QRegularExpression(re.escape(text), QRegularExpression.PatternOption.CaseInsensitiveOption)
        self.proxy_model.setFilterRegularExpression(regex)
        self._update_status_bar()

    def _on_table_item_edited(self, row: int, key: str, value: str):
        selected_rows = self._get_selected_source_rows()
        if row in selected_rows and len(selected_rows) == 1:
            item = self.table_model.get_item(row)
            self.tag_editor.set_selected_items([item])
        self._update_status_bar()

    # ---------------------------------------------------------
    # Saving & Reverting
    # ---------------------------------------------------------
    def _save_items_in_background(self, dirty_items: list[MediaItem]):
        if getattr(self, "_is_saving", False) or not dirty_items:
            return

        self._is_saving = True
        total_count = len(dirty_items)
        try:
            progress = QProgressDialog("Saving metadata and artwork to disk...", "Cancel", 0, total_count, self)
            progress.setWindowTitle("Saving Files")
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setMinimumDuration(0)
            progress.setMinimumWidth(440)
            progress.setValue(0)
            progress.show()

            loop = QEventLoop(self)
            result_holder = {"saved": 0, "errors": [], "cancelled": False}

            worker = SaveWorker(dirty_items, self)
            progress.canceled.connect(worker.cancel)

            def _on_progress(idx: int, total: int, fname: str):
                progress.setValue(idx - 1)
                progress.setLabelText(
                    f"Saving ({idx}/{total}): {fname}\nPlease wait — rewriting media files may take a moment..."
                )

            def _on_done(saved_count: int, error_items: list, was_cancelled: bool):
                progress.setValue(total_count)
                result_holder["saved"] = saved_count
                result_holder["errors"] = error_items
                result_holder["cancelled"] = was_cancelled
                loop.quit()

            worker.progress.connect(_on_progress)
            worker.finished_save.connect(_on_done)
            worker.start()
            loop.exec()
            worker.wait()
            progress.close()

            saved_count = result_holder["saved"]
            error_items = result_holder["errors"]
            was_cancelled = result_holder["cancelled"]

            self.table_model.notify_all_changed()
            self._update_status_bar()

            if error_items:
                err_msg = "\n".join([f"• {name}: {err}" for name, err, _ in error_items[:6]])
                if len(error_items) > 6:
                    err_msg += f"\n... and {len(error_items) - 6} more file(s)."

                details_blocks = []
                for name, err, detail in error_items:
                    details_blocks.append(
                        f"=== File: {name} ===\n"
                        f"Error: {err}\n"
                        f"Technical Details:\n{detail or '(No technical stack trace available)'}\n"
                    )
                full_details = "\n".join(details_blocks)

                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setWindowTitle("Save Incomplete - FileTagger")
                msg_box.setText(f"Saved {saved_count} of {total_count} file(s).\n\nErrors encountered:\n{err_msg}")
                msg_box.setDetailedText(full_details)
                msg_box.exec()
            elif was_cancelled:
                self.status_bar.showMessage(
                    f"Save cancelled by user. Saved {saved_count} of {total_count} file(s).", 5000
                )
            else:
                self.status_bar.showMessage(f"Successfully saved {saved_count} file(s).", 4000)
        finally:
            self._is_saving = False

    def save_selected(self):
        items = self._get_selected_items()
        if not items:
            return
        dirty_items = [it for it in items if it.is_dirty]
        if not dirty_items:
            self.status_bar.showMessage("Selected file(s) have no unsaved changes.", 3000)
            return
        self._save_items_in_background(dirty_items)

    def save_all(self):
        dirty_items = [it for it in self.table_model.items if it.is_dirty]
        if not dirty_items:
            QMessageBox.information(self, "No Changes", "There are no modified files to save.")
            return
        self._save_items_in_background(dirty_items)

    def revert_selected(self):
        items = self._get_selected_items()
        for item in items:
            item.revert()

        self._on_selection_changed()
        self.table_model.notify_all_changed()
        self._update_status_bar()

    def remove_selected(self):
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit)):
            return

        rows = self._get_selected_source_rows()
        if not rows:
            return
        dirty_count = sum(
            1 for r in rows if 0 <= r < len(self.table_model.items) and self.table_model.items[r].is_dirty
        )
        if dirty_count > 0:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"{dirty_count} selected file(s) have unsaved metadata changes.\n\nRemove them from the list anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.table_model.remove_rows(rows)
        self._on_selection_changed()
        self._update_status_bar()

    def clear_all(self):
        if not self.table_model.items:
            return
        dirty_count = sum(1 for it in self.table_model.items if it.is_dirty)
        if dirty_count > 0:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"{dirty_count} file(s) in the list have unsaved metadata changes.\n\nClear the entire list without saving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.table_model.clear()
        self._on_selection_changed()
        self._update_status_bar()

    # ---------------------------------------------------------
    # Tools Actions
    # ---------------------------------------------------------
    def open_rename_dialog(self):
        items = self._get_selected_items() or self.table_model.items
        if not items:
            QMessageBox.information(self, "Rename", "No files loaded to rename.")
            return

        dlg = RenameDialog(items, self)
        if dlg.exec() == RenameDialog.DialogCode.Accepted:
            self.table_model.notify_all_changed()

    def auto_number_tracks(self):
        selected = self._get_selected_items()
        items = selected if selected else self.table_model.items
        if not items:
            QMessageBox.information(self, "Auto-Number Tracks", "No files loaded to auto-number.")
            return

        total = len(items)
        target_desc = f"{total} selected track(s)" if selected else f"all {total} loaded track(s)"
        reply = QMessageBox.question(
            self,
            "Auto-Number Tracks",
            f"Auto-number {target_desc} in sequence from 1/{total} to {total}/{total}?\n\n"
            f"Example:\n  Track 1 → '1/{total}'\n  Track {total} → '{total}/{total}'\n\n"
            "This will update track numbers in memory. (Press Ctrl+S to save to disk).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for i, item in enumerate(items, 1):
            item.tags["track_number"] = f"{i}/{total}"
        self.table_model.notify_all_changed()
        self._on_selection_changed()
        self.status_bar.showMessage(f"Auto-numbered {total} tracks. Press Ctrl+S to save.", 4000)

    def guess_tags_from_filename(self):
        selected = self._get_selected_items()
        items = selected if selected else self.table_model.items
        if not items:
            QMessageBox.information(self, "Guess Tags from Filename", "No files loaded.")
            return

        total = len(items)
        target_desc = f"{total} selected file(s)" if selected else f"all {total} loaded file(s)"
        sample_item = items[0]
        sample_base = os.path.splitext(sample_item.file_name)[0]
        sample_m = re.match(r"^(?:(\d+)\s*[-.]\s*)?([^-]+)\s*-\s*(.+)$", sample_base)
        sample_hint = f"Sample: '{sample_item.file_name}'"
        if sample_m:
            tr, art, tit = sample_m.group(1), sample_m.group(2).strip(), sample_m.group(3).strip()
            preview_parts = []
            if tr:
                preview_parts.append(f"Track: {tr}")
            preview_parts.append(f"Artist: {art}")
            preview_parts.append(f"Title: {tit}")
            sample_hint += f"\n  → {', '.join(preview_parts)}"

        reply = QMessageBox.question(
            self,
            "Guess Tags from Filename",
            f"Extract Artist, Title, and Track Number from filenames for {target_desc}?\n\n"
            f"{sample_hint}\n\n"
            "Pattern: 'Artist - Title' or '01 - Artist - Title'\n"
            "(Press Ctrl+S afterwards to save to disk).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        updated = 0
        for item in items:
            base = os.path.splitext(item.file_name)[0]
            # Pattern: "Artist - Title" or "01 - Artist - Title" or "01. Artist - Title"
            m = re.match(r"^(?:(\d+)\s*[-.]\s*)?([^-]+)\s*-\s*(.+)$", base)
            if m:
                track, artist, title = m.groups()
                if track:
                    item.tags["track_number"] = track.strip()
                if artist:
                    item.tags["artist"] = artist.strip()
                if title:
                    item.tags["title"] = title.strip()
                updated += 1
            else:
                # Fallback: Just set title as filename
                if not item.tags.get("title"):
                    item.tags["title"] = base
                updated += 1

        self.table_model.notify_all_changed()
        self._on_selection_changed()
        self.status_bar.showMessage(f"Extracted tags for {updated} files. Press Ctrl+S to save.", 4000)

    def open_online_fetcher(self):
        items = self._get_selected_items()
        if not items:
            QMessageBox.information(self, "Fetch Online", "Please select a file to search for online metadata.")
            return

        # If audio track is selected, automatically route to the Music Album Art Fetcher
        if items[0].is_audio:
            self.open_music_fetcher()
            return

        first_item = items[0]
        default_query = first_item.tags.get("title") or first_item.file_name

        dlg = OnlineFetcherDialog(default_query, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_result:
            res = dlg.selected_result
            norm_poster = None
            if dlg.chk_poster.isChecked() and dlg.downloaded_poster_bytes:
                norm_poster, _ = normalize_cover_image(dlg.downloaded_poster_bytes)

            for it in items:
                if norm_poster:
                    it.set_cover(norm_poster, "image/jpeg")
                if dlg.chk_title.isChecked() and res.title:
                    it.tags["title"] = res.title
                if dlg.chk_year.isChecked() and res.year:
                    it.tags["year"] = res.year
                if dlg.chk_director.isChecked() and res.director:
                    it.tags["artist"] = res.director
                    it.extra_tags["director"] = res.director
                if dlg.chk_genres.isChecked() and res.genres:
                    it.tags["genre"] = ", ".join(res.genres)
                if dlg.chk_plot.isChecked() and res.overview:
                    it.tags["comment"] = res.overview
                    it.extra_tags["description"] = res.overview

            self.table_model.notify_all_changed()
            self._on_selection_changed()
            self.status_bar.showMessage(
                f"Applied online metadata for '{res.title}' ({res.year}). Press Ctrl+S to save.", 5000
            )

    def open_music_fetcher(self):
        items = self._get_selected_items()
        if not items:
            QMessageBox.information(self, "Fetch Album Art", "Please select a music file to search for album art.")
            return

        first_item = items[0]
        artist = first_item.tags.get("artist", "").strip()
        album = first_item.tags.get("album", "").strip()
        title = first_item.tags.get("title", "").strip()

        if artist and album:
            default_query = f"{artist} {album}"
        elif artist and title:
            default_query = f"{artist} {title}"
        elif album:
            default_query = album
        elif title:
            default_query = title
        else:
            default_query = first_item.file_name

        dlg = MusicFetcherDialog(default_query, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_result:
            res = dlg.selected_result
            norm_cover = None
            if dlg.chk_cover.isChecked() and dlg.downloaded_cover_bytes:
                norm_cover, _ = normalize_cover_image(dlg.downloaded_cover_bytes)

            for it in items:
                if norm_cover:
                    it.set_cover(norm_cover, "image/jpeg")
                if dlg.chk_album.isChecked() and res.album:
                    it.tags["album"] = res.album
                if dlg.chk_artist.isChecked() and res.artist:
                    it.tags["artist"] = res.artist
                if dlg.chk_year.isChecked() and res.year:
                    it.tags["year"] = res.year
                if dlg.chk_genre.isChecked() and res.genre:
                    it.tags["genre"] = res.genre

            self.table_model.notify_all_changed()
            self._on_selection_changed()
            self.status_bar.showMessage(
                f"Applied album art & metadata for '{res.album}' by {res.artist}. Press Ctrl+S to save.", 5000
            )

    def _show_table_context_menu(self, pos):
        items = self._get_selected_items()
        if not items:
            return

        menu = QMenu(self)
        menu.addAction(self.act_music_fetch)
        menu.addAction(self.act_acoustic_id)
        menu.addAction(self.act_lyrics)
        menu.addAction(self.act_replay_gain)
        menu.addSeparator()
        act_rename = QAction(get_icon("edit", "#cbd5e1", 16), "Batch Rename Files...", self)
        act_rename.triggered.connect(self.open_rename_dialog)
        menu.addAction(act_rename)
        act_fetch = QAction(get_icon("film", "#cbd5e1", 16), "Fetch Movie/TV Info (TMDb / IMDb)...", self)
        act_fetch.triggered.connect(self.open_online_fetcher)
        menu.addAction(act_fetch)
        menu.addSeparator()
        menu.addAction(self.act_save_sel)
        act_rem = QAction(get_icon("trash", "#cbd5e1", 16), "Remove from List", self)
        act_rem.triggered.connect(self.remove_selected)
        menu.addAction(act_rem)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def open_acoustic_id(self):
        items = self._get_selected_items()
        if not items:
            QMessageBox.information(self, "Identify Track", "Please select an audio file to identify.")
            return

        item = items[0]
        dlg = AcousticIdDialog(item, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.applied:
            self.table_model.notify_all_changed()
            self._on_selection_changed()
            title = item.tags.get("title") or item.file_name
            artist = item.tags.get("artist") or "Unknown"
            self.status_bar.showMessage(f"Identified '{title}' by {artist}. Press Ctrl+S to save.", 5000)

    def open_lyrics_dialog(self):
        items = self._get_selected_items()
        if not items:
            QMessageBox.information(self, "Download Lyrics", "Please select an audio file to fetch lyrics for.")
            return

        item = items[0]
        dlg = LyricsDialog(item, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.applied:
            self.table_model.notify_all_changed()
            self._on_selection_changed()
            title = item.tags.get("title") or item.file_name
            self.status_bar.showMessage(f"Lyrics updated for '{title}'. Press Ctrl+S to save.", 5000)

    def open_replay_gain(self):
        items = self._get_selected_items()
        if not items:
            items = self.table_model.items

        if not items:
            QMessageBox.information(self, "ReplayGain Scanner", "No files loaded to scan.")
            return

        dlg = ReplayGainDialog(items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.applied:
            self.table_model.notify_all_changed()
            self._on_selection_changed()
            self.status_bar.showMessage(
                f"ReplayGain loudness tags calculated for {len(items)} file(s). Press Ctrl+S to save.", 5000
            )

    # ---------------------------------------------------------
    # Status Bar
    # ---------------------------------------------------------
    def _update_status_bar(self):
        total = len(self.table_model.items)
        shown = self.proxy_model.rowCount()
        selected = len(self._get_selected_source_rows())
        dirty = sum(1 for it in self.table_model.items if it.is_dirty)

        if hasattr(self, "lbl_count_badge"):
            if self.txt_search.text().strip():
                self.lbl_count_badge.setText(f"{shown}/{total} files")
            else:
                self.lbl_count_badge.setText(f"{total} file{'s' if total != 1 else ''}")

        text = f"Total: {total} files  •  Selected: {selected}"
        if dirty > 0:
            text += f"  •  {dirty} unsaved"
        self.status_bar.showMessage(text)

    def _show_about(self):
        QMessageBox.about(
            self,
            "About FileTagger",
            "<h3>FileTagger</h3>"
            "<p>A powerful audio and video metadata tagger with interactive video thumbnail extraction.</p>"
            "<p><b>Supported formats:</b> MP3, FLAC, MP4, M4A, MKV, OGG, Opus, WAV, and more.</p>"
            "<hr>"
            "<p style='color: gray; font-size: 11px;'>This product uses the TMDB API but is not endorsed or certified by TMDB.</p>",
        )

    def closeEvent(self, event):
        dirty_count = sum(1 for it in self.table_model.items if it.is_dirty)
        if dirty_count > 0:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have {dirty_count} file(s) with unsaved metadata changes.\nDo you want to save them before exiting?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Save:
                self.save_all()
                if any(it.is_dirty for it in self.table_model.items):
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()
