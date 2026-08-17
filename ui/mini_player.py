from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication
from PyQt6.QtCore import Qt, QTime, QTimer, pyqtSignal, QPoint, QPropertyAnimation, QEasingCurve, QRectF
from PyQt6.QtGui import QMouseEvent, QCloseEvent, QPainter, QPainterPath, QColor, QPen, QEnterEvent
from PyQt6.QtMultimedia import QMediaPlayer
from ui.player_widget import ClickableSlider, ClickableLabel
from viewmodels.player_viewmodel import PlayerViewModel
from core import theme_manager


class MarqueeLabel(QLabel):
    """A label that scrolls its text left when it doesn't fit the
    available width.

    There's no built-in Qt widget for this, so it's hand-rolled: a QTimer
    advances a pixel offset used to draw the text shifted left in
    paintEvent, clipped to the label's own rect. Sequence per cycle:
    scroll to the end -> hold there -> reset to the start -> wait -> scroll
    again.
    """

    HOLD_AT_END_MS = 2000
    PAUSE_AT_START_MS = 3000
    STEP_MS = 30
    STEP_PX = 1

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self._full_text = text
        self._offset = 0
        self._pending_action = None

        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._advance)

        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.timeout.connect(self._on_pause_finished)

        super().setText(text)

    def setText(self, text: str) -> None:
        self._full_text = text
        super().setText(text)
        QTimer.singleShot(0, self._restart_cycle)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._restart_cycle()

    def _text_width(self) -> int:
        return self.fontMetrics().horizontalAdvance(self._full_text)

    def _restart_cycle(self) -> None:
        self._scroll_timer.stop()
        self._pause_timer.stop()
        self._offset = 0
        self.update()
        if self._text_width() > self.width():
            self._schedule(self.PAUSE_AT_START_MS, "start_scrolling")

    def _schedule(self, ms: int, action: str) -> None:
        self._pending_action = action
        self._pause_timer.start(ms)

    def _on_pause_finished(self) -> None:
        if self._pending_action == "start_scrolling":
            self._offset = 0
            self._scroll_timer.start(self.STEP_MS)
        elif self._pending_action == "reset_and_wait":
            self._offset = 0
            self.update()
            self._schedule(self.PAUSE_AT_START_MS, "start_scrolling")

    def _advance(self) -> None:
        max_offset = self._text_width() - self.width() + 4
        self._offset += self.STEP_PX
        if self._offset >= max_offset:
            self._offset = max_offset
            self._scroll_timer.stop()
            self.update()
            self._schedule(self.HOLD_AT_END_MS, "reset_and_wait")
            return
        self.update()

    def paintEvent(self, event) -> None:
        if self._text_width() <= self.width():
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        metrics = self.fontMetrics()
        y = (self.height() + metrics.ascent() - metrics.descent()) // 2
        painter.drawText(-self._offset, y, self._full_text)


class MiniPlayerWindow(QWidget):
    """Compact always-on-top player, meant to stay open while the user
    works in other apps without needing the full main window.

    Shares the same PlayerViewModel as MusicPlayerWidget — this is just a
    second, compact View over the same state, kept in sync by the same
    signals, and deliberately mirrors the main player's layout/sizing
    (same round transport buttons, same progress bar) rather than
    inventing a different look.

    Dragging and corner snapping are implemented by hand: Qt/Windows has
    no built-in "magnetism" API for arbitrary app windows.
    """

    restore_requested = pyqtSignal()

    CORNER_MARGIN = 10

    def __init__(self, view_model: PlayerViewModel, config) -> None:
        super().__init__()
        self.vm = view_model
        self.config = config
        self._drag_offset: QPoint | None = None
        self._current_duration = 0
        self._panel_bg = QColor("#1e1e22")
        self._panel_border = QColor("#ff2bd6")

        self.setObjectName("miniPlayer")
        # The container's own background/border are painted by hand in
        # paintEvent below (see refresh_panel_colors), not via QSS: mixing
        # a QSS-styled background with WA_TranslucentBackground led to the
        # whole window turning semi-transparent instead of just the
        # corners. Painting a smooth, anti-aliased rounded rect ourselves,
        # with the real window background left transparent, keeps the
        # corners see-through without a hard-edged mask (which never quite
        # lined up with the QSS-drawn border) and without breaking normal
        # opaque rendering or mouse interaction anywhere inside the shape.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(320, 140)
        self.setWindowOpacity(0.75)

        self.refresh_panel_colors()
        self.init_ui()
        self.bind_viewmodel()

    def refresh_panel_colors(self) -> None:
        """Re-reads the panel background (theme-neutral) and border
        (secondary color) from the config, so this stays in sync if the
        user changes them in Settings while the mini player is open."""
        bg_hex, _text, _field, _border = theme_manager.get_neutral_dialog_colors(self.config)
        self._panel_bg = QColor(bg_hex)
        self._panel_border = QColor(self.config.get_secondary_color())
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        painter.fillPath(path, self._panel_bg)
        pen = QPen(self._panel_border)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self.lbl_track_info = MarqueeLabel("No track loaded")
        self.lbl_track_info.setObjectName("lblTrackInfo")
        top_row.addWidget(self.lbl_track_info, 1)

        self.btn_restore = QPushButton("🗗")
        self.btn_restore.setObjectName("btnToolbarIcon")
        self.btn_restore.setFixedSize(26, 26)
        self.btn_restore.setToolTip("Restore main window")
        self.btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        top_row.addWidget(self.btn_restore)
        layout.addLayout(top_row)

        # Mirrors MusicPlayerWidget's progress row exactly (same widgets,
        # same object names) instead of inventing a different look.
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(8)

        self.lbl_time_current = QLabel("00:00")
        self.lbl_time_current.setObjectName("lblTime")

        self.sld_progress = ClickableSlider(Qt.Orientation.Horizontal)
        self.sld_progress.setObjectName("sldProgress")
        self.sld_progress.setRange(0, 0)
        self.sld_progress.setFixedHeight(14)

        self.lbl_time_total = QLabel("-00:00")
        self.lbl_time_total.setObjectName("lblTime")

        progress_layout.addWidget(self.lbl_time_current)
        progress_layout.addWidget(self.sld_progress)
        progress_layout.addWidget(self.lbl_time_total)
        layout.addLayout(progress_layout)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.btn_prev = QPushButton("⏮")
        self.btn_play = QPushButton("▶")
        self.btn_stop = QPushButton("⏹")
        self.btn_next = QPushButton("⏭")

        for btn in (self.btn_prev, self.btn_play, self.btn_stop, self.btn_next):
            # Same size as MusicPlayerWidget's transport buttons: the
            # border-radius that makes them round only forms a perfect
            # circle at this exact size (radius = half of it).
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("btnTransport")

        self.btn_play.setObjectName("btnPlay")

        controls_row.addWidget(self.btn_prev)
        controls_row.addWidget(self.btn_play)
        controls_row.addWidget(self.btn_stop)
        controls_row.addWidget(self.btn_next)
        controls_row.addStretch(1)

        self.lbl_vol_icon = ClickableLabel("🔊")
        self.lbl_vol_icon.setObjectName("lblVolIcon")
        self.lbl_vol_icon.setFixedWidth(20)
        self.lbl_vol_icon.setToolTip("Mute / restore volume")

        self.sld_volume = ClickableSlider(Qt.Orientation.Horizontal)
        self.sld_volume.setObjectName("sldVolume")
        self.sld_volume.setRange(0, 100)
        self.sld_volume.setValue(70)
        self.sld_volume.setFixedWidth(70)
        self.sld_volume.setFixedHeight(14)

        controls_row.addWidget(self.lbl_vol_icon)
        controls_row.addWidget(self.sld_volume)
        layout.addLayout(controls_row)

    def bind_viewmodel(self) -> None:
        self.vm.track_info_changed.connect(self.lbl_track_info.setText)
        self.vm.position_changed.connect(self.update_progress_slider)
        self.vm.duration_changed.connect(self.update_duration_range)
        self.vm.playback_state_changed.connect(self.btn_play.setText)
        self.vm.volume_icon_changed.connect(self.lbl_vol_icon.setText)
        self.vm.volume_changed.connect(self.sync_volume_slider)
        self.vm.queue_cleared.connect(self.reset_ui)

        self.btn_play.clicked.connect(self.vm.toggle_play)
        self.btn_stop.clicked.connect(self.vm.stop_audio)
        self.btn_next.clicked.connect(self.vm.next_track)
        self.btn_prev.clicked.connect(self.vm.prev_track)
        self.sld_progress.sliderReleased.connect(lambda: self.vm.set_position(self.sld_progress.value()))
        self.sld_volume.valueChanged.connect(self.vm.set_volume)
        self.lbl_vol_icon.clicked.connect(self.vm.toggle_mute)

        self.btn_restore.clicked.connect(self.restore_requested.emit)

        # The ViewModel may have already been playing before this window
        # existed to receive track_info_changed/duration_changed/etc., so
        # the current state is pulled explicitly here instead of relying
        # only on future signals (same reasoning as the output dropdown
        # in MusicPlayerWidget).
        self.lbl_track_info.setText(self.vm.get_current_track_display())
        self.update_duration_range(self.vm.player.duration())
        self.update_progress_slider(self.vm.player.position())
        is_playing = self.vm.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setText("⏸" if is_playing else "▶")
        self.sync_volume_slider(int(self.vm.audio_output.volume() * 100))

    def update_progress_slider(self, position: int) -> None:
        if not self.sld_progress.isSliderDown():
            self.sld_progress.blockSignals(True)
            self.sld_progress.setValue(position)
            self.sld_progress.blockSignals(False)
            self.lbl_time_current.setText(self._format_ms(position))
            remaining = max(0, self._current_duration - position)
            self.lbl_time_total.setText(f"-{self._format_ms(remaining)}")

    def update_duration_range(self, duration: int) -> None:
        self.sld_progress.setRange(0, duration)
        self._current_duration = duration

    def _format_ms(self, ms: int) -> str:
        return QTime(0, 0, 0).addMSecs(ms).toString("mm:ss")

    def sync_volume_slider(self, value: int) -> None:
        self.sld_volume.blockSignals(True)
        self.sld_volume.setValue(value)
        self.sld_volume.blockSignals(False)

    def reset_ui(self) -> None:
        self.btn_play.setText("▶")
        self.lbl_track_info.setText("No track loaded")
        self._current_duration = 0
        self.sld_progress.blockSignals(True)
        self.sld_progress.setValue(0)
        self.sld_progress.setRange(0, 0)
        self.sld_progress.blockSignals(False)
        self.lbl_time_current.setText("00:00")
        self.lbl_time_total.setText("-00:00")

    # ---------------- Hover opacity ----------------

    def enterEvent(self, event: QEnterEvent) -> None:
        self.setWindowOpacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setWindowOpacity(0.75)
        super().leaveEvent(event)

    # ---------------- Dragging + corner snapping ----------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self._snap_to_nearest_corner()
            event.accept()

    def _snap_to_nearest_corner(self) -> None:
        """Always snaps to whichever of the 4 corners of the CURRENT
        screen is nearest — never to an arbitrary point along an edge —
        leaving CORNER_MARGIN pixels of breathing room from that corner."""
        screen = QApplication.screenAt(self.frameGeometry().center()) or self.screen()
        if screen is None:
            return

        area = screen.availableGeometry()
        geo = self.frameGeometry()
        m = self.CORNER_MARGIN

        candidates = [
            QPoint(area.left() + m, area.top() + m),
            QPoint(area.right() - geo.width() - m + 1, area.top() + m),
            QPoint(area.left() + m, area.bottom() - geo.height() - m + 1),
            QPoint(area.right() - geo.width() - m + 1, area.bottom() - geo.height() - m + 1),
        ]

        nearest = min(candidates, key=lambda p: (p.x() - geo.x()) ** 2 + (p.y() - geo.y()) ** 2)

        # Animated instead of an instant jump, with an "overshoot and
        # settle" easing curve for the rubber-band feel at the end — also
        # gentler than a snap so the eye can actually follow it.
        self._snap_animation = QPropertyAnimation(self, b"pos", self)
        self._snap_animation.setDuration(400)
        self._snap_animation.setStartValue(self.pos())
        self._snap_animation.setEndValue(nearest)
        # Default OutBack overshoot (~1.7) was ending up outside the
        # monitor entirely; a much smaller value keeps the "rubber band"
        # feel without the exaggerated jump.
        bounce_curve = QEasingCurve(QEasingCurve.Type.OutBack)
        bounce_curve.setOvershoot(0.6)
        self._snap_animation.setEasingCurve(bounce_curve)
        self._snap_animation.start()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Alt+F4 (or any other way to close this frameless window)
        restores the main window instead of quitting anything."""
        event.ignore()
        self.restore_requested.emit()
