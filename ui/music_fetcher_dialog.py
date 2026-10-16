import html
import threading
from typing import List, Optional, Dict
from PySide6.QtCore import Qt, QObject, Signal, QSettings
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QCheckBox, QSplitter, QTextEdit, QFrame,
    QProgressBar, QMessageBox
)
from PySide6.QtGui import QPixmap

from core.music_online_fetcher import (
    MusicSearchResult, search_all_music_sources, search_itunes,
    search_deezer, search_musicbrainz_coverart, search_discogs,
    download_music_image_bytes, clean_query_text
)
from core.tagger import normalize_cover_image
from core.secure_storage import encrypt_secret, decrypt_secret

class MusicSearchSignals(QObject):
    results_ready = Signal(int, list)
    error_occurred = Signal(int, str)

class MusicImageSignals(QObject):
    image_ready = Signal(int, bytes)

class MusicFetcherDialog(QDialog):
    def __init__(self, initial_query: str = "", parent=None):
        super().__init__(parent)
        self.settings = QSettings("FileTagger", "FileTagger")
        self.initial_query = clean_query_text(initial_query)
        self.search_results: List[MusicSearchResult] = []
        self.selected_result: Optional[MusicSearchResult] = None
        self.downloaded_cover_bytes: Optional[bytes] = None
        self._search_req_id = 0
        self._img_req_id = 0

        self.setWindowTitle("Online Music Album Art & Metadata Fetcher (iTunes / Deezer / MusicBrainz / Discogs)")
        self.resize(920, 640)
        self._init_ui()

        if self.initial_query:
            self._start_search()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Search Bar Row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        search_row.addWidget(QLabel("Search Query:"))
        self.txt_query = QLineEdit(self.initial_query)
        self.txt_query.setPlaceholderText("Enter artist, album, or track title (e.g. Shaggy - Hot Shot)...")
        self.txt_query.returnPressed.connect(self._start_search)
        search_row.addWidget(self.txt_query, 1)

        self.cmb_engine = QComboBox()
        self.cmb_engine.addItems([
            "🎵 All Sources (iTunes, Deezer, MusicBrainz)",
            "🍎 iTunes / Apple Music (Hi-Res 1400x1400)",
            "🎧 Deezer (1000x1000 Artwork)",
            "🧠 MusicBrainz & Cover Art Archive",
            "💿 Discogs (Vinyl & CD Database)"
        ])
        saved_engine = self.settings.value("music_search_engine", "🎵 All Sources (iTunes, Deezer, MusicBrainz)")
        idx = self.cmb_engine.findText(saved_engine)
        if idx >= 0:
            self.cmb_engine.setCurrentIndex(idx)
        self.cmb_engine.currentTextChanged.connect(self._on_engine_changed)
        search_row.addWidget(self.cmb_engine)

        self.btn_search = QPushButton("🔍 Search")
        self.btn_search.setObjectName("PrimaryButton")
        self.btn_search.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_search.clicked.connect(self._start_search)
        search_row.addWidget(self.btn_search)

        layout.addLayout(search_row)

        # Optional Discogs Token Row (visible when Discogs is selected)
        self.discogs_row = QHBoxLayout()
        self.discogs_row.addWidget(QLabel("Discogs Personal Token:"))
        saved_token = decrypt_secret(str(self.settings.value("discogs_token", "")).strip())
        self.txt_discogs_token = QLineEdit(saved_token)
        self.txt_discogs_token.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.txt_discogs_token.setPlaceholderText("Enter Discogs Personal Access Token (from discogs.com/settings/developers)...")
        self.txt_discogs_token.textChanged.connect(lambda t: self.settings.setValue("discogs_token", encrypt_secret(t.strip())))
        self.discogs_row.addWidget(self.txt_discogs_token, 1)
        self.discogs_container = QFrame()
        self.discogs_container.setLayout(self.discogs_row)
        self.discogs_container.setVisible("Discogs" in self.cmb_engine.currentText())
        layout.addWidget(self.discogs_container)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Main splitter (Results Table on Left, Album Art & Detail Preview on Right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Results table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        left_layout.addWidget(QLabel("Search Results:"))
        self.table_results = QTableWidget(0, 6)
        self.table_results.setHorizontalHeaderLabels(["Source", "Album / Release", "Artist", "Year", "Tracks", "Genre"])
        self.table_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table_results.setColumnWidth(0, 85)
        self.table_results.setColumnWidth(2, 140)
        self.table_results.setColumnWidth(3, 50)
        self.table_results.setColumnWidth(4, 55)
        self.table_results.setColumnWidth(5, 80)
        self.table_results.verticalHeader().setVisible(False)
        self.table_results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_results.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_results.itemSelectionChanged.connect(self._on_result_selected)
        left_layout.addWidget(self.table_results, 1)

        splitter.addWidget(left_widget)

        # Right: Rich Detail / Album Art Preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(8)

        right_layout.addWidget(QLabel("Album Art && Metadata Preview:"))

        # Art Box
        self.art_preview = QLabel("No album selected")
        self.art_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_preview.setMinimumSize(250, 250)
        self.art_preview.setMaximumSize(320, 320)
        self.art_preview.setStyleSheet("""
            QLabel {
                background-color: #18181f;
                border: 2px dashed #2d2d3d;
                border-radius: 8px;
                color: #64748b;
                font-size: 10pt;
            }
        """)
        right_layout.addWidget(self.art_preview, 0, Qt.AlignmentFlag.AlignCenter)

        # Resolution & Size info label
        self.art_info_label = QLabel("")
        self.art_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_info_label.setStyleSheet("color: #94a3b8; font-size: 8.5pt;")
        right_layout.addWidget(self.art_info_label)

        # Metadata Card
        self.txt_details = QTextEdit()
        self.txt_details.setReadOnly(True)
        self.txt_details.setStyleSheet("background-color: #18181f; border: 1px solid #262632; border-radius: 6px; font-size: 9pt;")
        right_layout.addWidget(self.txt_details, 1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        # Bottom Bar: Checkboxes & Actions
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        bottom_bar.addWidget(QLabel("Apply:"))
        self.chk_cover = QCheckBox("Album Cover Art")
        self.chk_cover.setChecked(True)
        bottom_bar.addWidget(self.chk_cover)

        self.chk_album = QCheckBox("Album")
        self.chk_album.setChecked(True)
        bottom_bar.addWidget(self.chk_album)

        self.chk_artist = QCheckBox("Artist")
        self.chk_artist.setChecked(True)
        bottom_bar.addWidget(self.chk_artist)

        self.chk_year = QCheckBox("Year")
        self.chk_year.setChecked(True)
        bottom_bar.addWidget(self.chk_year)

        self.chk_genre = QCheckBox("Genre")
        self.chk_genre.setChecked(True)
        bottom_bar.addWidget(self.chk_genre)

        bottom_bar.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_bar.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Apply to Selected Files")
        self.btn_apply.setObjectName("PrimaryButton")
        self.btn_apply.setStyleSheet("font-weight: bold; padding: 7px 20px;")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_metadata)
        bottom_bar.addWidget(self.btn_apply)

        layout.addLayout(bottom_bar)

    def _on_engine_changed(self, text: str):
        self.settings.setValue("music_search_engine", text)
        self.discogs_container.setVisible("Discogs" in text)

    def _start_search(self):
        query = self.txt_query.text().strip()
        if not query:
            return

        self._search_req_id += 1
        req_id = self._search_req_id

        self.btn_search.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.btn_apply.setEnabled(False)
        self.art_preview.setText("Searching databases...")
        self.art_info_label.setText("")
        self.txt_details.clear()
        self.downloaded_cover_bytes = None

        engine = self.cmb_engine.currentText()
        discogs_tok = self.txt_discogs_token.text().strip()

        signals = MusicSearchSignals(self)
        signals.results_ready.connect(self._on_results_ready)
        signals.error_occurred.connect(self._on_search_error)
        self.search_signals = signals

        def _worker():
            try:
                if "iTunes" in engine:
                    res = search_itunes(query)
                elif "Deezer" in engine:
                    res = search_deezer(query)
                elif "MusicBrainz" in engine:
                    res = search_musicbrainz_coverart(query)
                elif "Discogs" in engine:
                    res = search_discogs(query, token=discogs_tok)
                else:
                    res = search_all_music_sources(query, discogs_token=discogs_tok)
                try:
                    signals.results_ready.emit(req_id, res)
                except RuntimeError:
                    pass
            except Exception as e:
                try:
                    signals.error_occurred.emit(req_id, str(e))
                except RuntimeError:
                    pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_results_ready(self, req_id: int, results: List[MusicSearchResult]):
        if req_id != self._search_req_id:
            return
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        self.search_results = results
        self.table_results.setRowCount(0)

        if not results:
            self.art_preview.setText("No results found.\nTry a broader search query.")
            return

        self.table_results.setRowCount(len(results))
        for row, res in enumerate(results):
            self.table_results.setItem(row, 0, QTableWidgetItem(res.source))
            self.table_results.setItem(row, 1, QTableWidgetItem(res.album))
            self.table_results.setItem(row, 2, QTableWidgetItem(res.artist))
            self.table_results.setItem(row, 3, QTableWidgetItem(res.year))
            self.table_results.setItem(row, 4, QTableWidgetItem(str(res.track_count) if res.track_count else ""))
            self.table_results.setItem(row, 5, QTableWidgetItem(res.genre))

        self.table_results.selectRow(0)

    def _on_search_error(self, req_id: int, err: str):
        if req_id != self._search_req_id:
            return
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        QMessageBox.warning(self, "Search Error", f"Search failed:\n{err}")

    def _on_result_selected(self):
        row = self.table_results.currentRow()
        if row < 0 or row >= len(self.search_results):
            self.btn_apply.setEnabled(False)
            return

        self.selected_result = self.search_results[row]
        res = self.selected_result

        # Details text (HTML-escaped against untrusted API metadata)
        details = f"<h3>{html.escape(res.album)}</h3>"
        details += f"<p><b>Artist:</b> {html.escape(res.artist)}<br>"
        if res.year:
            details += f"<b>Release Year:</b> {html.escape(res.year)}<br>"
        if res.genre:
            details += f"<b>Genre:</b> {html.escape(res.genre)}<br>"
        if res.track_count:
            details += f"<b>Track Count:</b> {int(res.track_count)}<br>"
        details += f"<b>Source:</b> {html.escape(res.source)}</p>"
        self.txt_details.setHtml(details)

        # Download cover art if available
        if res.cover_url:
            self._img_req_id += 1
            img_req_id = self._img_req_id

            self.art_preview.setText("Downloading high-res cover art...")
            self.art_info_label.setText("")
            self.downloaded_cover_bytes = None

            img_signals = MusicImageSignals(self)
            img_signals.image_ready.connect(self._on_image_downloaded)
            self.image_signals = img_signals

            cover_url = res.cover_url
            def _img_worker():
                img_data = download_music_image_bytes(cover_url)
                if img_data:
                    try:
                        img_signals.image_ready.emit(img_req_id, img_data)
                    except RuntimeError:
                        pass

            t = threading.Thread(target=_img_worker, daemon=True)
            t.start()
        else:
            self.art_preview.setText("No cover image available")
            self.art_info_label.setText("")
            self.downloaded_cover_bytes = None
            self.btn_apply.setEnabled(True)

    def _on_image_downloaded(self, req_id: int, data: bytes):
        if req_id != self._img_req_id:
            return
        self.downloaded_cover_bytes = data
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            scaled = pixmap.scaled(
                self.art_preview.width() - 8,
                self.art_preview.height() - 8,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.art_preview.setPixmap(scaled)
            size_kb = len(data) / 1024.0
            self.art_info_label.setText(f"Resolution: {pixmap.width()}×{pixmap.height()} | Size: {size_kb:.1f} KB")
        else:
            self.art_preview.setText("Failed to render image")

        self.btn_apply.setEnabled(True)

    def _apply_metadata(self):
        if not self.selected_result:
            return
        self.accept()
