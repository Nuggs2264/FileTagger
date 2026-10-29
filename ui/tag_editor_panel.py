from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.media_item import STANDARD_TAG_KEYS, MediaItem
from ui.icons import get_icon
from ui.theme import COLOR_TEXT_MUTED

COMMON_GENRES = [
    "",
    "Acoustic",
    "Alternative",
    "Ambient",
    "Blues",
    "Classical",
    "Country",
    "Dance",
    "Electronic",
    "Folk",
    "Funk",
    "Hip-Hop",
    "Indie",
    "Instrumental",
    "Jazz",
    "Lo-Fi",
    "Metal",
    "Orchestral",
    "Pop",
    "Podcast",
    "Punk",
    "R&B",
    "Rap",
    "Reggae",
    "Rock",
    "Score",
    "Soul",
    "Soundtrack",
    "Spoken Word",
    "Vlog",
]

COMMON_EXTENDED_TAGS = [
    "description",
    "encoder",
    "copyright",
    "lyrics",
    "publisher",
    "bpm",
    "initial_key",
    "isrc",
    "grouping",
    "subtitle",
    "tv_show",
    "season",
    "episode",
    "episode_id",
    "director",
    "conductor",
    "lyricist",
    "artist_sort",
    "album_sort",
    "title_sort",
    "compilation",
]

MULTIPLE_PLACEHOLDER = "<keep original / multiple values>"
FIELD_PLACEHOLDERS = {
    "year": "YYYY",
    "track_number": "1/12",
    "disc_number": "1/2",
}


class AddTagDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Metadata Tag")
        self.resize(380, 160)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QGridLayout()
        form.addWidget(QLabel("Tag Name:"), 0, 0)
        self.cmb_tag = QComboBox()
        self.cmb_tag.setEditable(True)
        self.cmb_tag.addItems(COMMON_EXTENDED_TAGS)
        form.addWidget(self.cmb_tag, 0, 1)

        form.addWidget(QLabel("Tag Value:"), 1, 0)
        self.txt_val = QLineEdit()
        form.addWidget(self.txt_val, 1, 1)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_tag_and_value(self):
        return self.cmb_tag.currentText().strip(), self.txt_val.text().strip()


class TagEditorPanel(QWidget):
    tags_applied = Signal(dict)
    save_requested = Signal()
    revert_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_items: list[MediaItem] = []
        self._fields: dict[str, QLineEdit] = {}
        self._modified_keys = set()
        self._is_loading = False

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 6, 0, 0)
        main_layout.setSpacing(6)

        # Header with selection info
        header_row = QHBoxLayout()
        header_row.setContentsMargins(12, 2, 12, 0)
        self.title_label = QLabel("TAG INSPECTOR")
        self.title_label.setObjectName("SectionTitle")
        header_row.addWidget(self.title_label)

        self.selection_label = QLabel("0 files selected")
        self.selection_label.setStyleSheet("color: #94a3b8; font-size: 8.5pt; font-weight: 500;")
        header_row.addWidget(self.selection_label, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(header_row)

        # Tab Widget for Standard, All/Extended, and Technical Info
        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(14, 14))
        self.tabs.tabBar().setUsesScrollButtons(False)

        # -------------------------------------------------------------
        # Tab 1: Standard Tags
        # -------------------------------------------------------------
        standard_scroll = QScrollArea()
        standard_scroll.setWidgetResizable(True)
        standard_scroll.setFrameShape(QFrame.Shape.NoFrame)
        standard_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        standard_scroll.setStyleSheet("background: transparent;")

        form_widget = QWidget()
        form_widget.setStyleSheet("background: transparent;")
        form_layout = QGridLayout(form_widget)
        form_layout.setContentsMargins(10, 4, 10, 6)
        form_layout.setHorizontalSpacing(8)
        form_layout.setVerticalSpacing(5)
        form_layout.setColumnStretch(7, 1)

        def _make_section_header(title: str) -> QWidget:
            w = QWidget()
            w_layout = QHBoxLayout(w)
            w_layout.setContentsMargins(0, 4, 0, 1)
            w_layout.setSpacing(8)

            lbl = QLabel(title.upper())
            lbl.setStyleSheet("font-size: 7.8pt; font-weight: 700; color: #60a5fa; letter-spacing: 0.8px;")
            w_layout.addWidget(lbl)

            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Plain)
            line.setStyleSheet("color: #1e2738; background-color: #1e2738;")
            line.setFixedHeight(1)
            w_layout.addWidget(line, 1)
            return w

        def _make_lbl(text: str, width: int = 84, align_top: bool = False) -> QLabel:
            lbl = QLabel(text)
            align = (
                (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                if align_top
                else (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            )
            lbl.setAlignment(align)
            lbl.setStyleSheet("color: #94a3b8; font-weight: 500; font-size: 9pt;")
            lbl.setFixedWidth(width)
            return lbl

        row = 0

        # Section 1: General Info
        form_layout.addWidget(_make_section_header("General Info"), row, 0, 1, 8)
        row += 1

        form_layout.addWidget(_make_lbl("Title:"), row, 0)
        self.txt_title = QLineEdit()
        self._setup_input("title", self.txt_title)
        form_layout.addWidget(self.txt_title, row, 1, 1, 7)
        row += 1

        form_layout.addWidget(_make_lbl("Artist:"), row, 0)
        self.txt_artist = QLineEdit()
        self._setup_input("artist", self.txt_artist)
        form_layout.addWidget(self.txt_artist, row, 1, 1, 7)
        row += 1

        form_layout.addWidget(_make_lbl("Album:"), row, 0)
        self.txt_album = QLineEdit()
        self._setup_input("album", self.txt_album)
        form_layout.addWidget(self.txt_album, row, 1, 1, 7)
        row += 1

        form_layout.addWidget(_make_lbl("Album Artist:"), row, 0)
        self.txt_album_artist = QLineEdit()
        self._setup_input("album_artist", self.txt_album_artist)
        form_layout.addWidget(self.txt_album_artist, row, 1, 1, 7)
        row += 1

        # Section 2: Release & Track
        form_layout.addWidget(_make_section_header("Release & Track"), row, 0, 1, 8)
        row += 1

        form_layout.addWidget(_make_lbl("Year:"), row, 0)
        num_row_layout = QHBoxLayout()
        num_row_layout.setSpacing(6)
        self.txt_year = QLineEdit()
        self.txt_year.setFixedWidth(56)
        self.txt_year.setPlaceholderText("YYYY")
        self._setup_input("year", self.txt_year)
        num_row_layout.addWidget(self.txt_year)

        lbl_track = QLabel("Track:")
        lbl_track.setStyleSheet("color: #94a3b8; font-weight: 500; font-size: 8.5pt;")
        num_row_layout.addWidget(lbl_track)
        self.txt_track = QLineEdit()
        self.txt_track.setFixedWidth(48)
        self.txt_track.setPlaceholderText("1/12")
        self._setup_input("track_number", self.txt_track)
        num_row_layout.addWidget(self.txt_track)

        lbl_disc = QLabel("Disc:")
        lbl_disc.setStyleSheet("color: #94a3b8; font-weight: 500; font-size: 8.5pt;")
        num_row_layout.addWidget(lbl_disc)
        self.txt_disc = QLineEdit()
        self.txt_disc.setFixedWidth(46)
        self.txt_disc.setPlaceholderText("1/2")
        self._setup_input("disc_number", self.txt_disc)
        num_row_layout.addWidget(self.txt_disc)
        num_row_layout.addStretch()

        form_layout.addLayout(num_row_layout, row, 1, 1, 7)
        row += 1

        form_layout.addWidget(_make_lbl("Genre:"), row, 0)
        self.cmb_genre = QComboBox()
        self.cmb_genre.setEditable(True)
        self.cmb_genre.addItems(COMMON_GENRES)
        self._fields["genre"] = self.cmb_genre.lineEdit()
        self.cmb_genre.currentTextChanged.connect(lambda txt: self._on_field_edited("genre", txt))
        form_layout.addWidget(self.cmb_genre, row, 1, 1, 7)
        row += 1

        # Section 3: Details & Notes
        form_layout.addWidget(_make_section_header("Details & Notes"), row, 0, 1, 8)
        row += 1

        form_layout.addWidget(_make_lbl("Composer:"), row, 0)
        self.txt_composer = QLineEdit()
        self._setup_input("composer", self.txt_composer)
        form_layout.addWidget(self.txt_composer, row, 1, 1, 7)
        row += 1

        form_layout.addWidget(_make_lbl("Comment:", align_top=True), row, 0)
        self.txt_comment = QTextEdit()
        self.txt_comment.setMaximumHeight(50)
        self.txt_comment.textChanged.connect(lambda: self._on_field_edited("comment", self.txt_comment.toPlainText()))
        form_layout.addWidget(self.txt_comment, row, 1, 1, 7)
        row += 1

        standard_scroll.setWidget(form_widget)
        self.tabs.addTab(standard_scroll, get_icon("tag", "#94a3b8", 14), "Standard")

        # -------------------------------------------------------------
        # Tab 2: All / Extended Tags
        # -------------------------------------------------------------
        extended_widget = QWidget()
        extended_widget.setStyleSheet("background: transparent;")
        ext_layout = QVBoxLayout(extended_widget)
        ext_layout.setContentsMargins(10, 8, 10, 8)
        ext_layout.setSpacing(6)

        # Extended tag filter with embedded leading search icon
        self.txt_ext_filter = QLineEdit()
        self.txt_ext_filter.addAction(get_icon("search", "#64748b", 14), QLineEdit.ActionPosition.LeadingPosition)
        self.txt_ext_filter.setPlaceholderText("Filter tag names or values...")
        self.txt_ext_filter.textChanged.connect(self._filter_extended_table)
        self.txt_ext_filter.setClearButtonEnabled(True)
        ext_layout.addWidget(self.txt_ext_filter)

        # Table showing all tags
        self.ext_table = QTableWidget(0, 2)
        self.ext_table.setObjectName("InspectorTable")
        self.ext_table.setShowGrid(False)
        self.ext_table.setWordWrap(False)
        self.ext_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ext_table.setHorizontalHeaderLabels(["Tag / Field", "Value"])
        self.ext_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.ext_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.ext_table.setColumnWidth(0, 145)
        self.ext_table.verticalHeader().setVisible(False)
        self.ext_table.verticalHeader().setDefaultSectionSize(30)
        self.ext_table.cellChanged.connect(self._on_ext_cell_changed)
        ext_layout.addWidget(self.ext_table, 1)

        # Buttons to Add / Delete custom tag
        ext_btn_row = QHBoxLayout()
        ext_btn_row.setSpacing(6)
        self.btn_add_tag = QPushButton("Add Tag")
        self.btn_add_tag.setIcon(get_icon("plus", "#cbd5e1", 14))
        self.btn_add_tag.setIconSize(QSize(14, 14))
        self.btn_add_tag.clicked.connect(self._on_add_tag_clicked)
        ext_btn_row.addWidget(self.btn_add_tag)

        self.btn_del_tag = QPushButton("Remove Tag")
        self.btn_del_tag.setObjectName("DangerButton")
        self.btn_del_tag.setIcon(get_icon("trash", "#cbd5e1", 14))
        self.btn_del_tag.setIconSize(QSize(14, 14))
        self.btn_del_tag.clicked.connect(self._on_remove_tag_clicked)
        ext_btn_row.addWidget(self.btn_del_tag)
        ext_btn_row.addStretch()

        ext_layout.addLayout(ext_btn_row)
        self.tabs.addTab(extended_widget, get_icon("list", "#94a3b8", 14), "All Tags")

        # -------------------------------------------------------------
        # Tab 3: Technical Specs
        # -------------------------------------------------------------
        tech_widget = QWidget()
        tech_widget.setStyleSheet("background: transparent;")
        tech_layout = QVBoxLayout(tech_widget)
        tech_layout.setContentsMargins(10, 8, 10, 8)

        self.tech_table = QTableWidget(0, 2)
        self.tech_table.setObjectName("InspectorTable")
        self.tech_table.setShowGrid(False)
        self.tech_table.setWordWrap(False)
        self.tech_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tech_table.setHorizontalHeaderLabels(["Property", "Details"])
        self.tech_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tech_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tech_table.setColumnWidth(0, 130)
        self.tech_table.verticalHeader().setVisible(False)
        self.tech_table.verticalHeader().setDefaultSectionSize(30)
        self.tech_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tech_layout.addWidget(self.tech_table, 1)

        self.tabs.addTab(tech_widget, get_icon("cpu", "#94a3b8", 14), "Specs")

        main_layout.addWidget(self.tabs, 1)

        # Sleek Low-Profile Action Footer
        footer_widget = QFrame()
        footer_widget.setObjectName("InspectorFooter")
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(12, 8, 12, 8)
        footer_layout.setSpacing(8)

        self.btn_revert = QPushButton("Revert")
        self.btn_revert.setIcon(get_icon("rotate-ccw", "#cbd5e1", 14))
        self.btn_revert.setIconSize(QSize(14, 14))
        self.btn_revert.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_revert.clicked.connect(self.revert_requested.emit)
        footer_layout.addWidget(self.btn_revert)

        footer_layout.addStretch()

        self.btn_save = QPushButton("Save Changes")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.setIcon(get_icon("save", "#ffffff", 14))
        self.btn_save.setIconSize(QSize(14, 14))
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_requested.emit)
        footer_layout.addWidget(self.btn_save)

        main_layout.addWidget(footer_widget)

        self.setEnabled(False)

    def _setup_input(self, key: str, widget: QLineEdit):
        self._fields[key] = widget
        widget.textEdited.connect(lambda txt, k=key: self._on_field_edited(k, txt))

    def _on_field_edited(self, key: str, value: str):
        if self._is_loading:
            return
        self._modified_keys.add(key)
        self.tags_applied.emit({key: value})

    def _set_standard_field_ui_value(self, key: str, val: str):
        if key == "comment":
            self.txt_comment.blockSignals(True)
            self.txt_comment.setPlainText(val)
            self.txt_comment.blockSignals(False)
        elif key == "genre":
            self.cmb_genre.blockSignals(True)
            self.cmb_genre.setEditText(val)
            self.cmb_genre.blockSignals(False)
        elif key in self._fields:
            self._fields[key].blockSignals(True)
            self._fields[key].setText(val)
            self._fields[key].blockSignals(False)

    def set_selected_items(self, items: list[MediaItem]):
        self.selected_items = items
        self._modified_keys.clear()
        self._is_loading = True

        count = len(items)
        if count == 0:
            self.selection_label.setText("0 files selected")
            self._clear_fields()
            self._clear_extended_table()
            self._clear_tech_table()
            self.setEnabled(False)
            self._is_loading = False
            return

        self.setEnabled(True)
        if count == 1:
            self.selection_label.setText("1 file selected")
            item = items[0]
            for key, widget in self._fields.items():
                widget.setPlaceholderText(FIELD_PLACEHOLDERS.get(key, ""))
                widget.setText(item.tags.get(key, ""))
            self.txt_comment.setPlaceholderText("")
            self.txt_comment.setPlainText(item.tags.get("comment", ""))
        else:
            self.selection_label.setText(f"{count} files selected (Batch Mode)")
            for key, widget in self._fields.items():
                vals = {it.tags.get(key, "") for it in items}
                if len(vals) == 1:
                    widget.setPlaceholderText(FIELD_PLACEHOLDERS.get(key, ""))
                    widget.setText(next(iter(vals)))
                else:
                    widget.setText("")
                    widget.setPlaceholderText(MULTIPLE_PLACEHOLDER)

            comment_vals = {it.tags.get("comment", "") for it in items}
            if len(comment_vals) == 1:
                self.txt_comment.setPlaceholderText("")
                self.txt_comment.setPlainText(next(iter(comment_vals)))
            else:
                self.txt_comment.setPlainText("")
                self.txt_comment.setPlaceholderText(MULTIPLE_PLACEHOLDER)

        # Populate Extended Tags Table
        self._populate_extended_table(items)
        # Populate Technical Specs
        self._populate_tech_table(items)

        self._is_loading = False

    def _clear_fields(self):
        for key, widget in self._fields.items():
            widget.clear()
            widget.setPlaceholderText(FIELD_PLACEHOLDERS.get(key, ""))
        self.txt_comment.clear()
        self.txt_comment.setPlaceholderText("")

    def _clear_extended_table(self):
        self.ext_table.blockSignals(True)
        self.ext_table.setRowCount(0)
        self.ext_table.blockSignals(False)

    def _clear_tech_table(self):
        self.tech_table.setRowCount(0)

    def _populate_extended_table(self, items: list[MediaItem]):
        self.ext_table.blockSignals(True)
        self.ext_table.setRowCount(0)

        if not items:
            self.ext_table.blockSignals(False)
            return

        if len(items) == 1:
            item = items[0]
            # Combine standard tags and extra tags for comprehensive view
            all_tags = item.get_all_tags()
            sorted_keys = sorted(all_tags.keys())
            self.ext_table.setRowCount(len(sorted_keys))

            for r, k in enumerate(sorted_keys):
                v = all_tags[k]
                item_k = QTableWidgetItem(k)
                item_k.setForeground(QColor(COLOR_TEXT_MUTED))
                item_k.setToolTip(k)
                # Keep standard tags read-only on key name
                item_k.setFlags(item_k.flags() ^ Qt.ItemFlag.ItemIsEditable)

                item_v = QTableWidgetItem(v)
                item_v.setToolTip(v)
                self.ext_table.setItem(r, 0, item_k)
                self.ext_table.setItem(r, 1, item_v)
        else:
            # Batch: list all keys present in any of the selected files
            all_keys: set = set()
            for it in items:
                all_keys.update(it.get_all_tags().keys())
            sorted_keys = sorted(all_keys)
            self.ext_table.setRowCount(len(sorted_keys))

            for r, k in enumerate(sorted_keys):
                vals = set()
                for it in items:
                    v = it.tags.get(k, "") or it.extra_tags.get(k, "")
                    vals.add(v)

                item_k = QTableWidgetItem(k)
                item_k.setForeground(QColor(COLOR_TEXT_MUTED))
                item_k.setToolTip(k)
                item_k.setFlags(item_k.flags() ^ Qt.ItemFlag.ItemIsEditable)

                if len(vals) == 1:
                    val_str = next(iter(vals))
                    item_v = QTableWidgetItem(val_str)
                    item_v.setToolTip(val_str)
                else:
                    item_v = QTableWidgetItem(MULTIPLE_PLACEHOLDER)
                    item_v.setForeground(QColor(COLOR_TEXT_MUTED))

                self.ext_table.setItem(r, 0, item_k)
                self.ext_table.setItem(r, 1, item_v)

        self.ext_table.blockSignals(False)
        self._filter_extended_table(self.txt_ext_filter.text())

    def _filter_extended_table(self, text: str):
        query = text.strip().lower()
        for r in range(self.ext_table.rowCount()):
            k_item = self.ext_table.item(r, 0)
            v_item = self.ext_table.item(r, 1)
            k_txt = k_item.text().lower() if k_item else ""
            v_txt = v_item.text().lower() if v_item else ""
            match = (not query) or (query in k_txt) or (query in v_txt)
            self.ext_table.setRowHidden(r, not match)

    def _populate_tech_table(self, items: list[MediaItem]):
        self.tech_table.setRowCount(0)
        if not items:
            return

        item = items[0]
        rows = [
            ("File Name", item.file_name),
            ("Format", item.extension.upper().replace(".", "")),
            ("File Size", item.formatted_size()),
            ("Duration", item.formatted_duration()),
        ]

        if item.resolution:
            rows.append(("Resolution", item.resolution))

        for k, v in item.technical_info.items():
            rows.append((k, v))

        rows.append(("Path", item.file_path))

        self.tech_table.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            k_it = QTableWidgetItem(k)
            k_it.setFlags(k_it.flags() ^ Qt.ItemFlag.ItemIsEditable)
            v_it = QTableWidgetItem(str(v))
            v_it.setFlags(v_it.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.tech_table.setItem(r, 0, k_it)
            self.tech_table.setItem(r, 1, v_it)

    def _on_ext_cell_changed(self, row: int, col: int):
        if self._is_loading or col != 1 or not self.selected_items:
            return

        k_item = self.ext_table.item(row, 0)
        v_item = self.ext_table.item(row, 1)
        if not k_item or not v_item:
            return

        key = k_item.text()
        val = v_item.text()
        if val == MULTIPLE_PLACEHOLDER:
            return

        # If it is a standard tag, also update the standard input field
        if key in STANDARD_TAG_KEYS:
            self._set_standard_field_ui_value(key, val)
            self.tags_applied.emit({key: val})
        else:
            for it in self.selected_items:
                it.extra_tags[key] = val
            self.tags_applied.emit({key: val})

    def _on_add_tag_clicked(self):
        if not self.selected_items:
            return

        dlg = AddTagDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tag, val = dlg.get_tag_and_value()
            if not tag:
                return

            if tag.lower() in STANDARD_TAG_KEYS:
                k = tag.lower()
                self._set_standard_field_ui_value(k, val)
                self.tags_applied.emit({k: val})
            else:
                for it in self.selected_items:
                    it.extra_tags[tag] = val
                self.tags_applied.emit({tag: val})

            self._populate_extended_table(self.selected_items)

    def _on_remove_tag_clicked(self):
        cur_row = self.ext_table.currentRow()
        if cur_row < 0 or not self.selected_items:
            return

        k_item = self.ext_table.item(cur_row, 0)
        if not k_item:
            return

        key = k_item.text()
        confirm = QMessageBox.question(
            self,
            "Remove Tag",
            f"Are you sure you want to remove the tag '{key}' from selected file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            if key in STANDARD_TAG_KEYS:
                self._set_standard_field_ui_value(key, "")
                self.tags_applied.emit({key: ""})
            else:
                for it in self.selected_items:
                    if key in it.extra_tags:
                        del it.extra_tags[key]
                self.tags_applied.emit({key: ""})

            self._populate_extended_table(self.selected_items)
