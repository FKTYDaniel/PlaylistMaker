import os
import sys
import json
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "theme": "dark",            # "dark" | "light" | "system"
    "primary_color": "#00e5ff",
    "secondary_color": "#ff2bd6",
    "volume": 70,               # last non-muted volume level (0-100)
}


class ConfigManager:
    """Loads and saves the user's config file (theme, colors, volume) from
    the OS's per-user data folder, not the app's install folder."""

    APP_FOLDER_NAME = "PlayListMaker"
    CONFIG_FILE_NAME = "config.json"

    def __init__(self) -> None:
        self._config_path = self._resolve_config_path()
        self._data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def _resolve_config_path(self) -> str:
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")

        app_dir = os.path.join(base, self.APP_FOLDER_NAME)
        try:
            os.makedirs(app_dir, exist_ok=True)
        except OSError:
            pass

        return os.path.join(app_dir, self.CONFIG_FILE_NAME)

    def load(self) -> None:
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self._data.update({k: v for k, v in loaded.items() if k in DEFAULT_CONFIG})
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.save()

    def save(self) -> None:
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"Warning: could not save config to {self._config_path}: {e}")

    def get_theme(self) -> str:
        return self._data.get("theme", DEFAULT_CONFIG["theme"])

    def set_theme(self, theme: str) -> None:
        if theme not in ("dark", "light", "system"):
            return
        self._data["theme"] = theme
        self.save()

    def get_primary_color(self) -> str:
        return self._data.get("primary_color", DEFAULT_CONFIG["primary_color"])

    def set_primary_color(self, color_hex: str) -> None:
        self._data["primary_color"] = color_hex
        self.save()

    def get_secondary_color(self) -> str:
        return self._data.get("secondary_color", DEFAULT_CONFIG["secondary_color"])

    def set_secondary_color(self, color_hex: str) -> None:
        self._data["secondary_color"] = color_hex
        self.save()

    def get_volume(self) -> int:
        """Last remembered non-muted volume level (0-100)."""
        value = self._data.get("volume", DEFAULT_CONFIG["volume"])
        try:
            return max(0, min(100, int(value)))
        except (TypeError, ValueError):
            return DEFAULT_CONFIG["volume"]

    def set_volume(self, value: int) -> None:
        self._data["volume"] = max(0, min(100, int(value)))
        self.save()
