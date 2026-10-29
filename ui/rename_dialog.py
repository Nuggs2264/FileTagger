import os
import re
import tempfile

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.media_item import MediaItem
from ui.icons import get_icon

ILLEGAL_CHARS = r'[\\/*?:"<>|\x00-\x1f]'
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
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


def _format_track_num(val: str) -> str:
    if not val:
        return "00"
    val_s = str(val).strip()
    first = val_s.split("/")[0].strip()
    digits = re.findall(r"\d+", first)
    if digits:
        return digits[0].zfill(2)
    return sanitize_filename(first)


def _format_disc_num(val: str) -> str:
    if not val:
        return "1"
    val_s = str(val).strip()
    first = val_s.split("/")[0].strip()
    digits = re.findall(r"\d+", first)
    if digits:
        return digits[0]
    return sanitize_filename(first)


class RenameDialog(QDialog):
    def __init__(self, items: list[MediaItem], parent=None):
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
            "Format pattern tokens: {artist}, {title}, {album}, {album_artist}, {track_number}, {disc_number}, {year}, {genre}, {composer}\n"
            "Example: {artist} - {title} or {track_number} - {title}"
        )
        desc.setStyleSheet("color: #94a3b8; font-size: 9pt;")
        layout.addWidget(desc)

        # Pattern row
        pattern_row = QHBoxLayout()
        pattern_row.addWidget(QLabel("Pattern:"))

        self.cmb_pattern = QComboBox()
        self.cmb_pattern.setEditable(True)
        self.cmb_pattern.addItems(
            [
                "{artist} - {title}",
                "{track_number} - {title}",
                "{track_number} - {artist} - {title}",
                "{year} - {album} - {track_number} - {title}",
                "{artist} - {album} - {track_number} - {title}",
            ]
        )
        self.cmb_pattern.currentTextChanged.connect(self._update_preview)
        pattern_row.addWidget(self.cmb_pattern, 1)

        layout.addLayout(pattern_row)

        # Preview Table
        self.table = QTableWidget(len(self.items), 2)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setHorizontalHeaderLabels(["Current Filename", "New Filename"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        layout.addWidget(self.table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_rename = QPushButton("Rename Files")
        self.btn_rename.setObjectName("PrimaryButton")
        self.btn_rename.setIcon(get_icon("edit", "#ffffff", 14))
        self.btn_rename.setIconSize(QSize(14, 14))
        self.btn_rename.clicked.connect(self._execute_rename)
        btn_row.addWidget(self.btn_rename)

        layout.addLayout(btn_row)

    def _generate_new_name(self, item: MediaItem, pattern: str) -> str:
        data = {
            "title": sanitize_filename(item.tags.get("title", "") or "Untitled"),
            "artist": sanitize_filename(item.tags.get("artist", "") or "Unknown Artist"),
            "album": sanitize_filename(item.tags.get("album", "") or "Unknown Album"),
            "album_artist": sanitize_filename(
                item.tags.get("album_artist", "") or item.tags.get("artist", "") or "Unknown Artist"
            ),
            "track_number": _format_track_num(item.tags.get("track_number", "")),
            "disc_number": _format_disc_num(item.tags.get("disc_number", "")),
            "year": sanitize_filename(item.tags.get("year", "") or ""),
            "genre": sanitize_filename(item.tags.get("genre", "") or ""),
            "composer": sanitize_filename(item.tags.get("composer", "") or ""),
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
        new_names = [self._generate_new_name(item, pattern) for item in self.items]

        # Detect intra-batch collisions
        target_paths = []
        for i, item in enumerate(self.items):
            dir_path = os.path.abspath(os.path.dirname(item.file_path))
            target_paths.append(os.path.abspath(os.path.join(dir_path, os.path.basename(new_names[i]))))

        path_counts = {}
        for p in target_paths:
            norm = os.path.normcase(p)
            path_counts[norm] = path_counts.get(norm, 0) + 1

        for i, item in enumerate(self.items):
            cur_item = QTableWidgetItem(item.file_name)
            cur_item.setFlags(cur_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            new_name = new_names[i]
            new_item = QTableWidgetItem(new_name)
            new_item.setFlags(new_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            new_path = target_paths[i]
            norm = os.path.normcase(new_path)
            tooltips = []
            if path_counts.get(norm, 0) > 1:
                tooltips.append("Warning: Multiple files in batch target this exact filename!")
                new_item.setForeground(QColor("#f87171"))
            if os.name == "nt" and len(new_path) >= 260:
                tooltips.append(f"Warning: Target path exceeds Windows MAX_PATH limit ({len(new_path)}/260 chars)")

            if tooltips:
                new_item.setToolTip("\n".join(tooltips))

            self.table.setItem(i, 0, cur_item)
            self.table.setItem(i, 1, new_item)

    def _execute_rename(self):
        pattern = self.cmb_pattern.currentText()
        plan: list[tuple[MediaItem, str, str]] = []
        errors = []

        seen_targets: set[str] = set()
        for item in self.items:
            new_name = self._generate_new_name(item, pattern)
            if new_name == item.file_name:
                continue

            dir_path = os.path.abspath(os.path.dirname(item.file_path))
            new_path = os.path.abspath(os.path.join(dir_path, os.path.basename(new_name)))

            if os.path.dirname(new_path) != dir_path:
                errors.append(f"Invalid target path rejected: {new_name}")
                continue

            if os.name == "nt" and len(new_path) >= 260:
                errors.append(f"Path exceeds Windows MAX_PATH (260 characters): {new_name}")
                continue

            norm_target = os.path.normcase(new_path)
            if norm_target in seen_targets:
                errors.append(f"Collision in batch: multiple files target '{new_name}'")
                continue
            seen_targets.add(norm_target)

            plan.append((item, item.file_path, new_path))

        if not plan and not errors:
            self.accept()
            return

        if errors:
            QMessageBox.warning(
                self,
                "Rename Validation Errors",
                "Please fix the following issues before renaming:\n\n" + "\n".join(errors[:5]),
            )
            return

        # Check existing destination files that are not part of this rename batch
        current_paths_norm = {os.path.normcase(it.file_path) for it in self.items}
        for _, _, target in plan:
            norm_target = os.path.normcase(target)
            if os.path.exists(target) and norm_target not in current_paths_norm:
                QMessageBox.warning(
                    self,
                    "File Exists",
                    f"Destination already exists on disk:\n{os.path.basename(target)}\nRename aborted.",
                )
                return

        # Two-phase atomic rename
        staged: list[tuple[MediaItem, str, str, str]] = []  # (item, orig_path, tmp_path, final_path)
        renamed_count = 0
        try:
            # Phase 1: Rename each changed file to temporary sibling file
            for item, orig_path, final_path in plan:
                parent_dir = os.path.dirname(orig_path)
                ext = os.path.splitext(orig_path)[1]
                fd, tmp_path = tempfile.mkstemp(prefix=".filetagger_rename_tmp_", suffix=ext, dir=parent_dir)
                os.close(fd)
                os.remove(tmp_path)
                os.rename(orig_path, tmp_path)
                staged.append((item, orig_path, tmp_path, final_path))

            # Phase 2: Rename each temporary file to final target
            for item, _orig_path, tmp_path, final_path in staged:
                os.rename(tmp_path, final_path)
                item.file_path = final_path
                renamed_count += 1
        except Exception as e:
            # Roll back any remaining staged files
            for _it, orig, tmp, _final in staged:
                if os.path.exists(tmp):
                    try:
                        os.rename(tmp, orig)
                    except Exception:
                        pass
            QMessageBox.warning(self, "Rename Failed", f"Error during batch rename:\n{e}\nChanges rolled back.")
            return

        self.renamed_count = renamed_count
        QMessageBox.information(self, "Success", f"Successfully renamed {renamed_count} files!")
        self.accept()
