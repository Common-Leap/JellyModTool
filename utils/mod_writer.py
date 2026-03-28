"""
Writes a JellyMods mod folder to disk.
Each mod is a folder containing a mod.xml manifest and its assets.
"""

import os
import shutil
import xml.etree.ElementTree as ET


def _write_manifest(folder: str, attribs: dict):
    root = ET.Element("Mod", attribs)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    path = os.path.join(folder, "mod.xml")
    with open(path, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        tree.write(f, encoding="utf-8", xml_declaration=False)


def write_song_mod(output_dir: str, mod_name: str, ogg_path: str) -> str:
    """
    Creates a song mod folder at output_dir/mod_name.
    ogg_path must already be an OGG file (convert before calling).
    Returns the created folder path.
    """
    folder = os.path.join(output_dir, _safe_name(mod_name))
    os.makedirs(folder, exist_ok=True)

    filename = os.path.basename(ogg_path)
    dest = os.path.join(folder, filename)
    if os.path.abspath(ogg_path) != os.path.abspath(dest):
        shutil.copy2(ogg_path, dest)

    _write_manifest(folder, {
        "type": "song",
        "name": mod_name,
        "file": filename,
    })
    return folder


def write_skin_mod(output_dir: str, mod_name: str,
                   chassis_small: str, chassis_big: str,
                   tire_small: str, tire_big: str) -> str:
    """
    Creates a skin mod folder at output_dir/mod_name.
    All image paths must be PNGs (convert before calling).
    Returns the created folder path.
    """
    folder = os.path.join(output_dir, _safe_name(mod_name))
    os.makedirs(folder, exist_ok=True)

    def copy(src, name):
        dest = os.path.join(folder, name)
        if os.path.abspath(src) != os.path.abspath(dest):
            shutil.copy2(src, dest)
        return name

    cs = copy(chassis_small, "chassisSmall.png")
    cb = copy(chassis_big,   "chassisBig.png")
    ts = copy(tire_small,    "tireSmall.png")
    tb = copy(tire_big,      "tireBig.png")

    _write_manifest(folder, {
        "type": "skin",
        "name": mod_name,
        "chassisSmall": cs,
        "chassisBig":   cb,
        "tireSmall":    ts,
        "tireBig":      tb,
    })
    return folder


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
