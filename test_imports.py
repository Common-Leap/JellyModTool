#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "import_result.txt")
with open(out_path, "w") as f:
    try:
        from tabs.music_tab import MusicTab
        from tabs.skin_tab import SkinTab
        from tabs.level_tab import LevelTab
        from tabs.manage_tab import ManageTab
        from utils.mod_writer import write_song_mod, write_skin_mod
        f.write("All imports OK\n")
    except Exception as e:
        import traceback
        f.write(f"ERROR: {e}\n")
        traceback.print_exc(file=f)
