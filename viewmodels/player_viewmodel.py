import os
from PyQt6.QtCore import QObject, pyqtSignal, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from core.audio_tools import AudioMetadataManager

class PlayerViewModel(QObject):
    track_info_changed = pyqtSignal(str)
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    playback_state_changed = pyqtSignal(str)  # "▶" or "⏸"
    volume_icon_changed = pyqtSignal(str)
    volume_changed = pyqtSignal(int)  # 0-100, so the View can sync the slider on mute/unmute
    queue_cleared = pyqtSignal()
    current_track_changed = pyqtSignal(str)  # absolute path of the current track, or "" if none

    available_outputs_changed = pyqtSignal(list)
    active_output_index_changed = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.playlist_queue: list[str] = []
        self.current_index: int = -1
        self.m3u_base_dir: str = ""

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.player.positionChanged.connect(self.position_changed.emit)
        self.player.durationChanged.connect(self.duration_changed.emit)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.errorOccurred.connect(self._on_player_error)

        # Watchdog: detects playback "stuck" at the same position while
        # supposedly playing (abrupt device disconnects, e.g. Bluetooth,
        # don't always trigger a clean audioOutputsChanged/errorOccurred).
        self._last_watchdog_position: int = -1
        self._stall_ticks: int = 0
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(3000)
        self._watchdog.timeout.connect(self._check_playback_health)
        self._watchdog.start()

        # By default the output follows the OS default device automatically.
        # A manual choice from the dropdown is remembered in
        # _manual_device_id and takes priority until that device disappears.
        self._available_devices: list = []
        self._manual_device_id = None

        self._media_devices = QMediaDevices()
        self._media_devices.audioOutputsChanged.connect(self._on_audio_outputs_changed)
        self._on_audio_outputs_changed()

        self._volume_before_mute: int = 70
        self._is_muted: bool = False
        self.set_volume(70)

        # Lets a View created after a track already started (e.g. the mini
        # player, opened mid-playback) pull the current display text
        # instead of only receiving it via signals it wasn't around for.
        self._current_display_text: str = "No track loaded"

    def get_current_track_display(self) -> str:
        return self._current_display_text

    def _set_track_info(self, text: str) -> None:
        self._current_display_text = text
        self.track_info_changed.emit(text)

    def reset_queue(self) -> None:
        self.playlist_queue = []
        self.current_index = -1
        self.player.stop()
        self._set_track_info("Empty playlist")
        self.playback_state_changed.emit("▶")
        self.current_track_changed.emit("")

    def load_single_mp3(self, file_path: str) -> None:
        self.m3u_base_dir = ""
        self.playlist_queue = [file_path]
        self.current_index = 0
        self.prepare_current_track()

    def load_m3u_playlist(self, m3u_path: str) -> None:
        self.reset_queue()

        if not os.path.exists(m3u_path):
            return

        self.m3u_base_dir = os.path.dirname(m3u_path)
        tracks = []
        try:
            with open(m3u_path, 'r', encoding='utf-8') as f:
                for line in f:
                    clean_line = line.strip()
                    if clean_line and not clean_line.startswith('#'):
                        full_path = os.path.normpath(os.path.join(self.m3u_base_dir, clean_line))
                        if os.path.exists(full_path):
                            tracks.append(full_path)
        except Exception as e:
            print(f"Error reading playlist in ViewModel: {e}")
            return

        if tracks:
            self.playlist_queue = tracks
            self.current_index = 0
            self.prepare_current_track()
        else:
            self._set_track_info("Empty playlist or invalid files")

    def prepare_current_track(self) -> None:
        if 0 <= self.current_index < len(self.playlist_queue):
            track_path = self.playlist_queue[self.current_index]
            self.player.setSource(QUrl.fromLocalFile(track_path))

            metadata = AudioMetadataManager.read_metadata(track_path)
            if metadata and metadata.get("title"):
                display_text = metadata['title']
                if metadata.get("artist"):
                    display_text = f"{metadata['artist']} - {metadata['title']}"
            else:
                display_text = os.path.basename(track_path)

            self._set_track_info(display_text)
            self.playback_state_changed.emit("▶")
            self.position_changed.emit(0)
            self.current_track_changed.emit(track_path)

    def toggle_play(self) -> None:
        if not self.playlist_queue:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.playback_state_changed.emit("▶")
        else:
            self.player.play()
            self.playback_state_changed.emit("⏸")

    def stop_audio(self) -> None:
        self.player.stop()
        self.playback_state_changed.emit("▶")
        self.position_changed.emit(0)

    def next_track(self) -> None:
        if self.current_index < len(self.playlist_queue) - 1:
            self.current_index += 1
            self.prepare_current_track()
            self.player.play()
            self.playback_state_changed.emit("⏸")

    def prev_track(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self.prepare_current_track()
            self.player.play()
            self.playback_state_changed.emit("⏸")

    def jump_to_queue_index(self, index: int) -> None:
        if 0 <= index < len(self.playlist_queue):
            self.current_index = index
            self.prepare_current_track()
            self.player.play()
            self.playback_state_changed.emit("⏸")

    def set_position(self, ms: int) -> None:
        self.player.setPosition(ms)

    def set_volume(self, value: int) -> None:
        value = max(0, min(100, value))
        self.audio_output.setVolume(value / 100.0)

        if value > 0:
            self._volume_before_mute = value
            self._is_muted = False
        else:
            self._is_muted = True

        if value == 0: self.volume_icon_changed.emit("🔇")
        elif value < 40: self.volume_icon_changed.emit("🔈")
        else: self.volume_icon_changed.emit("🔊")

    def toggle_mute(self) -> None:
        """Toggles between silence and the last known non-zero volume."""
        if self._is_muted:
            restore_value = self._volume_before_mute if self._volume_before_mute > 0 else 70
            self.set_volume(restore_value)
            self.volume_changed.emit(restore_value)
        else:
            self.set_volume(0)
            self.volume_changed.emit(0)

    def reload_queue_order(self, visual_order_list: list[str]) -> None:
        if not self.m3u_base_dir:
            return
        current_playing_path = self.playlist_queue[self.current_index] if 0 <= self.current_index < len(self.playlist_queue) else None

        self.playlist_queue = [
            os.path.normpath(os.path.join(self.m3u_base_dir, rel_path))
            for rel_path in visual_order_list
        ]
        if current_playing_path in self.playlist_queue:
            self.current_index = self.playlist_queue.index(current_playing_path)
        else:
            self.current_index = 0

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next_track()

    def _on_player_error(self, error, error_string: str) -> None:
        """Reacts to errors from the audio engine itself (e.g. failing to
        reach the output device). Recovery is deferred for the same
        reentrancy-safety reason as _on_audio_outputs_changed."""
        if error == QMediaPlayer.Error.NoError:
            return
        print(f"Audio engine error: {error_string}")
        QTimer.singleShot(400, self._recover_default_device)

    def _recover_default_device(self) -> None:
        default_device = QMediaDevices.defaultAudioOutput()
        if not default_device.isNull():
            self._manual_device_id = None
            self._switch_to_device(default_device)

    def _check_playback_health(self) -> None:
        """Watchdog tick: forces a recovery if playback appears stuck.
        Covers abrupt device disconnects (e.g. Bluetooth) that don't
        reliably trigger audioOutputsChanged or errorOccurred."""
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self._stall_ticks = 0
            self._last_watchdog_position = -1
            return

        current_position = self.player.position()
        if current_position == self._last_watchdog_position:
            self._stall_ticks += 1
        else:
            self._stall_ticks = 0
        self._last_watchdog_position = current_position

        if self._stall_ticks >= 2:  # ~6s stuck while playing
            self._stall_ticks = 0
            self._recover_default_device()

    # ---------------- Audio output device management ----------------

    def set_output_device_by_index(self, index: int) -> None:
        """Called by the View when the user manually picks an output
        device from the dropdown. Stops following the automatic default
        until this device becomes unavailable."""
        if not (0 <= index < len(self._available_devices)):
            return

        device = self._available_devices[index]
        self._manual_device_id = device.id()
        self._switch_to_device(device)

    def _current_output_index(self) -> int:
        current_id = self.audio_output.device().id()
        for i, device in enumerate(self._available_devices):
            if device.id() == current_id:
                return i
        return -1

    def get_available_output_descriptions(self) -> list:
        """Lets the View pull the current state explicitly, since
        available_outputs_changed is emitted during __init__, before the
        View exists to receive it."""
        return [d.description() for d in self._available_devices]

    def get_current_output_index(self) -> int:
        return self._current_output_index()

    def _switch_to_device(self, device) -> None:
        """Switches the audio output device.

        Calling pause() before setDevice() isn't enough on its own: some
        Qt Multimedia backends on Windows recreate the audio pipeline when
        the device changes, which can reset the position to 0 regardless
        of call order. So the position is saved explicitly and reapplied
        shortly after, giving the pipeline time to settle first."""
        if self.audio_output.device().id() == device.id():
            self.active_output_index_changed.emit(self._current_output_index())
            return

        saved_position = self.player.position()

        self.player.pause()
        self.audio_output.setDevice(device)

        if saved_position > 0:
            QTimer.singleShot(50, lambda: self.player.setPosition(saved_position))

        self.playback_state_changed.emit("▶")
        self.active_output_index_changed.emit(self._current_output_index())

    def _on_audio_outputs_changed(self) -> None:
        """Reacts to changes in the available audio devices (headphones,
        Bluetooth, etc plugged/unplugged).

        On Windows this signal typically originates from a system COM
        callback (IMMNotificationClient). Synchronously querying the audio
        subsystem again from within that same callback is a known cause of
        reentrancy deadlocks. So this handler does nothing risky itself; it
        just defers the real handling to the next event loop iteration."""
        QTimer.singleShot(400, self._handle_audio_outputs_changed_deferred)

    def _handle_audio_outputs_changed_deferred(self) -> None:
        """Actual audioOutputsChanged handling, run outside the original
        callback (see _on_audio_outputs_changed)."""
        self._available_devices = QMediaDevices.audioOutputs()
        self.available_outputs_changed.emit([d.description() for d in self._available_devices])

        target_device = None
        if self._manual_device_id is not None:
            target_device = next(
                (d for d in self._available_devices if d.id() == self._manual_device_id), None
            )
            if target_device is None:
                self._manual_device_id = None

        if target_device is None:
            target_device = QMediaDevices.defaultAudioOutput()

        if target_device.isNull():
            return

        self._switch_to_device(target_device)

    def clear_queue(self) -> None:
        """Stops playback, clears the queue, and releases the current
        file's Windows lock."""
        self.player.stop()
        self.player.setSource(QUrl())

        self.playlist_queue = []
        self.current_index = -1
        self.m3u_base_dir = ""

        self.queue_cleared.emit()
        self.current_track_changed.emit("")
