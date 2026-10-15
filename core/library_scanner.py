import os
from concurrent.futures import ThreadPoolExecutor
from typing import List
from PyQt6.QtCore import QThread, pyqtSignal

from core.audio_tools import AudioMetadataManager


class LibraryScanThread(QThread):
    """Scans every .mp3 under a root folder for a matching artist/genre
    tag, off the UI thread."""

    finished_ok = pyqtSignal(list)  # matching files, as absolute paths
    failed = pyqtSignal(str)

    MAX_WORKERS = 4

    def __init__(self, root_dir: str, field: str, value: str, parent=None) -> None:
        super().__init__(parent)
        self.root_dir = root_dir
        self.field = field  # "artist" or "genre"
        self.value = value.strip().casefold()

    def _matches(self, mp3_path: str) -> bool:
        """Substring match, since tags often list several artists/genres."""
        metadata = AudioMetadataManager.read_metadata(mp3_path)
        if not metadata:
            return False
        tag_value = (metadata.get(self.field) or "").strip().casefold()
        return self.value in tag_value

    def run(self) -> None:
        try:
            mp3_paths = []
            for dirpath, _dirnames, filenames in os.walk(self.root_dir):
                for name in filenames:
                    if name.lower().endswith(".mp3"):
                        mp3_paths.append(os.path.join(dirpath, name))

            matches: List[str] = []
            with ThreadPoolExecutor(max_workers=self.MAX_WORKERS, thread_name_prefix="lib-scan") as executor:
                for path, is_match in zip(mp3_paths, executor.map(self._matches, mp3_paths)):
                    if is_match:
                        matches.append(path)

            self.finished_ok.emit(matches)
        except Exception as e:
            self.failed.emit(str(e))
