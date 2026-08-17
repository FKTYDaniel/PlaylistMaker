import os
from PyQt6.QtCore import QObject, pyqtSignal

class PlaylistViewModel(QObject):
    playlist_loaded = pyqtSignal(str, list)
    playlist_saved = pyqtSignal(str, list)
    tracks_updated = pyqtSignal(list)
    playlist_cleared = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_playlist_file: str | None = None

    def load_playlist(self, file_path: str) -> None:
        if not file_path or not os.path.exists(file_path):
            self.reset_state()
            return

        self.current_playlist_file = file_path
        playlist_name = os.path.splitext(os.path.basename(file_path))[0]
        tracks = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        tracks.append(line)
            self.playlist_loaded.emit(playlist_name, tracks)
        except Exception as e:
            self.error_occurred.emit(f"Failed to read playlist:\n{e}")

    def create_empty_playlist(self, base_dir: str, name: str) -> None:
        """Prepares a new playlist in memory without writing to disk yet."""
        name = name.strip()
        if not name:
            return

        if not name.lower().endswith('.m3u'):
            name += '.m3u'

        full_path = os.path.normpath(os.path.join(base_dir, name))

        if os.path.exists(full_path):
            self.error_occurred.emit("A playlist with that name already exists on the drive.")
            return

        # Sets the active path but does NOT create the file yet; the file
        # is only written once save_playlist() is called.
        self.current_playlist_file = full_path
        self.playlist_loaded.emit(os.path.splitext(name)[0], [])

    def create_playlist_from_tracks(self, base_dir: str, name: str, relative_tracks: list[str]) -> None:
        """Same as create_empty_playlist, but pre-filled with tracks already
        found elsewhere (e.g. LibraryScanThread's "by artist"/"by genre"
        results) — used so the "New playlist by Artist/Genre" buttons in
        PlaylistTab can drop straight into the normal load/save flow."""
        name = name.strip()
        if not name:
            return

        if not name.lower().endswith('.m3u'):
            name += '.m3u'

        full_path = os.path.normpath(os.path.join(base_dir, name))

        if os.path.exists(full_path):
            self.error_occurred.emit("A playlist with that name already exists on the drive.")
            return

        self.current_playlist_file = full_path
        self.playlist_loaded.emit(os.path.splitext(name)[0], relative_tracks)

    def add_tracks(self, absolute_paths: list[str], current_relative_tracks: list[str]) -> None:
        if not self.current_playlist_file:
            return

        playlist_dir = os.path.dirname(self.current_playlist_file)
        updated_tracks = list(current_relative_tracks)

        for full_path in absolute_paths:
            rel_path = os.path.relpath(full_path, start=playlist_dir).replace('\\', '/')
            if rel_path not in updated_tracks:
                updated_tracks.append(rel_path)

        self.tracks_updated.emit(updated_tracks)

    def save_playlist(self, new_name: str, tracks: list) -> None:
        if not self.current_playlist_file:
            return

        new_name = new_name.strip()
        if not new_name.lower().endswith('.m3u'):
            new_name += '.m3u'

        current_dir = os.path.dirname(self.current_playlist_file)
        new_path = os.path.normpath(os.path.join(current_dir, new_name))

        old_path_clean = os.path.normpath(self.current_playlist_file).lower()
        new_path_clean = os.path.normpath(new_path).lower()

        try:
            with open(new_path, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for track in tracks:
                    f.write(f"{track}\n")

            if old_path_clean != new_path_clean:
                if os.path.exists(self.current_playlist_file):
                    os.remove(self.current_playlist_file)

            self.current_playlist_file = new_path
            self.playlist_saved.emit(self.current_playlist_file, tracks)
        except Exception as e:
            self.error_occurred.emit(f"Failed to save playlist:\n{e}")

    def delete_playlist(self) -> None:
        if not self.current_playlist_file:
            return
        try:
            if os.path.exists(self.current_playlist_file):
                os.remove(self.current_playlist_file)
            self.reset_state()
        except Exception as e:
            self.error_occurred.emit(f"Failed to delete playlist:\n{e}")

    def reset_state(self) -> None:
        self.current_playlist_file = None
        self.playlist_cleared.emit()
