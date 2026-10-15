from typing import List, Optional

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QIcon, QPixmap, QPolygonF

from core import theme_manager


def _make_badge_icon(level: str, color_hex: str, size: int = 20) -> QIcon:
    """Hand-drawn status badge (filled circle + symbol)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))
    painter.drawEllipse(QRectF(0, 0, size, size))

    symbol_color = QColor("#ffffff")
    if level == "success":
        pen = QPen(symbol_color)
        pen.setWidthF(size * 0.11)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        points = [QPointF(size * 0.27, size * 0.53), QPointF(size * 0.43, size * 0.70), QPointF(size * 0.75, size * 0.32)]
        painter.drawPolyline(QPolygonF(points))
    elif level in ("error", "warning"):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(symbol_color)
        bar = QRectF(size * 0.46, size * 0.22, size * 0.08, size * 0.36)
        painter.drawRoundedRect(bar, bar.width() * 0.4, bar.width() * 0.4)
        dot = QRectF(size * 0.44, size * 0.68, size * 0.12, size * 0.12)
        painter.drawEllipse(dot)
    else:  # info
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(symbol_color)
        dot = QRectF(size * 0.44, size * 0.22, size * 0.12, size * 0.12)
        painter.drawEllipse(dot)
        bar = QRectF(size * 0.46, size * 0.42, size * 0.08, size * 0.34)
        painter.drawRoundedRect(bar, bar.width() * 0.4, bar.width() * 0.4)

    painter.end()
    return QIcon(pixmap)


class ToastNotification(QWidget):
    """Small, self-dismissing toast that fades out and closes itself
    after SHOW_MS + FADE_MS. Multiple toasts stack bottom-right."""

    SHOW_MS = 2000
    FADE_MS = 1500
    MARGIN = 18
    SPACING = 10

    _active: List["ToastNotification"] = []

    def __init__(self, anchor_widget: Optional[QWidget], message: str, level: str, config) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._anchor_widget = anchor_widget
        self._config = config
        self._level = level

        bg_hex, text_hex, _field, _border = theme_manager.get_neutral_dialog_colors(config)
        self._bg_color = QColor(bg_hex)
        self._border_color = QColor(self._resolve_accent_color())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 18, 12)
        layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        icon_label.setPixmap(_make_badge_icon(self._level, self._border_color.name()).pixmap(20, 20))
        layout.addWidget(icon_label)

        text_label = QLabel(message)
        text_label.setWordWrap(True)
        text_label.setStyleSheet(f"color: {text_hex}; font-size: 13px; background: transparent;")
        text_label.setMaximumWidth(320)
        layout.addWidget(text_label, 1)

        self.setMinimumWidth(200)
        self.adjustSize()

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_in_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_in_anim.setDuration(180)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_out_anim.setDuration(self.FADE_MS)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out_anim.finished.connect(self._on_faded_out)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._fade_out_anim.start)

    def _resolve_accent_color(self) -> str:
        if self._level == "success":
            return theme_manager.FIXED_TOKENS["SUCCESS"]
        if self._level in ("error", "warning"):
            return theme_manager.FIXED_TOKENS["DANGER"]
        return self._config.get_secondary_color()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.fillPath(path, self._bg_color)
        pen = QPen(self._border_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawPath(path)

    def _on_faded_out(self) -> None:
        if self in ToastNotification._active:
            ToastNotification._active.remove(self)
        self._reposition_all()
        self.close()

    @classmethod
    def _reposition_all(cls) -> None:
        for toast in cls._active:
            toast._update_position()

    def _reference_geometry(self):
        window = self._anchor_widget.window() if self._anchor_widget else None
        if window is not None and window.isVisible():
            return window.geometry()
        screen = QApplication.primaryScreen()
        return screen.geometry() if screen else self.geometry()

    def _update_position(self) -> None:
        try:
            index = ToastNotification._active.index(self)
        except ValueError:
            index = 0

        geo = self._reference_geometry()
        x = geo.right() - self.width() - self.MARGIN
        y = geo.bottom() - self.MARGIN - self.height()
        for other in ToastNotification._active[:index]:
            y -= other.height() + self.SPACING
        self.move(x, y)

    def show_toast(self) -> None:
        ToastNotification._active.append(self)
        self._update_position()
        self.show()
        self._fade_in_anim.start()
        self._dismiss_timer.start(self.SHOW_MS)


def show_toast(anchor_widget: Optional[QWidget], message: str, level: str = "info", config=None) -> None:
    """Shows a self-dismissing toast anchored near the bottom-right corner
    of anchor_widget's window. level: "info", "success", "warning"/"error"."""
    if config is None and anchor_widget is not None:
        config = getattr(anchor_widget.window(), "config", None)
    toast = ToastNotification(anchor_widget, message, level, config)
    toast.show_toast()
