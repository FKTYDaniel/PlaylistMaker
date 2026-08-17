import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from ui.main_window import MainWindow
from core.config_manager import ConfigManager
from core import theme_manager

# Known, harmless messages from the Windows multimedia (WASAPI) backend
# that appear in the brief moment an audio device is unplugged/plugged,
# before PlayerViewModel reacts and switches output.
_SILENCED_SUBSTRINGS = (
    "AUDCLNT_E_DEVICE_INVALIDATED",
    "Failed to activate audio device",
)


def _qt_message_handler(mode: QtMsgType, context, message: str) -> None:
    if any(substring in message for substring in _SILENCED_SUBSTRINGS):
        return
    print(message, file=sys.stderr)


def resource_base_dir() -> str:
    """Locates the resources folder, both running as a script and packaged
    into a .exe by PyInstaller. In --onefile mode, extra files (--add-data)
    live in a temp folder pointed to by sys._MEIPASS, not next to the .exe."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def main():
    qInstallMessageHandler(_qt_message_handler)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # The main window is only ever *hidden* (not closed) while the mini
    # player is active (see MainWindow.open_mini_player), so the default
    # "quit when the last window closes" behavior would end the app the
    # moment that happens. Quitting is now handled explicitly in
    # MainWindow.closeEvent instead.
    app.setQuitOnLastWindowClosed(False)

    # Config (theme, colors) lives in %APPDATA%, not next to the .exe —
    # see core/config_manager.py. The stylesheet template is combined with
    # that config here at startup, and again whenever the user changes
    # something in Settings (see MainWindow._on_theme_or_color_changed).
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
