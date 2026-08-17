from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QGraphicsBlurEffect, QSplitter, QTreeView, QAbstractItemView,
                             QLabel, QPushButton, QFileDialog, QSizePolicy, QApplication,
                             QStyledItemDelegate, QStyle, QStyleOptionViewItem)
from PyQt6.QtGui import QCloseEvent, QFileSystemModel, QKeyEvent, QPainter, QColor, QPen, QPalette
from PyQt6.QtCore import Qt, QDir, QTimer, pyqtSignal, QRect
from typing import List
import os

from ui.overlay import UsbWaitingOverlay
from ui.settings_overlay import SettingsOverlay
from core.usb_detector import UsbDetectorThread
from core.playlist_sync import PlaylistSyncManager
from core.config_manager import ConfigManager
from core import theme_manager
from ui.tabs.music_tab import MusicTab
from ui.tabs.playlist_tab import PlaylistTab
from ui.player_widget import MusicPlayerWidget
from ui.mini_player import MiniPlayerWindow

from viewmodels.player_viewmodel import PlayerViewModel
from viewmodels.playlist_viewmodel import PlaylistViewModel
from viewmodels.music_viewmodel import MusicViewModel


class TreeRowHighlightDelegate(QStyledItemDelegate):
    """Paints the explorer's own hover/selection (primary, left/right
    borders — no native fill) plus a persistent secondary-colored marker
    on whichever file is currently open (the .mp3 loaded in Music, or the
    .m3u loaded in Playlist), regardless of the tree's actual selection
    state — a single click elsewhere shouldn't make that marker disappear.
    """

    HIGHLIGHT_INSET = 4

    def __init__(self, file_model: QFileSystemModel, parent=None) -> None:
        super().__init__(parent)
        self.file_model = file_model
        self.hover_select_color = "#00e5ff"  # primary
        self.active_color = "#ff2bd6"        # secondary
        self.hover_bg_color = "#2a2a30"
        self.active_path = ""

    def set_hover_select_color(self, color_hex: str) -> None:
        self.hover_select_color = color_hex

    def set_active_color(self, color_hex: str) -> None:
        self.active_color = color_hex

    def set_hover_bg_color(self, color_hex: str) -> None:
        self.hover_bg_color = color_hex

    def set_active_path(self, path: str) -> None:
        self.active_path = os.path.normpath(path).lower() if path else ""

    def paint(self, painter: QPainter, option, index) -> None:
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        plain_option = QStyleOptionViewItem(option)
        plain_option.state &= ~QStyle.StateFlag.State_Selected
        plain_option.state &= ~QStyle.StateFlag.State_MouseOver
        plain_option.state &= ~QStyle.StateFlag.State_HasFocus

        rect = option.rect

        is_active = False
        if self.active_path and index.column() == 0:
            item_path = os.path.normpath(self.file_model.filePath(index)).lower()
            is_active = item_path == self.active_path

        if is_hover or is_selected:
            color = self.hover_select_color
        elif is_active:
            color = self.active_color
        else:
            color = None

        # The highlight fill/borders are painted first, and the item's own
        # icon/text on top of it via super().paint() below — otherwise the
        # fill would be drawn over the text and hide it.
        if color is not None:
            highlight_rect = QRect(
                rect.left() + self.HIGHLIGHT_INSET, rect.top(),
                rect.width() - self.HIGHLIGHT_INSET, rect.height()
            )
            painter.save()
            painter.fillRect(highlight_rect, QColor(self.hover_bg_color))
            pen = QPen(QColor(color))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(highlight_rect.left(), rect.top(), highlight_rect.left(), rect.bottom())
            painter.drawLine(highlight_rect.right() - 1, rect.top(), highlight_rect.right() - 1, rect.bottom())
            painter.restore()

        super().paint(painter, plain_option, index)


class GlobalTreeView(QTreeView):
    enter_pressed = pyqtSignal(list)

    def __init__(self, file_model: QFileSystemModel) -> None:
        super().__init__()
        self.file_model = file_model
        self.setModel(self.file_model)
        self.setObjectName("globalTree")
        self.setColumnHidden(1, True)
        self.setColumnHidden(2, True)
        self.setColumnHidden(3, True)

        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.row_delegate = TreeRowHighlightDelegate(self.file_model, self)
        self.setItemDelegate(self.row_delegate)

        # Without mouse tracking, Qt only updates the "hovered row" state
        # on button press/release, not as the mouse simply moves — and
        # without forcing a full repaint on every row change (the
        # `entered` signal), fast mouse movement can leave a partial,
        # dotted trail of un-cleared highlight fragments behind.
        self.setMouseTracking(True)
        self.entered.connect(lambda _index: self.viewport().update())

        # `entered` only fires while the cursor is over a valid row, so
        # changing the selection purely by clicking (no further mouse
        # movement afterwards) can leave the *previous* row's hand-painted
        # border/fill on screen — Qt's own partial repaint on selection
        # change doesn't reliably clear the delegate's custom-drawn extras.
        # Forcing a full repaint on every selection change closes that gap.
        self.selectionModel().selectionChanged.connect(lambda *_: self.viewport().update())

        self._last_hover_row = -1

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)

        # `entered` (used above) never fires when the cursor moves into
        # empty space with no item under it — e.g. past the last row, in
        # the leftover viewport space below a short tree. That transition
        # still needs a repaint, or the last real row's hover highlight
        # stays painted on screen with nothing left to clear it.
        row = self.indexAt(event.position().toPoint()).row()
        if row != self._last_hover_row:
            self._last_hover_row = row
            self.viewport().update()

    def sync_palette(self, base_hex: str, text_hex: str) -> None:
        """Matches QPalette::Highlight/HighlightedText to the tree's normal
        (non-selected) colors. All selection/hover feedback is painted by
        TreeRowHighlightDelegate, but that only covers column 0's own item
        rect — the branch/expand-arrow strip to its left is still painted
        natively by Qt for a selected row, using QPalette::Highlight. Left
        at its default, that can end up as a stray, mismatched colored
        sliver (e.g. picking up the OS accent color on Windows) next to the
        delegate's own highlight. Matching it to the ordinary background
        makes that strip effectively invisible in every state."""
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor(base_hex))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(text_hex))
        self.setPalette(palette)

    def set_active_path(self, path: str) -> None:
        self.row_delegate.set_active_path(path)
        self.viewport().update()

    def leaveEvent(self, event) -> None:
        self._last_hover_row = -1
        self.viewport().update()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            indexes = self.selectionModel().selectedRows()
            paths = [self.file_model.filePath(idx) for idx in indexes
                     if not self.file_model.isDir(idx) and self.file_model.filePath(idx).lower().endswith('.mp3')]

            if paths:
                self.enter_pressed.emit(paths)
                self.clearSelection()
        else:
            super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.player_vm = PlayerViewModel()
        self.playlist_vm = PlaylistViewModel()
        self.music_vm = MusicViewModel()

        # User config (theme, colors) lives in %APPDATA%, never inside the
        # install folder — see core/config_manager.py.
        self.config = ConfigManager()

        # Tracks the last file opened in the Music tab, used to sync
        # playlists when that file gets renamed.
        self._pending_old_path: str | None = None

        self.setObjectName("mainWindow")
        self.setWindowTitle("Music Organizer - No Folder Selected")
        self.setGeometry(200, 200, 1100, 750)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(8, 8, 8, 8)
        top_layout.setSpacing(8)

        self.actions_toolbar = QWidget()
        self.actions_toolbar.setObjectName("actionsToolbar")
        # "Fixed" vertical policy keeps this bar from growing to fill the
        # extra space that a plain QVBoxLayout would otherwise distribute
        # ambiguously between it and h_splitter.
        self.actions_toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar_layout = QHBoxLayout(self.actions_toolbar)
        toolbar_layout.setContentsMargins(10, 10, 10, 10)
        toolbar_layout.setSpacing(10)

        self.btn_open_folder = QPushButton("📂")
        self.btn_open_folder.setObjectName("btnToolbarIcon")
        self.btn_open_folder.setFixedSize(40, 40)
        self.btn_open_folder.setToolTip("Open Music Folder")
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self.open_folder_dialog)
        toolbar_layout.addWidget(self.btn_open_folder)

        self.btn_search_usb = QPushButton("🔍")
        self.btn_search_usb.setObjectName("btnToolbarIcon")
        self.btn_search_usb.setFixedSize(40, 40)
        self.btn_search_usb.setToolTip("Search USB Drive")
        self.btn_search_usb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search_usb.clicked.connect(self.start_usb_search)
        toolbar_layout.addWidget(self.btn_search_usb)

        toolbar_layout.addStretch(1)

        self.btn_mini_player = QPushButton("🗗")
        self.btn_mini_player.setObjectName("btnToolbarIcon")
        self.btn_mini_player.setFixedSize(40, 40)
        self.btn_mini_player.setToolTip("Mini Player")
        self.btn_mini_player.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mini_player.clicked.connect(self.open_mini_player)
        toolbar_layout.addWidget(self.btn_mini_player)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setObjectName("btnToolbarIcon")
        self.btn_settings.setFixedSize(40, 40)
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.clicked.connect(self.open_settings)
        toolbar_layout.addWidget(self.btn_settings)

        top_layout.addWidget(self.actions_toolbar, 0)

        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_layout.addWidget(self.h_splitter, 1)

        self.file_model = QFileSystemModel()
        self.file_model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.AllEntries)

        self.global_tree = GlobalTreeView(self.file_model)
        self.global_tree.doubleClicked.connect(self.on_tree_double_clicked)
        self.global_tree.setExpandsOnDoubleClick(False)

        self.h_splitter.addWidget(self.global_tree)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.tabBar().setExpanding(True)
        self.tabs.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)

        self.tab_music = MusicTab(self.music_vm)
        self.tabs.addTab(self.tab_music, "Music")

        self.tab_playlist = PlaylistTab(self.playlist_vm)
        self.tabs.addTab(self.tab_playlist, "Playlist")

        self.music_vm.about_to_rename.connect(self.handle_before_mp3_rename)
        self.music_vm.save_success.connect(self.handle_mp3_rename_success)
        self.playlist_vm.playlist_saved.connect(self.handle_playlist_saved)
        self.playlist_vm.playlist_cleared.connect(self.handle_playlist_cleared)

        self.h_splitter.addWidget(self.tabs)
        self.h_splitter.setSizes([350, 650])

        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.addWidget(top_container)
        self.v_splitter.setSizes([600, 150])

        self.main_layout.addWidget(self.v_splitter)

        self.player_widget = MusicPlayerWidget(self.player_vm, self.config)
        self.player_widget.setFixedHeight(85)

        # Created lazily on first use — see open_mini_player()
        self.mini_player: MiniPlayerWindow | None = None

        self.player_vm.current_track_changed.connect(self.tab_playlist.highlight_current_track)

        self.main_layout.addWidget(self.player_widget)

        self.global_tree.enter_pressed.connect(self.tab_playlist.add_multiple_mp3s)
        self.tab_playlist.edit_metadata_requested.connect(self.edit_track_metadata)

        self.blur_effect = QGraphicsBlurEffect()
        self.blur_effect.setBlurRadius(10)
        self.central_widget.setGraphicsEffect(self.blur_effect)
        self.blur_effect.setEnabled(False)

        self.overlay = UsbWaitingOverlay(self)
        self.overlay.drive_selected.connect(self.on_drive_selected)
        self.overlay.search_cancelled.connect(self.cancel_usb_search)

        self.settings_overlay = SettingsOverlay(self.config, self)
        self.settings_overlay.theme_changed.connect(self._on_theme_or_color_changed)
        self.settings_overlay.primary_color_changed.connect(self._on_theme_or_color_changed)
        self.settings_overlay.secondary_color_changed.connect(self._on_theme_or_color_changed)
        self.settings_overlay.closed.connect(self.hide_settings)

        # The play button's glow and the '+' icon are painted directly in
        # Python (not covered by the shared QSS), so they must be synced
        # manually with the saved config on startup.
        self.player_widget.set_glow_color(self.config.get_primary_color())
        self.tab_playlist.set_new_button_color(self.config.get_secondary_color())
        self.tab_playlist.set_primary_color(self.config.get_primary_color())
        self.tab_playlist.set_hover_background(theme_manager.get_hover_background(self.config))
        self._sync_tree_colors()
        self.player_widget.sync_output_combo_palette()

        self.usb_thread = UsbDetectorThread()
        self.usb_thread.state_changed.connect(self.handle_usb_state)
        # The USB search only starts when the user clicks "Search USB
        # Drive" — see start_usb_search(). This keeps the overlay from
        # appearing on its own at startup.

    def open_mini_player(self) -> None:
        """Hides the main window (not closed — the ViewModels and USB
        thread keep running) and shows the compact always-on-top player."""
        if self.mini_player is None:
            self.mini_player = MiniPlayerWindow(self.player_vm, self.config)
            self.mini_player.restore_requested.connect(self.restore_main_window)

        self.hide()
        self.mini_player.show()

    def restore_main_window(self) -> None:
        if self.mini_player is not None:
            self.mini_player.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def open_settings(self) -> None:
        self.blur_effect.setEnabled(True)
        self.settings_overlay.show()

    def _on_theme_or_color_changed(self, _value: str) -> None:
        app = QApplication.instance()
        if app is not None:
            theme_manager.apply_theme(app, self.config)

        self.player_widget.set_glow_color(self.config.get_primary_color())
        self.tab_playlist.set_new_button_color(self.config.get_secondary_color())
        self.tab_playlist.set_primary_color(self.config.get_primary_color())
        self.tab_playlist.set_hover_background(theme_manager.get_hover_background(self.config))
        self._sync_tree_colors()
        self.player_widget.sync_output_combo_palette()

        if self.mini_player is not None:
            self.mini_player.refresh_panel_colors()

    def _sync_tree_colors(self) -> None:
        self.global_tree.row_delegate.set_hover_select_color(self.config.get_primary_color())
        self.global_tree.row_delegate.set_active_color(self.config.get_secondary_color())
        self.global_tree.row_delegate.set_hover_bg_color(theme_manager.get_hover_background(self.config))
        panel_bg, text_color, _, _ = theme_manager.get_neutral_dialog_colors(self.config)
        self.global_tree.sync_palette(panel_bg, text_color)
        self.global_tree.viewport().update()

    def hide_settings(self) -> None:
        self.blur_effect.setEnabled(False)

    def start_usb_search(self) -> None:
        self.blur_effect.setEnabled(True)
        self.overlay.set_searching_mode()
        self.overlay.show()

        # Clears the thread's "last known drives" cache: it only emits
        # state_changed when the detected list differs from the previous
        # poll, which is the right behavior for the thread running quietly
        # in the background, but means an already-detected drive (e.g. one
        # already selected earlier) would never get reported again on a
        # fresh manual search, since nothing actually changed from the
        # thread's point of view. Resetting this forces the very next poll
        # to report the current drives regardless.
        self.usb_thread.current_drives = None

        # A QThread can't be restarted directly once finished; 'running' is
        # what drives the loop in UsbDetectorThread.run(), so it's reset to
        # True before (re)starting.
        self.usb_thread.running = True
        if not self.usb_thread.isRunning():
            self.usb_thread.start()

    def cancel_usb_search(self) -> None:
        self.usb_thread.stop()
        self.blur_effect.setEnabled(False)
        self.overlay.hide()

    def open_folder_dialog(self) -> None:
        """Lets the user pick any system folder without needing a USB
        drive. USB auto-detection keeps running in parallel; this is just
        an alternative, manual way to set the working folder."""
        folder = QFileDialog.getExistingDirectory(self, "Choose Music Folder")
        if not folder:
            return

        self.blur_effect.setEnabled(False)
        self.overlay.hide()
        self.setWindowTitle(f"Music Organizer - Folder: {folder}")
        QTimer.singleShot(0, lambda: self.update_file_explorer(folder))

    def handle_before_mp3_rename(self, old_path: str) -> None:
        """Releases the QMediaPlayer's Windows file lock before the rename."""
        self.player_vm.load_single_mp3("")

    def handle_mp3_rename_success(self, new_path: str) -> None:
        """Refreshes the explorer and reloads the renamed file into the
        UI. Also fixes references in any .m3u under the root folder that
        pointed to the old filename, so the track doesn't silently
        disappear from existing playlists."""
        root = self.file_model.rootPath()
        if root and self._pending_old_path:
            PlaylistSyncManager.update_references(root, self._pending_old_path, new_path)
        self._pending_old_path = None

        self.refresh_explorer()
        self.music_vm.load_file(new_path)
        self.player_vm.load_single_mp3(new_path)
        self.global_tree.set_active_path(new_path)

    def handle_playlist_saved(self, file_path: str, tracks: list) -> None:
        self.refresh_explorer()
        self.player_vm.load_m3u_playlist(file_path)
        self.global_tree.set_active_path(file_path)

    def handle_playlist_cleared(self) -> None:
        if hasattr(self.player_vm, 'clear_queue'):
            self.player_vm.clear_queue()
        else:
            self.player_vm.load_m3u_playlist("")

    def refresh_explorer(self) -> None:
        QApplication.processEvents()

        current_root = self.file_model.rootPath()
        if current_root:
            self.global_tree.setRootIndex(self.file_model.index(current_root))

    def on_tree_double_clicked(self, index) -> None:
        if self.file_model.isDir(index):
            return

        file_path = self.file_model.filePath(index)

        if file_path.lower().endswith('.mp3'):
            self.tabs.setCurrentWidget(self.tab_music)
            self._pending_old_path = file_path
            self.music_vm.load_file(file_path)
            self.player_vm.load_single_mp3(file_path)
            self.global_tree.set_active_path(file_path)

        elif file_path.lower().endswith('.m3u'):
            self.tabs.setCurrentWidget(self.tab_playlist)
            self.playlist_vm.load_playlist(file_path)
            self.player_vm.load_m3u_playlist(file_path)
            self.global_tree.set_active_path(file_path)

    def edit_track_metadata(self, absolute_path: str) -> None:
        """Switches to the Music tab and loads the given file for editing.
        Called from the playlist's right-click context menu."""
        self.tabs.setCurrentWidget(self.tab_music)
        self._pending_old_path = absolute_path
        self.music_vm.load_file(absolute_path)
        self.global_tree.set_active_path(absolute_path)

    def handle_usb_state(self, state: str, drives: List[str]) -> None:
        if state == "SEARCHING":
            if not self.file_model.rootPath():
                self.setWindowTitle("Music Organizer - No Folder Selected")
            self.blur_effect.setEnabled(True)
            self.overlay.set_searching_mode()
            if not self.overlay.isVisible():
                self.overlay.show()

        elif state == "DRIVES_FOUND":
            self.blur_effect.setEnabled(True)
            self.overlay.update_drive_list(drives)
            if not self.overlay.isVisible():
                self.overlay.show()

    def on_drive_selected(self, drive_path: str, drive_label: str) -> None:
        self.blur_effect.setEnabled(False)
        self.overlay.hide()

        current_root = self.file_model.rootPath()
        if current_root and os.path.normpath(current_root).lower() == os.path.normpath(drive_path).lower():
            # Already the active drive — the app already keeps Music/
            # Playlist content in sync via the reloads that happen
            # naturally while playlists are created/edited/deleted and
            # metadata is edited, so there's nothing else to refresh here.
            return

        clean_letter = drive_path.strip("\\")
        self.setWindowTitle(f"Music Organizer - Drive: {clean_letter} [{drive_label}]")

        QTimer.singleShot(0, lambda: self.update_file_explorer(drive_path))

    def update_file_explorer(self, drive: str) -> None:
        self.blur_effect.setEnabled(False)
        self.overlay.hide()

        self.file_model.setRootPath(drive)
        self.refresh_explorer()

        self.music_vm.load_file("")
        self.playlist_vm.reset_state()
        self.global_tree.set_active_path("")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.usb_thread.stop()
        if self.mini_player is not None:
            # hide(), not close(): MiniPlayerWindow's own closeEvent
            # ignores the close and restores the main window instead,
            # which we don't want while the whole app is quitting.
            self.mini_player.hide()
        event.accept()
        # Explicit quit: quitOnLastWindowClosed is disabled (see main.py),
        # since the main window is only ever *hidden* while the mini
        # player is active, which would otherwise never count as "closed".
        QApplication.instance().quit()
