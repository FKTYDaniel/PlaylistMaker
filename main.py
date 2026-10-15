import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from ui.main_window import MainWindow
from core.config_manager import ConfigManager
from core import theme_manager

# Harmless WASAPI messages that appear briefly when an audio device is
# unplugged/plugged, before PlayerViewModel switches output.
_SILENCED_SUBSTRINGS = (
    "AUDCLNT_E_DEVICE_INVALIDATED",
    "Failed to activate audio device",
)


def _qt_message_handler(mode: QtMsgType, context, message: str) -> None:
    if any(substring in message for substring in _SILENCED_SUBSTRINGS):
        return
    print(message, file=sys.stderr)


def resource_base_dir() -> str:
    """Locates the resources folder, both as a script and packaged by
    PyInstaller into a .exe."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def main():
    qInstallMessageHandler(_qt_message_handler)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Quitting is handled explicitly in MainWindow.closeEvent instead.
    app.setQuitOnLastWindowClosed(False)

    config = ConfigManager()
    theme_manager.apply_theme(app, config)

    icon_path = os.path.join(resource_base_dir(), "resources", "logo.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
