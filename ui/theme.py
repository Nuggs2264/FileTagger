COLOR_ACCENT = "#60a5fa"
COLOR_SUCCESS = "#34d399"
COLOR_WARNING = "#fbbf24"
COLOR_DANGER = "#f87171"
COLOR_TEXT_MUTED = "#94a3b8"

DARK_THEME_QSS = """
QMainWindow {
    background-color: #0d1017;
}

QWidget {
    background-color: #0d1017;
    color: #e2e8f0;
}

/* Unified Studio Action Bar (ToolBar) */
QToolBar {
    background: #111621;
    border-bottom: 1px solid #1e2738;
    padding: 4px 8px;
    spacing: 2px;
}

QToolBar::separator {
    background-color: #232e42;
    width: 1px;
    margin: 4px 4px;
}

QToolButton {
    background: transparent;
    color: #cbd5e1;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 4px 6px;
    font-weight: 500;
    font-size: 8.5pt;
}

QToolButton:hover {
    background: #1a2233;
    border: 1px solid #2b3852;
    color: #ffffff;
}

QToolButton:pressed {
    background: #232f46;
}

/* Menu Bar */
QMenuBar {
    background: #0d1017;
    border-bottom: 1px solid #1a2130;
    color: #94a3b8;
    padding: 2px 6px;
    font-size: 9pt;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background: #1a2233;
    color: #f8fafc;
}

QMenu {
    background-color: #141a26;
    border: 1px solid #28344b;
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
    background: #232d42;
    margin: 4px 8px;
}

/* Splitter */
QSplitter::handle {
    background-color: #1b2333;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #3b82f6;
}

/* Right Inspector Sidebar Container */
#RightInspectorSidebar {
    background-color: #111621;
    border: 1px solid #1e2738;
    border-radius: 8px;
}

/* Compact Cover Art Header Card */
#CoverHeaderCard {
    background-color: #111621;
    border-bottom: 1px solid #1e2738;
}

#CoverDropZone {
    background-color: #0a0d14;
    border: 1px dashed #2e3b52;
    border-radius: 7px;
    color: #64748b;
    font-size: 8pt;
    padding: 6px;
}

#CoverDropZone:hover {
    border-color: #3b82f6;
    color: #94a3b8;
}

#CoverDropZone[hasCover="true"] {
    border: 1px solid #28354c;
    padding: 0px;
}

#CoverMetaBadge {
    color: #94a3b8;
    font-size: 8.5pt;
}

#SectionTitle {
    font-weight: 700;
    color: #94a3b8;
    font-size: 8pt;
    letter-spacing: 1px;
}

/* Tab Widget (Inspector Tabs) */
QTabWidget::pane {
    border: none;
    border-top: 1px solid #1e2738;
    background-color: #111621;
}

QTabBar::tab {
    background: transparent;
    color: #94a3b8;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 7px 14px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 9pt;
}

QTabBar::tab:selected {
    color: #f8fafc;
    border-bottom: 2px solid #3b82f6;
}

QTabBar::tab:hover:!selected {
    color: #cbd5e1;
    border-bottom: 2px solid #28354c;
}

/* Borderless Studio Tracklist & Tables */
QTableView, QTableWidget {
    background-color: #0d1017;
    border: 1px solid #1e2738;
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: #1e3a5f;
    selection-color: #f8fafc;
    alternate-background-color: #10141d;
    outline: none;
}

#InspectorTable {
    background-color: #0e131d;
    border: 1px solid #1e2738;
    border-radius: 6px;
}

QTableView::item, QTableWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid #151b26;
}

QTableView::item:hover, QTableWidget::item:hover {
    background-color: #151d2c;
}

QTableView::item:selected, QTableWidget::item:selected {
    background-color: #1e3a5f;
    color: #f8fafc;
    border-bottom: 1px solid #274b7a;
}

QHeaderView {
    background-color: transparent;
}

QHeaderView::section {
    background-color: #121824;
    color: #8b9bb4;
    font-weight: 600;
    font-size: 8.5pt;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #1f293d;
    border-right: 1px solid #192131;
}

QHeaderView::section:hover {
    background-color: #182030;
    color: #e2e8f0;
}

/* Inputs & Labels */
QLabel {
    color: #94a3b8;
    background: transparent;
}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #0d111a;
    border: 1px solid #232e42;
    border-radius: 5px;
    padding: 4px 9px;
    color: #f1f5f9;
    font-size: 9.5pt;
    min-height: 22px;
    selection-background-color: #2563eb;
}

QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover {
    border-color: #334360;
    background-color: #0f1420;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
    background-color: #111726;
}

/* Inline Table Cell Editors */
QTableView QLineEdit, QTableWidget QLineEdit {
    background-color: #0e1626;
    color: #f8fafc;
    border: 1.5px solid #3b82f6;
    border-radius: 4px;
    padding: 2px 6px;
    min-height: 20px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

/* Toolbar Search Input & Count Badge */
#ToolbarSearchInput {
    background-color: #0b0e16;
    border: 1px solid #232e42;
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 20px;
    font-size: 9pt;
}

#ToolbarSearchInput:focus {
    border-color: #3b82f6;
}

#ToolbarCountBadge {
    color: #94a3b8;
    background-color: #161d2b;
    border: 1px solid #232e42;
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 8.5pt;
    font-weight: 600;
}

/* In-cell Table Editor */
QTableView QLineEdit {
    background-color: #0b0f19;
    border: 1px solid #3b82f6;
    border-radius: 3px;
    padding: 1px 4px;
    margin: 0px;
    min-height: 18px;
    color: #ffffff;
    font-size: 9.5pt;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #141a26;
    border: 1px solid #28344b;
    selection-background-color: #2563eb;
    color: #f8fafc;
}

/* Buttons */
QPushButton {
    background-color: #182030;
    border: 1px solid #28354c;
    border-radius: 5px;
    padding: 5px 11px;
    color: #e2e8f0;
    font-weight: 500;
    font-size: 9pt;
}

QPushButton:hover {
    background-color: #212c42;
    border-color: #384a69;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #141b29;
}

QPushButton:disabled,
QPushButton#PrimaryButton:disabled,
QPushButton#SuccessButton:disabled,
QPushButton#DangerButton:disabled {
    background-color: #121722;
    border-color: #1b2333;
    color: #475569;
}

QPushButton#PrimaryButton {
    background-color: #2563eb;
    border-color: #3b82f6;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #1d4ed8;
    border-color: #60a5fa;
}

QPushButton#PrimaryButton:pressed {
    background-color: #1e40af;
}

QPushButton#SuccessButton {
    background-color: #059669;
    border-color: #10b981;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#SuccessButton:hover {
    background-color: #047857;
}

/* Ghost Danger Button: subtle neutral until hovered */
QPushButton#DangerButton {
    background-color: #182030;
    border: 1px solid #28354c;
    color: #cbd5e1;
    font-weight: 500;
}

QPushButton#DangerButton:hover {
    background-color: #3b1219;
    border-color: #dc2626;
    color: #fca5a5;
}

QPushButton#DangerButton:pressed {
    background-color: #4c0519;
}

/* Inspector Sticky Footer */
#InspectorFooter {
    background-color: #0f141f;
    border-top: 1px solid #1e2738;
}

/* ScrollBar */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #263147;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #384866;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #263147;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #384866;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Status Bar */
QStatusBar {
    background: #111621;
    border-top: 1px solid #1e2738;
    color: #8b9bb4;
    font-size: 8.5pt;
}

/* GroupBox / Panel */
QGroupBox {
    border: 1px solid #1e2738;
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
    color: #60a5fa;
}

/* Slider */
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #1e2738;
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
    border: 1px solid #232e42;
    border-radius: 5px;
    background-color: #0d111a;
    text-align: center;
    color: #f1f5f9;
    font-weight: 600;
    font-size: 8.5pt;
    min-height: 14px;
}

QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 4px;
}

QProgressDialog {
    background-color: #141a26;
    border: 1px solid #28344b;
    border-radius: 8px;
}

QProgressDialog QLabel {
    color: #f1f5f9;
    font-size: 9.5pt;
}

/* Empty State Card Components */
#EmptyStateCard {
    background-color: #121824;
    border: 1px solid #222d42;
    border-radius: 12px;
}

#EmptyStateTitle {
    color: #f8fafc;
    font-size: 12.5pt;
    font-weight: 700;
}

#EmptyStateSub {
    color: #8b9bb4;
    font-size: 9.5pt;
}

#EmptyStateKbd {
    color: #8b9bb4;
    font-size: 8pt;
    background-color: #182030;
    border: 1px solid #26324a;
    border-radius: 4px;
    padding: 2px 7px;
}
"""
