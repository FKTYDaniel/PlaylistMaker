from PyQt6.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
from viewmodels.music_viewmodel import MusicViewModel

class MusicTab(QWidget):
    def __init__(self, view_model: MusicViewModel) -> None:
        super().__init__()
        self.vm = view_model
        self.init_ui()
        self.bind_viewmodel()

    def init_ui(self) -> None:
        self.setObjectName("musicTab")

        layout = QFormLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self.edit_title = QLineEdit()
        self.edit_artist = QLineEdit()
        self.edit_genre = QLineEdit()
        self.edit_filename = QLineEdit()

        self.btn_save = QPushButton("Save Metadata")
        self.btn_save.setObjectName("btnSaveMetadata")
        self.btn_save.setEnabled(False)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addRow("Title:", self.edit_title)
        layout.addRow("Artist:", self.edit_artist)
        layout.addRow("Genre:", self.edit_genre)
        layout.addRow("File:", self.edit_filename)
        layout.addRow("", self.btn_save)

    def bind_viewmodel(self) -> None:
        self.vm.metadata_loaded.connect(self.on_metadata_loaded)
        self.vm.filename_auto_updated.connect(self.edit_filename.setText)
        self.vm.save_success.connect(self.on_save_success)
        self.vm.save_error.connect(lambda error_msg: QMessageBox.warning(self, "Warning", error_msg))

        self.edit_title.textChanged.connect(self.vm.handle_title_changed)
        self.btn_save.clicked.connect(self.on_save_clicked)

    def on_metadata_loaded(self, title: str, artist: str, genre: str, filename: str) -> None:
        self.edit_title.blockSignals(True)
        self.edit_title.setText(title)
        self.edit_title.blockSignals(False)

        self.edit_artist.setText(artist)
        self.edit_genre.setText(genre)
        self.edit_filename.setText(filename)
        self.btn_save.setEnabled(True)

    def on_save_clicked(self) -> None:
        self.vm.save_metadata(
            self.edit_title.text(),
            self.edit_artist.text(),
            self.edit_genre.text(),
            self.edit_filename.text()
        )

    def on_save_success(self) -> None:
        QMessageBox.information(self, "Success", "Metadata saved successfully!")
