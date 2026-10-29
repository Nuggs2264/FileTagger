import html

from PySide6.QtCore import QSettings, QSize, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.online_fetcher import (
    SearchResult,
    clean_search_query,
    download_image_bytes,
    fetch_wikipedia_plot_and_director,
    search_imdb,
    search_tmdb,
    search_tvmaze,
)
from core.secure_storage import decrypt_secret, encrypt_secret
from ui.icons import get_icon
from ui.theme import COLOR_SUCCESS, COLOR_WARNING


class SearchWorker(QThread):
    results_ready = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, query: str, engine: str, tmdb_key: str = ""):
        super().__init__()
        self.query = query
        self.engine = engine
        self.tmdb_key = tmdb_key

    def run(self):
        try:
            if self.engine == "TMDb":
                res = search_tmdb(self.query, self.tmdb_key)
            elif self.engine == "TVMaze":
                res = search_tvmaze(self.query)
            else:
                res = search_imdb(self.query)

            self.results_ready.emit(res)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ImageDownloadWorker(QThread):
    image_ready = Signal(bytes)
    failed = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            data = download_image_bytes(self.url)
            if data:
                self.image_ready.emit(data)
            else:
                self.failed.emit("Empty image data received.")
        except Exception as e:
            self.failed.emit(str(e))


class DetailWorker(QThread):
    details_ready = Signal(dict)

    def __init__(self, title: str):
        super().__init__()
        self.title = title

    def run(self):
        try:
            extra = fetch_wikipedia_plot_and_director(self.title)
            self.details_ready.emit(extra)
        except Exception:
            self.details_ready.emit({})


class OnlineFetcherDialog(QDialog):
    def __init__(self, initial_query: str = "", parent=None, auto_start: bool = True):
        super().__init__(parent)
        self.settings = QSettings("FileTagger", "FileTagger")
        self.initial_query = clean_search_query(initial_query)
        self.search_results: list[SearchResult] = []
        self.selected_result: SearchResult | None = None
        self.downloaded_poster_bytes: bytes | None = None

        self.search_worker: SearchWorker | None = None
        self.image_worker: ImageDownloadWorker | None = None
        self.detail_worker: DetailWorker | None = None
        self._retired_workers: list = []

        self.setWindowTitle("Online Movie & TV Poster & Metadata Fetcher")
        self.resize(880, 620)
        self._init_ui()

        if auto_start and self.initial_query:
            self._start_search()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Top search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        search_row.addWidget(QLabel("Search Query:"))
        self.txt_query = QLineEdit(self.initial_query)
        self.txt_query.addAction(get_icon("search", "#64748b", 14), QLineEdit.ActionPosition.LeadingPosition)
        self.txt_query.setPlaceholderText("Enter movie or TV show title...")
        self.txt_query.returnPressed.connect(self._start_search)
        search_row.addWidget(self.txt_query, 1)

        self.cmb_engine = QComboBox()
        self.cmb_engine.addItems(["IMDb & Open Web (No Key)", "TVMaze (TV Shows - No Key)", "TMDb (API Key)"])
        saved_engine = str(self.settings.value("search_engine", "IMDb & Open Web (No Key)"))
        for i in range(self.cmb_engine.count()):
            if self.cmb_engine.itemText(i) in saved_engine or saved_engine in self.cmb_engine.itemText(i):
                self.cmb_engine.setCurrentIndex(i)
                break
        self.cmb_engine.currentTextChanged.connect(self._on_engine_changed)
        search_row.addWidget(self.cmb_engine)

        self.btn_search = QPushButton("Search")
        self.btn_search.setObjectName("PrimaryButton")
        self.btn_search.setIcon(get_icon("search", "#ffffff", 14))
        self.btn_search.setIconSize(QSize(14, 14))
        self.btn_search.clicked.connect(self._start_search)
        search_row.addWidget(self.btn_search)

        layout.addLayout(search_row)

        # Optional TMDb key row (hidden by default unless TMDb is selected)
        tmdb_box_layout = QVBoxLayout()
        tmdb_box_layout.setContentsMargins(0, 0, 0, 0)
        tmdb_box_layout.setSpacing(3)

        self.tmdb_row = QHBoxLayout()
        self.tmdb_row.addWidget(QLabel("TMDb API Key:"))
        saved_key = decrypt_secret(str(self.settings.value("tmdb_api_key", "")).strip())
        self.txt_tmdb_key = QLineEdit(saved_key)
        self.txt_tmdb_key.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.txt_tmdb_key.setPlaceholderText("Paste your 32-character TMDb v3 API Key...")
        self.txt_tmdb_key.returnPressed.connect(self._on_tmdb_key_enter)
        self.txt_tmdb_key.textChanged.connect(self._on_tmdb_key_changed)
        self.tmdb_row.addWidget(self.txt_tmdb_key, 1)

        self.btn_save_key = QPushButton("Save Key")
        self.btn_save_key.setIcon(get_icon("save", "#cbd5e1", 14))
        self.btn_save_key.setIconSize(QSize(14, 14))
        self.btn_save_key.clicked.connect(self._save_tmdb_key)
        self.tmdb_row.addWidget(self.btn_save_key)

        self.lbl_key_status = QLabel("Saved" if saved_key else "")
        self.lbl_key_status.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold; margin-left: 4px;")
        self.tmdb_row.addWidget(self.lbl_key_status)

        tmdb_box_layout.addLayout(self.tmdb_row)

        lbl_tmdb_note = QLabel(
            "<small style='color: #64748b;'>This product uses the TMDB API but is not endorsed or certified by TMDB.</small>"
        )
        tmdb_box_layout.addWidget(lbl_tmdb_note)

        self.tmdb_container = QFrame()
        self.tmdb_container.setLayout(tmdb_box_layout)
        self.tmdb_container.setVisible("TMDb" in self.cmb_engine.currentText())
        layout.addWidget(self.tmdb_container)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Main splitter (Results Table on Left, Rich Preview on Right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Results table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        left_layout.addWidget(QLabel("Search Results:"))
        self.table_results = QTableWidget(0, 4)
        self.table_results.setShowGrid(False)
        self.table_results.setWordWrap(False)
        self.table_results.setHorizontalHeaderLabels(["Title", "Year", "Type", "Cast / Details"])
        self.table_results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_results.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_results.setColumnWidth(0, 160)
        self.table_results.setColumnWidth(1, 55)
        self.table_results.setColumnWidth(2, 70)
        self.table_results.verticalHeader().setVisible(False)
        self.table_results.verticalHeader().setDefaultSectionSize(30)
        self.table_results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_results.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_results.itemSelectionChanged.connect(self._on_result_selected)
        left_layout.addWidget(self.table_results, 1)

        splitter.addWidget(left_widget)

        # Right: Rich Detail / Poster Preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(8)

        right_layout.addWidget(QLabel("Poster && Metadata Preview:"))

        # Poster image box
        self.lbl_poster = QLabel("No Poster Selected")
        self.lbl_poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_poster.setMinimumSize(180, 240)
        self.lbl_poster.setStyleSheet("""
            QLabel {
                background-color: #0a0d14;
                border: 1px solid #232e42;
                border-radius: 6px;
                color: #64748b;
            }
        """)
        right_layout.addWidget(self.lbl_poster, 1, Qt.AlignmentFlag.AlignCenter)

        # Text detail view
        self.txt_details = QTextEdit()
        self.txt_details.setReadOnly(True)
        self.txt_details.setMaximumHeight(140)
        self.txt_details.setStyleSheet(
            "background-color: #0a0d14; border: 1px solid #232e42; border-radius: 6px; font-size: 9pt;"
        )
        right_layout.addWidget(self.txt_details)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        # Field application checkboxes
        chk_row = QHBoxLayout()
        chk_row.setSpacing(14)
        chk_row.addWidget(QLabel("Apply:"))

        self.chk_poster = QCheckBox("Poster Artwork")
        self.chk_poster.setChecked(True)
        chk_row.addWidget(self.chk_poster)

        self.chk_title = QCheckBox("Title")
        self.chk_title.setChecked(True)
        chk_row.addWidget(self.chk_title)

        self.chk_year = QCheckBox("Year")
        self.chk_year.setChecked(True)
        chk_row.addWidget(self.chk_year)

        self.chk_director = QCheckBox("Director / Artist")
        self.chk_director.setChecked(True)
        chk_row.addWidget(self.chk_director)

        self.chk_genres = QCheckBox("Genres")
        self.chk_genres.setChecked(True)
        chk_row.addWidget(self.chk_genres)

        self.chk_plot = QCheckBox("Plot / Overview")
        self.chk_plot.setChecked(True)
        chk_row.addWidget(self.chk_plot)

        chk_row.addStretch()
        layout.addLayout(chk_row)

        # Bottom action buttons
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_row.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Apply to Selected File(s)")
        self.btn_apply.setObjectName("PrimaryButton")
        self.btn_apply.setIcon(get_icon("check", "#ffffff", 14))
        self.btn_apply.setIconSize(QSize(14, 14))
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_apply.setEnabled(False)
        bottom_row.addWidget(self.btn_apply)

        layout.addLayout(bottom_row)

    def _on_engine_changed(self, text: str):
        self.settings.setValue("search_engine", text)
        self.tmdb_container.setVisible("TMDb" in text)

    def _on_tmdb_key_changed(self, text: str):
        key = text.strip()
        self.settings.setValue("tmdb_api_key", encrypt_secret(key))
        if key:
            self.lbl_key_status.setText("Saved")
            self.lbl_key_status.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold; margin-left: 4px;")
        else:
            self.lbl_key_status.setText("")

    def _save_tmdb_key(self):
        key = self.txt_tmdb_key.text().strip()
        self.settings.setValue("tmdb_api_key", encrypt_secret(key))
        if key:
            self.lbl_key_status.setText("Saved")
            self.lbl_key_status.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold; margin-left: 4px;")
            QMessageBox.information(self, "TMDb Key Saved", "Your TMDb API key has been saved successfully.")
        else:
            self.lbl_key_status.setText("Cleared")
            self.lbl_key_status.setStyleSheet(f"color: {COLOR_WARNING}; margin-left: 4px;")

    def _on_tmdb_key_enter(self):
        self._save_tmdb_key()
        if self.txt_query.text().strip():
            self._start_search()

    def _start_search(self):
        query = self.txt_query.text().strip()
        if not query:
            return

        engine_text = self.cmb_engine.currentText()
        engine = "TMDb" if "TMDb" in engine_text else ("TVMaze" if "TVMaze" in engine_text else "IMDb")
        tmdb_key = self.txt_tmdb_key.text().strip()

        if engine == "TMDb" and not tmdb_key:
            QMessageBox.warning(
                self,
                "TMDb Key Required",
                "Please enter your TMDb API key to use TMDb, or switch to 'IMDb & Open Web (No Key)'.",
            )
            return

        self.progress_bar.setVisible(True)
        self.btn_search.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.table_results.setRowCount(0)
        self.lbl_poster.setText("Searching...")
        self.txt_details.clear()

        if self.search_worker and self.search_worker.isRunning():
            self._retire_worker(self.search_worker)

        self.search_worker = SearchWorker(query, engine, tmdb_key)
        self.search_worker.results_ready.connect(self._on_results_ready)
        self.search_worker.error_occurred.connect(self._on_search_error)
        self.search_worker.start()

    def _on_results_ready(self, results: list[SearchResult]):
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        self.search_results = results

        if not results:
            self.lbl_poster.setText("No results found.\nTry a simpler title or alternate engine.")
            return

        self.table_results.setRowCount(len(results))
        for r, res in enumerate(results):
            it_title = QTableWidgetItem(res.title)
            it_year = QTableWidgetItem(res.year)
            it_type = QTableWidgetItem(res.media_type)
            details = res.cast or (", ".join(res.genres) if res.genres else res.source)
            it_details = QTableWidgetItem(details)

            self.table_results.setItem(r, 0, it_title)
            self.table_results.setItem(r, 1, it_year)
            self.table_results.setItem(r, 2, it_type)
            self.table_results.setItem(r, 3, it_details)

        # Automatically select the first result
        self.table_results.selectRow(0)

    def _on_search_error(self, err: str):
        self.progress_bar.setVisible(False)
        self.btn_search.setEnabled(True)
        QMessageBox.warning(self, "Search Error", f"Failed to fetch metadata: {err}")

    def _render_details_html(self, res: SearchResult):
        lines = [f"<b>{html.escape(res.title)}</b> ({html.escape(res.year)}) - <i>{html.escape(res.media_type)}</i>"]
        if res.genres:
            safe_genres = ", ".join(html.escape(g) for g in res.genres)
            lines.append(f"<b>Genres:</b> {safe_genres}")
        if res.director:
            lines.append(f"<b>Director:</b> {html.escape(res.director)}")
        if res.cast:
            lines.append(f"<b>Cast:</b> {html.escape(res.cast)}")
        if res.overview:
            lines.append(f"<br><b>Overview:</b> {html.escape(res.overview)}")
        self.txt_details.setHtml("<br>".join(lines))

    def _on_result_selected(self):
        selected_rows = self.table_results.selectionModel().selectedRows()
        if not selected_rows:
            self.selected_result = None
            self.btn_apply.setEnabled(False)
            return

        idx = selected_rows[0].row()
        res = self.search_results[idx]
        self.selected_result = res
        self.btn_apply.setEnabled(True)

        # Build details HTML safely
        self._render_details_html(res)

        # Asynchronously fetch Wikipedia summary if overview is missing (e.g. IMDb results)
        if not res.overview and res.title and res.source == "IMDb":
            if self.detail_worker and self.detail_worker.isRunning():
                self._retire_worker(self.detail_worker)
            self.detail_worker = DetailWorker(res.title)
            self.detail_worker.details_ready.connect(lambda extra, r=res: self._on_wiki_details_ready(r, extra))
            self.detail_worker.start()

        # Download and display poster preview
        self.downloaded_poster_bytes = None
        if self.image_worker and self.image_worker.isRunning():
            self._retire_worker(self.image_worker)

        if res.poster_url:
            self.lbl_poster.clear()
            self.lbl_poster.setText("Loading poster...")
            self.image_worker = ImageDownloadWorker(res.poster_url)
            self.image_worker.image_ready.connect(self._on_poster_downloaded)
            self.image_worker.failed.connect(self._on_poster_failed)
            self.image_worker.start()
        else:
            self.lbl_poster.clear()
            self.lbl_poster.setText("No poster image available")

    def _on_poster_downloaded(self, data: bytes):
        self.downloaded_poster_bytes = data
        pix = QPixmap()
        if pix.loadFromData(data):
            scaled = pix.scaled(
                180, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_poster.clear()
            self.lbl_poster.setPixmap(scaled)
        else:
            self.lbl_poster.clear()
            self.lbl_poster.setText("Could not display poster")

    def _on_poster_failed(self, msg: str):
        self.lbl_poster.clear()
        self.lbl_poster.setText(f"Poster unavailable\n({msg})")

    def _on_wiki_details_ready(self, res: SearchResult, extra: dict):
        if self.selected_result is not res:
            return
        updated = False
        if extra.get("overview") and not res.overview:
            res.overview = extra["overview"]
            updated = True
        if extra.get("director") and not res.director:
            res.director = extra["director"]
            updated = True
        if updated:
            self._render_details_html(res)

    def _retire_worker(self, worker: QThread | None):
        if worker and worker.isRunning():
            worker.blockSignals(True)
            self._retired_workers.append(worker)
            worker.finished.connect(
                lambda w=worker: self._retired_workers.remove(w) if w in self._retired_workers else None
            )

    def _stop_workers(self):
        for w in [self.search_worker, self.image_worker, self.detail_worker, *self._retired_workers]:
            if w and w.isRunning():
                w.blockSignals(True)
                w.wait(500)
        self._retired_workers.clear()

    def closeEvent(self, event):
        self._stop_workers()
        super().closeEvent(event)

    def reject(self):
        self._stop_workers()
        super().reject()

    def _on_apply_clicked(self):
        if not self.selected_result:
            return
        self._stop_workers()
        self.accept()
