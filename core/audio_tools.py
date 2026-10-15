import os
import re
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError, USLT
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
    def _read_lyrics(file_path: str) -> str:
        """Returns the first embedded USLT (unsynchronized lyrics) text."""
        try:
            frames = ID3(file_path).getall("USLT")
            return frames[0].text if frames else ""
        except Exception:
            return ""

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
                "album": audio.get('album', [''])[0],
                "genre": audio.get('genre', [''])[0],
                "lyrics": AudioMetadataManager._read_lyrics(file_path),
            }
        except ID3NoHeaderError:
            return {"title": "", "artist": "", "album": "", "genre": "", "lyrics": ""}
        except Exception:
            return None

    @staticmethod
    def save_metadata(file_path: str, title: str, artist: str, album: str,
                      genre: str, lyrics: str) -> bool:
        """Writes new metadata (including lyrics) to the file."""
        try:
            try:
                audio = EasyID3(file_path)
            except ID3NoHeaderError:
                audio = EasyID3()

            audio['title'] = title
            audio['artist'] = artist
            audio['album'] = album
            audio['genre'] = genre
            audio.save(file_path)

            tags = ID3(file_path)
            tags.delall("USLT")
            if lyrics:
                tags.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))
            tags.save(file_path)
            return True
        except Exception:
            return False
