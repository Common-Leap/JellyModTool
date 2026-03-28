"""
JellyMod Tool — companion app for creating JellyCar mods.
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt6.QtGui import QIcon

from tabs.music_tab import MusicTab
from tabs.skin_tab import SkinTab
from tabs.level_tab import LevelTab
from tabs.manage_tab import ManageTab

DARK_STYLE = """
QWidget {
    background-color: #1a1a1a;
    color: #e0e0e0;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #1a1a1a;
}
QTabWidget::pane {
    border: 1px solid #333;
    border-radius: 4px;
    background: #1e1e1e;
}
QTabBar::tab {
    background: #2a2a2a;
    color: #aaa;
    padding: 8px 20px;
    border: 1px solid #333;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 100px;
}
QTabBar::tab:selected {
    background: #1e1e1e;
    color: #fff;
    border-bottom: 1px solid #1e1e1e;
}
QTabBar::tab:hover:!selected {
    background: #333;
}
QGroupBox {
    border: 1px solid #333;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    color: #ccc;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QPushButton {
    background-color: #2d5a8e;
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #3a6fa8;
}
QPushButton:pressed {
    background-color: #1e4070;
}
QPushButton:disabled {
    background-color: #333;
    color: #666;
}
QLineEdit {
    background: #2a2a2a;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e0e0e0;
}
QLineEdit:focus {
    border-color: #2d5a8e;
}
QListWidget {
    background: #222;
    border: 1px solid #444;
    border-radius: 4px;
    color: #ddd;
}
QListWidget::item:selected {
    background: #2d5a8e;
}
QProgressBar {
    background: #2a2a2a;
    border: 1px solid #444;
    border-radius: 4px;
    text-align: center;
    color: #fff;
}
QProgressBar::chunk {
    background: #2d5a8e;
    border-radius: 3px;
}
QScrollBar:vertical {
    background: #222;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #444;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JellyMod Tool")
        self.resize(900, 700)
        self.setMinimumSize(700, 500)

        tabs = QTabWidget()
        tabs.addTab(MusicTab(),   "🎵  Music")
        tabs.addTab(SkinTab(),    "🎨  Skins")
        tabs.addTab(LevelTab(),   "🗺  Levels")
        tabs.addTab(ManageTab(),  "⚙  Manage")
        self.setCentralWidget(tabs)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
