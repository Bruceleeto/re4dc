#!/usr/bin/env python3
"""lookwarps.py: object-facing warps for the objs13 look sheet (work/warps/look<r>.txt). Leon is put D units from a
converted object (ETS placement or room-code position), on the line toward the room's entry warp (walkable), facing it
(warp angle a: facing = (sin a, cos a) in x/z, as x101). The entry warp's room/scenario/find/inv/dead lines are kept;
goto / kill / census / freeze are dropped; `god` and `freeze 1200` (settled, frame-locked still) are added."""
import math
W = '/root/probe/lanes-20261014/objs/work/warps'
# room: (object label, object x, y, z, distance, leon y or None = object y)
T = {
    '102': ('et1300 door', -12664, 0, -16316, 3500, None),
    '103': ('et0500', -7977, -15, -2517, 3500, None),
    '104': ('et1700', -4599, -78, -3011, 3000, None),
    '105': ('et2200 door', 18291, 3160, 3365, 3500, None),
    '106': ('BIN 0x34 closet', 158202, -9297, -43582, 4000, None),
    '107': ('et1600', 62987, 252, -41141, 3500, None),
    '108': ('et1a00 medal', 62496, 8326, -8632, 2500, 8624),
    '109': ('et1000 torch', 113675, 3293, 16415, 3500, 2226),
    '10a': ('BIN 0x20 rock', -43779, 18285, 67184, 9000, 7346),
    '10b': ('BIN 0x1e island', 12708, -1300, 33719, 7000, 0),
    '117': ('et1600', 6650, 4175, -3291, 3000, 4151),
    '118': ('et1a00 medal', 62496, 8326, -8632, 2500, 8624),
    '11a': ('et1000 torch', 35180, -5265, 93656, 3500, None),
    '11b': ('et0300', 130639, -189, 170191, 4000, None),
    '119': ('BIN 0x22 tree', 108540, 2350, 9387, 4500, None),
}
TOWARD = {'117': (0, -2072)}  # r117: from the church centre (chandelier) side
for r, (lab, ox, oy, oz, d, ly) in T.items():
    src = '%s/w%s.txt' % (W, r) if r != '11b' else '%s/x11b.txt' % W
    lines = open(src).read().splitlines()
    ex, ez = None, None
    keep = []
    for ln in lines:
        k = ln.split()[0] if ln.split() else ''
        if k == 'pos':
            ex, ez = float(ln.split()[1]), float(ln.split()[3])
            continue
        if k in ('ang', 'goto', 'kill', 'census', 'freeze', 'god', 'name', 'pad', 'act', 'act_clock', 'dump'):
            continue
        keep.append('room 0x109' if (r == '109' and k == 'room') else ln)
    tx, tz = TOWARD.get(r, (ex, ez))
    vx, vz = tx - ox, tz - oz
    n = math.hypot(vx, vz) or 1.0
    px, pz = ox + d * vx / n, oz + d * vz / n
    a = math.atan2(ox - px, oz - pz)
    out = ['name look%s' % r, '# objs13 look sheet: Leon %d from %s (%d %d %d), facing it' % (d, lab, ox, oy, oz)]
    out += [x for x in keep if not x.startswith('#')]
    out += ['pos %d %d %d' % (px, ly if ly is not None else oy, pz), 'ang %.4f' % a, 'god', 'freeze 1200']
    # room line must come first in the rig's order: keep the source order (room first), pos/ang after
    open('%s/look%s.txt' % (W, r), 'w').write('\n'.join(out) + '\n')
    print(r, lab, 'pos %d %d %d ang %.3f' % (px, ly if ly is not None else oy, pz, a))
