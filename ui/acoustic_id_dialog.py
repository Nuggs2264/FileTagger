import html
import os
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.audio_fingerprint import (
    AudioFingerprintMatch,
    identify_audio_file,
    search_musicbrainz,
)
from core.media_item import MediaItem


class AcousticWorkerSignals(QObject):
    finished_matches = Signal(int, list)
    error_occurred = Signal(int, str)


class AcousticIdDialog(QDialog):
    def __init__(self, item: MediaItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.matches: list[AudioFingerprintMatch] = []
        self.selected_match: AudioFingerprintMatch | None = None
        self.applied = False
        self._request_id = 0

        self.setWindowTitle("Acoustic Fingerprinting & Audio ID (AcoustID / MusicBrainz)")
        self.resize(750, 480)
        self._init_ui()
        self._start_scan()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header info
        header = QLabel(f"<b>File:</b> {html.escape(self.item.file_name)}")
        header.setToolTip(f"Full Path:\n{self.item.file_path}")
        header.setStyleSheet("color: #e2e8f0; font-size: 10pt;")
        layout.addWidget(header)

        # Search Query Bar (for manual refinement or fallback)
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        default_query = ""
        if self.item.tags.get("artist") and self.item.tags.get("title"):
            default_query = f"{self.item.tags['artist']} - {self.item.tags['title']}"
        elif self.item.tags.get("title"):
            default_query = self.item.tags["title"]
        else:
            default_query = os.path.splitext(self.item.file_name)[0]

        self.txt_search = QLineEdit(default_query)
        self.txt_search.setPlaceholderText("Search MusicBrainz (e.g. Artist - Title)...")
        self.txt_search.returnPressed.connect(self._on_manual_search)
        search_row.addWidget(self.txt_search, 1)

        self.btn_search = QPushButton("🔍 Search MusicBrainz")
        self.btn_search.setStyleSheet("font-weight: bold; padding: 5px 14px;")
        self.btn_search.clicked.connect(self._on_manual_search)
        search_row.addWidget(self.btn_search)

        self.btn_rescan = QPushButton("🎵 Re-scan Waveform")
        self.btn_rescan.setToolTip("Re-run audio waveform fingerprinting on this audio file")
        self.btn_rescan.setStyleSheet("padding: 5px 14px;")
        self.btn_rescan.clicked.connect(self._start_scan)
        search_row.addWidget(self.btn_rescan)

        layout.addLayout(search_row)

        # Progress / Status
        self.status_label = QLabel("Computing Chromaprint audio waveform fingerprint...")
        self.status_label.setStyleSheet("color: #38bdf8; font-size: 9pt;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        layout.addWidget(self.progress_bar)

        # Results Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Confidence", "Source", "Title", "Artist", "Album", "Year", "Track", "MBID"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

        # Apply Options Group
        options_group = QGroupBox("Apply Fields to File")
        options_layout = QHBoxLayout(options_group)
        options_layout.setSpacing(14)

        self.chk_title = QCheckBox("Title")
        self.chk_title.setChecked(True)
        options_layout.addWidget(self.chk_title)

        self.chk_artist = QCheckBox("Artist")
        self.chk_artist.setChecked(True)
        options_layout.addWidget(self.chk_artist)

        self.chk_album = QCheckBox("Album")
        self.chk_album.setChecked(True)
        options_layout.addWidget(self.chk_album)

        self.chk_year = QCheckBox("Year")
        self.chk_year.setChecked(True)
        options_layout.addWidget(self.chk_year)

        self.chk_track = QCheckBox("Track #")
        self.chk_track.setChecked(True)
        options_layout.addWidget(self.chk_track)

        self.chk_mbid = QCheckBox("MusicBrainz / AcoustID IDs")
        self.chk_mbid.setChecked(True)
        options_layout.addWidget(self.chk_mbid)

        options_layout.addStretch()
        layout.addWidget(options_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Apply to Track")
        self.btn_apply.setStyleSheet("font-weight: bold; padding: 7px 20px;")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_selected)
        btn_row.addWidget(self.btn_apply)

        layout.addLayout(btn_row)

    def _start_scan(self):
        self._request_id += 1
        req_id = self._request_id

        self.progress_bar.setVisible(True)
        self.status_label.setText("Computing Chromaprint audio fingerprint & querying AcoustID...")
        self.status_label.setStyleSheet("color: #38bdf8; font-size: 9pt;")
        self.btn_search.setEnabled(False)
        self.btn_rescan.setEnabled(False)

        signals = AcousticWorkerSignals(self)
        signals.finished_matches.connect(self._on_matches_ready)
        signals.error_occurred.connect(self._on_scan_error)
        self.signals = signals

        path = self.item.file_path
        fallback_q = self.txt_search.text().strip()

        def _scan_target():
            try:
                res = identify_audio_file(path, fallback_query=fallback_q)
                try:
                    signals.finished_matches.emit(req_id, res)
                except RuntimeError:
                    pass
            except Exception as e:
                try:
                    signals.error_occurred.emit(req_id, str(e))
                except RuntimeError:
                    pass

        t = threading.Thread(target=_scan_target, daemon=True)
        t.start()

    def _on_manual_search(self):
        query = self.txt_search.text().strip()
        if not query:
            return

        self._request_id += 1
        req_id = self._request_id

        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Searching MusicBrainz for '{query}'...")
        self.status_label.setStyleSheet("color: #38bdf8; font-size: 9pt;")
        self.btn_search.setEnabled(False)
        self.btn_rescan.setEnabled(False)

        signals = AcousticWorkerSignals(self)
        signals.finished_matches.connect(self._on_matches_ready)
        signals.error_occurred.connect(self._on_scan_error)
        self.signals = signals

        def _mb_search():
            try:
                res = search_musicbrainz(query)
                try:
                    signals.finished_matches.emit(req_id, res)
                except RuntimeError:
                    pass
            except Exception as e:
                try:
                    signals.error_occurred.emit(req_id, str(e))
                except RuntimeError:
                    pass

        t = threading.Thread(target=_mb_search, daemon=True)
        t.start()

    def _on_matches_ready(self, req_id: int, matches: list[AudioFingerprintMatch]):
        if req_id != self._request_id:
            return
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        self.btn_rescan.setEnabled(True)
        self.matches = matches

        if not matches:
            self.status_label.setText(
                "No matching tracks found. Try searching with a different artist/title query above."
            )
            self.status_label.setStyleSheet("color: #f87171; font-size: 9pt;")
            self.table.setRowCount(0)
            return

        is_waveform = any(m.source.startswith("AcoustID") for m in matches)
        if is_waveform:
            self.status_label.setText(f"✅ Verified audio waveform match via AcoustID ({len(matches)} track(s) found):")
            self.status_label.setStyleSheet("color: #4ade80; font-size: 9pt; font-weight: bold;")
        else:
            search_term = self.txt_search.text().strip()
            self.status_label.setText(
                f"ℹ️ No acoustic waveform match in AcoustID database. Showing MusicBrainz results for '{search_term}' ({len(matches)} match(es)):"
            )
            self.status_label.setStyleSheet("color: #38bdf8; font-size: 9pt;")

        self.table.setRowCount(len(matches))
        for row, m in enumerate(matches):
            conf_str = f"{int(m.score * 100)}%"
            item_conf = QTableWidgetItem(conf_str)
            item_conf.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if m.score >= 0.8:
                item_conf.setForeground(Qt.GlobalColor.green)
            else:
                item_conf.setForeground(Qt.GlobalColor.yellow)

            # Source badge
            src_str = "🎧 AcoustID" if m.source.startswith("AcoustID") else "🔍 MusicBrainz"
            item_src = QTableWidgetItem(src_str)
            item_src.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if m.source.startswith("AcoustID"):
                item_src.setForeground(QColor("#38bdf8"))
            else:
                item_src.setForeground(QColor("#94a3b8"))

            self.table.setItem(row, 0, item_conf)
            self.table.setItem(row, 1, item_src)
            self.table.setItem(row, 2, QTableWidgetItem(m.title))
            self.table.setItem(row, 3, QTableWidgetItem(m.artist))
            self.table.setItem(row, 4, QTableWidgetItem(m.album))
            self.table.setItem(row, 5, QTableWidgetItem(m.year))
            self.table.setItem(row, 6, QTableWidgetItem(m.track_number))
            self.table.setItem(row, 7, QTableWidgetItem(m.recording_id))

        self.table.resizeColumnsToContents()
        self.table.selectRow(0)

    def _on_scan_error(self, req_id: int, err_msg: str):
        if req_id != self._request_id:
            return
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        self.btn_rescan.setEnabled(True)
        self.status_label.setText(f"Audio identification error: {err_msg}")
        self.status_label.setStyleSheet("color: #ef4444; font-size: 9pt;")
        QMessageBox.warning(self, "Acoustic ID Error", f"Failed to identify audio:\n{err_msg}")

    def _on_selection_changed(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.matches):
            self.selected_match = self.matches[row]
            self.btn_apply.setEnabled(True)
        else:
            self.selected_match = None
            self.btn_apply.setEnabled(False)

    def _apply_selected(self):
        if not self.selected_match:
            return

        m = self.selected_match
        if self.chk_title.isChecked() and m.title:
            self.item.tags["title"] = m.title
        if self.chk_artist.isChecked() and m.artist:
            self.item.tags["artist"] = m.artist
        if self.chk_album.isChecked() and m.album:
            self.item.tags["album"] = m.album
        if self.chk_year.isChecked() and m.year:
            self.item.tags["year"] = m.year
        if self.chk_track.isChecked() and m.track_number:
            self.item.tags["track_number"] = m.track_number

        if self.chk_mbid.isChecked():
            if m.recording_id:
                self.item.extra_tags["MUSICBRAINZ_TRACKID"] = m.recording_id
            if m.acoustid_id:
                self.item.extra_tags["ACOUSTID_ID"] = m.acoustid_id

        # Clean up any legacy bloated raw fingerprint if present
        if "ACOUSTID_FINGERPRINT" in self.item.extra_tags:
            del self.item.extra_tags["ACOUSTID_FINGERPRINT"]

        self.item.mark_dirty()
        self.applied = True
        self.accept()
