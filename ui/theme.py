DARK_THEME_QSS = """
QMainWindow {
    background-color: #12131a;
}

QWidget {
    background-color: #12131a;
    color: #f1f5f9;
}

/* ToolBar */
QToolBar {
    background: #181922;
    border-bottom: 1px solid #282937;
    padding: 4px 8px;
    spacing: 6px;
}

QToolButton {
    background: transparent;
    color: #cbd5e1;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 500;
}

QToolButton:hover {
    background: #252736;
    border: 1px solid #3b3e54;
    color: #ffffff;
}

QToolButton:pressed {
    background: #36394d;
}

/* Menu Bar */
QMenuBar {
    background: #181922;
    border-bottom: 1px solid #282937;
    color: #cbd5e1;
    padding: 2px 4px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background: #252736;
    color: #ffffff;
}

QMenu {
    background-color: #1e202c;
    border: 1px solid #33364a;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: #2b2e40;
    margin: 4px 8px;
}

/* Splitter */
QSplitter::handle {
    background-color: #222330;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #282937;
    border-radius: 6px;
    background-color: #171821;
    top: -1px;
}

QTabBar::tab {
    background: #111218;
    color: #a1a1aa;
    border: 1px solid #282937;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 6px 14px;
    margin-right: 2px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background: #171821;
    color: #ffffff;
    border-bottom: 2px solid #3b82f6;
}

QTabBar::tab:hover:!selected {
    background: #212330;
    color: #f1f5f9;
}

/* Table View */
QTableView {
    background-color: #12131a;
    border: 1px solid #282937;
    border-radius: 6px;
    gridline-color: #1e202c;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #171822;
}

QTableView::item {
    padding: 4px 8px;
}

QTableView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #181923;
    color: #a1a1aa;
    font-weight: 600;
    font-size: 9pt;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #242533;
    border-bottom: 1px solid #282937;
}

QHeaderView::section:hover {
    background-color: #222432;
    color: #f8fafc;
}

/* Inputs & Labels */
QLabel {
    color: #a1a1aa;
}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #161722;
    border: 1px solid #2b2d3d;
    border-radius: 5px;
    padding: 5px 9px;
    color: #f8fafc;
    font-size: 10pt;
    min-height: 22px;
    selection-background-color: #2563eb;
}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover {
    border-color: #3b3e54;
    background-color: #191b28;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
    background-color: #1a1c2a;
}

/* In-cell Table Editor */
QTableView QLineEdit {
    background-color: #0f172a;
    border: 2px solid #3b82f6;
    border-radius: 0px;
    padding: 1px 4px;
    margin: 0px;
    min-height: 18px;
    color: #ffffff;
    font-size: 10pt;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1e202c;
    border: 1px solid #33364a;
    selection-background-color: #2563eb;
    color: #f8fafc;
}

/* Buttons */
QPushButton {
    background-color: #232534;
    border: 1px solid #36394e;
    border-radius: 5px;
    padding: 6px 14px;
    color: #f1f5f9;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2d3043;
    border-color: #484c67;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #181923;
}

QPushButton:disabled,
QPushButton#PrimaryButton:disabled,
QPushButton#SuccessButton:disabled,
QPushButton#DangerButton:disabled {
    background-color: #161720;
    border-color: #232431;
    color: #55586d;
}

QPushButton#PrimaryButton {
    background-color: #2563eb;
    border-color: #1d4ed8;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #1d4ed8;
    border-color: #1e40af;
}

QPushButton#PrimaryButton:pressed {
    background-color: #1e40af;
}

QPushButton#SuccessButton {
    background-color: #15803d;
    border-color: #166534;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#SuccessButton:hover {
    background-color: #166534;
}

QPushButton#DangerButton {
    background-color: #dc2626;
    border-color: #b91c1c;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#DangerButton:hover {
    background-color: #b91c1c;
}

/* ScrollBar */
QScrollBar:vertical {
    border: none;
    background: #12131a;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #2b2e40;
    min-height: 24px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #3e425b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #12131a;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #2b2e40;
    min-width: 24px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #3e425b;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Status Bar */
QStatusBar {
    background: #181922;
    border-top: 1px solid #282937;
    color: #94a3b8;
    font-size: 9pt;
}

/* GroupBox / Panel */
QGroupBox {
    border: 1px solid #282937;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 14px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #3b82f6;
}

/* Slider */
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #252736;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #2563eb;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #93c5fd;
}

/* Progress Bar & Progress Dialog */
QProgressBar {
    border: 1px solid #282937;
    border-radius: 5px;
    background-color: #161722;
    text-align: center;
    color: #f1f5f9;
    font-weight: 600;
    font-size: 8.5pt;
    min-height: 14px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #3b82f6);
    border-radius: 4px;
}

QProgressDialog {
    background-color: #181923;
    border: 1px solid #2d2e3f;
    border-radius: 8px;
}

QProgressDialog QLabel {
    color: #f1f5f9;
    font-size: 9.5pt;
}

/* Empty State Card Components */
#EmptyStateCard {
    background-color: #171822;
    border: 1px solid #2a2c3d;
    border-radius: 12px;
}

#EmptyStateTitle {
    color: #f8fafc;
    font-size: 13pt;
    font-weight: 700;
}

#EmptyStateSub {
    color: #94a3b8;
    font-size: 9.5pt;
}

#EmptyStateKbd {
    color: #94a3b8;
    font-size: 8pt;
    background-color: #1e202e;
    border: 1px solid #2f3246;
    border-radius: 4px;
    padding: 2px 7px;
}
"""
