from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
                             QWidget, QListWidget, QListWidgetItem, QPushButton)
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional, List, Tuple


class UsbWaitingOverlay(QDialog):
    drive_selected = pyqtSignal(str, str)  # (full_path, label)
    search_cancelled = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setObjectName("usbOverlay")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.label = QLabel("Searching for USB drives...")
        self.label.setObjectName("overlayLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setObjectName("overlayProgress")
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        self.drive_list = QListWidget()
        self.drive_list.setObjectName("overlayDriveList")
        self.drive_list.hide()
        self.drive_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.drive_list)

        # Frameless with no close button; Escape/click-outside is blocked
        # (see keyPressEvent), so Cancel is the only way to dismiss it.
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btnCancelOverlay")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

    def set_searching_mode(self) -> None:
        self.label.setText("Searching for USB drives...")
        self.progress.show()
        self.drive_list.clear()
        self.drive_list.hide()

    def update_drive_list(self, drives: List[Tuple[str, str]]) -> None:
        self.drive_list.clear()
        self.progress.hide()
        self.label.setText("Drives found (double-click to open):")

        for path, label in drives:
            clean_letter = path.strip("\\")
            display_text = f"💾 Drive {clean_letter}   [{label}]"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, (path, label))
            self.drive_list.addItem(item)

        self.drive_list.show()

    def on_item_double_clicked(self, item: QListWidgetItem) -> None:
        path, label = item.data(Qt.ItemDataRole.UserRole)
        self.drive_selected.emit(path, label)

    def _on_cancel_clicked(self) -> None:
        self.search_cancelled.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Blocks Escape so only the Cancel button can dismiss this modal."""
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)


class ConfirmDialog(QDialog):
    """Frameless confirmation dialog for actions needing a decision,
    styled like UsbWaitingOverlay."""

    def __init__(self, parent: Optional[QWidget], title: str, message: str,
                 confirm_text: str = "Yes", cancel_text: str = "Cancel", destructive: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("usbOverlay")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("overlayLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_cancel = QPushButton(cancel_text)
        self.btn_cancel.setObjectName("btnCancelOverlay")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_confirm = QPushButton(confirm_text)
        self.btn_confirm.setObjectName("btnConfirmDestructive" if destructive else "btnConfirmOverlay")
        self.btn_confirm.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_confirm)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    @staticmethod
    def confirm(parent: Optional[QWidget], title: str, message: str,
                confirm_text: str = "Yes", cancel_text: str = "Cancel", destructive: bool = True) -> bool:
        dialog = ConfirmDialog(parent, title, message, confirm_text, cancel_text, destructive)
        return dialog.exec() == QDialog.DialogCode.Accepted
