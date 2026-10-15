#!/usr/bin/env python3
"""tools/d367/objs_census.py <room> <dar> [<room> <dar> ...]: offline room-object census of a staged room archive (lane objs).
Every model the room archive gives the source model path (room BINs + ETM etc BINs) is classified:
  PS2     geometry rebuilt from the PS2 BIN (bytes differ from le_mirror(GC BIN), triangles > 0)
  WORLD   emptied: the PS2 draws the object in its scenario SMD (world package)
  GC      byte-equal to le_mirror(GC BIN): a GameCube model is drawn (a bug unless listed with a reason)
Prints one line per model and a per-room summary; exit 1 if any GC model is not in the known list (KNOWN)."""
import struct, sys
from pathlib import Path
T = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(T), str(T.parents[2] / 'tools')]
import ps2_objects as po, ps2_bin as pb, room_smd as rs  # noqa
import convert_character as cc  # noqa
from assetpipe.rooms import GcIso  # noqa

# GC models kept on purpose (reason). Anything else GC fails the census.
KNOWN = {
    'et0000.bin': 'window pane: the PS2 model is a placeholder (1 degenerate triangle); pane source on PS2 unproven',
    'et2500.bin': 'window pane: the PS2 model is a placeholder (1 degenerate triangle); pane source on PS2 unproven',
    'et1400.bin': 'torch type 0: absent from the PS2 room ETM',
    'et1000.bin@r11a': 'torch type 4: absent from the r11a PS2 ETM',
    'et1100.bin@r119': 'r119 dark block (look lane): et1100 stays GC with BIN 0x22 converted',
    'et1000.bin@r119': 'r119 keeps the r119c package (heap 4 at the limit; not regenerated)',
}


def main():
    a = sys.argv[1:]
    g = GcIso(po.GC_ISO)
    keys = dict(g.rooms())
    bad = 0
    for room, dar_path in zip(a[0::2], a[1::2]):
        dar = Path(dar_path).read_bytes()
        kind, size, dest, off = struct.unpack_from('<4I', dar, 0x20)
        pay = dar[off:off + size]
        gd = g.read(keys[room])
        if gd[:32] == rs.CONTAINER_MAGIC:
            gd = rs.decode_das(gd)
        ge = rs.tagged_entries(gd, '>')
        le = rs.tagged_entries(pay, '<')
        rows = []
        for i, (tag, s, e) in enumerate(ge):
            if tag.rstrip(b'\0') == b'BIN' and e > s:
                cur = pay[le[i][1]:le[i][2]].rstrip(b'\0')
                src = po.to_le(gd[s:e], hex(i + 4)).rstrip(b'\0')
                gt = sum(len(p['tris']) for p in po.GcModel(gd[s:e]).parts)
                rows.append(('BIN %#x' % (i + 4), cur == src, len(cur) < 0.05 * len(src), gt, len(src), len(cur)))
            if tag.rstrip(b'\0') == b'ETM':
                gb = gd[s:e]
                lb = pay[le[i][1]:le[i][2]]
                for (nm, gs, gend), (lnm, ls, lend) in zip(po.etm_entries(gb, '>'), po.etm_entries(lb, '<')):
                    if not nm.lower().endswith('.bin'):
                        continue
                    try:
                        src = po.to_le(gb[gs + 0x40:gend], nm).rstrip(b'\0')
                        gt = sum(len(p['tris']) for p in po.GcModel(gb[gs + 0x40:gend]).parts)
                    except Exception as ex:
                        rows.append((nm, None, False, None, 0, 0)); continue
                    cur = lb[ls + 0x40:lend].rstrip(b'\0')
                    rows.append((nm, cur == src, False, gt, len(src), len(cur)))
        n = {'PS2': 0, 'WORLD': 0, 'GC': 0, 'GC-known': 0, '?': 0}
        for nm, same, empty, gt, sb, cb in rows:
            if same is None:
                st, why = '?', 'GC parse failed'
            elif not same:
                st, why = ('WORLD' if empty else 'PS2'), ''
            else:
                k = KNOWN.get('%s@%s' % (nm, room)) or KNOWN.get(nm)
                st, why = ('GC-known', k) if k else ('GC', 'NOT CONVERTED')
            n[st] += 1
            if st in ('GC', '?'):
                bad += 1
            print('%s %-10s %-8s GC tris %-5s bytes %6d -> %6d %s' % (room, nm, st, gt, sb, cb, why))
        print('%s SUMMARY %s payload %d' % (room, ' '.join('%s=%d' % kv for kv in n.items()), size))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
