import os
from typing import List, Any
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from core.media_item import MediaItem
from ui.rename_dialog import sanitize_filename

COLUMNS = [
    ("Mod", 45),
    ("Filename", 220),
    ("Format", 65),
    ("Title", 180),
    ("Artist", 160),
    ("Album", 160),
    ("Year", 60),
    ("Track", 60),
    ("Genre", 100),
    ("Duration", 75),
    ("Cover", 70),
    ("Path", 250),
]

EDITABLE_COLUMNS = {
    1: "filename",
    3: "title",
    4: "artist",
    5: "album",
    6: "year",
    7: "track_number",
    8: "genre",
}

class FileTableModel(QAbstractTableModel):
    item_edited = Signal(int, str, str)  # (row, key, new_value)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[MediaItem] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][0]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() in EDITABLE_COLUMNS:
            return base_flags | Qt.ItemFlag.ItemIsEditable
        return base_flags

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self.items)):
            return None

        item = self.items[index.row()]
        col = index.column()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == 0:
                return "●" if item.is_dirty else ""
            elif col == 1:
                return item.file_name
            elif col == 2:
                return item.extension.upper().replace(".", "")
            elif col == 3:
                return item.tags.get("title", "")
            elif col == 4:
                return item.tags.get("artist", "")
            elif col == 5:
                return item.tags.get("album", "")
            elif col == 6:
                return item.tags.get("year", "")
            elif col == 7:
                return item.tags.get("track_number", "")
            elif col == 8:
                return item.tags.get("genre", "")
            elif col == 9:
                return item.formatted_duration()
            elif col == 10:
                if item.cover_bytes:
                    return f"Yes ({len(item.cover_bytes) // 1024}K)"
                return "No"
            elif col == 11:
                return item.file_path

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in {0, 2, 6, 7, 9, 10}:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 0 and item.is_dirty:
                from PySide6.QtGui import QColor
                return QColor("#f59e0b")  # Amber dot for modified
            if col == 10 and item.cover_bytes:
                from PySide6.QtGui import QColor
                return QColor("#10b981")  # Green for has cover

        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 0:
                return "Modified (Unsaved changes)" if item.is_dirty else "Saved"
            elif col == 1:
                return f"Filename: {item.file_name}\nFull Path: {item.file_path}"
            elif col == 10:
                if item.cover_bytes:
                    mime = item.cover_mime or "image"
                    return f"Cover embedded: {len(item.cover_bytes) // 1024} KB ({mime})"
                return "No cover embedded"
            elif col == 11:
                return item.file_path
            else:
                val = self.data(index, Qt.ItemDataRole.DisplayRole)
                return str(val) if val else None

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        row = index.row()
        col = index.column()
        if not (0 <= row < len(self.items)) or col not in EDITABLE_COLUMNS:
            return False

        item = self.items[row]
        tag_key = EDITABLE_COLUMNS[col]
        str_val = str(value).strip()

        if tag_key == "filename":
            if not str_val:
                return False
            # Reject directory separators or relative traversal sequences
            base_val = os.path.basename(str_val)
            if base_val != str_val or ".." in str_val:
                return False
            if not str_val.lower().endswith(item.extension):
                str_val = f"{str_val}{item.extension}"
            stem, ext = os.path.splitext(str_val)
            safe_stem = sanitize_filename(stem)
            if not safe_stem:
                return False
            str_val = f"{safe_stem}{ext}"
            if str_val == item.file_name:
                return False

            old_path = item.file_path
            dir_name = os.path.abspath(os.path.dirname(old_path))
            new_path = os.path.abspath(os.path.join(dir_name, str_val))
            if os.path.dirname(new_path) != dir_name:
                return False
            try:
                if os.path.exists(new_path) and new_path.lower() != old_path.lower():
                    return False
                os.rename(old_path, new_path)
                item.file_path = new_path
            except Exception:
                return False
        else:
            old_val = item.tags.get(tag_key, "")
            if old_val == str_val:
                return False
            item.tags[tag_key] = str_val

        self.dataChanged.emit(self.index(row, 0), self.index(row, len(COLUMNS) - 1))
        self.item_edited.emit(row, tag_key, str_val)
        return True

    def add_items(self, new_items: List[MediaItem]):
        if not new_items:
            return
        start = len(self.items)
        self.beginInsertRows(QModelIndex(), start, start + len(new_items) - 1)
        self.items.extend(new_items)
        self.endInsertRows()

    def remove_rows(self, rows: List[int]):
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self.items):
                self.beginRemoveRows(QModelIndex(), row, row)
                del self.items[row]
                self.endRemoveRows()

    def clear(self):
        self.beginResetModel()
        self.items.clear()
        self.endResetModel()

    def get_item(self, row: int) -> MediaItem:
        return self.items[row]

    def notify_item_changed(self, row: int):
        if 0 <= row < len(self.items):
            top_left = self.index(row, 0)
            bottom_right = self.index(row, len(COLUMNS) - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def notify_all_changed(self):
        if self.items:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self.items) - 1, len(COLUMNS) - 1)
            self.dataChanged.emit(top_left, bottom_right)
