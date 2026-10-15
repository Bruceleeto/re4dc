"""stage-scenario.py front door (lane stage-ext4, 2026-10-14; source port/dreamcast/tools/d367/stage_ext4/harness-shim.py).

Default: stage-ext4/stage_scenario.py - the image is built and verified on WSL ext4, copied once into the C: disc cache
(C:\\Flycast-Evidence\\_disccache\\<sha256>\\disc.bin) and hard-linked into scenarios/<name>/disc/disc.bin; a staging
with the same inputs as a cached image reuses it. Same arguments, same scenario files, same stage.json status.
RE4DC_STAGE_EXT4=0: stage-scenario-copy.py, the previous script, unchanged (old copy path; kept for one day).
"""
import os, sys
H = os.path.dirname(os.path.abspath(__file__))
if os.environ.get('RE4DC_STAGE_EXT4', '1') == '0':
    t = os.path.join(H, 'stage-scenario-copy.py')
else:
    t = os.path.join(H, 'stage-ext4', 'stage_scenario.py')
os.execv(sys.executable, [sys.executable, t] + sys.argv[1:])
