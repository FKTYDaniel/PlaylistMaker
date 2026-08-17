import psutil
import time
import ctypes
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import List, Tuple, Optional
from PyQt6.QtCore import QThread, pyqtSignal

class UsbDetectorThread(QThread):
    state_changed = pyqtSignal(str, list)

    PROBE_TIMEOUT_SECONDS = 2.0

    def __init__(self) -> None:
        super().__init__()
        self.running: bool = True
        self.current_drives: Optional[List[Tuple[str, str]]] = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="usb-probe")

    def stop(self) -> None:
        """Stops the detection loop and waits for the thread to finish.

        The executor is intentionally NOT shut down here: the user can
        cancel and restart the search multiple times, and a shut-down
        ThreadPoolExecutor rejects new submissions. Python guarantees the
        executor is cleaned up on process exit."""
        self.running = False
        self.wait()

    def get_volume_label(self, drive_letter: str) -> str:
        """Returns the drive's Windows volume label."""
        try:
            kernel32 = ctypes.windll.kernel32
            volume_name_buffer = ctypes.create_unicode_buffer(1024)
            rc = kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive_letter),
                volume_name_buffer,
                ctypes.sizeof(volume_name_buffer),
                None, None, None, None, 0
            )
            if rc and volume_name_buffer.value:
                return volume_name_buffer.value
            return "Unnamed"
        except Exception:
            return "Removable Device"

    def get_removable_drives(self) -> List[Tuple[str, str]]:
        partitions = psutil.disk_partitions(all=False)
        removable = []
        for p in partitions:
            if 'removable' in p.opts:
                label = self.get_volume_label(p.device)
                removable.append((p.device, label))
        return removable

    def _get_removable_drives_with_timeout(self) -> List[Tuple[str, str]]:
        """Runs get_removable_drives() with a time limit.

        If a misbehaving drive makes the native call take longer than
        PROBE_TIMEOUT_SECONDS, this gives up on the current cycle and
        returns the last known list instead of blocking the detection
        loop (and, by extension, stop()) indefinitely."""
        future = self._executor.submit(self.get_removable_drives)
        try:
            return future.result(timeout=self.PROBE_TIMEOUT_SECONDS)
        except FutureTimeoutError:
            return list(self.current_drives) if self.current_drives is not None else []
        except Exception:
            return list(self.current_drives) if self.current_drives is not None else []

    def run(self) -> None:
        while self.running:
            time.sleep(1)
            drives = self._get_removable_drives_with_timeout()

            if self.current_drives is None or drives != self.current_drives:
                self.current_drives = drives
                if len(drives) == 0:
                    self.state_changed.emit("SEARCHING", [])
                else:
                    self.state_changed.emit("DRIVES_FOUND", drives)
