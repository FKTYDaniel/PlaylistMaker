import os
import re
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from typing import Dict, Optional

class AudioMetadataManager:
    @staticmethod
    def sanitize_filename(title: str) -> str:
        """Turns a title into a safe filename."""
        cleaned: str = title.lower()
        cleaned = re.sub(r'[\\/:*?"<>|]', '-', cleaned)
        cleaned = re.sub(r'\s+', '-', cleaned)
        cleaned = re.sub(r'-+', '-', cleaned)
        return cleaned.strip('-') + '.mp3'

    @staticmethod
    def read_metadata(file_path: str) -> Optional[Dict[str, str]]:
        """Reads a file's ID3 metadata. Returns None on failure."""
        if not os.path.isfile(file_path) or not file_path.lower().endswith('.mp3'):
            return None

        try:
            audio = EasyID3(file_path)
            return {
                "title": audio.get('title', [''])[0],
                "artist": audio.get('artist', [''])[0],
                "genre": audio.get('genre', [''])[0]
            }
        except ID3NoHeaderError:
            return {"title": "", "artist": "", "genre": ""}
        except Exception:
            return None

    @staticmethod
    def save_metadata(file_path: str, title: str, artist: str, genre: str) -> bool:
        """Writes new metadata to the file."""
        try:
            try:
                audio = EasyID3(file_path)
            except ID3NoHeaderError:
                audio = EasyID3()

            audio['title'] = title
            audio['artist'] = artist
            audio['genre'] = genre
            audio.save(file_path)
            return True
        except Exception:
            return False
