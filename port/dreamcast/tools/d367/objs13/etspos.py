#!/usr/bin/env python3
"""etspos.py <room...>: etc model placements (ETS: u16 id, u16 slot, pad, f32 x6) from the objs13 dars, little-endian.
Prints id (etXX00), slot and the six floats (which three are the position is checked against the room bounds)."""
import struct, sys
from pathlib import Path
T = Path('/root/probe/lanes-20261014/objs/tree/port/dreamcast/tools')
sys.path[:0] = [str(T), str(T.parents[2] / 'tools')]
import room_smd as rs  # noqa
S = '/mnt/c/Game Dev/Emulators/re4-assets-private/objs-20261014/t13'
for room in sys.argv[1:]:
    dar = Path('%s/%s/%s.dar' % (S, room, room)).read_bytes()
    kind, size, dest, off = struct.unpack_from('<4I', dar, 0x20)
    pay = dar[off:off + size]
    for i, (tag, s, e) in enumerate(rs.tagged_entries(pay, '<')):
        if tag.rstrip(b'\0') != b'ETS':
            continue
        n = struct.unpack_from('<H', pay, s)[0]
        for k in range(n):
            p = s + 16 + k * 40
            ident, slot = struct.unpack_from('<2H', pay, p)
            f = struct.unpack_from('<6f', pay, p + 16)
            print(room, 'ets#%d' % i, 'et%02x00' % ident, 'slot %2d' % slot, ' '.join('%.0f' % x if abs(x) > 10 else '%.3f' % x for x in f))
