#!/usr/bin/env python3
"""et17.py <room> <etNNNN.bin>: GC vs rebuilt (PS2) model parts: per part tri count, image, flags, normal facing."""
import sys, struct
from pathlib import Path
T = Path('/root/probe/lanes-20261014/objs/tree/port/dreamcast/tools')
sys.path[:0] = [str(T), str(T.parents[2] / 'tools')]
import ps2_objects as po, ps2_bin as pb, room_smd as rs  # noqa
room, nm = sys.argv[1], sys.argv[2]
gd = Path('/mnt/c/tmp/objs/gcroom/%s.arc' % room).read_bytes()
ge = rs.tagged_entries(gd, '>')
ei = next(i for i, (t, s, e) in enumerate(ge) if t.rstrip(b'\0') == b'ETM')
gb = gd[ge[ei][1]:ge[ei][2]]
g_etm = {n.lower(): gb[s + 0x40:e] for n, s, e in po.etm_entries(gb, '>')}
PS2 = 'C:/Game Dev/Emulators/re4_helpers/Resident Evil 4 (USA)/Resident Evil 4 (USA).iso'.replace('C:', '/mnt/c')
pd = pb.afs_read(PS2, room + '.dat', pb.afs_index(PS2))
pbm = next(b for i, t, b in pb.dat_entries(pd) if t == 'ETM')
p_etm = {n.lower(): pbm[s + 0x40:e] for n, s, e in po.etm_entries(pbm, '<')}
gbin, ps2bin = g_etm[nm], p_etm[nm]
newbin, st = po.rebuild(gbin, ps2bin)
for lab, b in (('GC', gbin), ('rebuilt', newbin)):
    m = po.GcModel(b)
    print(lab, 'nv', m.nv, 'parts', m.nd)
    for k, q in enumerate(m.parts):
        h = q['hdr']
        tris = q['tris']
        # facing: mean dot(face normal, corner normal)
        pos = 0; neg = 0
        for t in tris[:400]:
            try:
                ps = [m.p(c[0]) for c in t]
                ns = [m.n(c[1]) for c in t] if hasattr(m, 'n') else None
            except Exception:
                ns = None; ps = None
            if ps and ns:
                ux, uy, uz = [ps[1][i] - ps[0][i] for i in range(3)]
                vx, vy, vz = [ps[2][i] - ps[0][i] for i in range(3)]
                fn = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
                cn = [sum(n[i] for n in ns) for i in range(3)]
                d = sum(fn[i] * cn[i] for i in range(3))
                pos += d > 0; neg += d < 0
        print('  part', k, 'tris', len(tris), 'img', h[0x0C], 'flags %02x' % h[0x0B], 'mask', h[0x0E], 'facing +%d -%d' % (pos, neg))
print('stats', {k: v for k, v in st.items() if k != 'part_images'}, st.get('part_images'))
