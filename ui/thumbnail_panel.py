from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.media_item import MediaItem
from core.tagger import normalize_cover_image
from ui.frame_grabber_dialog import FrameGrabberDialog
from ui.icons import get_icon
from ui.rename_dialog import sanitize_filename


class CoverDropLabel(QLabel):
    image_dropped = Signal(bytes, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CoverDropZone")
        self.setProperty("hasCover", False)
        self.setFixedSize(120, 120)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setText("No Artwork\nDrop image")

    def set_has_cover(self, has_cover: bool):
        if self.property("hasCover") != has_cover:
            self.setProperty("hasCover", has_cover)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = url.toLocalFile().lower()
                if ext.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and any(path.lower().endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
                try:
                    with open(path, "rb") as f:
                        raw_data = f.read()
                    data, mime = normalize_cover_image(raw_data)
                    self.image_dropped.emit(data, mime)
                    event.acceptProposedAction()
                    return
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not load image: {e}")
        event.ignore()


class ThumbnailPanel(QFrame):
    cover_updated = Signal(object, str)  # (bytes or None, mime)
    fetch_online_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CoverHeaderCard")
        self.current_item: MediaItem | None = None
        self._init_ui()
        self.set_media_item(None)

    def _init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(12)

        # Left: 120x120 Square Artwork Frame
        self.cover_label = CoverDropLabel()
        self.cover_label.image_dropped.connect(self._set_cover_data)
        root_layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignTop)

        # Right: Metadata + Compact Action Rows
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("COVER ARTWORK")
        title.setObjectName("SectionTitle")
        header_row.addWidget(title)
        header_row.addStretch()
        right_col.addLayout(header_row)

        self.info_label = QLabel("No file selected")
        self.info_label.setObjectName("CoverMetaBadge")
        self.info_label.setWordWrap(True)
        right_col.addWidget(self.info_label)

        right_col.addStretch(1)

        # Row 1: Choose, Fetch, Grab Frame
        btn_row_1 = QHBoxLayout()
        btn_row_1.setSpacing(6)

        self.btn_choose = QPushButton("Choose")
        self.btn_choose.setIcon(get_icon("folder", "#cbd5e1", 14))
        self.btn_choose.setIconSize(QSize(14, 14))
        self.btn_choose.setToolTip("Choose Cover Image from Disk")
        self.btn_choose.setEnabled(False)
        self.btn_choose.clicked.connect(self._choose_image_file)
        btn_row_1.addWidget(self.btn_choose)

        self.btn_fetch_online = QPushButton("Fetch")
        self.btn_fetch_online.setIcon(get_icon("globe", "#cbd5e1", 14))
        self.btn_fetch_online.setIconSize(QSize(14, 14))
        self.btn_fetch_online.setToolTip("Fetch Cover Art Online")
        self.btn_fetch_online.clicked.connect(self.fetch_online_requested.emit)
        self.btn_fetch_online.setEnabled(False)
        btn_row_1.addWidget(self.btn_fetch_online)

        self.btn_grab = QPushButton("Frame")
        self.btn_grab.setIcon(get_icon("camera", "#cbd5e1", 14))
        self.btn_grab.setIconSize(QSize(14, 14))
        self.btn_grab.setToolTip("Grab Thumbnail Frame from Video")
        self.btn_grab.clicked.connect(self._open_frame_grabber)
        self.btn_grab.setEnabled(False)
        btn_row_1.addWidget(self.btn_grab)

        right_col.addLayout(btn_row_1)

        # Row 2: Export & Ghost Remove
        btn_row_2 = QHBoxLayout()
        btn_row_2.setSpacing(6)

        self.btn_export = QPushButton("Export")
        self.btn_export.setIcon(get_icon("download", "#cbd5e1", 14))
        self.btn_export.setIconSize(QSize(14, 14))
        self.btn_export.setToolTip("Export Embedded Cover to Disk")
        self.btn_export.clicked.connect(self._export_cover)
        self.btn_export.setEnabled(False)
        btn_row_2.addWidget(self.btn_export)

        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setObjectName("DangerButton")
        self.btn_remove.setIcon(get_icon("trash", "#cbd5e1", 14))
        self.btn_remove.setIconSize(QSize(14, 14))
        self.btn_remove.setToolTip("Remove Embedded Cover Art")
        self.btn_remove.clicked.connect(self._remove_cover)
        self.btn_remove.setEnabled(False)
        btn_row_2.addWidget(self.btn_remove)

        btn_row_2.addStretch(1)
        right_col.addLayout(btn_row_2)

        root_layout.addLayout(right_col, 1)

    def set_media_item(self, item: MediaItem | None):
        self.current_item = item
        if not item:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.set_has_cover(False)
            self.cover_label.setText("No file\nselected")
            self.info_label.setText("Select a file to inspect artwork")
            self.btn_choose.setEnabled(False)
            self.btn_grab.setEnabled(False)
            self.btn_fetch_online.setEnabled(False)
            self.btn_export.setEnabled(False)
            self.btn_remove.setEnabled(False)
            return

        self.btn_choose.setEnabled(True)
        self.btn_grab.setEnabled(item.is_video)
        self.btn_fetch_online.setEnabled(True)
        self.update_cover_display(item.cover_bytes, item.cover_mime)

    def update_cover_display(self, data: bytes | None, mime: str | None = None):
        if not data:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.set_has_cover(False)
            hint = (
                "Drop image\nor grab frame"
                if (self.current_item and self.current_item.is_video)
                else "Drop image\nor click Choose"
            )
            self.cover_label.setText(f"No Cover\n\n{hint}")
            self.info_label.setText("No embedded artwork")
            self.btn_export.setEnabled(False)
            self.btn_remove.setEnabled(False)
            return

        pix = QPixmap()
        if pix.loadFromData(data):
            self.cover_label.set_has_cover(True)
            scaled = pix.scaled(
                self.cover_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.cover_label.setPixmap(scaled)
            size_kb = len(data) / 1024.0
            mime_str = (mime or "image").replace("image/", "").upper()
            self.info_label.setText(f"{pix.width()} × {pix.height()} • {size_kb:.1f} KB {mime_str}")
            self.btn_export.setEnabled(True)
            self.btn_remove.setEnabled(True)
        else:
            self.cover_label.set_has_cover(False)
            self.cover_label.setText("Invalid\nimage")
            self.info_label.setText("Corrupt cover data")
            self.btn_export.setEnabled(False)
            self.btn_remove.setEnabled(True)

    def _set_cover_data(self, data: bytes | None, mime: str):
        if data:
            data, mime = normalize_cover_image(data)
        self.update_cover_display(data, mime)
        self.cover_updated.emit(data, mime)

    def _choose_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Image", "", "Image Files (*.jpg *.jpeg *.png *.webp *.bmp *.gif)"
        )
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    raw_data = f.read()
                data, mime = normalize_cover_image(raw_data)
                self._set_cover_data(data, mime)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load image: {e}")

    def _open_frame_grabber(self):
        if not self.current_item or not self.current_item.is_video:
            return

        dialog = FrameGrabberDialog(
            file_path=self.current_item.file_path, duration=self.current_item.duration, parent=self
        )
        if dialog.exec() == FrameGrabberDialog.DialogCode.Accepted and dialog.captured_bytes:
            self._set_cover_data(dialog.captured_bytes, "image/jpeg")

    def _export_cover(self):
        if not self.current_item or not self.current_item.cover_bytes:
            return

        ext = ".png" if (self.current_item.cover_mime == "image/png") else ".jpg"
        safe_title = sanitize_filename(self.current_item.tags.get("title") or "export") or "export"
        default_name = f"cover_{safe_title}{ext}"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export Cover Art", default_name, "JPEG Image (*.jpg);;PNG Image (*.png);;All Files (*)"
        )
        if save_path:
            try:
                with open(save_path, "wb") as f:
                    f.write(self.current_item.cover_bytes)
                QMessageBox.information(self, "Exported", f"Saved cover to {save_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to export cover: {e}")

    def _remove_cover(self):
        self.update_cover_display(None, None)
        self.cover_updated.emit(None, "")
