import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor
from core.config_manager import ConfigManager


FIXED_TOKENS = {
    "DANGER": "#ff5c5c",
    "ON_DANGER": "#1a1a1a",
    "SUCCESS": "#2ecc71",
    "ON_SUCCESS": "#0a1f0f",
}

DARK_TOKENS = {
    "BG_APP": "#1b1b1f",
    "BG_WINDOW": "#17171a",
    "BG_PANEL": "#1e1e22",
    "BG_INPUT": "#232328",
    "BORDER": "#333338",
    "BORDER_INPUT": "#3a3a42",
    "TEXT": "#e8e8ee",
    "TEXT_STRONG": "#ffffff",
    "TEXT_MUTED": "#9a9aa4",
    "HOVER_BG": "#2a2a30",
    "PRESSED_BG": "#101012",
    "DISABLED_TEXT": "#7a7a84",
    "DISABLED_BG": "#3a3a42",
    "HANDLE_COLOR": "#ffffff",
}

LIGHT_TOKENS = {
    "BG_APP": "#f2f2f5",
    "BG_WINDOW": "#e9e9ee",
    "BG_PANEL": "#ffffff",
    "BG_INPUT": "#ffffff",
    "BORDER": "#d0d0d6",
    "BORDER_INPUT": "#c2c2ca",
    "TEXT": "#1c1c22",
    "TEXT_STRONG": "#000000",
    "TEXT_MUTED": "#5a5a64",
    "HOVER_BG": "#e2e2e8",
    "PRESSED_BG": "#c8c8d0",
    "DISABLED_TEXT": "#a0a0a8",
    "DISABLED_BG": "#dcdce0",
    "HANDLE_COLOR": "#ffffff",
}


def _resource_base_dir() -> str:
    """Locates the resources folder, both running as a script and
    packaged into a .exe by PyInstaller (see also main.py)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _relative_luminance(hex_color: str) -> float:
    """Approximate relative luminance (0 = black, 1 = white), used to pick
    light or dark text over an accent color chosen freely by the user."""
    color = QColor(hex_color)
    r, g, b = color.redF(), color.greenF(), color.blueF()
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrasting_text_color(hex_color: str) -> str:
    return "#101012" if _relative_luminance(hex_color) > 0.5 else "#ffffff"


def _lighten(hex_color: str, factor: int = 125) -> str:
    return QColor(hex_color).lighter(factor).name()


def _darken(hex_color: str, factor: int = 125) -> str:
    return QColor(hex_color).darker(factor).name()


def _detect_system_is_dark() -> bool:
    """Best-effort detection of the OS theme. Defaults to dark if
    detection isn't reliably supported."""
    try:
        app = QApplication.instance()
        if app is not None and hasattr(app, "styleHints"):
            scheme = app.styleHints().colorScheme()
            name = getattr(scheme, "name", "")
            if name == "Light":
                return False
            if name == "Dark":
                return True
    except Exception:
        pass
    return True


def _resolve_theme_tokens(config: ConfigManager) -> dict:
    theme = config.get_theme()
    if theme == "light":
        return LIGHT_TOKENS
    if theme == "system":
        return DARK_TOKENS if _detect_system_is_dark() else LIGHT_TOKENS
    return DARK_TOKENS


def get_neutral_dialog_colors(config: ConfigManager) -> tuple:
    """Returns (background, text, field, border) for native Qt dialogs
    not covered by the global stylesheet."""
    tokens = _resolve_theme_tokens(config)
    return tokens["BG_PANEL"], tokens["TEXT"], tokens["BG_INPUT"], tokens["BORDER_INPUT"]


def get_hover_background(config: ConfigManager) -> str:
    """Returns the theme's neutral hover/selected gray, for delegates that
    paint it manually instead of through QSS."""
    return _resolve_theme_tokens(config)["HOVER_BG"]


def build_stylesheet(config: ConfigManager) -> str:
    tokens = dict(_resolve_theme_tokens(config))
    tokens.update(FIXED_TOKENS)

    primary = config.get_primary_color()
    secondary = config.get_secondary_color()

    tokens["PRIMARY"] = primary
    tokens["SECONDARY"] = secondary
    tokens["PRIMARY_HOVER"] = _lighten(primary)
    tokens["PRIMARY_PRESSED"] = _darken(primary)
    tokens["ON_PRIMARY"] = _contrasting_text_color(primary)
    tokens["ON_SECONDARY"] = _contrasting_text_color(secondary)

    template_path = os.path.join(_resource_base_dir(), "resources", "style_template.qss")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    for key, value in tokens.items():
        content = content.replace("{{" + key + "}}", value)

    return content


def apply_theme(app: QApplication, config: ConfigManager) -> None:
    try:
        app.setStyleSheet(build_stylesheet(config))
    except FileNotFoundError:
        print("Warning: could not find the stylesheet template (resources/style_template.qss).")
