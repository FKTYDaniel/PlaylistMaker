# PlayListMaker

A lightweight desktop app for organizing an offline MP3 library — browse a folder or USB drive, edit ID3 tags, and build `.m3u` playlists (including automatically, by artist or genre) — all from a single dark/light themed window.

Built with **Python 3** and **PyQt6**.

## Features

### Library explorer
- Browse any local folder or removable USB drive as a file tree (folders, `.mp3` files, and `.m3u` playlists).
- Double-click an `.mp3` to load and play it in the **Music** tab; double-click an `.m3u` to load and play it in the **Playlist** tab.
- Select one or more `.mp3` files and press **Enter** to add them straight to the playlist currently open in the **Playlist** tab.
- The currently loaded/playing file is marked in the tree with a persistent colored indicator, separate from the normal hover/selection highlight.

### USB drive detection
- **Search USB Drive** opens an overlay that polls for removable drives in the background (no window freeze) and lists every drive found, labeled with its Windows volume name — double-click one to open it in the explorer.
- **Open Music Folder** is the manual alternative, for browsing any regular folder instead of a USB drive.

### Metadata editing (Music tab)
- View and edit a track's **Title**, **Artist**, **Genre**, and file name.
- Editing the title automatically suggests a matching file name (slug); the file name field can also be edited by hand.
- Saving writes the ID3 tags and renames the file on disk if the name changed — and automatically updates any `.m3u` playlist elsewhere on the drive that referenced the old file name, so playlists never end up with dead links after a rename.

### Playlists (Playlist tab)
- Create a new empty playlist, rename it, and edit its track list directly.
- **Drag and drop** `.mp3` files from the explorer straight into the list to add them; drag tracks within the list to reorder them.
- Right-click a track for **Play Music**, **Edit Metadata**, or **Remove from Playlist**; the **Delete** key removes the current selection.
- **Save**, **Delete**, and **Clear** the active playlist from the side toolbar.
- **Smart playlists:** hovering the "+" (new playlist) button reveals two extra options — **new playlist by Artist** and **new playlist by Genre**. Enter a name and the app scans every `.mp3` on the active drive/folder (recursively, in a background thread so the UI stays responsive) for a tag containing that text — a partial, case-insensitive match, so it also catches tags with several artists or several comma/semicolon-separated genres — and builds the playlist from whatever matches.

### Player
- Play / pause, stop, previous / next track, a seek bar, and a volume slider.
- Choose the audio output device from the ones Windows currently reports (headphones, speakers, etc.).
- **Mini Player**: pop out a small always-visible player window with the same transport controls while the main window is hidden; bring the main window back from there at any time.

### Customization (Settings)
- **Theme**: Dark, Light, or System.
- **Primary color** — used for outlines, the "now playing" marker, and selection highlights.
- **Secondary color** — used for the new-playlist controls, selection accents, and the volume slider.
- Preferences are saved automatically and persist between launches (see [Configuration](#configuration) below).

## Requirements

- Windows 10/11 (USB drive labels and removable-drive detection use the Windows API; other parts of the app may work cross-platform but this hasn't been the focus).
- Python 3.10+ if running from source.

Python dependencies (see `requirements.txt`):

- [`PyQt6`](https://pypi.org/project/PyQt6/) — UI framework, including the multimedia (playback) and audio-device APIs.
- [`mutagen`](https://pypi.org/project/mutagen/) — reading/writing MP3 ID3 tags.
- [`psutil`](https://pypi.org/project/psutil/) — enumerating disk partitions to find removable drives.

## Running from source

```bash
git clone <this-repo>
cd PlaylistMaker
pip install -r requirements.txt
python main.py
```

## Building a standalone .exe

1. Install [Inno Setup](https://jrsoftware.org/isinfo.php) if you also want to build the installer (optional — the `.exe` alone is enough to run the app).
2. From the project root, run:
   ```bash
   build_exe.bat
   ```
   This installs `pyinstaller` if needed and packages `main.py` (plus the `resources` folder) into a single file at `dist\PlayListMaker.exe`.
3. Optional installer: open `installer\PlayListMaker.iss` in the Inno Setup Compiler and build it (`Build > Compile` or F9). The finished installer is written to `installer_output\PlayListMakerSetup.exe`, with optional Desktop/Start Menu shortcuts.

## Configuration

User preferences (theme, primary/secondary colors) are stored as JSON in the current user's own data folder, **never** inside the app's install folder (which is typically read-only without admin rights):

```
%APPDATA%\PlayListMaker\config.json
```

The file is created automatically on first run with sensible defaults, and rewritten whenever a setting changes in **Settings**.

## Project structure

```
main.py                  Entry point — builds the QApplication, applies the theme, shows MainWindow
core/                     Non-UI logic: config, theming, USB detection, ID3 metadata,
                          .m3u ↔ file-rename syncing, the artist/genre library scanner
viewmodels/               Qt-signal-driven state between core and UI (music, playlist, player)
ui/                       Windows, tabs, and widgets (main window, mini player, settings, overlays)
resources/                Stylesheet template, app icon/logo
installer/                Inno Setup script for the Windows installer
build_exe.bat             PyInstaller packaging script
```

## Known limitations

- Only `.mp3` files are supported for playback and tag editing.
- Removable-drive detection and volume labeling rely on the Windows API (`psutil` + `ctypes.windll`); on other platforms drive detection will not work as described above.
