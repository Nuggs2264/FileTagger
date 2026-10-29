import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.media_item import MediaItem
from core.replay_gain import (
    apply_replaygain_tags,
    format_replaygain_album,
    format_replaygain_track,
    scan_track_loudness,
)


class ReplayGainWorkerSignals(QObject):
    track_scanned = Signal(int, str, float, float, str, str)  # idx, path, lufs, peak_db, gain, peak
    all_scanned = Signal(str, str)  # album_gain, album_peak
    progress_updated = Signal(int, int, str)  # current, total, name
    error_occurred = Signal(str, str)  # filename, error


class ReplayGainDialog(QDialog):
    def __init__(self, items: list[MediaItem], parent=None):
        super().__init__(parent)
        self.items = items
        self.track_results: dict[int, tuple[str, str]] = {}  # idx -> (track_gain, track_peak)
        self.album_gain: str = ""
        self.album_peak: str = ""
        self.applied = False
        self._is_cancelled = False
        self._active_procs: list = []

        self.setWindowTitle("ReplayGain / Loudness Normalization Scanner (EBU R128)")
        self.resize(780, 500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Mode Selection
        mode_group = QGroupBox("Scan Mode")
        mode_layout = QHBoxLayout(mode_group)
        self.rb_album = QRadioButton("Calculate Track + Album Gain (Recommended for full albums)")
        self.rb_album.setChecked(len(self.items) > 1)
        self.rb_track = QRadioButton("Track Gain only (Individual songs)")
        self.rb_track.setChecked(len(self.items) <= 1)
        mode_layout.addWidget(self.rb_album)
        mode_layout.addWidget(self.rb_track)
        mode_layout.addStretch()
        layout.addWidget(mode_group)

        # Status & Progress
        self.status_label = QLabel(f"Ready to scan {len(self.items)} file(s)...")
        self.status_label.setStyleSheet("color: #38bdf8; font-size: 9pt;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.items))
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Results Table
        self.table = QTableWidget(len(self.items), 6)
        self.table.setHorizontalHeaderLabels(
            ["File", "Loudness (LUFS)", "True Peak (dBFS)", "Track Gain", "Track Peak", "Album Gain"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for row, item in enumerate(self.items):
            self.table.setItem(row, 0, QTableWidgetItem(item.file_name))
            self.table.setItem(row, 1, QTableWidgetItem("Waiting..."))
            self.table.setItem(row, 2, QTableWidgetItem("Waiting..."))
            self.table.setItem(row, 3, QTableWidgetItem("Waiting..."))
            self.table.setItem(row, 4, QTableWidgetItem("Waiting..."))
            self.table.setItem(row, 5, QTableWidgetItem("Waiting..."))

        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        # Album Summary Label
        self.album_label = QLabel("Album Summary: Not calculated yet")
        self.album_label.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 9pt;")
        layout.addWidget(self.album_label)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start Analysis")
        self.btn_start.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_start.clicked.connect(self._start_scan)
        btn_row.addWidget(self.btn_start)

        btn_row.addStretch()

        self.btn_cancel = QPushButton("Close")
        self.btn_cancel.clicked.connect(self._on_close)
        btn_row.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Apply ReplayGain Tags")
        self.btn_apply.setStyleSheet("font-weight: bold; padding: 7px 20px;")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_tags)
        btn_row.addWidget(self.btn_apply)

        layout.addLayout(btn_row)

    def _start_scan(self):
        self.btn_start.setEnabled(False)
        self.rb_album.setEnabled(False)
        self.rb_track.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self._is_cancelled = False

        signals = ReplayGainWorkerSignals(self)
        signals.track_scanned.connect(self._on_track_scanned)
        signals.all_scanned.connect(self._on_all_scanned)
        signals.progress_updated.connect(self._on_progress)
        signals.error_occurred.connect(self._on_error)
        self.signals = signals

        items_copy = list(self.items)
        scan_album = self.rb_album.isChecked()

        def _scan_worker():
            total = len(items_copy)
            track_scans: list[tuple[float, float, float]] = []

            for idx, item in enumerate(items_copy):
                if self._is_cancelled:
                    return

                try:
                    signals.progress_updated.emit(idx + 1, total, item.file_name)
                except RuntimeError:
                    return

                try:
                    lufs, true_peak, dur = scan_track_loudness(item.file_path, self._active_procs)
                    if self._is_cancelled:
                        return
                    track_gain, track_peak = format_replaygain_track(lufs, true_peak)
                    track_scans.append((lufs, true_peak, dur))
                    try:
                        signals.track_scanned.emit(idx, item.file_path, lufs, true_peak, track_gain, track_peak)
                    except RuntimeError:
                        return
                except Exception as e:
                    if self._is_cancelled:
                        return
                    try:
                        signals.error_occurred.emit(item.file_name, str(e))
                    except RuntimeError:
                        return
                    track_scans.append((-18.0, 0.0, 0.0))

            if scan_album and len(track_scans) > 0 and not self._is_cancelled:
                album_gain, album_peak = format_replaygain_album(track_scans)
                try:
                    signals.all_scanned.emit(album_gain, album_peak)
                except RuntimeError:
                    return
            elif not self._is_cancelled:
                try:
                    signals.all_scanned.emit("", "")
                except RuntimeError:
                    return

        t = threading.Thread(target=_scan_worker, daemon=True)
        t.start()

    def _on_progress(self, current: int, total: int, filename: str):
        if self._is_cancelled:
            return
        self.progress_bar.setValue(current - 1)
        self.status_label.setText(f"Scanning ({current}/{total}): {filename}...")

    def _on_track_scanned(self, idx: int, path: str, lufs: float, peak_db: float, gain: str, peak: str):
        if self._is_cancelled:
            return
        self.track_results[idx] = (gain, peak)
        self.table.setItem(idx, 1, QTableWidgetItem(f"{lufs:.2f} LUFS"))
        self.table.setItem(idx, 2, QTableWidgetItem(f"{peak_db:.2f} dBFS"))

        gain_item = QTableWidgetItem(gain)
        gain_item.setForeground(Qt.GlobalColor.cyan)
        self.table.setItem(idx, 3, gain_item)

        self.table.setItem(idx, 4, QTableWidgetItem(peak))

    def _on_all_scanned(self, album_gain: str, album_peak: str):
        if self._is_cancelled:
            return
        self.progress_bar.setValue(len(self.items))
        self.status_label.setText("✓ Loudness analysis complete!")
        self.status_label.setStyleSheet("color: #4ade80; font-size: 9pt; font-weight: bold;")
        self.album_gain = album_gain
        self.album_peak = album_peak

        if album_gain:
            for row in range(len(self.items)):
                item_ag = QTableWidgetItem(album_gain)
                item_ag.setForeground(Qt.GlobalColor.green)
                self.table.setItem(row, 5, item_ag)
            self.album_label.setText(f"Album Summary: Gain {album_gain} | Peak {album_peak}")
            self.album_label.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 9.5pt;")
        else:
            self.album_label.setText("Album Gain not requested (Track Gain only).")

        self.btn_apply.setEnabled(True)
        self.btn_start.setEnabled(True)

    def _on_error(self, filename: str, err: str):
        if self._is_cancelled:
            return
        QMessageBox.warning(self, "Scan Warning", f"Could not analyze {filename}:\n{err}")

    def _apply_tags(self):
        for idx, item in enumerate(self.items):
            if idx in self.track_results:
                tg, tp = self.track_results[idx]
                ag = self.album_gain if self.album_gain else None
                ap = self.album_peak if self.album_peak else None
                apply_replaygain_tags(item, tg, tp, ag, ap)

        self.applied = True
        QMessageBox.information(
            self,
            "ReplayGain Applied",
            f"Successfully applied ReplayGain tags to {len(self.track_results)} file(s)!\n"
            "Press 'Save Changes' or Ctrl+S to write tags to disk.",
        )
        self.accept()

    def _cancel_active_scan(self):
        self._is_cancelled = True
        for proc in list(self._active_procs):
            try:
                proc.terminate()
            except Exception:
                pass

    def _on_close(self):
        self._cancel_active_scan()
        self.reject()

    def closeEvent(self, event):
        self._cancel_active_scan()
        super().closeEvent(event)
