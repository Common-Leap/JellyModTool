# JellyModTool

A companion GUI app for creating and managing mods for **JellyCar** (Switch/Vita port).

Built with PyQt6.

## Features

- **Music tab** — add custom background music tracks
- **Skin tab** — replace car skins with custom images
- **Level tab** — full level editor with canvas, shape presets, physics properties, save/load (`.jlvl`), and export to `.scenec` mod format
- **Manage tab** — browse, enable/disable, and delete installed mods

## Requirements

```
pip install -r requirements.txt
```

Requires Python 3.10+.

## Running

```
python3 main.py
```

## Level Editor

The level editor exports binary `.scenec` mod files compatible with the JellyCar mod loader.

- Place shapes from presets (ground, dynamic, platform, circles)
- Set car spawn and finish marker positions
- Configure per-object physics (mass, spring stiffness, kinematic flag)
- Save/load editor state as `.jlvl` (JSON)
- Import a custom thumbnail or auto-generate one from the canvas
- Patch preview images into already-exported mods

## Mod format

Mods are folders containing:
- `mod.xml` — manifest (type, name, file reference)
- The asset file (`.scenec` for levels, `.ogg`/`.mp3` for music, `.png` for skins)
- `thumb.png` — optional preview image shown in-game
