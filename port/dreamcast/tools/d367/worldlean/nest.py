"""nest.py mesh sidecar: do meshlet boxes nest inside their cluster box, and cluster boxes (grid -> model) inside the mesh
bounds? (hierarchical fully-inside skip needs child box <= parent box)."""
import sys
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r4im_pkg import Pkg
p = Pkg(sys.argv[1], sys.argv[2])
bad_l = tot_l = 0; worst_m = [0.0, 0.0, 0.0]; bad_c = tot_c = 0
for mi, m in enumerate(p.meshes):
    for k in range(m['part_count']):
        part = m['first_part'] + k
        fc, cc = p.plod[part]
        for c in range(fc, fc + cc):
            cl = p.clusters[c]; tot_c += 1
            lo = [m['origin'][a] + m['step'][a] * cl['bmin'][a] for a in range(3)]
            hi = [m['origin'][a] + m['step'][a] * cl['bmax'][a] for a in range(3)]
            out = False
            for a in range(3):
                l0, h0 = min(lo[a], hi[a]), max(lo[a], hi[a])
                d = max(m['bmin'][a] - l0, h0 - m['bmax'][a], 0.0)
                st = abs(m['step'][a])
                if d > 0:
                    out = True; worst_m[a] = max(worst_m[a], d / st if st else d)
            bad_c += out
            for lv in range(cl['first_level'], cl['first_level'] + cl['level_count']):
                fm, mc, _ = p.levels[lv]
                for li in range(fm, fm + mc):
                    L = p.lets[li]; tot_l += 1
                    if any(L['bmin'][a] < cl['bmin'][a] or L['bmax'][a] > cl['bmax'][a] for a in range(3)):
                        bad_l += 1
print('meshlets outside their cluster box: %d of %d' % (bad_l, tot_l))
print('clusters outside the mesh bounds: %d of %d; worst overhang in grid steps per axis %s' % (bad_c, tot_c, ['%.2f' % w for w in worst_m]))
