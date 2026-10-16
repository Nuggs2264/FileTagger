import os
import re
from typing import List, Set

from PySide6.QtCore import Qt, QSortFilterProxyModel, QRegularExpression
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableView, QToolBar, QMenuBar, QMenu, QStatusBar,
    QFileDialog, QMessageBox, QLineEdit, QLabel, QHeaderView,
    QProgressDialog, QApplication, QDialog
)
from PySide6.QtGui import QAction, QKeySequence, QDragEnterEvent, QDropEvent

from core.media_item import MediaItem, SUPPORTED_EXTENSIONS
from core.tagger import read_media_item, save_media_item, normalize_cover_image
from ui.file_table_model import FileTableModel, COLUMNS
from ui.tag_editor_panel import TagEditorPanel
from ui.thumbnail_panel import ThumbnailPanel
from ui.rename_dialog import RenameDialog
from ui.online_fetcher_dialog import OnlineFetcherDialog
from ui.acoustic_id_dialog import AcousticIdDialog
from ui.lyrics_dialog import LyricsDialog
from ui.replay_gain_dialog import ReplayGainDialog
from ui.music_fetcher_dialog import MusicFetcherDialog

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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileTagger - Advanced Media Tag & Thumbnail Editor")
        self.resize(1240, 780)
        self.setAcceptDrops(True)

        self.table_model = FileTableModel(self)
        self.proxy_model = FileSearchFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._init_ui()
        self._create_actions_and_menus()
        self._update_status_bar()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Search / Quick Filter Bar
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 Filter:"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search by filename, title, artist, or album...")
        self.txt_search.textChanged.connect(self._on_search_changed)
        self.txt_search.setClearButtonEnabled(True)
        search_row.addWidget(self.txt_search, 1)
        main_layout.addLayout(search_row)

        # Main horizontal splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: File Table
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.horizontalHeader().setStretchLastSection(True)

        # Set default column widths
        for col_idx, (name, width) in enumerate(COLUMNS):
            self.table_view.setColumnWidth(col_idx, width)

        self.table_view.setEditTriggers(
            QTableView.EditTrigger.DoubleClicked |
            QTableView.EditTrigger.EditKeyPressed |
            QTableView.EditTrigger.SelectedClicked
        )

        self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table_model.item_edited.connect(self._on_table_item_edited)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_table_context_menu)
        self.main_splitter.addWidget(self.table_view)

        # Right side: Inspector Panel (vertical splitter for Tag Editor + Thumbnail Panel)
        self.inspector_splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.tag_editor = TagEditorPanel()
        self.tag_editor.tags_applied.connect(self._on_tags_applied)
        self.tag_editor.save_requested.connect(self.save_selected)
        self.tag_editor.revert_requested.connect(self.revert_selected)
        self.inspector_splitter.addWidget(self.tag_editor)

        self.thumbnail_panel = ThumbnailPanel()
        self.thumbnail_panel.cover_updated.connect(self._on_cover_updated)
        self.thumbnail_panel.fetch_online_requested.connect(self.open_online_fetcher)
        self.inspector_splitter.addWidget(self.thumbnail_panel)

        self.inspector_splitter.setStretchFactor(0, 3)
        self.inspector_splitter.setStretchFactor(1, 2)

        self.main_splitter.addWidget(self.inspector_splitter)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)

        main_layout.addWidget(self.main_splitter, 1)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _create_actions_and_menus(self):
        # Menu Bar
        menu_bar = self.menuBar()

        # --- File Menu ---
        file_menu = menu_bar.addMenu("&File")

        act_add_files = QAction("📁 Add Files...", self)
        act_add_files.setShortcut(QKeySequence.StandardKey.Open)
        act_add_files.triggered.connect(self.add_files_dialog)
        file_menu.addAction(act_add_files)

        act_add_folder = QAction("📂 Add Folder...", self)
        act_add_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_add_folder.triggered.connect(self.add_folder_dialog)
        file_menu.addAction(act_add_folder)

        file_menu.addSeparator()

        self.act_save_sel = QAction("💾 Save Selected", self)
        self.act_save_sel.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save_sel.triggered.connect(self.save_selected)
        file_menu.addAction(self.act_save_sel)

        self.act_save_all = QAction("💾 Save All Modified", self)
        self.act_save_all.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_all.triggered.connect(self.save_all)
        file_menu.addAction(self.act_save_all)

        file_menu.addSeparator()

        act_remove_sel = QAction("🗑️ Remove Selected from List", self)
        act_remove_sel.setShortcut(QKeySequence("Del"))
        act_remove_sel.triggered.connect(self.remove_selected)
        file_menu.addAction(act_remove_sel)

        act_clear_all = QAction("🧹 Clear List", self)
        act_clear_all.triggered.connect(self.clear_all)
        file_menu.addAction(act_clear_all)

        file_menu.addSeparator()

        act_exit = QAction("Exit", self)
        act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # --- Tools Menu ---
        tools_menu = menu_bar.addMenu("&Tools")

        act_rename = QAction("✏️ Batch Rename Files...", self)
        act_rename.setShortcut(QKeySequence("Ctrl+R"))
        act_rename.triggered.connect(self.open_rename_dialog)
        tools_menu.addAction(act_rename)

        act_fetch_online = QAction("🌐 Fetch Movie/TV Info (TMDb / IMDb)...", self)
        act_fetch_online.setShortcut(QKeySequence("Ctrl+F"))
        act_fetch_online.triggered.connect(self.open_online_fetcher)
        tools_menu.addAction(act_fetch_online)

        act_autonum = QAction("🔢 Auto-Number Tracks (1..N)", self)
        act_autonum.triggered.connect(self.auto_number_tracks)
        tools_menu.addAction(act_autonum)

        act_guess_tags = QAction("🏷️ Guess Tags from Filename (Artist - Title)", self)
        act_guess_tags.triggered.connect(self.guess_tags_from_filename)
        tools_menu.addAction(act_guess_tags)

        # --- Audio Superpowers Menu ---
        audio_menu = menu_bar.addMenu("&Audio")

        self.act_music_fetch = QAction("🎨 Fetch Album Art & Tags (iTunes / Deezer / Discogs)...", self)
        self.act_music_fetch.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.act_music_fetch.triggered.connect(self.open_music_fetcher)
        audio_menu.addAction(self.act_music_fetch)

        self.act_acoustic_id = QAction("🎵 Identify Track (Acoustic ID)...", self)
        self.act_acoustic_id.setShortcut(QKeySequence("Ctrl+I"))
        self.act_acoustic_id.triggered.connect(self.open_acoustic_id)
        audio_menu.addAction(self.act_acoustic_id)

        self.act_lyrics = QAction("🎤 Download Lyrics (LRCLIB)...", self)
        self.act_lyrics.setShortcut(QKeySequence("Ctrl+L"))
        self.act_lyrics.triggered.connect(self.open_lyrics_dialog)
        audio_menu.addAction(self.act_lyrics)

        self.act_replay_gain = QAction("🔊 Scan ReplayGain (EBU R128)...", self)
        self.act_replay_gain.setShortcut(QKeySequence("Ctrl+G"))
        self.act_replay_gain.triggered.connect(self.open_replay_gain)
        audio_menu.addAction(self.act_replay_gain)

        # --- Help Menu ---
        help_menu = menu_bar.addMenu("&Help")
        act_about = QAction("About FileTagger", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

        # --- Toolbar ---
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction(act_add_files)
        toolbar.addAction(act_add_folder)
        toolbar.addSeparator()
        toolbar.addAction(self.act_save_sel)
        toolbar.addAction(act_remove_sel)
        toolbar.addSeparator()
        toolbar.addAction(self.act_music_fetch)
        toolbar.addAction(self.act_acoustic_id)
        toolbar.addAction(self.act_lyrics)
        toolbar.addAction(self.act_replay_gain)
        toolbar.addSeparator()
        toolbar.addAction(act_fetch_online)
        toolbar.addAction(act_rename)
        toolbar.addAction(act_autonum)

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

    def load_paths(self, paths: List[str]):
        if getattr(self, "_is_loading", False):
            return

        all_files: List[str] = []
        for path in paths:
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    all_files.append(path)
            elif os.path.isdir(path):
                for root, _, filenames in os.walk(path):
                    for fname in filenames:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            all_files.append(os.path.join(root, fname))

        if not all_files:
            return

        # Avoid duplicates
        existing_paths = {item.file_path for item in self.table_model.items}
        new_files = [f for f in all_files if f not in existing_paths]

        if not new_files:
            return

        self._is_loading = True
        try:
            progress = QProgressDialog("Reading metadata and covers...", "Cancel", 0, len(new_files), self)
            progress.setWindowModality(Qt.WindowModality.ApplicationModal)
            progress.setMinimumDuration(200)

            items_to_add: List[MediaItem] = []
            for i, fpath in enumerate(new_files):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                progress.setLabelText(f"Reading ({i+1}/{len(new_files)}): {os.path.basename(fpath)}")
                QApplication.processEvents()

                item = read_media_item(fpath)
                items_to_add.append(item)

            progress.setValue(len(new_files))
            self.table_model.add_items(items_to_add)
            self._update_status_bar()
        finally:
            self._is_loading = False

    # ---------------------------------------------------------
    # Selection & Editing
    # ---------------------------------------------------------
    def _get_selected_source_rows(self) -> List[int]:
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

    def _get_selected_items(self) -> List[MediaItem]:
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
    def save_selected(self):
        items = self._get_selected_items()
        if not items:
            return

        saved_count = 0
        error_items = []
        for item in items:
            if item.is_dirty:
                if save_media_item(item):
                    saved_count += 1
                else:
                    error_items.append((item.file_name, item.error))

        self.table_model.notify_all_changed()
        self._update_status_bar()

        if error_items:
            err_msg = "\n".join([f"• {name}: {err}" for name, err in error_items[:5]])
            QMessageBox.warning(self, "Save Incomplete", f"Saved {saved_count} files.\n\nErrors encountered:\n{err_msg}")
        else:
            self.status_bar.showMessage(f"Successfully saved {saved_count} file(s).", 4000)

    def save_all(self):
        dirty_items = [it for it in self.table_model.items if it.is_dirty]
        if not dirty_items:
            QMessageBox.information(self, "No Changes", "There are no modified files to save.")
            return

        saved_count = 0
        error_items = []
        for item in dirty_items:
            if save_media_item(item):
                saved_count += 1
            else:
                error_items.append((item.file_name, item.error))

        self.table_model.notify_all_changed()
        self._update_status_bar()
        if error_items:
            err_msg = "\n".join([f"• {name}: {err}" for name, err in error_items[:5]])
            QMessageBox.warning(self, "Save Incomplete", f"Saved {saved_count} files.\n\nErrors encountered:\n{err_msg}")
        else:
            self.status_bar.showMessage(f"Saved {saved_count} modified file(s).", 4000)

    def revert_selected(self):
        items = self._get_selected_items()
        for item in items:
            item.revert()

        self._on_selection_changed()
        self.table_model.notify_all_changed()
        self._update_status_bar()

    def remove_selected(self):
        rows = self._get_selected_source_rows()
        if not rows:
            return
        self.table_model.remove_rows(rows)
        self._on_selection_changed()
        self._update_status_bar()

    def clear_all(self):
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
        items = self._get_selected_items() or self.table_model.items
        if not items:
            return
        total = len(items)
        for i, item in enumerate(items, 1):
            item.tags["track_number"] = f"{i}/{total}"
        self.table_model.notify_all_changed()
        self._on_selection_changed()
        self.status_bar.showMessage(f"Auto-numbered {total} tracks.", 3000)

    def guess_tags_from_filename(self):
        items = self._get_selected_items() or self.table_model.items
        if not items:
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

        self.table_model.notify_all_changed()
        self._on_selection_changed()
        self.status_bar.showMessage(f"Extracted tags for {updated} files.", 3000)

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
            self.status_bar.showMessage(f"Applied online metadata for '{res.title}' ({res.year}). Press Ctrl+S to save.", 5000)

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
            self.status_bar.showMessage(f"Applied album art & metadata for '{res.album}' by {res.artist}. Press Ctrl+S to save.", 5000)

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
        act_rename = QAction("✏️ Batch Rename Files...", self)
        act_rename.triggered.connect(self.open_rename_dialog)
        menu.addAction(act_rename)
        act_fetch = QAction("🌐 Fetch Movie/TV Info (TMDb / IMDb)...", self)
        act_fetch.triggered.connect(self.open_online_fetcher)
        menu.addAction(act_fetch)
        menu.addSeparator()
        menu.addAction(self.act_save_sel)
        act_rem = QAction("🗑️ Remove from List", self)
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
            self.status_bar.showMessage(f"ReplayGain loudness tags calculated for {len(items)} file(s). Press Ctrl+S to save.", 5000)

    # ---------------------------------------------------------
    # Status Bar
    # ---------------------------------------------------------
    def _update_status_bar(self):
        total = len(self.table_model.items)
        selected = len(self._get_selected_source_rows())
        dirty = sum(1 for it in self.table_model.items if it.is_dirty)

        text = f"Total: {total} files | Selected: {selected}"
        if dirty > 0:
            text += f" | ⚠️ {dirty} file(s) unsaved"
        self.status_bar.showMessage(text)

    def _show_about(self):
        QMessageBox.about(
            self,
            "About FileTagger",
            "<h3>FileTagger</h3>"
            "<p>A powerful audio and video metadata tagger with interactive video thumbnail extraction.</p>"
            "<p><b>Supported formats:</b> MP3, FLAC, MP4, M4A, MKV, OGG, Opus, WAV, and more.</p>"
            "<hr>"
            "<p style='color: gray; font-size: 11px;'>This product uses the TMDB API but is not endorsed or certified by TMDB.</p>"
        )

    def closeEvent(self, event):
        dirty_count = sum(1 for it in self.table_model.items if it.is_dirty)
        if dirty_count > 0:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have {dirty_count} file(s) with unsaved metadata changes.\nDo you want to save them before exiting?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
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

