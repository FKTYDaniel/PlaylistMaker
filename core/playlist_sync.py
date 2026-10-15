import os
from typing import List


class PlaylistSyncManager:
    """Keeps references inside .m3u files consistent when an .mp3 file is
    renamed, so playlists don't end up with dead paths."""

    @staticmethod
    def update_references(root_dir: str, old_path: str, new_path: str) -> List[str]:
        """Scans root_dir for .m3u files referencing old_path and updates
        them to new_path. Returns the list of playlists that were updated."""
        if not root_dir or not os.path.isdir(root_dir):
            return []

        updated_playlists: List[str] = []

        for dirpath, _dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                if not filename.lower().endswith('.m3u'):
                    continue

                m3u_path = os.path.join(dirpath, filename)
                if PlaylistSyncManager._update_single_playlist(m3u_path, old_path, new_path):
                    updated_playlists.append(m3u_path)

        return updated_playlists

    @staticmethod
    def _update_single_playlist(m3u_path: str, old_path: str, new_path: str) -> bool:
        playlist_dir = os.path.dirname(m3u_path)
        old_abs = os.path.normpath(old_path).lower()

        try:
            with open(m3u_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return False

        changed = False
        new_lines = []

        for line in lines:
            stripped = line.strip()

            if stripped and not stripped.startswith('#'):
                candidate_abs = os.path.normpath(
                    os.path.join(playlist_dir, stripped)
                ).lower()

                if candidate_abs == old_abs:
                    new_rel = os.path.relpath(new_path, start=playlist_dir).replace('\\', '/')
                    new_lines.append(f"{new_rel}\n")
                    changed = True
                    continue

            new_lines.append(line)

        if not changed:
            return False

        try:
            with open(m3u_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        except Exception:
            return False

        return True
