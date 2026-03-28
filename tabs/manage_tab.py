"""
Manage Tab — disable built-in songs, skins, and levels.
Writes a disable.xml to the JellyMods folder.
"""

import os
import xml.etree.ElementTree as ET

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QMessageBox, QGroupBox, QCheckBox,
    QScrollArea, QGridLayout,
)
from PyQt6.QtCore import Qt

# ── Built-in content lists ────────────────────────────────────────────────────

BUILTIN_SONGS = [
    (1, "Song 1"), (2, "Song 2"), (3, "Song 3"), (4, "Song 4"),
    (5, "Song 5"), (6, "Song 6"), (7, "Song 7"),
]

BUILTIN_SKINS = [
    "Classic", "Car 65", "It's me, Mario!", "Hell Car", "Pata Car",
    "Donkey Car", "Footbal", "Red Steel Car", "Pac Man", "Kitty Car", "Peace",
]

BUILTIN_LEVELS = [
    "Tutorial", "Initiation", "Forest", "Slide", "Crusher",
    "Moving Platforms", "Kerplunk", "Balloon Squeeze", "Snake", "Lance",
    "Cave", "Saw", "Ski Jump", "Spiral", "Catapult", "Boat", "Boulders",
    "Mouse", "Factory", "Grass Lifts", "Platformer", "Slow Spin", "Circus",
    "Descent", "Ride the Wave", "Water Underneath", "Cave Escape",
    "Semi Circles", "The Dryer", "Space Ship", "Spongy Bridges", "Lemons",
    "Rocket Launch", "Pinwheels", "The Big Wheel", "Up", "Circle Waves",
    "Horseshoes", "Jello Fortress", "Launch", "Box Towers", "Candy Canes",
    "Beware The Spikes", "Round and Round", "Grinder", "Boulders 2",
    "Homeward", "Float By", "Revolver", "Grapes", "Loading", "Homerun",
    "Jelly Derby", "Lift", "Piter Pan", "Slow Fall", "Jaklub",
    "Storm the Castle", "Cogs", "Green Maze", "Mouse Ears",
]


def _make_scroll_group(title: str, items: list, key_fn) -> tuple:
    """
    Returns (group_widget, {key: QCheckBox}, select_all_btn).
    key_fn(item) -> hashable key used in the returned dict.
    """
    group = QGroupBox(title)
    outer = QVBoxLayout(group)
    outer.setSpacing(4)

    # Select All / None row
    btn_row = QHBoxLayout()
    btn_all  = QPushButton("Select All")
    btn_none = QPushButton("Select None")
    btn_all.setFixedHeight(26)
    btn_none.setFixedHeight(26)
    btn_row.addWidget(btn_all)
    btn_row.addWidget(btn_none)
    btn_row.addStretch()
    outer.addLayout(btn_row)

    # Scrollable checkbox area
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFixedHeight(160)
    scroll.setStyleSheet("QScrollArea { border: none; }")

    inner = QWidget()
    grid  = QGridLayout(inner)
    grid.setSpacing(4)
    grid.setContentsMargins(4, 4, 4, 4)

    cols = 3
    checks = {}
    for i, item in enumerate(items):
        cb = QCheckBox(str(item) if not isinstance(item, tuple) else item[1])
        cb.setChecked(False)
        grid.addWidget(cb, i // cols, i % cols)
        checks[key_fn(item)] = cb

    scroll.setWidget(inner)
    outer.addWidget(scroll)

    # Wire select all/none
    def _set_all(state):
        for cb in checks.values():
            cb.setChecked(state)

    btn_all.clicked.connect(lambda: _set_all(True))
    btn_none.clicked.connect(lambda: _set_all(False))

    return group, checks


class ManageTab(QWidget):
    def __init__(self):
        super().__init__()
        self._song_checks  = {}
        self._skin_checks  = {}
        self._level_checks = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lbl = QLabel(
            "Check items to DISABLE them from the base game. "
            "Export writes a disable.xml to your JellyMods folder."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(lbl)

        # Songs
        song_group, self._song_checks = _make_scroll_group(
            "Built-in Songs  (check = disabled)",
            BUILTIN_SONGS,
            key_fn=lambda x: x[0],  # key is the 1-based index
        )
        layout.addWidget(song_group)

        # Skins
        skin_group, self._skin_checks = _make_scroll_group(
            "Built-in Skins  (check = disabled)",
            BUILTIN_SKINS,
            key_fn=lambda x: x,
        )
        layout.addWidget(skin_group)

        # Levels
        level_group, self._level_checks = _make_scroll_group(
            "Built-in Levels  (check = disabled)",
            BUILTIN_LEVELS,
            key_fn=lambda x: x,
        )
        layout.addWidget(level_group)

        # Output
        out_group = QGroupBox("Output — JellyMods folder")
        og = QHBoxLayout(out_group)
        self._out_edit = QLineEdit()
        self._out_edit.setPlaceholderText("Path to your JellyMods folder on SD card…")
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        og.addWidget(self._out_edit)
        og.addWidget(btn_browse)
        layout.addWidget(out_group)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        btn_export = QPushButton("Export disable.xml")
        btn_export.setFixedHeight(40)
        btn_export.clicked.connect(self._export)
        layout.addWidget(btn_export)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select JellyMods Folder")
        if folder:
            self._out_edit.setText(folder)

    def _export(self):
        out = self._out_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "No Output", "Choose the JellyMods folder first.")
            return

        disabled_songs  = [idx for idx, cb in self._song_checks.items()  if cb.isChecked()]
        disabled_skins  = [name for name, cb in self._skin_checks.items() if cb.isChecked()]
        disabled_levels = [name for name, cb in self._level_checks.items() if cb.isChecked()]

        root = ET.Element("Disable")

        if disabled_songs:
            songs_el = ET.SubElement(root, "Songs")
            for idx in sorted(disabled_songs):
                ET.SubElement(songs_el, "Song", index=str(idx))

        if disabled_skins:
            skins_el = ET.SubElement(root, "Skins")
            for name in disabled_skins:
                ET.SubElement(skins_el, "Skin", name=name)

        if disabled_levels:
            levels_el = ET.SubElement(root, "Levels")
            for name in disabled_levels:
                ET.SubElement(levels_el, "Level", name=name)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="    ")
        dest = os.path.join(out, "disable.xml")
        try:
            os.makedirs(out, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
                tree.write(f, encoding="utf-8", xml_declaration=False)
            total = len(disabled_songs) + len(disabled_skins) + len(disabled_levels)
            self._status.setText(f"✓ Wrote disable.xml  ({total} items disabled)")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def load_existing(self, path: str):
        """Optionally pre-populate checkboxes from an existing disable.xml."""
        if not os.path.exists(path):
            return
        try:
            tree = ET.parse(path)
            root = tree.getroot()

            songs = root.find("Songs")
            if songs is not None:
                for s in songs.findall("Song"):
                    idx = int(s.get("index", 0))
                    if idx in self._song_checks:
                        self._song_checks[idx].setChecked(True)

            skins = root.find("Skins")
            if skins is not None:
                for s in skins.findall("Skin"):
                    name = s.get("name", "")
                    if name in self._skin_checks:
                        self._skin_checks[name].setChecked(True)

            levels = root.find("Levels")
            if levels is not None:
                for l in levels.findall("Level"):
                    name = l.get("name", "")
                    if name in self._level_checks:
                        self._level_checks[name].setChecked(True)
        except Exception:
            pass
