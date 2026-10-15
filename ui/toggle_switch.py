from PyQt6.QtWidgets import QAbstractButton
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRectF, QSize, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen

from core import theme_manager


class ToggleSwitch(QAbstractButton):
    """Painted ON/OFF switch: green when checked, red when not, in the
    same outlined style as the Save/Delete playlist buttons."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._offset = 0.0  # 0.0 = knob left (off), 1.0 = knob right (on)

        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate_to_state)

    def sizeHint(self) -> QSize:
        return QSize(44, 24)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = pyqtProperty(float, _get_offset, _set_offset)

    def _animate_to_state(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, event) -> None:
        tokens = theme_manager.FIXED_TOKENS
        accent = QColor(tokens["SUCCESS"] if self.isChecked() else tokens["DANGER"])

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        fill = QColor(accent)
        fill.setAlpha(45)
        painter.setBrush(fill)
        painter.setPen(QPen(accent, 1.5))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        margin = 4.0
        diameter = track.height() - 2 * margin
        travel = track.width() - 2 * margin - diameter
        x = track.left() + margin + travel * self._offset
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(QRectF(x, track.top() + margin, diameter, diameter))
