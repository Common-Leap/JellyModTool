"""
Music Tab — import a folder of MP3/OGG files and export a song mod.
Uses ffmpeg to convert MP3 → OGG when needed.
"""

import os
import subprocess
import tempfile

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QLineEdit,
    QProgressBar, QMessageBox, QGroupBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from utils.mod_writer import write_song_mod


def _has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def convert_to_ogg(src: str, dest: str):
    """Convert any audio file to OGG Vorbis via ffmpeg."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-c:a", "libvorbis", "-q:a", "4", dest],
        capture_output=True, check=True,
    )


class ExportWorker(QThread):
    progress = pyqtSignal(int, str)   # (percent, message)
    finished = pyqtSignal(str)        # output folder
    error = pyqtSignal(str)

    def __init__(self, files: list, mod_name: str, output_dir: str):
        super().__init__()
        self.files = files
        self.mod_name = mod_name
        self.output_dir = output_dir

    def run(self):
        try:
            total = len(self.files)
            ogg_files = []

            with tempfile.TemporaryDirectory() as tmp:
                for i, src in enumerate(self.files):
                    name = os.path.splitext(os.path.basename(src))[0]
                    dest = os.path.join(tmp, name + ".ogg")
                    self.progress.emit(int(i / total * 80), f"Converting {os.path.basename(src)}…")

                    if src.lower().endswith(".ogg"):
                        import shutil
                        shutil.copy2(src, dest)
                    else:
                        convert_to_ogg(src, dest)

                    ogg_files.append(dest)

                # For multi-file imports, create one mod per song
                results = []
                for j, ogg in enumerate(ogg_files):
                    base = os.path.splitext(os.path.basename(ogg))[0]
                    song_name = self.mod_name if total == 1 else f"{self.mod_name} - {base}"
                    self.progress.emit(80 + int(j / total * 20), f"Writing mod for {base}…")
                    folder = write_song_mod(self.output_dir, song_name, ogg)
                    results.append(folder)

            self.finished.emit("\n".join(results))
        except Exception as e:
            self.error.emit(str(e))


class MusicTab(QWidget):
    def __init__(self):
        super().__init__()
        self._files = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- Input group ---
        input_group = QGroupBox("1. Select Audio Files")
        ig_layout = QVBoxLayout(input_group)

        btn_row = QHBoxLayout()
        self._btn_folder = QPushButton("Import Folder…")
        self._btn_files  = QPushButton("Import Files…")
        self._btn_clear  = QPushButton("Clear")
        btn_row.addWidget(self._btn_folder)
        btn_row.addWidget(self._btn_files)
        btn_row.addWidget(self._btn_clear)
        btn_row.addStretch()
        ig_layout.addLayout(btn_row)

        self._list = QListWidget()
        self._list.setMinimumHeight(160)
        ig_layout.addWidget(self._list)
        layout.addWidget(input_group)

        # --- Mod name ---
        name_group = QGroupBox("2. Mod Name")
        ng_layout = QHBoxLayout(name_group)
        ng_layout.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit("My Custom Song")
        ng_layout.addWidget(self._name_edit)
        layout.addWidget(name_group)

        # --- Output ---
        out_group = QGroupBox("3. Output Folder")
        og_layout = QHBoxLayout(out_group)
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Where to save the mod folder(s)…")
        btn_out = QPushButton("Browse…")
        og_layout.addWidget(self._out_edit)
        og_layout.addWidget(btn_out)
        layout.addWidget(out_group)

        # --- Export ---
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        self._btn_export = QPushButton("Export Mod(s)")
        self._btn_export.setFixedHeight(40)
        layout.addWidget(self._btn_export)
        layout.addStretch()

        # Connections
        self._btn_folder.clicked.connect(self._import_folder)
        self._btn_files.clicked.connect(self._import_files)
        self._btn_clear.clicked.connect(self._clear)
        btn_out.clicked.connect(self._browse_output)
        self._btn_export.clicked.connect(self._export)

        if not _has_ffmpeg():
            self._status.setText("⚠ ffmpeg not found — MP3 conversion unavailable")

    def _import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not folder:
            return
        exts = {".mp3", ".ogg"}
        for f in sorted(os.listdir(folder)):
            if os.path.splitext(f)[1].lower() in exts:
                path = os.path.join(folder, f)
                if path not in self._files:
                    self._files.append(path)
                    self._list.addItem(QListWidgetItem(f))

    def _import_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio Files", "",
            "Audio Files (*.mp3 *.ogg)"
        )
        for path in files:
            if path not in self._files:
                self._files.append(path)
                self._list.addItem(QListWidgetItem(os.path.basename(path)))

    def _clear(self):
        self._files.clear()
        self._list.clear()

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._out_edit.setText(folder)

    def _export(self):
        if not self._files:
            QMessageBox.warning(self, "No Files", "Add at least one audio file first.")
            return
        out = self._out_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "No Output", "Choose an output folder first.")
            return
        name = self._name_edit.text().strip() or "My Song"

        self._btn_export.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)

        self._worker = ExportWorker(list(self._files), name, out)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, pct, msg):
        self._progress.setValue(pct)
        self._status.setText(msg)

    def _on_done(self, folders):
        self._progress.setValue(100)
        self._btn_export.setEnabled(True)
        count = len(folders.splitlines())
        self._status.setText(f"✓ Exported {count} mod(s) successfully")

    def _on_error(self, msg):
        self._progress.setVisible(False)
        self._btn_export.setEnabled(True)
        self._status.setText("Export failed")
        QMessageBox.critical(self, "Export Error", msg)
