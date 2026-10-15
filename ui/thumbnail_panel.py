import io
from typing import Optional
from PIL import Image

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QFrame, QMessageBox
)
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent

from core.media_item import MediaItem
from core.tagger import normalize_cover_image
from ui.frame_grabber_dialog import FrameGrabberDialog

class CoverDropLabel(QLabel):
    image_dropped = Signal(bytes, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("No Cover Art\n\n(Drop image here or click 'Choose Image')")
        self.setStyleSheet("""
            QLabel {
                background-color: #131317;
                border: 2px dashed #2d2d3d;
                border-radius: 8px;
                color: #64748b;
                font-size: 10pt;
                padding: 12px;
            }
            QLabel:hover {
                border-color: #3b82f6;
                color: #94a3b8;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = url.toLocalFile().lower()
                if ext.endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and any(path.lower().endswith(e) for e in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')):
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

class ThumbnailPanel(QWidget):
    cover_updated = Signal(object, str)  # (bytes or None, mime)
    fetch_online_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_item: Optional[MediaItem] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header
        title = QLabel("COVER ART / THUMBNAIL")
        title.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 8.5pt; letter-spacing: 1px;")
        layout.addWidget(title)

        # Image Drop Label
        self.cover_label = CoverDropLabel()
        self.cover_label.setMinimumSize(220, 220)
        self.cover_label.image_dropped.connect(self._set_cover_data)
        layout.addWidget(self.cover_label, 1)

        # Info label (dimensions & size)
        self.info_label = QLabel("No image loaded")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #64748b; font-size: 8.5pt;")
        layout.addWidget(self.info_label)

        # Button row 1: Choose, Grab Frame, Fetch Online
        btn_row_1 = QHBoxLayout()
        btn_row_1.setSpacing(6)

        self.btn_choose = QPushButton("📁 Choose...")
        self.btn_choose.clicked.connect(self._choose_image_file)
        btn_row_1.addWidget(self.btn_choose)

        self.btn_grab = QPushButton("🎬 Grab Frame...")
        self.btn_grab.setStyleSheet("font-weight: 500;")
        self.btn_grab.clicked.connect(self._open_frame_grabber)
        self.btn_grab.setEnabled(False)
        btn_row_1.addWidget(self.btn_grab)

        self.btn_fetch_online = QPushButton("🌐 Fetch Online...")
        self.btn_fetch_online.setStyleSheet("font-weight: 500;")
        self.btn_fetch_online.clicked.connect(self.fetch_online_requested.emit)
        self.btn_fetch_online.setEnabled(False)
        btn_row_1.addWidget(self.btn_fetch_online)

        layout.addLayout(btn_row_1)

        # Button row 2: Export & Remove
        btn_row_2 = QHBoxLayout()
        btn_row_2.setSpacing(6)

        self.btn_export = QPushButton("💾 Export...")
        self.btn_export.clicked.connect(self._export_cover)
        self.btn_export.setEnabled(False)
        btn_row_2.addWidget(self.btn_export)

        self.btn_remove = QPushButton("❌ Remove")
        self.btn_remove.setObjectName("DangerButton")
        self.btn_remove.clicked.connect(self._remove_cover)
        self.btn_remove.setEnabled(False)
        btn_row_2.addWidget(self.btn_remove)

        layout.addLayout(btn_row_2)

    def set_media_item(self, item: Optional[MediaItem]):
        self.current_item = item
        if not item:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("No file selected")
            self.info_label.setText("")
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

    def update_cover_display(self, data: Optional[bytes], mime: Optional[str] = None):
        if not data:
            self.cover_label.setPixmap(QPixmap())
            hint = "Drop image here\nor click 'Grab Video Frame...'" if (self.current_item and self.current_item.is_video) else "Drop image here\nor click 'Choose Image...'"
            self.cover_label.setText(f"No Cover Art\n\n({hint})")
            self.info_label.setText("No cover embedded")
            self.btn_export.setEnabled(False)
            self.btn_remove.setEnabled(False)
            return

        pix = QPixmap()
        if pix.loadFromData(data):
            scaled = pix.scaled(
                self.cover_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.cover_label.setPixmap(scaled)
            size_kb = len(data) / 1024.0
            mime_str = (mime or "image").replace("image/", "").upper()
            self.info_label.setText(f"{pix.width()} × {pix.height()} • {size_kb:.1f} KB {mime_str}")
            self.btn_export.setEnabled(True)
            self.btn_remove.setEnabled(True)
        else:
            self.cover_label.setText("Invalid image data")
            self.info_label.setText("Corrupt cover")
            self.btn_export.setEnabled(False)
            self.btn_remove.setEnabled(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_item and self.current_item.cover_bytes:
            self.update_cover_display(self.current_item.cover_bytes, self.current_item.cover_mime)

    def _set_cover_data(self, data: Optional[bytes], mime: str):
        if data:
            data, mime = normalize_cover_image(data)
        self.update_cover_display(data, mime)
        self.cover_updated.emit(data, mime)

    def _choose_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cover Image",
            "",
            "Image Files (*.jpg *.jpeg *.png *.webp *.bmp *.gif)"
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
            file_path=self.current_item.file_path,
            duration=self.current_item.duration,
            parent=self
        )
        if dialog.exec() == FrameGrabberDialog.DialogCode.Accepted and dialog.captured_bytes:
            self._set_cover_data(dialog.captured_bytes, "image/jpeg")

    def _export_cover(self):
        if not self.current_item or not self.current_item.cover_bytes:
            return

        ext = ".png" if (self.current_item.cover_mime == "image/png") else ".jpg"
        default_name = f"cover_{self.current_item.tags.get('title') or 'export'}{ext}"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Cover Art",
            default_name,
            "JPEG Image (*.jpg);;PNG Image (*.png);;All Files (*)"
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
