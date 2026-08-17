import os
from PyQt6.QtCore import QObject, pyqtSignal
from core.audio_tools import AudioMetadataManager

class MusicViewModel(QObject):
    metadata_loaded = pyqtSignal(str, str, str, str)
    filename_auto_updated = pyqtSignal(str)
    about_to_rename = pyqtSignal(str)
    save_success = pyqtSignal(str)
    save_error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.current_edit_file: str | None = None

    def load_file(self, file_path: str) -> None:
        if not file_path or not os.path.exists(file_path):
            self.current_edit_file = None
            self.metadata_loaded.emit("", "", "", "")
            return

        self.current_edit_file = file_path
        metadata = AudioMetadataManager.read_metadata(file_path)

        title = metadata.get("title", "") if metadata else ""
        artist = metadata.get("artist", "") if metadata else ""
        genre = metadata.get("genre", "") if metadata else ""
        filename = os.path.basename(file_path)

        self.metadata_loaded.emit(title, artist, genre, filename)

    def handle_title_changed(self, title: str) -> None:
        if not self.current_edit_file:
            return
        clean_name = AudioMetadataManager.sanitize_filename(title)
        self.filename_auto_updated.emit(clean_name)

    def save_metadata(self, title: str, artist: str, genre: str, filename: str) -> None:
        if not self.current_edit_file:
            return

        title = title.strip()
        artist = artist.strip()
        genre = genre.strip()
        filename = filename.strip()

        success = AudioMetadataManager.save_metadata(self.current_edit_file, title, artist, genre)
        if not success:
            self.save_error.emit("Failed to write ID3 metadata to the file.")
            return

        if not filename.lower().endswith('.mp3'):
            filename += '.mp3'

        current_dir = os.path.dirname(self.current_edit_file)
        new_path = os.path.normpath(os.path.join(current_dir, filename))

        if self.current_edit_file != new_path:
            # Synchronous signal so MainWindow can release the Player's file lock first
            self.about_to_rename.emit(self.current_edit_file)
            try:
                os.rename(self.current_edit_file, new_path)
                self.current_edit_file = new_path
            except Exception as e:
                self.save_error.emit(f"Metadata saved, but failed to rename the file:\n{e}")
                return

        self.save_success.emit(self.current_edit_file)
