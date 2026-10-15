DARK_THEME_QSS = """
QMainWindow {
    background-color: #1e1e24;
}

QWidget {
    background-color: #1e1e24;
    color: #e2e8f0;
}

/* ToolBar */
QToolBar {
    background: #18181c;
    border-bottom: 1px solid #2d2d38;
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
    background: #2a2a36;
    border: 1px solid #3b3b4d;
    color: #ffffff;
}

QToolButton:pressed {
    background: #3b3b4d;
}

/* Menu Bar */
QMenuBar {
    background: #18181c;
    border-bottom: 1px solid #2d2d38;
    color: #cbd5e1;
    padding: 2px 4px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background: #2a2a36;
    color: #ffffff;
}

QMenu {
    background-color: #24242d;
    border: 1px solid #3b3b4d;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: #333342;
    margin: 4px 8px;
}

/* Splitter */
QSplitter::handle {
    background-color: #272733;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #2d2d38;
    border-radius: 6px;
    background-color: #1a1a22;
    top: -1px;
}

QTabBar::tab {
    background: #141418;
    color: #94a3b8;
    border: 1px solid #2d2d38;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 6px 14px;
    margin-right: 2px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background: #1e1e26;
    color: #ffffff;
    border-bottom: 2px solid #3b82f6;
}

QTabBar::tab:hover:!selected {
    background: #24242f;
    color: #e2e8f0;
}

/* Table View */
QTableView {
    background-color: #16161a;
    border: 1px solid #2d2d38;
    border-radius: 6px;
    gridline-color: #22222c;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    alternate-background-color: #1a1a20;
}

QTableView::item {
    padding: 4px 8px;
}

QTableView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #1c1c22;
    color: #94a3b8;
    font-weight: 600;
    font-size: 9pt;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #262633;
    border-bottom: 1px solid #2d2d38;
}

QHeaderView::section:hover {
    background-color: #24242e;
    color: #f1f5f9;
}

/* Inputs & Labels */
QLabel {
    color: #94a3b8;
}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #141419;
    border: 1px solid #2d2d3d;
    border-radius: 5px;
    padding: 5px 9px;
    color: #f8fafc;
    font-size: 10pt;
    min-height: 20px;
    selection-background-color: #2563eb;
}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover {
    border-color: #3f3f54;
    background-color: #171720;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
    background-color: #191924;
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
    background-color: #24242d;
    border: 1px solid #3b3b4d;
    selection-background-color: #3b82f6;
    color: #f8fafc;
}

/* Buttons */
QPushButton {
    background-color: #2a2a36;
    border: 1px solid #3e3e52;
    border-radius: 5px;
    padding: 6px 14px;
    color: #e2e8f0;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #383848;
    border-color: #4f4f66;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #1e1e28;
}

QPushButton:disabled {
    background-color: #18181f;
    border-color: #252530;
    color: #555566;
}

QPushButton#PrimaryButton {
    background-color: #2563eb;
    border-color: #1d4ed8;
    color: #ffffff;
}

QPushButton#PrimaryButton:hover {
    background-color: #1d4ed8;
    border-color: #1e40af;
}

QPushButton#PrimaryButton:pressed {
    background-color: #1e40af;
}

QPushButton#SuccessButton {
    background-color: #16a34a;
    border-color: #15803d;
    color: #ffffff;
}

QPushButton#SuccessButton:hover {
    background-color: #15803d;
}

QPushButton#DangerButton {
    background-color: #dc2626;
    border-color: #b91c1c;
    color: #ffffff;
}

QPushButton#DangerButton:hover {
    background-color: #b91c1c;
}

/* ScrollBar */
QScrollBar:vertical {
    border: none;
    background: #16161a;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #333342;
    min-height: 24px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #47475c;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #16161a;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #333342;
    min-width: 24px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #47475c;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Status Bar */
QStatusBar {
    background: #18181c;
    border-top: 1px solid #2d2d38;
    color: #94a3b8;
    font-size: 9pt;
}

/* GroupBox / Panel */
QGroupBox {
    border: 1px solid #2d2d38;
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
    background: #2a2a36;
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
"""
