"""sgcheck.py old.re4mesh new.re4mesh sidecar.r4pw groups.r4sg: every meshlet draws the same oriented triangles
(full vertex records, rotation-canonical) before and after; group records cover the strips and their corners."""
import sys, struct
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r4im_pkg import Pkg
a = Pkg(sys.argv[1], sys.argv[3]); b = Pkg(sys.argv[2], sys.argv[3])
g = open(sys.argv[4], 'rb').read()
mag, ver, n, G, crc, nbytes, scrc, rcrc = struct.unpack_from('<4s7I', g, 0)
assert mag == b'R4SG' and n == a.nlet
bad = 0; badg = 0
def tris(p, li):
    cn, ts = p.let_tris(li)
    out = []
    for t in ts:
        r = [tuple(int(x) for x in cn[k]) for k in t]
        i = r.index(min(r)); out.append(tuple(r[i:] + r[:i]))
    return sorted(out)
for li in range(n):
    if tris(a, li) != tris(b, li):
        bad += 1
    L = b.lets[li]
    fs = b.o_strip + L['first_strip'] + (2 * L['vc'] if L['sc'] & 0x8000 else 0)
    prev = 0
    for k in range(G):
        lo0, lo1, lo2, hi0, hi1, hi2, send, v0, v1 = struct.unpack_from('<6HHBB', g, 32 + 16 * (li * G + k))
        s = fs + prev
        while s < fs + send:
            nn = b.m[s]; idx = b.m[s + 1:s + 1 + nn]; s += 1 + nn
            if any(x < v0 or x > v1 for x in idx): badg += 1
        if s != fs + send: badg += 1
        prev = send
    if prev != L['strip_bytes']: badg += 1
print('meshlets %d, triangle sets differ in %d, group record faults %d' % (n, bad, badg))
