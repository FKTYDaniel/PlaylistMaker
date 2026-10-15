from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QRadioButton, QButtonGroup, QWidget, QColorDialog)
from PyQt6.QtGui import QKeyEvent, QColor, QPalette
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional

from core.config_manager import ConfigManager
from core import theme_manager


class ColorSwatchButton(QPushButton):
    """Square button showing the current color; opens a QColorDialog on
    click."""

    color_changed = pyqtSignal(str)  # emits the new hex color

    def __init__(self, initial_color: str, config: ConfigManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("colorSwatchButton")
        self.setFixedSize(36, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.config = config
        self._current_color = initial_color
        self._apply_color(initial_color)
        self.clicked.connect(self._open_color_dialog)

    def _apply_color(self, color_hex: str) -> None:
        self.setStyleSheet(f"background-color: {color_hex}; border-radius: 6px;")

    def current_color(self) -> str:
        return self._current_color

    def _open_color_dialog(self) -> None:
        """Opens QColorDialog with a theme-neutral background (both QSS
        and QPalette overridden, since internal widgets use either)."""
        bg, text, field_bg, border = theme_manager.get_neutral_dialog_colors(self.config)

        dialog = QColorDialog(QColor(self._current_color), self)
        dialog.setWindowTitle("Choose color")
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)

        palette = dialog.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(bg))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
        palette.setColor(QPalette.ColorRole.Base, QColor(field_bg))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(field_bg))
        palette.setColor(QPalette.ColorRole.Text, QColor(text))
        palette.setColor(QPalette.ColorRole.Button, QColor(field_bg))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(text))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(field_bg))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(text))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(field_bg))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(text))
        dialog.setPalette(palette)

        dialog.setStyleSheet(f"""
            QColorDialog {{ background-color: {bg}; }}
            QColorDialog QLabel {{
                background-color: transparent;
                color: {text};
            }}
            QColorDialog QLineEdit {{
                background-color: {field_bg}; color: {text}; border: 1px solid {border};
            }}
            QColorDialog QSpinBox {{
                background-color: {field_bg}; color: {text}; border: 1px solid {border};
            }}
            QColorDialog QPushButton {{
                background-color: {field_bg}; color: {text}; border: 1px solid {border};
                border-radius: 4px; padding: 5px 14px;
            }}
            QColorDialog QPushButton:hover {{ border-color: {text}; }}
        """)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            chosen = dialog.selectedColor()
            if chosen.isValid():
                self._current_color = chosen.name()
                self._apply_color(self._current_color)
                self.color_changed.emit(self._current_color)


class SettingsOverlay(QDialog):
    """Settings overlay; only the Close button dismisses it."""

    theme_changed = pyqtSignal(str)
    primary_color_changed = pyqtSignal(str)
    secondary_color_changed = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, config: ConfigManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.config = config

        self.setObjectName("settingsOverlay")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(800, 450)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(20)

        title = QLabel("Settings")
        title.setObjectName("overlayLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        theme_label = QLabel("Theme:")
        theme_label.setObjectName("settingsSectionLabel")
        layout.addWidget(theme_label)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(24)

        self.radio_dark = QRadioButton("Dark")
        self.radio_light = QRadioButton("Light")
        self.radio_system = QRadioButton("System")

        self.theme_group = QButtonGroup(self)
        self.theme_group.addButton(self.radio_dark)
        self.theme_group.addButton(self.radio_light)
        self.theme_group.addButton(self.radio_system)

        current_theme = self.config.get_theme()
        self.radio_dark.setChecked(current_theme == "dark")
        self.radio_light.setChecked(current_theme == "light")
        self.radio_system.setChecked(current_theme == "system")

        theme_row.addWidget(self.radio_dark)
        theme_row.addWidget(self.radio_light)
        theme_row.addWidget(self.radio_system)
        theme_row.addStretch(1)
        layout.addLayout(theme_row)

        primary_row = QHBoxLayout()
        primary_label = QLabel("Primary color (outlines, now-playing marker, selection):")
        self.swatch_primary = ColorSwatchButton(self.config.get_primary_color(), self.config)
        primary_row.addWidget(primary_label)
        primary_row.addStretch(1)
        primary_row.addWidget(self.swatch_primary)
        layout.addLayout(primary_row)

        secondary_row = QHBoxLayout()
        secondary_label = QLabel("Secondary color (new playlist, selection, volume):")
        self.swatch_secondary = ColorSwatchButton(self.config.get_secondary_color(), self.config)
        secondary_row.addWidget(secondary_label)
        secondary_row.addStretch(1)
        secondary_row.addWidget(self.swatch_secondary)
        layout.addLayout(secondary_row)

        layout.addStretch(1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("btnCloseSettings")
        btn_layout.addWidget(self.btn_close)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        self._bind_signals()

    def _bind_signals(self) -> None:
        self.radio_dark.toggled.connect(lambda checked: checked and self._on_theme_selected("dark"))
        self.radio_light.toggled.connect(lambda checked: checked and self._on_theme_selected("light"))
        self.radio_system.toggled.connect(lambda checked: checked and self._on_theme_selected("system"))

        self.swatch_primary.color_changed.connect(self._on_primary_color_selected)
        self.swatch_secondary.color_changed.connect(self._on_secondary_color_selected)

        self.btn_close.clicked.connect(self._on_close_clicked)

    def _on_close_clicked(self) -> None:
        self.hide()
        self.closed.emit()

    def _on_theme_selected(self, theme: str) -> None:
        self.config.set_theme(theme)
        self.theme_changed.emit(theme)

    def _on_primary_color_selected(self, color_hex: str) -> None:
        self.config.set_primary_color(color_hex)
        self.primary_color_changed.emit(color_hex)

    def _on_secondary_color_selected(self, color_hex: str) -> None:
        self.config.set_secondary_color(color_hex)
        self.secondary_color_changed.emit(color_hex)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Blocks Escape so only the Close button can dismiss this modal."""
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)
