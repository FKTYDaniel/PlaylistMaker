from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QStyle, QStyleOptionSlider, QGraphicsDropShadowEffect, QComboBox
from PyQt6.QtCore import Qt, QTime, pyqtSignal, QSize, QRectF, QPointF
from PyQt6.QtGui import QMouseEvent, QColor, QPalette, QIcon, QPixmap, QPainter, QPolygonF
from core import theme_manager
from viewmodels.player_viewmodel import PlayerViewModel


def _make_play_icon(color_hex: str, size: int = 18) -> QIcon:
    """Hand-drawn play triangle (vector, not a Unicode glyph, so it can
    be recolored at runtime)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))

    w = size * 0.6
    h = size * 0.72
    x = (size - w) / 2 + size * 0.05  # nudged right: optically centers the triangle
    y = (size - h) / 2
    points = [QPointF(x, y), QPointF(x, y + h), QPointF(x + w, y + h / 2)]
    painter.drawPolygon(QPolygonF(points))
    painter.end()
    return QIcon(pixmap)


def _make_pause_icon(color_hex: str, size: int = 18) -> QIcon:
    """Hand-drawn pause bars — see _make_play_icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))

    bar_w = size * 0.18
    bar_h = size * 0.64
    gap = size * 0.16
    top = (size - bar_h) / 2
    left_x = size / 2 - gap / 2 - bar_w
    right_x = size / 2 + gap / 2
    radius = bar_w * 0.3
    painter.drawRoundedRect(QRectF(left_x, top, bar_w, bar_h), radius, radius)
    painter.drawRoundedRect(QRectF(right_x, top, bar_w, bar_h), radius, radius)
    painter.end()
    return QIcon(pixmap)


def _make_stop_icon(color_hex: str, size: int = 16) -> QIcon:
    """Hand-drawn stop square — see _make_play_icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))

    side = size * 0.56
    rect = QRectF((size - side) / 2, (size - side) / 2, side, side)
    painter.drawRoundedRect(rect, side * 0.2, side * 0.2)
    painter.end()
    return QIcon(pixmap)


def _make_prev_icon(color_hex: str, size: int = 16) -> QIcon:
    """Hand-drawn "skip to previous" glyph (bar + triangle) — see
    _make_play_icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))

    bar_w = size * 0.14
    bar_h = size * 0.64
    bar_x = size * 0.16
    top = (size - bar_h) / 2
    painter.drawRoundedRect(QRectF(bar_x, top, bar_w, bar_h), bar_w * 0.3, bar_w * 0.3)

    tri_w = size * 0.44
    tri_h = size * 0.64
    tri_x = bar_x + bar_w + size * 0.08
    points = [QPointF(tri_x + tri_w, top), QPointF(tri_x + tri_w, top + tri_h), QPointF(tri_x, top + tri_h / 2)]
    painter.drawPolygon(QPolygonF(points))
    painter.end()
    return QIcon(pixmap)


def _make_next_icon(color_hex: str, size: int = 16) -> QIcon:
    """Hand-drawn "skip to next" glyph (triangle + bar), mirroring
    _make_prev_icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))

    bar_w = size * 0.14
    bar_h = size * 0.64
    bar_x = size - size * 0.16 - bar_w
    top = (size - bar_h) / 2
    painter.drawRoundedRect(QRectF(bar_x, top, bar_w, bar_h), bar_w * 0.3, bar_w * 0.3)

    tri_w = size * 0.44
    tri_h = size * 0.64
    tri_x = bar_x - size * 0.08 - tri_w
    points = [QPointF(tri_x, top), QPointF(tri_x, top + tri_h), QPointF(tri_x + tri_w, top + tri_h / 2)]
    painter.drawPolygon(QPolygonF(points))
    painter.end()
    return QIcon(pixmap)


class ClickableSlider(QSlider):
    """Slider supporting both click-to-position and free dragging, with
    fully custom mouse handling."""

    def __init__(self, orientation: Qt.Orientation) -> None:
        super().__init__(orientation)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._dragging = False

    def _handle_length(self) -> int:
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        handle_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderHandle, self
        )
        return handle_rect.width() if self.orientation() == Qt.Orientation.Horizontal else handle_rect.height()

    def _value_from_x(self, x: float) -> int:
        handle_len = self._handle_length()
        usable_span = max(1, self.width() - handle_len)
        click_pos = int(x) - handle_len // 2
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), click_pos, usable_span)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._dragging = True
            self.setSliderDown(True)

            val = self._value_from_x(event.position().x())
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            val = self._value_from_x(event.position().x())
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._dragging = False
            self.setSliderDown(False)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class ClickableLabel(QLabel):
    """A QLabel that behaves like a simple button (used for mute)."""

    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MusicPlayerWidget(QWidget):
    def __init__(self, view_model: PlayerViewModel, config) -> None:
        super().__init__()
        self.vm = view_model
        self.config = config
        self._current_duration = 0
        self._is_playing = False
        self.init_ui()
        self.bind_viewmodel()

    def init_ui(self) -> None:
        self.setObjectName("playerWidget")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 6, 15, 6)
        main_layout.setSpacing(2)

        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(8)

        self.lbl_time_current = QLabel("00:00")
        self.lbl_time_current.setObjectName("lblTime")
        self.lbl_time_current.setFixedHeight(14)

        self.sld_progress = ClickableSlider(Qt.Orientation.Horizontal)
        self.sld_progress.setObjectName("sldProgress")
        self.sld_progress.setRange(0, 0)
        self.sld_progress.setFixedHeight(14)

        self.lbl_time_total = QLabel("-00:00")
        self.lbl_time_total.setObjectName("lblTime")
        self.lbl_time_total.setFixedHeight(14)

        progress_layout.addWidget(self.lbl_time_current)
        progress_layout.addWidget(self.sld_progress)
        progress_layout.addWidget(self.lbl_time_total)
        main_layout.addLayout(progress_layout)

        bottom_layout = QHBoxLayout()

        self.lbl_track_info = QLabel("No track loaded")
        self.lbl_track_info.setObjectName("lblTrackInfo")
        self.lbl_track_info.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bottom_layout.addWidget(self.lbl_track_info, 1)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        self.btn_prev = QPushButton()
        self.btn_play = QPushButton()
        self.btn_stop = QPushButton()
        self.btn_next = QPushButton()

        for btn in (self.btn_prev, self.btn_play, self.btn_stop, self.btn_next):
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("btnTransport")

        self.btn_prev.setIconSize(QSize(16, 16))
        self.btn_stop.setIconSize(QSize(16, 16))
        self.btn_next.setIconSize(QSize(16, 16))
        self.btn_play.setIconSize(QSize(18, 18))

        self.btn_play.setObjectName("btnPlay")
        # Real neon glow, not achievable via QSS alone (see set_glow_color).
        self._play_glow = QGraphicsDropShadowEffect(self.btn_play)
        self._play_glow.setBlurRadius(20)
        self._play_glow.setColor(QColor(0, 229, 255, 200))
        self._play_glow.setOffset(0, 0)
        self.btn_play.setGraphicsEffect(self._play_glow)

        controls_layout.addWidget(self.btn_prev)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addWidget(self.btn_next)
        bottom_layout.addLayout(controls_layout, 0)

        volume_container = QWidget()
        volume_container.setObjectName("volumeContainer")
        volume_layout = QHBoxLayout(volume_container)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(6)
        volume_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.lbl_vol_icon = ClickableLabel("🔊")
        self.lbl_vol_icon.setObjectName("lblVolIcon")
        self.lbl_vol_icon.setFixedWidth(20)
        self.lbl_vol_icon.setToolTip("Mute / restore volume")

        self.sld_volume = ClickableSlider(Qt.Orientation.Horizontal)
        self.sld_volume.setObjectName("sldVolume")
        self.sld_volume.setRange(0, 100)
        self.sld_volume.setValue(70)
        self.sld_volume.setFixedWidth(80)
        self.sld_volume.setFixedHeight(14)

        self.cmb_output = QComboBox()
        self.cmb_output.setObjectName("cmbOutput")
        self.cmb_output.setFixedWidth(150)
        self.cmb_output.setToolTip("Audio output")
        self.cmb_output.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cmb_output.view().setCursor(Qt.CursorShape.PointingHandCursor)

        volume_layout.addWidget(self.cmb_output)
        volume_layout.addWidget(self.lbl_vol_icon)
        volume_layout.addWidget(self.sld_volume)
        bottom_layout.addWidget(volume_container, 1)

        main_layout.addLayout(bottom_layout)

    def bind_viewmodel(self) -> None:
        self.vm.track_info_changed.connect(self.lbl_track_info.setText)
        self.vm.position_changed.connect(self.update_progress_slider)
        self.vm.duration_changed.connect(self.update_duration_range)
        self.vm.playback_state_changed.connect(self._on_playback_state_changed)
        self.vm.volume_icon_changed.connect(self.lbl_vol_icon.setText)
        self.vm.volume_changed.connect(self.sync_volume_slider)
        self.vm.queue_cleared.connect(self.reset_ui)
        self.vm.available_outputs_changed.connect(self.populate_output_combo)
        self.vm.active_output_index_changed.connect(self.sync_output_combo)

        self.btn_play.clicked.connect(self.vm.toggle_play)
        self.btn_stop.clicked.connect(self.vm.stop_audio)
        self.btn_next.clicked.connect(self.vm.next_track)
        self.btn_prev.clicked.connect(self.vm.prev_track)
        self.sld_progress.sliderReleased.connect(lambda: self.vm.set_position(self.sld_progress.value()))

        self.sld_volume.valueChanged.connect(self.vm.set_volume)

        self.lbl_vol_icon.clicked.connect(self.vm.toggle_mute)
        self.cmb_output.activated.connect(self.vm.set_output_device_by_index)

        # The ViewModel may have already emitted its initial state before
        # this widget existed to receive it, so pull it explicitly too.
        self.populate_output_combo(self.vm.get_available_output_descriptions())
        self.sync_output_combo(self.vm.get_current_output_index())
        self.sync_output_combo_palette()
        self.sync_volume_slider(round(self.vm.audio_output.volume() * 100))

    def sync_output_combo_palette(self) -> None:
        """The popup's item highlighting comes from its QPalette, not the
        QSS ::item:selected rule, so it's overridden directly here."""
        primary = self.config.get_primary_color()
        bg_hex, text_hex, _field, _border = theme_manager.get_neutral_dialog_colors(self.config)

        palette = self.cmb_output.view().palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(bg_hex))
        palette.setColor(QPalette.ColorRole.Text, QColor(text_hex))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(primary))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(text_hex))
        self.cmb_output.view().setPalette(palette)

    def populate_output_combo(self, descriptions: list) -> None:
        self.cmb_output.blockSignals(True)
        self.cmb_output.clear()
        self.cmb_output.addItems(descriptions if descriptions else ["No output detected"])
        self.cmb_output.blockSignals(False)

    def sync_output_combo(self, index: int) -> None:
        """Reflects the active output in the dropdown without firing
        activated back to the ViewModel."""
        if index < 0:
            return
        self.cmb_output.blockSignals(True)
        self.cmb_output.setCurrentIndex(index)
        self.cmb_output.blockSignals(False)

    def set_glow_color(self, color_hex: str) -> None:
        """Recolors the play button's neon glow (painted via
        QGraphicsDropShadowEffect, not covered by QSS)."""
        color = QColor(color_hex)
        color.setAlpha(200)
        self._play_glow.setColor(color)

    def set_icon_color(self, color_hex: str) -> None:
        """Recolors the transport button icons to the secondary color."""
        self._icon_prev = _make_prev_icon(color_hex, 16)
        self._icon_stop = _make_stop_icon(color_hex, 16)
        self._icon_next = _make_next_icon(color_hex, 16)
        self._icon_play = _make_play_icon(color_hex, 18)
        self._icon_pause = _make_pause_icon(color_hex, 18)

        self.btn_prev.setIcon(self._icon_prev)
        self.btn_stop.setIcon(self._icon_stop)
        self.btn_next.setIcon(self._icon_next)
        self._apply_play_pause_icon()

    def _apply_play_pause_icon(self) -> None:
        self.btn_play.setIcon(self._icon_pause if self._is_playing else self._icon_play)

    def _on_playback_state_changed(self, symbol: str) -> None:
        self._is_playing = (symbol == "⏸")
        self._apply_play_pause_icon()

    def sync_volume_slider(self, value: int) -> None:
        """Updates the slider on programmatic volume changes (mute/unmute)
        without re-emitting valueChanged back to the ViewModel."""
        self.sld_volume.blockSignals(True)
        self.sld_volume.setValue(value)
        self.sld_volume.blockSignals(False)

    def update_progress_slider(self, position: int) -> None:
        if not self.sld_progress.isSliderDown():
            self.sld_progress.blockSignals(True)
            self.sld_progress.setValue(position)
            self.sld_progress.blockSignals(False)
            self.lbl_time_current.setText(self.format_milliseconds(position))
            self._update_remaining_label(position)

    def update_duration_range(self, duration: int) -> None:
        self.sld_progress.setRange(0, duration)
        self._current_duration = duration
        self._update_remaining_label(self.sld_progress.value())

    def _update_remaining_label(self, position: int) -> None:
        remaining = max(0, self._current_duration - position)
        self.lbl_time_total.setText(f"-{self.format_milliseconds(remaining)}")

    def format_milliseconds(self, ms: int) -> str:
        return QTime(0, 0, 0).addMSecs(ms).toString("mm:ss")

    def reset_ui(self) -> None:
        self._is_playing = False
        self._apply_play_pause_icon()
        self.lbl_track_info.setText("No track loaded")

        self.sld_progress.blockSignals(True)
        self.sld_progress.setValue(0)
        self.sld_progress.setRange(0, 0)
        self.sld_progress.blockSignals(False)

        self._current_duration = 0
        self.lbl_time_current.setText("00:00")
        self.lbl_time_total.setText("-00:00")
