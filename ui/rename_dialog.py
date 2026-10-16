import os
import re
from typing import List, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox
)
from core.media_item import MediaItem

ILLEGAL_CHARS = r'[\\/*?:"<>|\x00-\x1f]'
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

def sanitize_filename(name: str) -> str:
    if not name:
        return ""
    # Replace illegal NTFS characters and control characters
    cleaned = re.sub(ILLEGAL_CHARS, "_", name)
    # Collapse multiple whitespace and strip leading/trailing spaces and dots
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    # Prevent relative traversal tokens
    if cleaned in {".", ".."}:
        cleaned = "_"
    # Guard against Windows reserved device names (case-insensitive stem check)
    stem = cleaned.split(".")[0].upper()
    if stem in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    # Enforce reasonable max filename stem length (NTFS 255-char component limit)
    return cleaned[:200].strip(" .")

class RenameDialog(QDialog):
    def __init__(self, items: List[MediaItem], parent=None):
        super().__init__(parent)
        self.items = items
        self.renamed_count = 0

        self.setWindowTitle("Batch Rename Files from Tags")
        self.resize(750, 480)
        self._init_ui()
        self._update_preview()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Instructions
        desc = QLabel(
            "Format pattern tokens: {artist}, {title}, {album}, {track_number}, {year}, {genre}\n"
            "Example: {artist} - {title} or {track_number} - {title}"
        )
        desc.setStyleSheet("color: #94a3b8; font-size: 9pt;")
        layout.addWidget(desc)

        # Pattern row
        pattern_row = QHBoxLayout()
        pattern_row.addWidget(QLabel("Pattern:"))

        self.cmb_pattern = QComboBox()
        self.cmb_pattern.setEditable(True)
        self.cmb_pattern.addItems([
            "{artist} - {title}",
            "{track_number} - {title}",
            "{track_number} - {artist} - {title}",
            "{year} - {album} - {track_number} - {title}",
            "{artist} - {album} - {track_number} - {title}"
        ])
        self.cmb_pattern.currentTextChanged.connect(self._update_preview)
        pattern_row.addWidget(self.cmb_pattern, 1)

        layout.addLayout(pattern_row)

        # Preview Table
        self.table = QTableWidget(len(self.items), 2)
        self.table.setHorizontalHeaderLabels(["Current Filename", "New Filename"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_rename = QPushButton("Rename Files")
        self.btn_rename.setObjectName("PrimaryButton")
        self.btn_rename.setStyleSheet("font-weight: bold; padding: 7px 18px;")
        self.btn_rename.clicked.connect(self._execute_rename)
        btn_row.addWidget(self.btn_rename)

        layout.addLayout(btn_row)

    def _generate_new_name(self, item: MediaItem, pattern: str) -> str:
        data = {
            "title": sanitize_filename(item.tags.get("title", "") or "Untitled"),
            "artist": sanitize_filename(item.tags.get("artist", "") or "Unknown Artist"),
            "album": sanitize_filename(item.tags.get("album", "") or "Unknown Album"),
            "track_number": sanitize_filename(str(item.tags.get("track_number", "00")).zfill(2)),
            "year": sanitize_filename(item.tags.get("year", "") or ""),
            "genre": sanitize_filename(item.tags.get("genre", "") or "")
        }
        
        try:
            # Safe token replacement without arbitrary Python str.format attribute access
            base = pattern
            for k, v in data.items():
                base = base.replace(f"{{{k}}}", v)
            base = sanitize_filename(base)
            if not base:
                return item.file_name
            return f"{base}{item.extension}"
        except Exception:
            return item.file_name

    def _update_preview(self):
        pattern = self.cmb_pattern.currentText()
        for i, item in enumerate(self.items):
            cur_item = QTableWidgetItem(item.file_name)
            cur_item.setFlags(cur_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            new_name = self._generate_new_name(item, pattern)
            new_item = QTableWidgetItem(new_name)
            new_item.setFlags(new_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(i, 0, cur_item)
            self.table.setItem(i, 1, new_item)

    def _execute_rename(self):
        pattern = self.cmb_pattern.currentText()
        renamed = 0
        errors = []

        for item in self.items:
            new_name = self._generate_new_name(item, pattern)
            if new_name == item.file_name:
                continue

            dir_path = os.path.abspath(os.path.dirname(item.file_path))
            new_path = os.path.abspath(os.path.join(dir_path, os.path.basename(new_name)))
            if os.path.dirname(new_path) != dir_path:
                errors.append(f"Invalid target path rejected: {new_name}")
                continue

            if os.path.exists(new_path) and new_path.lower() != item.file_path.lower():
                errors.append(f"Destination already exists: {new_name}")
                continue

            try:
                os.rename(item.file_path, new_path)
                item.file_path = new_path
                renamed += 1
            except Exception as e:
                errors.append(f"Failed to rename {item.file_name}: {str(e)}")

        self.renamed_count = renamed
        if errors:
            QMessageBox.warning(self, "Rename Finished with Warnings", f"Renamed {renamed} files.\n\nIssues:\n" + "\n".join(errors[:5]))
        else:
            QMessageBox.information(self, "Success", f"Successfully renamed {renamed} files!")

        self.accept()
