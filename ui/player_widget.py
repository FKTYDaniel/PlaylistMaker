from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QStyle, QStyleOptionSlider, QGraphicsDropShadowEffect, QComboBox
from PyQt6.QtCore import Qt, QTime, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QColor, QPalette
from core import theme_manager
from viewmodels.player_viewmodel import PlayerViewModel


class ClickableSlider(QSlider):
    """Slider supporting both click-to-position and free dragging.

    Mouse handling (press/move/release) is fully custom because partially
    delegating to the native QSlider caused two problems:
    1) a plain click didn't account for handle width, skewing the value
       near the edges (most noticeable on the narrow volume slider);
    2) without entering QSlider's internal drag state, the native
       mouseMoveEvent did nothing, and since isSliderDown() never became
       True, playback position updates fought the user's drag in real time.

    setSliderDown(True/False) is the correct way to enter/exit
    QAbstractSlider's drag state: it emits sliderPressed()/sliderReleased()
    and makes isSliderDown() report correctly, which the View relies on to
    know when to ignore automatic position updates.
    """

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

        self.btn_prev = QPushButton("⏮")
        self.btn_play = QPushButton("▶")
        self.btn_stop = QPushButton("⏹")
        self.btn_next = QPushButton("⏭")

        for btn in (self.btn_prev, self.btn_play, self.btn_stop, self.btn_next):
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("btnTransport")

        self.btn_play.setObjectName("btnPlay")
        # Real neon glow (not achievable via QSS alone). Kept as an
        # attribute so it can be recolored when the user changes the
        # primary color in Settings (see set_glow_color).
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

        # Lives inside the same stretch widget (volume_container) as the
        # volume slider, to its left, so the bottom row stays symmetric
        # (lbl_track_info vs volume_container, both stretch 1) and the
        # transport buttons stay centered.
        volume_layout.addWidget(self.cmb_output)
        volume_layout.addWidget(self.lbl_vol_icon)
        volume_layout.addWidget(self.sld_volume)
        bottom_layout.addWidget(volume_container, 1)

        main_layout.addLayout(bottom_layout)

    def bind_viewmodel(self) -> None:
        self.vm.track_info_changed.connect(self.lbl_track_info.setText)
        self.vm.position_changed.connect(self.update_progress_slider)
        self.vm.duration_changed.connect(self.update_duration_range)
        self.vm.playback_state_changed.connect(self.btn_play.setText)
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

        # setValue() already fires valueChanged on both click and drag
        # (ClickableSlider calls it in both cases), so a single connection
        # covers both without duplicating calls.
        self.sld_volume.valueChanged.connect(self.vm.set_volume)

        self.lbl_vol_icon.clicked.connect(self.vm.toggle_mute)
        self.cmb_output.activated.connect(self.vm.set_output_device_by_index)

        # The ViewModel may have already emitted the initial output list
        # before this widget existed (in its __init__), so pull the
        # current state explicitly instead of relying only on the signal.
        self.populate_output_combo(self.vm.get_available_output_descriptions())
        self.sync_output_combo(self.vm.get_current_output_index())
        self.sync_output_combo_palette()

    def sync_output_combo_palette(self) -> None:
        """The popup's item highlighting turned out to come from its
        QPalette (Highlight/HighlightedText), not the QSS ::item:selected
        rule — same underlying cause as the QColorDialog fix in
        ui/settings_overlay.py. Overriding the palette directly is what
        actually controls it; QSS alone wasn't enough."""
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
        """Recolors the play button's neon glow (called by MainWindow when
        the primary color changes in Settings). The glow is painted via
        QGraphicsDropShadowEffect, so it isn't covered by the shared QSS."""
        color = QColor(color_hex)
        color.setAlpha(200)
        self._play_glow.setColor(color)

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
        self.btn_play.setText("▶")
        self.lbl_track_info.setText("No track loaded")

        self.sld_progress.blockSignals(True)
        self.sld_progress.setValue(0)
        self.sld_progress.setRange(0, 0)
        self.sld_progress.blockSignals(False)

        self._current_duration = 0
        self.lbl_time_current.setText("00:00")
        self.lbl_time_total.setText("-00:00")
