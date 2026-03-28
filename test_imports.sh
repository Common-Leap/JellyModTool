#!/bin/bash
python3 -c "
import sys
sys.path.insert(0, '.')
from tabs.music_tab import MusicTab
from tabs.skin_tab import SkinTab
from tabs.level_tab import LevelTab
from utils.mod_writer import write_song_mod, write_skin_mod
print('All imports OK')
" > /home/leap/Workshop/JellyModTool/import_result.txt 2>&1
echo "exit: $?" >> /home/leap/Workshop/JellyModTool/import_result.txt
