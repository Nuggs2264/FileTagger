import os
import threading
from typing import Optional
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QTabWidget, QCheckBox,
    QProgressBar, QMessageBox, QGroupBox
)

from core.media_item import MediaItem
from core.lyrics_fetcher import fetch_lyrics, save_lrc_file, LyricsResult

class LyricsWorkerSignals(QObject):
    finished_lyrics = Signal(int, object)
    error_occurred = Signal(int, str)

class LyricsDialog(QDialog):
    def __init__(self, item: MediaItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.lyrics_result: Optional[LyricsResult] = None
        self.applied = False
        self._request_id = 0

        self.setWindowTitle("Synchronized Lyrics Downloader (LRCLIB)")
        self.resize(700, 540)
        self._init_ui()
        self._start_fetch()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Search Controls
        search_group = QGroupBox("Track Metadata Query")
        search_layout = QHBoxLayout(search_group)
        search_layout.setSpacing(8)

        self.txt_title = QLineEdit(self.item.tags.get("title", ""))
        self.txt_title.setPlaceholderText("Title")
        search_layout.addWidget(QLabel("Title:"))
        search_layout.addWidget(self.txt_title, 2)

        self.txt_artist = QLineEdit(self.item.tags.get("artist", ""))
        self.txt_artist.setPlaceholderText("Artist")
        search_layout.addWidget(QLabel("Artist:"))
        search_layout.addWidget(self.txt_artist, 2)

        self.txt_album = QLineEdit(self.item.tags.get("album", ""))
        self.txt_album.setPlaceholderText("Album (optional)")
        search_layout.addWidget(QLabel("Album:"))
        search_layout.addWidget(self.txt_album, 1)

        self.btn_search = QPushButton("🔍 Fetch")
        self.btn_search.setStyleSheet("font-weight: bold; padding: 5px 14px;")
        self.btn_search.clicked.connect(self._start_fetch)
        search_layout.addWidget(self.btn_search)

        layout.addWidget(search_group)

        # Status & Progress
        self.status_label = QLabel("Searching LRCLIB for synchronized lyrics...")
        self.status_label.setStyleSheet("color: #38bdf8; font-size: 9pt;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        # Tabs for Synced & Plain Lyrics
        self.tabs = QTabWidget()
        
        self.txt_synced = QTextEdit()
        self.txt_synced.setPlaceholderText("Timestamped lyrics [mm:ss.xx] will appear here...")
        self.txt_synced.setStyleSheet("font-family: Consolas, monospace; font-size: 9.5pt;")
        self.tabs.addTab(self.txt_synced, "⏱️ Synchronized (.lrc)")

        self.txt_plain = QTextEdit()
        self.txt_plain.setPlaceholderText("Plain lyrics text will appear here...")
        self.txt_plain.setStyleSheet("font-size: 9.5pt;")
        self.tabs.addTab(self.txt_plain, "📄 Plain Lyrics")

        layout.addWidget(self.tabs, 1)

        # Storage Options Group
        opts_group = QGroupBox("Save && Storage Options")
        opts_layout = QHBoxLayout(opts_group)
        opts_layout.setSpacing(14)

        self.chk_embed = QCheckBox("Embed lyrics directly into audio tag (USLT / \u00a9lyr / LYRICS)")
        self.chk_embed.setChecked(True)
        opts_layout.addWidget(self.chk_embed)

        self.chk_save_lrc = QCheckBox("Save as .lrc file alongside audio")
        self.chk_save_lrc.setChecked(True)
        opts_layout.addWidget(self.chk_save_lrc)

        opts_layout.addStretch()
        layout.addWidget(opts_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Apply Lyrics")
        self.btn_apply.setStyleSheet("font-weight: bold; padding: 7px 20px;")
        self.btn_apply.clicked.connect(self._apply_lyrics)
        btn_row.addWidget(self.btn_apply)

        layout.addLayout(btn_row)

    def _start_fetch(self):
        self._request_id += 1
        req_id = self._request_id

        title = self.txt_title.text().strip() or self.item.file_name
        artist = self.txt_artist.text().strip()
        album = self.txt_album.text().strip()

        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Querying LRCLIB for '{title}'...")
        self.status_label.setStyleSheet("color: #38bdf8; font-size: 9pt;")
        self.btn_search.setEnabled(False)

        signals = LyricsWorkerSignals(self)
        signals.finished_lyrics.connect(self._on_lyrics_ready)
        signals.error_occurred.connect(self._on_fetch_error)
        self.signals = signals

        duration = self.item.duration
        def _fetch_target():
            try:
                res = fetch_lyrics(title, artist, album, duration)
                try:
                    signals.finished_lyrics.emit(req_id, res)
                except RuntimeError:
                    pass
            except Exception as e:
                try:
                    signals.error_occurred.emit(req_id, str(e))
                except RuntimeError:
                    pass

        t = threading.Thread(target=_fetch_target, daemon=True)
        t.start()

    def _on_lyrics_ready(self, req_id: int, result: Optional[LyricsResult]):
        if req_id != self._request_id:
            return
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        self.lyrics_result = result

        if not result:
            self.status_label.setText("No lyrics found for this track on LRCLIB.")
            self.status_label.setStyleSheet("color: #f87171; font-size: 9pt;")
            return

        self.txt_synced.setPlainText(result.synced_lyrics)
        self.txt_plain.setPlainText(result.plain_lyrics)

        if result.is_synced:
            self.status_label.setText("✓ Synchronized karaoke lyrics found!")
            self.status_label.setStyleSheet("color: #4ade80; font-size: 9pt; font-weight: bold;")
            self.tabs.setCurrentIndex(0)
        else:
            self.status_label.setText("✓ Plain lyrics found (unsynchronized).")
            self.status_label.setStyleSheet("color: #fbbf24; font-size: 9pt;")
            self.tabs.setCurrentIndex(1)

    def _on_fetch_error(self, req_id: int, err_msg: str):
        if req_id != self._request_id:
            return
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        self.status_label.setText(f"Fetch error: {err_msg}")
        self.status_label.setStyleSheet("color: #ef4444; font-size: 9pt;")

    def _apply_lyrics(self):
        synced_text = self.txt_synced.toPlainText().strip()
        plain_text = self.txt_plain.toPlainText().strip()
        lyrics_to_save = synced_text or plain_text

        if not lyrics_to_save:
            QMessageBox.information(self, "No Lyrics", "No lyrics text to apply.")
            return

        # 1. Embed in tags
        if self.chk_embed.isChecked():
            # Store lyrics in extra_tags under 'lyrics'
            self.item.extra_tags["lyrics"] = lyrics_to_save
            self.item.mark_dirty()

        # 2. Save .lrc file alongside audio
        if self.chk_save_lrc.isChecked() and lyrics_to_save:
            try:
                lrc_path = save_lrc_file(self.item.file_path, lyrics_to_save)
                QMessageBox.information(
                    self,
                    "Saved",
                    f"Lyrics saved to:\n{os.path.basename(lrc_path)}"
                )
            except Exception as e:
                QMessageBox.warning(self, "LRC File Error", f"Failed to save .lrc file:\n{e}")

        self.applied = True
        self.accept()
