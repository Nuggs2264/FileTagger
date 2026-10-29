from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from core.ffmpeg_utils import extract_frame_bytes
from ui.icons import get_icon


class FrameExtractWorker(QThread):
    frame_ready = Signal(bytes, float)

    def __init__(self, file_path: str, timestamp: float):
        super().__init__()
        self.file_path = file_path
        self.timestamp = timestamp

    def run(self):
        data = extract_frame_bytes(self.file_path, self.timestamp, max_width=960)
        if data:
            self.frame_ready.emit(data, self.timestamp)


class FrameGrabberDialog(QDialog):
    def __init__(self, file_path: str, duration: float, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.duration = max(duration, 1.0)
        self.current_time = min(5.0, self.duration * 0.1)  # Default 5s or 10%
        self.captured_bytes: bytes | None = None

        self.worker: FrameExtractWorker | None = None
        self._retired_workers: list = []
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(120)  # 120ms debounce
        self.debounce_timer.timeout.connect(self._trigger_extract)

        self.setWindowTitle(f"Video Frame Grabber - {self.file_path.split('/')[-1].split(chr(92))[-1]}")
        self.resize(780, 560)
        self.setModal(True)

        self._init_ui()
        self._trigger_extract()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Frame preview area
        self.preview_container = QFrame()
        self.preview_container.setStyleSheet(
            "background-color: #0a0d14; border-radius: 8px; border: 1px solid #232e42;"
        )
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(4, 4, 4, 4)

        self.preview_label = QLabel("Extracting preview...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setStyleSheet("color: #64748b; font-size: 10.5pt;")
        preview_layout.addWidget(self.preview_label)

        layout.addWidget(self.preview_container, 1)

        # Timecode & Controls
        time_row = QHBoxLayout()
        self.time_label = QLabel(self._format_timecode(self.current_time))
        self.time_label.setStyleSheet("font-size: 10.5pt; font-weight: bold; color: #38bdf8;")
        time_row.addWidget(self.time_label)

        time_row.addStretch()

        # Preset jumps
        for pct, label in [(0.1, "10%"), (0.25, "25%"), (0.5, "50%"), (0.75, "75%"), (0.9, "90%")]:
            btn = QPushButton(label)
            btn.setStyleSheet("padding: 3px 8px; font-size: 8.5pt;")
            btn.clicked.connect(lambda _, p=pct: self.seek_to(self.duration * p))
            time_row.addWidget(btn)

        layout.addLayout(time_row)

        # Timeline Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        initial_val = int((self.current_time / self.duration) * 1000)
        self.slider.setValue(initial_val)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        # Stepper Buttons
        stepper_row = QHBoxLayout()
        stepper_row.setSpacing(6)

        btn_m10 = QPushButton("<< -10s")
        btn_m10.clicked.connect(lambda: self.seek_to(self.current_time - 10))
        btn_m1 = QPushButton("< -1s")
        btn_m1.clicked.connect(lambda: self.seek_to(self.current_time - 1))
        btn_m01 = QPushButton("< -0.1s")
        btn_m01.clicked.connect(lambda: self.seek_to(self.current_time - 0.1))

        btn_p01 = QPushButton("+0.1s >")
        btn_p01.clicked.connect(lambda: self.seek_to(self.current_time + 0.1))
        btn_p1 = QPushButton("+1s >")
        btn_p1.clicked.connect(lambda: self.seek_to(self.current_time + 1))
        btn_p10 = QPushButton("+10s >>")
        btn_p10.clicked.connect(lambda: self.seek_to(self.current_time + 10))

        stepper_row.addWidget(btn_m10)
        stepper_row.addWidget(btn_m1)
        stepper_row.addWidget(btn_m01)
        stepper_row.addSpacing(20)
        stepper_row.addWidget(btn_p01)
        stepper_row.addWidget(btn_p1)
        stepper_row.addWidget(btn_p10)
        stepper_row.addStretch()

        layout.addLayout(stepper_row)

        # Dialog Buttons
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setIcon(get_icon("x"))
        self.btn_cancel.clicked.connect(self.reject)
        bottom_row.addWidget(self.btn_cancel)

        self.btn_use = QPushButton("Use as Video Thumbnail")
        self.btn_use.setIcon(get_icon("check", "#ffffff"))
        self.btn_use.setObjectName("PrimaryButton")
        self.btn_use.setStyleSheet("font-weight: bold; padding: 7px 18px;")
        self.btn_use.clicked.connect(self._accept_thumbnail)
        bottom_row.addWidget(self.btn_use)

        layout.addLayout(bottom_row)

    def _format_timecode(self, sec: float) -> str:
        sec = max(0.0, min(sec, self.duration))
        curr_m = int(sec // 60)
        curr_s = sec % 60
        tot_m = int(self.duration // 60)
        tot_s = self.duration % 60
        return f"{curr_m:02d}:{curr_s:05.2f} / {tot_m:02d}:{tot_s:05.2f}"

    def seek_to(self, sec: float):
        sec = max(0.0, min(sec, self.duration))
        self.current_time = sec
        self.slider.blockSignals(True)
        self.slider.setValue(int((sec / self.duration) * 1000))
        self.slider.blockSignals(False)
        self.time_label.setText(self._format_timecode(sec))
        self.debounce_timer.start()

    def _on_slider_changed(self, value: int):
        self.current_time = (value / 1000.0) * self.duration
        self.time_label.setText(self._format_timecode(self.current_time))
        self.debounce_timer.start()

    def _trigger_extract(self):
        if self.worker and self.worker.isRunning():
            try:
                self.worker.frame_ready.disconnect(self._on_frame_ready)
            except Exception:
                pass
            old_worker = self.worker
            self._retired_workers.append(old_worker)
            old_worker.finished.connect(
                lambda w=old_worker: self._retired_workers.remove(w) if w in self._retired_workers else None
            )

        self.preview_label.setText("Loading frame...")
        self.worker = FrameExtractWorker(self.file_path, self.current_time)
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.worker.start()

    def _on_frame_ready(self, data: bytes, timestamp: float):
        self.captured_bytes = data
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
        else:
            self.preview_label.setText("Could not render frame")

    def _cleanup_workers(self):
        self.debounce_timer.stop()
        for w in [self.worker, *self._retired_workers]:
            if w and w.isRunning():
                w.blockSignals(True)
                w.wait(1000)
        self._retired_workers.clear()

    def closeEvent(self, event):
        self._cleanup_workers()
        super().closeEvent(event)

    def reject(self):
        self._cleanup_workers()
        super().reject()

    def _accept_thumbnail(self):
        self._cleanup_workers()
        if self.captured_bytes:
            self.accept()
        else:
            self.reject()
