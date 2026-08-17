import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QListWidget, QListWidgetItem, QListView, QLineEdit,
                             QPushButton, QMessageBox, QAbstractItemView, QInputDialog,
                             QStyledItemDelegate, QStyle, QStyleOptionViewItem, QMenu,
                             QApplication)
from PyQt6.QtGui import (QKeyEvent, QDropEvent, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent,
                         QPainter, QColor, QPen, QIcon, QPixmap, QPalette, QFont)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF, QSize, QEvent, QTimer, QPropertyAnimation, QEasingCurve
from viewmodels.playlist_viewmodel import PlaylistViewModel
from core.audio_tools import AudioMetadataManager
from core.library_scanner import LibraryScanThread

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.main_window import MainWindow

# True if this item is the track currently loaded/playing in PlayerViewModel.
PLAYING_ROLE = Qt.ItemDataRole.UserRole + 100

# Title read from the file's ID3 metadata (or the filename without
# extension, as a fallback). Drawn in column 1 by the delegate; the item's
# actual text() stays the relative path (the source of truth used for
# saving/moving/etc.) and is only shown in column 3.
TITLE_ROLE = Qt.ItemDataRole.UserRole + 101

# Artist read from ID3 metadata (column 2).
ARTIST_ROLE = Qt.ItemDataRole.UserRole + 102


def _make_plus_icon(color_hex: str, size: int = 16) -> QIcon:
    """Hand-draws a "+" icon with QPainter instead of relying on a
    QPushButton's text glyph, whose padding/baseline varies across Qt
    styles and can end up visibly off-center on small buttons. Also lets
    the icon be recolored freely to follow the user's secondary color."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color_hex))
    pen.setWidth(2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    margin = 3
    mid = size / 2
    painter.drawLine(int(mid), margin, int(mid), size - margin)
    painter.drawLine(margin, int(mid), size - margin, int(mid))
    painter.end()

    return QIcon(pixmap)


def _make_person_icon(color_hex: str, size: int = 14) -> QIcon:
    """Small "person" glyph (head + shoulders) for the "new playlist from
    an artist" sub-option button. Same hand-drawn approach as
    _make_plus_icon, for the same reasons."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))

    head_d = size * 0.34
    head_rect = QRectF((size - head_d) / 2, size * 0.08, head_d, head_d)
    painter.drawEllipse(head_rect)

    shoulders_w = size * 0.66
    shoulders_h = size * 0.42
    shoulders_rect = QRectF((size - shoulders_w) / 2, size - shoulders_h - size * 0.08, shoulders_w, shoulders_h)
    radius = shoulders_w * 0.4
    painter.drawRoundedRect(shoulders_rect, radius, radius)

    painter.end()
    return QIcon(pixmap)


def _make_genre_icon(color_hex: str, size: int = 14) -> QIcon:
    """Small music-note glyph for the "new playlist from a genre" sub-
    option button. Same hand-drawn approach as _make_plus_icon, for the
    same reasons."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color_hex))
    pen.setWidth(2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    stem_x = size * 0.6
    stem_top = size * 0.14
    stem_bottom = size * 0.8
    painter.drawLine(int(stem_x), int(stem_top), int(stem_x), int(stem_bottom))
    painter.drawLine(int(stem_x), int(stem_top), int(size * 0.92), int(stem_top + size * 0.16))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))
    note_d = size * 0.3
    note_rect = QRectF(stem_x - note_d, stem_bottom - note_d * 0.62, note_d, note_d)
    painter.drawEllipse(note_rect)

    painter.end()
    return QIcon(pixmap)


class DropHighlightDelegate(QStyledItemDelegate):
    """Draws:
    1) each row split into 3 equal columns — Title (normal style), Artist
       (same small size as the path, but the title's color), and Path
       (small and faded) — instead of the single text a QListWidget would
       show by default;
    2) a neon line above or below the item being dragged over, to make it
       clear whether the dragged track will land before or after it;
    3) its own hover/selection highlight (a translucent fill plus
       left/right borders, inset from the left edge), with no dotted
       focus rectangle. Priority: live hover always wins (primary); a
       track marked "now playing" — the result of a double-click, or the
       "Play Music" context menu action — keeps a persistent secondary-
       colored marker even when it's no longer the actual click-selection;
       a plain single-click selection falls back to primary.
    """

    LEFT_PADDING = 10  # room for the "now playing" bar
    RIGHT_PADDING = 8
    COLUMN_GAP = 10
    SMALL_FONT_SIZE_DELTA = -2  # points smaller than normal (artist and path)
    HIGHLIGHT_LEFT_INSET = 8  # keeps the highlight clear of the "now playing" bar

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.hint_row = -1
        self.hint_above = True
        self.accent_color = "#00e5ff"        # drag-reorder hint line (primary)
        self.hover_select_color = "#00e5ff"  # hover/selection border (primary)
        self.playing_color = "#ff2bd6"       # "now playing" bar (secondary)
        self.hover_bg_color = "#2a2a30"

    def set_hint(self, row: int, above: bool) -> None:
        if self.hint_row == row and self.hint_above == above:
            return
        self.hint_row = row
        self.hint_above = above

    def clear_hint(self) -> None:
        self.hint_row = -1

    def set_accent_color(self, color_hex: str) -> None:
        self.accent_color = color_hex

    def set_hover_select_color(self, color_hex: str) -> None:
        self.hover_select_color = color_hex

    def set_playing_color(self, color_hex: str) -> None:
        self.playing_color = color_hex

    def set_hover_bg_color(self, color_hex: str) -> None:
        self.hover_bg_color = color_hex

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        # Suppress the default text (the full relative path); paint() draws
        # our own three-column text instead.
        option.text = ""

    def paint(self, painter: QPainter, option, index) -> None:
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        is_playing = bool(index.data(PLAYING_ROLE))

        # Paint the plain row (no native selection/hover fill and no
        # dotted focus rectangle) — the highlight below is drawn by hand
        # instead, so it can be inset from the left edge.
        plain_option = QStyleOptionViewItem(option)
        plain_option.state &= ~QStyle.StateFlag.State_Selected
        plain_option.state &= ~QStyle.StateFlag.State_MouseOver
        plain_option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, plain_option, index)

        rect = option.rect

        # Priority: live hover feedback always wins; otherwise a track
        # marked "now playing" (the result of a double-click, or the
        # "Play Music" context menu action) keeps its secondary-colored
        # marker even when it's no longer the actual click-selection;
        # a plain single-click selection falls back to primary.
        highlight_color = None
        if is_hover:
            highlight_color = self.hover_select_color
        elif is_playing:
            highlight_color = self.playing_color
        elif is_selected:
            highlight_color = self.hover_select_color

        if highlight_color:
            highlight_rect = QRect(
                rect.left() + self.HIGHLIGHT_LEFT_INSET, rect.top(),
                rect.width() - self.HIGHLIGHT_LEFT_INSET, rect.height()
            )
            painter.save()
            # Same neutral gray fill as the explorer's own hover/selected
            # rows; only the left/right accent differs between lists.
            painter.fillRect(highlight_rect, QColor(self.hover_bg_color))
            pen = QPen(QColor(highlight_color))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(highlight_rect.left(), rect.top(), highlight_rect.left(), rect.bottom())
            painter.drawLine(highlight_rect.right(), rect.top(), highlight_rect.right(), rect.bottom())
            painter.restore()

        title_color = option.palette.color(QPalette.ColorRole.Text)

        path_color = QColor(title_color)
        path_color.setAlpha(150)

        title = index.data(TITLE_ROLE) or index.data(Qt.ItemDataRole.DisplayRole) or ""
        artist = index.data(ARTIST_ROLE) or ""
        path_text = index.data(Qt.ItemDataRole.DisplayRole) or ""

        normal_font = option.font
        small_font = QFont(normal_font)
        small_font.setPointSize(max(7, normal_font.pointSize() + self.SMALL_FONT_SIZE_DELTA))

        text_rect = QRect(
            rect.left() + self.LEFT_PADDING, rect.top(),
            rect.width() - self.LEFT_PADDING - self.RIGHT_PADDING, rect.height()
        )

        column_width = (text_rect.width() - 2 * self.COLUMN_GAP) / 3
        title_rect = QRect(text_rect.left(), text_rect.top(), int(column_width), text_rect.height())
        artist_rect = QRect(
            title_rect.right() + self.COLUMN_GAP, text_rect.top(), int(column_width), text_rect.height()
        )
        path_rect = QRect(
            artist_rect.right() + self.COLUMN_GAP, text_rect.top(),
            text_rect.right() - (artist_rect.right() + self.COLUMN_GAP), text_rect.height()
        )

        painter.save()

        painter.setFont(normal_font)
        title_metrics = painter.fontMetrics()
        elided_title = title_metrics.elidedText(title, Qt.TextElideMode.ElideRight, title_rect.width())
        painter.setPen(title_color)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)

        painter.setFont(small_font)
        small_metrics = painter.fontMetrics()
        elided_artist = small_metrics.elidedText(artist, Qt.TextElideMode.ElideRight, artist_rect.width())
        painter.setPen(title_color)
        painter.drawText(artist_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_artist)

        elided_path = small_metrics.elidedText(path_text, Qt.TextElideMode.ElideLeft, path_rect.width())
        painter.setPen(path_color)
        painter.drawText(path_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, elided_path)

        painter.restore()

        if index.row() == self.hint_row:
            pen = QPen(QColor(self.accent_color))
            pen.setWidth(3)
            painter.save()
            painter.setPen(pen)
            y = rect.top() + 1 if self.hint_above else rect.bottom() - 1
            painter.drawLine(rect.left() + 4, y, rect.right() - 4, y)
            painter.restore()


class PlaylistEditorList(QListWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_tab: PlaylistTab = parent
        self.setObjectName("playlistEditorList")
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setMovement(QListView.Movement.Snap)
        # The native Qt drop indicator and our custom line computed
        # position slightly differently, causing a visual "jump" near item
        # boundaries. Since we draw our own indicator in the delegate, the
        # native one is disabled.
        self.setDropIndicatorShown(False)

        # Without this, Qt only updates the "hovered index" state on
        # button press/release, not as the mouse simply moves over rows —
        # which is why the custom hover highlight painted by the delegate
        # (see DropHighlightDelegate.paint) never showed up.
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.drop_delegate = DropHighlightDelegate(self)
        self.setItemDelegate(self.drop_delegate)

        # Qt's default partial-repaint region for a hover change moving
        # smoothly through a row isn't always the full row rect, which
        # left a dotted/broken trail of un-cleared highlight behind fast
        # mouse movement. Forcing a full viewport repaint on every row
        # change fixes that at a negligible cost for a list this size.
        self.entered.connect(lambda _index: self.viewport().update())

        # `entered` only fires while the cursor sits over a valid item, so
        # moving from the last row down into the empty space below it (no
        # item there, but still inside the viewport) never emits it — the
        # last-hovered row's highlight was left painted on screen with
        # nothing to trigger clearing it. mouseMoveEvent covers that gap
        # too, since it also runs over the empty area below the items.
        self._last_hover_row = -1

        # Likewise, changing the selection purely by clicking a different
        # row (no further mouse movement afterwards) can leave the
        # *previous* row's hand-painted border/fill on screen — Qt's own
        # partial repaint on selection change doesn't reliably clear the
        # delegate's custom-drawn extras. Forcing a full repaint on every
        # selection change closes that gap.
        self.itemSelectionChanged.connect(self.viewport().update)

        self.itemDoubleClicked.connect(self.handle_item_double_click)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def handle_item_double_click(self, item: QListWidgetItem) -> None:
        self._play_item(item)

    def _play_item(self, item: QListWidgetItem) -> None:
        """Finds the given file in the Player's current queue and jumps to
        it, so the right track plays even if the visual list has been
        reordered but not saved to disk yet."""
        main_win: "MainWindow" = self.window()
        if not (main_win and hasattr(main_win, 'player_widget')):
            return

        playlist_file = self.parent_tab.vm.current_playlist_file
        if not playlist_file:
            return

        track_path = self._resolve_absolute_path(item)
        if not track_path:
            return

        player_vm = main_win.player_widget.vm
        for idx, path in enumerate(player_vm.playlist_queue):
            if os.path.normpath(path).lower() == track_path.lower():
                player_vm.jump_to_queue_index(idx)
                break

    def _resolve_absolute_path(self, item: QListWidgetItem) -> str:
        playlist_file = self.parent_tab.vm.current_playlist_file
        if not playlist_file:
            return ""
        playlist_dir = os.path.dirname(playlist_file)
        return os.path.normpath(os.path.join(playlist_dir, item.text()))

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None:
            return

        if item not in self.selectedItems():
            self.clearSelection()
            item.setSelected(True)
            self.setCurrentItem(item)

        menu = QMenu(self)
        menu.setCursor(Qt.CursorShape.PointingHandCursor)
        play_action = menu.addAction("Play Music")
        edit_action = menu.addAction("Edit Metadata")
        remove_action = menu.addAction("Remove from Playlist")

        chosen = menu.exec(self.viewport().mapToGlobal(pos))

        if chosen == play_action:
            self._play_item(item)
        elif chosen == edit_action:
            self._request_edit_metadata(item)
        elif chosen == remove_action:
            self._remove_selected_items()

    def _request_edit_metadata(self, item: QListWidgetItem) -> None:
        abs_path = self._resolve_absolute_path(item)
        if abs_path:
            self.parent_tab.edit_metadata_requested.emit(abs_path)

    def _remove_selected_items(self) -> None:
        for item in self.selectedItems():
            self.takeItem(self.row(item))
        self.parent_tab.evaluate_save_button()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self._remove_selected_items()
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)

        # Repaint whenever the hovered row changes, including transitions
        # to/from the empty space below the last item (row == -1), which
        # `entered` alone doesn't cover — see the comment in __init__.
        row = self.indexAt(event.position().toPoint()).row()
        if row != self._last_hover_row:
            self._last_hover_row = row
            self.viewport().update()

    def leaveEvent(self, event) -> None:
        # Otherwise the last-hovered row's highlight can linger after the
        # mouse actually leaves the list entirely.
        self._last_hover_row = -1
        self.viewport().update()
        super().leaveEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.source() == self or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.source() == self or event.mimeData().hasUrls():
            self._update_drop_hint(event)
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.drop_delegate.clear_hint()
        self.viewport().update()
        super().dragLeaveEvent(event)

    def _update_drop_hint(self, event: QDragMoveEvent) -> None:
        """Computes a single canonical insertion position and always maps
        it to the same visual rule: a line below the item before the
        insertion point, except when inserting at the very start of the
        list, which draws above the first item.

        This avoids the earlier ambiguity where the same logical position
        could be represented either as "below item i" or "above item i+1"
        depending on which half of the item the cursor was over, which
        made the line appear to jump."""
        pos = event.position().toPoint()
        index = self.indexAt(pos)

        if index.isValid():
            rect = self.visualRect(index)
            insertion_index = index.row() if pos.y() < rect.center().y() else index.row() + 1
        else:
            insertion_index = self.count()

        if self.count() == 0:
            self.drop_delegate.clear_hint()
        elif insertion_index <= 0:
            self.drop_delegate.set_hint(0, above=True)
        else:
            self.drop_delegate.set_hint(insertion_index - 1, above=False)

        self.viewport().update()

    def dropEvent(self, event: QDropEvent) -> None:
        self.drop_delegate.clear_hint()
        self.viewport().update()

        if event.source() == self:
            super().dropEvent(event)  # native visual reordering
            return

        if not self.parent_tab.vm.current_playlist_file:
            QMessageBox.warning(self, "Warning", "Open or create a playlist first.")
            return

        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile().lower().endswith('.mp3')]
            if paths:
                self.parent_tab.add_multiple_mp3s(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class PlaylistTab(QWidget):
    PLAYING_BACKGROUND = QColor(0, 229, 255, 40)

    edit_metadata_requested = pyqtSignal(str)  # absolute path of the track to edit

    def __init__(self, view_model: PlaylistViewModel) -> None:
        super().__init__()
        self.vm = view_model
        self._current_playing_abs_path: str = ""
        self._scan_thread: LibraryScanThread | None = None
        self.init_ui()
        self.bind_viewmodel()
        self._setup_new_playlist_drawer()
        # Clicking anywhere outside the playlist area (but not on its own
        # action buttons/name field) clears its selection, without ever
        # touching the explorer's own selection.
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            clicked = QApplication.widgetAt(event.globalPosition().toPoint())
            if clicked is not None and not self._is_within_playlist_area(clicked):
                self.playlist_list.clearSelection()
        elif obj in (self.btn_new, self.btn_by_artist, self.btn_by_genre):
            # Keeps the "+" sub-option drawer open while the cursor is over
            # any of the three buttons, and starts the auto-close countdown
            # the moment it leaves all of them (restarted/cancelled by the
            # next Enter, so hopping between the three never closes it).
            if event.type() == QEvent.Type.Enter:
                self._open_new_playlist_drawer()
            elif event.type() == QEvent.Type.Leave:
                self._drawer_hide_timer.start()
        return super().eventFilter(obj, event)

    def _is_within_playlist_area(self, widget) -> bool:
        protected = (self.playlist_list, self.btn_new, self.btn_by_artist, self.btn_by_genre,
                     self.btn_save, self.btn_delete, self.btn_clear, self.edit_name)
        w = widget
        while w is not None:
            if w in protected:
                return True
            w = w.parentWidget()
        return False

    def _setup_new_playlist_drawer(self) -> None:
        """Wires up the slide-open/auto-close behavior for the "+" button's
        Artist/Genre sub-options (see the drawer_container built in
        init_ui). A single animation on the container's own maximumHeight
        does the "cascade" reveal: as it grows top-down, Artist (closer to
        "+") is uncovered first and Genre shortly after, like a drawer
        opening — no need to juggle two separate per-button animations."""
        self._drawer_open = False
        self._drawer_anim: QPropertyAnimation | None = None

        self._drawer_hide_timer = QTimer(self)
        self._drawer_hide_timer.setSingleShot(True)
        self._drawer_hide_timer.setInterval(2500)
        self._drawer_hide_timer.timeout.connect(self._close_new_playlist_drawer)

        for btn in (self.btn_new, self.btn_by_artist, self.btn_by_genre):
            btn.installEventFilter(self)

    def _animate_drawer_to(self, target_height: int, easing: QEasingCurve.Type) -> None:
        # A fresh QPropertyAnimation per call (instead of restarting one
        # long-lived instance) avoids relying on stop()/start() leaving a
        # perfectly clean internal state across many rapid open/close
        # cycles — cheap to create, and there's never more than one alive.
        if self._drawer_anim is not None:
            self._drawer_anim.stop()

        anim = QPropertyAnimation(self.drawer_container, b"maximumHeight", self)
        anim.setDuration(280)
        anim.setEasingCurve(easing)
        anim.setStartValue(self.drawer_container.maximumHeight())
        anim.setEndValue(target_height)
        # Driving maximumHeight alone leaves the widget's *actual* height
        # governed only by whatever the parent QVBoxLayout last computed
        # for it — after it's been collapsed to 0 once, some later resizes
        # don't reliably trigger a fresh layout pass on their own. Pinning
        # minimumHeight to the same value on every frame removes that
        # ambiguity and keeps the drawer's visible height in lockstep with
        # the animation instead of jumping straight to its end state.
        anim.valueChanged.connect(lambda value: self.drawer_container.setMinimumHeight(value))
        self._drawer_anim = anim
        anim.start()

    def _open_new_playlist_drawer(self) -> None:
        self._drawer_hide_timer.stop()
        if self._drawer_open:
            return
        self._drawer_open = True
        target_height = self.drawer_container.sizeHint().height()
        self._animate_drawer_to(target_height, QEasingCurve.Type.OutCubic)

    def _close_new_playlist_drawer(self) -> None:
        if not self._drawer_open:
            return
        self._drawer_open = False
        self._animate_drawer_to(0, QEasingCurve.Type.InCubic)

    def init_ui(self) -> None:
        self.setObjectName("playlistTab")

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.edit_name = QLineEdit()
        self.edit_name.setMaxLength(30)
        # "M" is the widest possible character, so sizing off 33 of them
        # left a large gap for any realistic text. Average char width for
        # the 30-char limit, plus a small buffer matching the field's own
        # left inset, fits much closer to what people actually type.
        name_metrics = self.edit_name.fontMetrics()
        self.edit_name.setFixedWidth(name_metrics.averageCharWidth() * 38 + 24)
        form_layout.addRow("Playlist Name:", self.edit_name)
        layout.addLayout(form_layout)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        self.playlist_list = PlaylistEditorList(self)
        content_layout.addWidget(self.playlist_list, 1)

        self.button_column_widget = QWidget()
        self.button_column_widget.setObjectName("playlistButtonColumn")
        button_column = QVBoxLayout(self.button_column_widget)
        button_column.setContentsMargins(10, 10, 10, 10)
        button_column.setSpacing(0)

        self.btn_new = QPushButton()
        self.btn_new.setObjectName("btnNewPlaylist")
        self.btn_new.setFixedSize(40, 40)
        self.btn_new.setIconSize(QSize(18, 18))
        self.btn_new.setIcon(_make_plus_icon("#ff2bd6"))
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setToolTip("New playlist")
        button_column.addWidget(self.btn_new)

        # "New playlist by Artist/Genre" — smaller sub-option buttons that
        # slide open beneath "+" like a drawer on hover, and auto-close a
        # couple of seconds after the mouse leaves all three buttons. See
        # _open_new_playlist_drawer/_close_new_playlist_drawer and the
        # Enter/Leave handling added to eventFilter() below.
        self.drawer_container = QWidget()
        self.drawer_container.setObjectName("playlistNewDrawer")
        self.drawer_container.setMaximumHeight(0)
        drawer_layout = QVBoxLayout(self.drawer_container)
        # Bigger gap between "+" and the first sub-option (matches the
        # Delete->Clear gap below); no side margins so AlignHCenter below
        # can center the (narrower) sub-buttons under "+" on its own.
        drawer_layout.setContentsMargins(0, 20, 0, 0)
        drawer_layout.setSpacing(0)

        self.btn_by_artist = QPushButton()
        self.btn_by_artist.setObjectName("btnPlaylistSubOption")
        self.btn_by_artist.setFixedSize(30, 30)
        self.btn_by_artist.setIconSize(QSize(14, 14))
        self.btn_by_artist.setIcon(_make_person_icon("#ff2bd6"))
        self.btn_by_artist.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_by_artist.setToolTip("New playlist from an artist")
        drawer_layout.addWidget(self.btn_by_artist, 0, Qt.AlignmentFlag.AlignHCenter)

        # Same gap as the one between Save and Delete.
        drawer_layout.addSpacing(10)

        self.btn_by_genre = QPushButton()
        self.btn_by_genre.setObjectName("btnPlaylistSubOption")
        self.btn_by_genre.setFixedSize(30, 30)
        self.btn_by_genre.setIconSize(QSize(14, 14))
        self.btn_by_genre.setIcon(_make_genre_icon("#ff2bd6"))
        self.btn_by_genre.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_by_genre.setToolTip("New playlist from a genre")
        drawer_layout.addWidget(self.btn_by_genre, 0, Qt.AlignmentFlag.AlignHCenter)

        button_column.addWidget(self.drawer_container)

        # Large flexible gap, free for future options below "+"
        button_column.addStretch(1)

        self.btn_save = QPushButton("💾")
        self.btn_save.setObjectName("btnSavePlaylist")
        self.btn_save.setFixedSize(40, 40)
        self.btn_save.setToolTip("Save")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        button_column.addWidget(self.btn_save)

        # Matches the spacing between the Open Folder / Search USB Drive
        # toolbar buttons
        button_column.addSpacing(10)

        self.btn_delete = QPushButton("🗑")
        self.btn_delete.setObjectName("btnDeletePlaylist")
        self.btn_delete.setFixedSize(40, 40)
        self.btn_delete.setToolTip("Delete")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        button_column.addWidget(self.btn_delete)

        # Sets Clear apart from Save/Delete
        button_column.addSpacing(20)

        self.btn_clear = QPushButton("✕")
        self.btn_clear.setObjectName("btnClearPlaylist")
        self.btn_clear.setFixedSize(40, 40)
        self.btn_clear.setToolTip("Clear")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        button_column.addWidget(self.btn_clear)

        content_layout.addWidget(self.button_column_widget, 0)

        layout.addLayout(content_layout)

        self.set_controls_enabled(False)

    def bind_viewmodel(self) -> None:
        self.vm.playlist_loaded.connect(self.on_playlist_loaded)
        self.vm.tracks_updated.connect(self.on_tracks_updated)
        self.vm.playlist_saved.connect(self.on_save_success)
        self.vm.playlist_cleared.connect(self.on_playlist_cleared)
        self.vm.error_occurred.connect(lambda msg: QMessageBox.critical(self, "Error", msg))

        self.edit_name.textChanged.connect(lambda: self.evaluate_save_button())

        self.btn_new.clicked.connect(self.on_new_playlist_clicked)
        self.btn_by_artist.clicked.connect(self.on_new_playlist_by_artist_clicked)
        self.btn_by_genre.clicked.connect(self.on_new_playlist_by_genre_clicked)
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_delete.clicked.connect(self.on_delete_clicked)
        self.btn_clear.clicked.connect(self.vm.reset_state)

    def set_controls_enabled(self, enabled: bool) -> None:
        if not enabled:
            self.btn_save.setEnabled(False)
        self.btn_delete.setEnabled(enabled)
        self.btn_clear.setEnabled(enabled)
        self.edit_name.setEnabled(enabled)

    def on_new_playlist_clicked(self) -> None:
        main_win: "MainWindow" = self.window()
        if not main_win or not hasattr(main_win, 'file_model'):
            QMessageBox.warning(self, "Warning", "Please wait for USB drive detection.")
            return

        root = main_win.file_model.rootPath()
        if not root:
            QMessageBox.warning(self, "Warning", "No folder or USB drive selected.")
            return

        name, ok = QInputDialog.getText(self, "New Playlist", "Enter the new playlist name:")
        if ok and name.strip():
            self.vm.create_empty_playlist(root, name)

    def on_new_playlist_by_artist_clicked(self) -> None:
        self._start_smart_playlist_flow(
            field="artist",
            dialog_title="New Playlist by Artist",
            prompt="Enter the artist's name (this also becomes the playlist name):",
        )

    def on_new_playlist_by_genre_clicked(self) -> None:
        self._start_smart_playlist_flow(
            field="genre",
            dialog_title="New Playlist by Genre",
            prompt="Enter the genre's name (this also becomes the playlist name):",
        )

    def _start_smart_playlist_flow(self, field: str, dialog_title: str, prompt: str) -> None:
        """Shared "by Artist"/"by Genre" flow: ask for the name (used both
        as the match criteria and as the playlist's own title), then scan
        the active drive/folder for it in the background (see
        core/library_scanner.py) and drop the results straight into the
        normal load flow, same as clicking an item in the explorer would."""
        if self._scan_thread is not None:
            QMessageBox.information(self, "Please wait", "Already scanning the library — please wait for it to finish.")
            return

        main_win: "MainWindow" = self.window()
        if not main_win or not hasattr(main_win, 'file_model'):
            QMessageBox.warning(self, "Warning", "Please wait for USB drive detection.")
            return

        root = main_win.file_model.rootPath()
        if not root:
            QMessageBox.warning(self, "Warning", "No folder or USB drive selected.")
            return

        value, ok = QInputDialog.getText(self, dialog_title, prompt)
        value = value.strip()
        if not (ok and value):
            return

        self._set_scanning_state(True)

        self._scan_thread = LibraryScanThread(root, field, value, self)
        self._scan_thread.finished_ok.connect(lambda matches: self._on_scan_finished(matches, root, value))
        self._scan_thread.failed.connect(self._on_scan_failed)
        self._scan_thread.finished.connect(self._on_scan_thread_done)
        self._scan_thread.start()

    def _set_scanning_state(self, scanning: bool) -> None:
        self.btn_new.setEnabled(not scanning)
        self.btn_by_artist.setEnabled(not scanning)
        self.btn_by_genre.setEnabled(not scanning)
        if scanning:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _on_scan_finished(self, matches: list, root: str, name: str) -> None:
        if not matches:
            QMessageBox.information(self, "No tracks found", f'No .mp3 files matched "{name}".')
            return

        relative_tracks = [os.path.relpath(path, start=root).replace('\\', '/') for path in matches]
        self.vm.create_playlist_from_tracks(root, name, relative_tracks)

    def _on_scan_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Error", f"Failed to scan the library:\n{message}")

    def _on_scan_thread_done(self) -> None:
        # Runs after finished_ok/failed either way, so the drive can't get
        # stuck "busy" if a scan raises partway through.
        self._set_scanning_state(False)
        self._scan_thread = None

    def on_playlist_loaded(self, name: str, tracks: list) -> None:
        self.edit_name.setText(name)
        self._populate_track_items(tracks)
        self.set_controls_enabled(True)
        self.evaluate_save_button()
        self._apply_playing_highlight()

    def on_tracks_updated(self, tracks: list) -> None:
        self._populate_track_items(tracks)
        self.evaluate_save_button()
        self._apply_playing_highlight()

    def _populate_track_items(self, tracks: list) -> None:
        """Rebuilds the list, reading each file's ID3 title/artist for the
        delegate to paint (see DropHighlightDelegate). The item's own
        text() always stays the relative path — the source of truth used
        elsewhere (saving, moving, locating in the player queue); title
        and artist are stored only as extra data (TITLE_ROLE/ARTIST_ROLE)
        for display."""
        self.playlist_list.clear()

        playlist_file = self.vm.current_playlist_file
        playlist_dir = os.path.dirname(playlist_file) if playlist_file else ""

        for rel_path in tracks:
            title, artist = self._read_track_metadata(playlist_dir, rel_path)
            item = QListWidgetItem(rel_path)
            item.setData(TITLE_ROLE, title)
            item.setData(ARTIST_ROLE, artist)
            self.playlist_list.addItem(item)

    def _read_track_metadata(self, playlist_dir: str, rel_path: str) -> tuple:
        """Returns (title, artist). Falls back to the filename (without
        extension) as the title if there's no tag; artist is empty if
        there's no tag or no folder to resolve the absolute path."""
        fallback_title = os.path.splitext(os.path.basename(rel_path))[0]
        if not playlist_dir:
            return fallback_title, ""

        abs_path = os.path.normpath(os.path.join(playlist_dir, rel_path))
        metadata = AudioMetadataManager.read_metadata(abs_path)
        if not metadata:
            return fallback_title, ""

        title = metadata.get("title") or fallback_title
        artist = metadata.get("artist") or ""
        return title, artist

    def add_multiple_mp3s(self, file_paths: list) -> None:
        current_tracks = [self.playlist_list.item(i).text() for i in range(self.playlist_list.count())]
        self.vm.add_tracks(file_paths, current_tracks)

    def on_save_clicked(self) -> None:
        tracks = [self.playlist_list.item(i).text() for i in range(self.playlist_list.count())]
        self.vm.save_playlist(self.edit_name.text(), tracks)

    def on_delete_clicked(self) -> None:
        confirm = QMessageBox.question(
            self, "Confirm", "Are you sure you want to delete this playlist?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.vm.delete_playlist()

    def on_save_success(self, new_path: str, tracks: list) -> None:
        QMessageBox.information(self, "Success", "Playlist saved successfully!")

        main_win: "MainWindow" = self.window()
        if main_win and hasattr(main_win, 'handle_playlist_saved'):
            main_win.handle_playlist_saved(new_path, tracks)

    def on_playlist_cleared(self) -> None:
        self.edit_name.clear()
        self.playlist_list.clear()
        self.set_controls_enabled(False)
        self.edit_name.setEnabled(False)

    def get_current_songs_list(self) -> list[str]:
        return [self.playlist_list.item(i).text() for i in range(self.playlist_list.count())]

    def set_new_button_color(self, color_hex: str) -> None:
        """Recolors the '+' icon and its Artist/Genre sub-option icons, plus
        the playlist's "now playing" bar (called by MainWindow when the
        secondary color changes in Settings). None of these are covered by
        the shared QSS: the icons are hand-drawn (see _make_plus_icon and
        friends), and the bar is painted by DropHighlightDelegate — it only
        exists as a result of a double-click, so it uses the secondary
        color distinctly from the primary-colored hover/selection
        highlight."""
        self.btn_new.setIcon(_make_plus_icon(color_hex))
        self.btn_by_artist.setIcon(_make_person_icon(color_hex))
        self.btn_by_genre.setIcon(_make_genre_icon(color_hex))
        self.playlist_list.drop_delegate.set_playing_color(color_hex)
        self.playlist_list.viewport().update()

    def set_primary_color(self, color_hex: str) -> None:
        """Recolors the hover/selection highlight and the drag-and-drop
        hint line (called by MainWindow when the primary color changes in
        Settings). Both are painted by DropHighlightDelegate, so they
        aren't covered by the shared QSS."""
        self.playlist_list.drop_delegate.set_accent_color(color_hex)
        self.playlist_list.drop_delegate.set_hover_select_color(color_hex)
        self.playlist_list.viewport().update()

    def set_hover_background(self, color_hex: str) -> None:
        """Matches the row hover/selected fill to the theme's neutral gray
        (the same one used by the explorer), since it isn't covered by the
        shared QSS — DropHighlightDelegate paints it by hand so it can stay
        inset from the "now playing" bar."""
        self.playlist_list.drop_delegate.set_hover_bg_color(color_hex)
        self.playlist_list.viewport().update()

    def evaluate_save_button(self) -> None:
        has_name = bool(self.edit_name.text().strip())
        has_tracks = self.playlist_list.count() > 0
        self.btn_save.setEnabled(has_name and has_tracks)

    # ---------------- Now-playing highlight ----------------

    def highlight_current_track(self, current_abs_path: str) -> None:
        """Called by MainWindow whenever the playing track changes, to mark
        that item in the list (if it belongs to the currently open playlist)."""
        self._current_playing_abs_path = current_abs_path
        self._apply_playing_highlight()

    def _apply_playing_highlight(self) -> None:
        playlist_file = self.vm.current_playlist_file
        target_abs = os.path.normpath(self._current_playing_abs_path).lower() if self._current_playing_abs_path else ""

        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            is_playing = False

            if playlist_file and target_abs:
                playlist_dir = os.path.dirname(playlist_file)
                item_abs = os.path.normpath(os.path.join(playlist_dir, item.text())).lower()
                is_playing = item_abs == target_abs

            item.setData(PLAYING_ROLE, is_playing)
            item.setBackground(self.PLAYING_BACKGROUND if is_playing else QColor(0, 0, 0, 0))

        self.playlist_list.viewport().update()
