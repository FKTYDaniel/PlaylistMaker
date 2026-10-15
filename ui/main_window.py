from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QGraphicsBlurEffect, QSplitter, QTreeView, QAbstractItemView,
                             QLabel, QPushButton, QFileDialog, QSizePolicy, QApplication,
                             QStyledItemDelegate, QStyle, QStyleOptionViewItem, QProxyStyle)
from PyQt6.QtGui import QCloseEvent, QFileSystemModel, QKeyEvent, QPainter, QColor, QPen, QPalette, QPolygonF
from PyQt6.QtCore import Qt, QDir, QTimer, pyqtSignal, QRect, QModelIndex, QPointF, QEvent
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
    """Paints the explorer's hover/selection border, plus a persistent
    marker on whichever file is currently open."""

    HIGHLIGHT_INSET = 4
    HIGHLIGHT_RIGHT_INSET = 4
    CONTENT_PADDING = 6

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
        plain_option.rect = option.rect.adjusted(
            self.HIGHLIGHT_INSET + self.CONTENT_PADDING, 0, -self.CONTENT_PADDING, 0
        )

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

        # Painted first, then the icon/text on top via super().paint()
        # below, so the fill doesn't cover the text.
        if color is not None:
            highlight_rect = QRect(
                rect.left() + self.HIGHLIGHT_INSET, rect.top(),
                rect.width() - self.HIGHLIGHT_INSET - self.HIGHLIGHT_RIGHT_INSET, rect.height()
            )
            painter.save()
            # Clipped to this row's own rect so the 2px pen's stroke
            # doesn't bleed 1px into the neighboring row.
            painter.setClipRect(rect)
            painter.fillRect(highlight_rect, QColor(self.hover_bg_color))
            pen = QPen(QColor(color))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(highlight_rect.left(), rect.top(), highlight_rect.left(), rect.bottom())
            painter.drawLine(highlight_rect.right() - 1, rect.top(), highlight_rect.right() - 1, rect.bottom())
            painter.restore()

        super().paint(painter, plain_option, index)


class ArrowBranchStyle(QProxyStyle):
    """Draws the explorer's expand/collapse arrows by hand, in the user's
    primary color (QSS can't recolor the built-in arrow at runtime)."""

    def __init__(self, base_style: QStyle) -> None:
        super().__init__(base_style)
        self._arrow_color = QColor("#00e5ff")

    def set_arrow_color(self, color_hex: str) -> None:
        self._arrow_color = QColor(color_hex)

    def drawPrimitive(self, element, option, painter, widget=None) -> None:
        if element != QStyle.PrimitiveElement.PE_IndicatorBranch:
            super().drawPrimitive(element, option, painter, widget)
            return

        if not (option.state & QStyle.StateFlag.State_Children):
            return  # Leaf item: no arrow, and no connecting guide lines.

        rect = option.rect
        size = min(rect.width(), rect.height()) * 0.16
        cx, cy = rect.center().x(), rect.center().y()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._arrow_color)

        if option.state & QStyle.StateFlag.State_Open:
            points = [QPointF(cx - size, cy - size * 0.55),
                      QPointF(cx + size, cy - size * 0.55),
                      QPointF(cx, cy + size * 0.55)]
        else:
            points = [QPointF(cx - size * 0.55, cy - size),
                      QPointF(cx - size * 0.55, cy + size),
                      QPointF(cx + size * 0.55, cy)]

        painter.drawPolygon(QPolygonF(points))
        painter.restore()


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

        self._arrow_style = ArrowBranchStyle(self.style())
        self.setStyle(self._arrow_style)

        # Clicking anywhere on a folder's row expands/collapses it, not
        # just the arrow itself.
        self.clicked.connect(self._toggle_expand_on_click)

        self.setMouseTracking(True)
        self.entered.connect(lambda _index: self.viewport().update())
        self.selectionModel().selectionChanged.connect(lambda *_: self.viewport().update())

        self._last_hover_index = QModelIndex()

    def _toggle_expand_on_click(self, index) -> None:
        if self.file_model.isDir(index):
            self.setExpanded(index, not self.isExpanded(index))

    def _update_hover_index(self, index) -> None:
        """Compares the actual QModelIndex, not row(): the same row()
        number can belong to different items in different folders."""
        if index != self._last_hover_index:
            self._last_hover_index = index
            self.viewport().update()

    def viewportEvent(self, event) -> bool:
        """Reads MouseMove/Leave off the viewport directly, since the
        view's own mouseMoveEvent/leaveEvent misses some exit paths."""
        if event.type() == QEvent.Type.MouseMove:
            self._update_hover_index(self.indexAt(event.position().toPoint()))
        elif event.type() == QEvent.Type.Leave:
            self._update_hover_index(QModelIndex())
        return super().viewportEvent(event)

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        self._update_hover_index(self.indexAt(event.position().toPoint()))

    def sync_palette(self, base_hex: str, text_hex: str) -> None:
        """Matches QPalette::Highlight to the normal background, so the
        native branch/arrow strip doesn't show a mismatched accent color."""
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor(base_hex))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(text_hex))
        self.setPalette(palette)

    def set_arrow_color(self, color_hex: str) -> None:
        self._arrow_style.set_arrow_color(color_hex)
        self.viewport().update()

    def set_active_path(self, path: str) -> None:
        self.row_delegate.set_active_path(path)
        self.viewport().update()

    def leaveEvent(self, event) -> None:
        self._update_hover_index(QModelIndex())
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

        # Created before PlayerViewModel so it can restore the saved volume.
        self.config = ConfigManager()

        self.player_vm = PlayerViewModel(self.config)
        self.playlist_vm = PlaylistViewModel()
        self.music_vm = MusicViewModel()

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
        self.tab_playlist.repeat_mode_changed.connect(self.player_vm.set_repeat_mode)

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

        # The play button's glow and icons are painted directly (not
        # covered by QSS), so sync them with the saved config manually.
        self.player_widget.set_glow_color(self.config.get_primary_color())
        self.player_widget.set_icon_color(self.config.get_secondary_color())
        self.tab_playlist.set_new_button_color(self.config.get_secondary_color())
        self.tab_playlist.set_primary_color(self.config.get_primary_color())
        self.tab_playlist.set_hover_background(theme_manager.get_hover_background(self.config))
        self._sync_tree_colors()
        self.player_widget.sync_output_combo_palette()

        self.usb_thread = UsbDetectorThread()
        self.usb_thread.state_changed.connect(self.handle_usb_state)

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
        self.player_widget.set_icon_color(self.config.get_secondary_color())
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
        self.global_tree.set_arrow_color(self.config.get_primary_color())
        panel_bg, text_color, _, _ = theme_manager.get_neutral_dialog_colors(self.config)
        self.global_tree.sync_palette(panel_bg, text_color)
        self.global_tree.viewport().update()

    def hide_settings(self) -> None:
        self.blur_effect.setEnabled(False)

    def start_usb_search(self) -> None:
        self.blur_effect.setEnabled(True)
        self.overlay.set_searching_mode()
        self.overlay.show()

        # Reset so the next poll reports current drives even if nothing
        # actually changed since the last background check.
        self.usb_thread.current_drives = None

        # A finished QThread can't be restarted directly; 'running' drives
        # the loop in UsbDetectorThread.run().
        self.usb_thread.running = True
        if not self.usb_thread.isRunning():
            self.usb_thread.start()

    def cancel_usb_search(self) -> None:
        self.usb_thread.stop()
        self.blur_effect.setEnabled(False)
        self.overlay.hide()

    def open_folder_dialog(self) -> None:
        """Lets the user pick any system folder as an alternative to a
        USB drive."""
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
        """Refreshes the explorer, reloads the renamed file, and fixes
        references to it in any .m3u under the root folder."""
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
            return  # already the active drive

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
            # would otherwise just restore the main window.
            self.mini_player.hide()
        event.accept()
        QApplication.instance().quit()
