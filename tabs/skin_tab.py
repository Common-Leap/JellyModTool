"""
Skin Tab — drag images onto 4 slots (chassisSmall, chassisBig, tireSmall, tireBig),
preview them, and export a skin mod.
"""

import os
import tempfile

from PIL import Image

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QMessageBox, QGroupBox, QSizePolicy,
    QScrollArea, QSlider, QGridLayout,
)
from PyQt6.QtCore import Qt, QMimeData, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QDragEnterEvent,
    QDropEvent, QMouseEvent,
)

from utils.mod_writer import write_skin_mod


# ── Slot sizes matching the game's expected texture dimensions ──────────────
SLOT_SIZES = {
    "chassisSmall": (128, 64),
    "chassisBig":   (256, 128),
    "tireSmall":    (64,  64),
    "tireBig":      (128, 128),
}

SLOT_LABELS = {
    "chassisSmall": "Chassis Small\n(128×64)",
    "chassisBig":   "Chassis Big\n(256×128)",
    "tireSmall":    "Tire Small\n(64×64)",
    "tireBig":      "Tire Big\n(128×128)",
}


def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class ImageSlot(QLabel):
    """A drop target that holds one skin texture."""
    changed = pyqtSignal(str)  # emits slot key

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.source_path: str | None = None
        self._pil: Image.Image | None = None

        w, h = SLOT_SIZES[key]
        self.setFixedSize(max(w, 128), max(h, 64) + 24)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            "QLabel { border: 2px dashed #888; border-radius: 6px; background: #1e1e1e; color: #aaa; }"
        )
        self.setText(SLOT_LABELS[key])
        self.setWordWrap(True)

    # ── Drag & drop ──────────────────────────────────────────────────────────
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            self.load_image(urls[0].toLocalFile())

    # ── Load ─────────────────────────────────────────────────────────────────
    def load_image(self, path: str):
        try:
            img = Image.open(path).convert("RGBA")
            self.source_path = path
            self._pil = img
            self._refresh()
            self.changed.emit(self.key)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", str(e))

    def _refresh(self):
        if self._pil is None:
            return
        w, h = SLOT_SIZES[self.key]
        preview = self._pil.resize((w, h), Image.LANCZOS)
        px = pil_to_qpixmap(preview)
        self.setPixmap(px.scaled(
            self.width() - 4, self.height() - 28,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def get_pil(self) -> Image.Image | None:
        return self._pil

    def save_resized(self, dest: str):
        """Save a correctly-sized PNG to dest."""
        if self._pil is None:
            raise ValueError(f"No image loaded for slot '{self.key}'")
        w, h = SLOT_SIZES[self.key]
        self._pil.resize((w, h), Image.LANCZOS).save(dest, "PNG")

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            path, _ = QFileDialog.getOpenFileName(
                self, f"Load {self.key}", "",
                "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
            )
            if path:
                self.load_image(path)


class SkinPreview(QLabel):
    """Shows a rough composite preview of the car skin."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 180)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: #2a2a2a; border-radius: 6px;")
        self._slots: dict[str, Image.Image | None] = {k: None for k in SLOT_SIZES}
        self._draw()

    def update_slot(self, key: str, img: Image.Image | None):
        self._slots[key] = img
        self._draw()

    def _draw(self):
        canvas = Image.new("RGBA", (320, 180), (42, 42, 42, 255))

        # Chassis big centred
        cb = self._slots.get("chassisBig")
        if cb:
            thumb = cb.resize((256, 128), Image.LANCZOS)
            canvas.paste(thumb, (32, 26), thumb)

        # Tire big — left and right
        tb = self._slots.get("tireBig")
        if tb:
            thumb = tb.resize((64, 64), Image.LANCZOS)
            canvas.paste(thumb, (20, 100), thumb)
            canvas.paste(thumb, (236, 100), thumb)

        self.setPixmap(pil_to_qpixmap(canvas).scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._draw()


class SkinTab(QWidget):
    def __init__(self):
        super().__init__()
        self._slots: dict[str, ImageSlot] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Slots ────────────────────────────────────────────────────────────
        slots_group = QGroupBox("1. Load Textures  (click a slot or drag & drop an image)")
        grid = QGridLayout(slots_group)
        grid.setSpacing(12)

        keys = ["chassisSmall", "chassisBig", "tireSmall", "tireBig"]
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for key, (row, col) in zip(keys, positions):
            slot = ImageSlot(key)
            slot.changed.connect(self._on_slot_changed)
            self._slots[key] = slot
            grid.addWidget(slot, row, col)

        layout.addWidget(slots_group)

        # ── Preview ──────────────────────────────────────────────────────────
        prev_group = QGroupBox("2. Preview")
        prev_layout = QVBoxLayout(prev_group)
        self._preview = SkinPreview()
        prev_layout.addWidget(self._preview)
        layout.addWidget(prev_group)

        # ── Mod name + output ────────────────────────────────────────────────
        meta_group = QGroupBox("3. Export")
        meta_layout = QGridLayout(meta_group)

        meta_layout.addWidget(QLabel("Mod Name:"), 0, 0)
        self._name_edit = QLineEdit("My Car Skin")
        meta_layout.addWidget(self._name_edit, 0, 1)

        meta_layout.addWidget(QLabel("Output Folder:"), 1, 0)
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Where to save the mod folder…")
        meta_layout.addWidget(self._out_edit, 1, 1)
        btn_out = QPushButton("Browse…")
        btn_out.clicked.connect(self._browse_output)
        meta_layout.addWidget(btn_out, 1, 2)

        layout.addWidget(meta_group)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        btn_export = QPushButton("Export Skin Mod")
        btn_export.setFixedHeight(40)
        btn_export.clicked.connect(self._export)
        layout.addWidget(btn_export)
        layout.addStretch()

    def _on_slot_changed(self, key: str):
        self._preview.update_slot(key, self._slots[key].get_pil())

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._out_edit.setText(folder)

    def _export(self):
        missing = [k for k, s in self._slots.items() if s.get_pil() is None]
        if missing:
            QMessageBox.warning(
                self, "Missing Textures",
                "Please load images for:\n" + "\n".join(missing)
            )
            return

        out = self._out_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "No Output", "Choose an output folder first.")
            return

        name = self._name_edit.text().strip() or "My Car Skin"

        try:
            with tempfile.TemporaryDirectory() as tmp:
                paths = {}
                for key, slot in self._slots.items():
                    dest = os.path.join(tmp, key + ".png")
                    slot.save_resized(dest)
                    paths[key] = dest

                folder = write_skin_mod(
                    out, name,
                    paths["chassisSmall"], paths["chassisBig"],
                    paths["tireSmall"],    paths["tireBig"],
                )

            self._status.setText(f"✓ Skin mod exported to {folder}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
