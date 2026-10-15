#!/usr/bin/env python3
"""fx_keys.py <ps2lib root> [--rooms r100,...]: the texture keys of every GameCube effect picture (lane vram12 D4).

The runtime logs a GameCube-picture effect texture by its package key ("vram gc-fx: r=101 f=.. key=crc-fnv",
native_ui.cpp VRAM_ROOM_LOG=1); ps2lib/INDEX.tsv lists effect textures by GameCube id (st1/r101.arc#8:0xc4). This walks
the same GameCube EFF tables as test12fx/fx_ps2_pack.py lib (common = etc/core.das EFF#1, each route room = its
decoded room archive) and writes <ps2lib>/effects-tex/KEYS.tsv: key, room, gc_id, frame (one row per picture; a key
shared by several ids gets one row each). vram/vram_gate.py joins it with INDEX.tsv. Re-run after fx_ps2_pack lib.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'test12fx'))
import fx_ps2_pack as F  # noqa: E402


def main(a):
    lib = Path(a[0])
    rooms = F.ROUTE
    if '--rooms' in a:
        rooms = a[a.index('--rooms') + 1].split(',')
    jobs = [('common', [('etc/core.das', Path('/root/re4data/etc/core.das'))], {'etc/core.das:0#1'})]
    jobs += [(r, [('st1/%s.arc' % r, Path('/root/probe/worldfx-cache/%s.gc' % r))], None) for r in rooms]
    rows = []
    for room, files, only in jobs:
        ids, tpls = F.gc_eff_tables_files(files)
        if only:
            ids = {k: v for k, v in ids.items() if k in only}
        for ctx, tids in ids.items():
            for n, tid in enumerate(tids):
                for f, (key, w, h) in enumerate(tpls.get('%s/tpl%d' % (ctx, n), [])):
                    rows.append((key, room, '%s:0x%02x' % (ctx, tid), f, w, h))
        print('%s: %d pictures' % (room, sum(1 for r in rows if r[1] == room)))
    out = lib / 'effects-tex' / 'KEYS.tsv'
    out.write_text('key\troom\tgc_id\tframe\twidth\theight\n' + ''.join('%s\t%s\t%s\t%d\t%d\t%d\n' % r for r in rows))
    print('fx_keys: %d rows, %d keys -> %s' % (len(rows), len({r[0] for r in rows}), out))


if __name__ == '__main__':
    main(sys.argv[1:])
