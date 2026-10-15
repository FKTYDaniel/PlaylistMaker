from PyQt6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QPlainTextEdit,
                             QPushButton, QLabel, QSizePolicy)
from PyQt6.QtCore import Qt
from viewmodels.music_viewmodel import MusicViewModel
from ui.toast import show_toast

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

        self.edit_filename = QLineEdit()
        self.edit_title = QLineEdit()
        self.edit_artist = QLineEdit()
        self.edit_album = QLineEdit()
        self.edit_genre = QLineEdit()

        self.edit_lyrics = QPlainTextEdit()
        self.edit_lyrics.setMinimumHeight(140)
        self.edit_lyrics.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.btn_save = QPushButton("Save Metadata")
        self.btn_save.setObjectName("btnSaveMetadata")
        self.btn_save.setEnabled(False)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)

        lyrics_label = QLabel("Lyrics:")
        lyrics_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        layout.addRow("File:", self.edit_filename)
        layout.addRow("Title:", self.edit_title)
        layout.addRow("Artist:", self.edit_artist)
        layout.addRow("Album:", self.edit_album)
        layout.addRow("Genre:", self.edit_genre)
        layout.addRow(lyrics_label, self.edit_lyrics)
        layout.addRow("", self.btn_save)

    def bind_viewmodel(self) -> None:
        self.vm.metadata_loaded.connect(self.on_metadata_loaded)
        self.vm.filename_auto_updated.connect(self.edit_filename.setText)
        self.vm.save_success.connect(self.on_save_success)
        self.vm.save_error.connect(lambda error_msg: show_toast(self, error_msg, level="error"))

        self.edit_title.textChanged.connect(self.vm.handle_title_changed)
        self.btn_save.clicked.connect(self.on_save_clicked)

    def on_metadata_loaded(self, title: str, artist: str, album: str, genre: str,
                           lyrics: str, filename: str) -> None:
        self.edit_title.blockSignals(True)
        self.edit_title.setText(title)
        self.edit_title.blockSignals(False)

        self.edit_artist.setText(artist)
        self.edit_album.setText(album)
        self.edit_genre.setText(genre)
        self.edit_lyrics.setPlainText(lyrics)
        self.edit_filename.setText(filename)
        self.btn_save.setEnabled(True)

    def on_save_clicked(self) -> None:
        self.vm.save_metadata(
            self.edit_title.text(),
            self.edit_artist.text(),
            self.edit_album.text(),
            self.edit_genre.text(),
            self.edit_lyrics.toPlainText(),
            self.edit_filename.text()
        )

    def on_save_success(self) -> None:
        show_toast(self, "Metadata saved successfully!", level="success")
