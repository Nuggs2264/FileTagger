import os
import sys

# Suppress harmless Windows monitor ICC profile warnings
os.environ.setdefault("QT_LOGGING_RULES", "qt.gui.icc=false")

from PySide6.QtCore import Qt, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import DARK_THEME_QSS


def _qt_message_handler(mode, context, message):
    # Filter benign Qt internal warnings on Windows
    if "setPointSize: Point size <= 0" in message:
        return
    if "fromIccProfile" in message:
        return
    if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        sys.stderr.write(f"{message}\n")


def main():
    qInstallMessageHandler(_qt_message_handler)
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("FileTagger")
    app.setApplicationDisplayName("FileTagger")

    # Set default application font cleanly via QFont
    default_font = QFont("Segoe UI", 10)
    default_font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(default_font)

    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
