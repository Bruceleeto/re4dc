#!/usr/bin/env python3
"""elfdiff.py A.elf B.elf: per-symbol byte comparison (functions + objects), by name, plus section sizes."""
import subprocess, sys
TOOL = '/opt/toolchains/dc/sh-elf/bin/sh-elf-'
def syms(e):
    out = {}
    for l in subprocess.check_output([TOOL + 'nm', '-S', '--size-sort', e], text=True).splitlines():
        f = l.split()
        if len(f) == 4 and f[2] in 'tTdDrRbB':
            out.setdefault(f[3], []).append((int(f[0], 16), int(f[1], 16), f[2]))
    return out
def secs(e):
    r = {}
    for l in subprocess.check_output([TOOL + 'objdump', '-h', e], text=True).splitlines():
        f = l.split()
        if len(f) >= 7 and f[0].isdigit():
            r[f[1]] = (int(f[2], 16), int(f[3], 16), int(f[5], 16))
    return r
def image(e):
    import tempfile, os
    t = tempfile.mktemp()
    subprocess.check_call([TOOL + 'objcopy', '-R', '.stack', '-O', 'binary', e, t])
    d = open(t, 'rb').read(); os.unlink(t); return d
A, B = sys.argv[1:3]
sa, sb = secs(A), secs(B)
base = min(v[1] for v in sa.values() if v[1] >= 0x8c000000)
for k in sorted(set(sa) | set(sb)):
    if sa.get(k, (0,))[0] != sb.get(k, (0,))[0]: print('section', k, 'size', hex(sa.get(k, (0,))[0]), '->', hex(sb.get(k, (0,))[0]))
ia, ib = image(A), image(B)
ya, yb = syms(A), syms(B)
for n in sorted(set(ya) - set(yb)): print('only A', n, ya[n])
for n in sorted(set(yb) - set(ya)): print('only B', n, yb[n])
ch = []
for n in sorted(set(ya) & set(yb)):
    if len(ya[n]) != 1 or len(yb[n]) != 1: continue
    (a0, al, at), (b0, bl, bt) = ya[n][0], yb[n][0]
    if at in 'bB':
        if al != bl: ch.append((n, 'size %d->%d' % (al, bl)))
        continue
    da = ia[a0 - base:a0 - base + al]; db = ib[b0 - base:b0 - base + bl]
    if al != bl: ch.append((n, 'size %d->%d' % (al, bl)))
    elif da != db:
        # same size: count differing bytes (relocated addresses differ when layout shifts)
        nd = sum(1 for x, y in zip(da, db) if x != y)
        ch.append((n, 'bytes differ %d/%d' % (nd, al)))
shift = sum(1 for n in ya if n in yb and len(ya[n]) == 1 and len(yb[n]) == 1 and ya[n][0][0] != yb[n][0][0])
print('symbols moved', shift)
for n, w in ch: print('changed', n, w)
print('image sizes', len(ia), len(ib), 'identical' if ia == ib else 'DIFFERENT')
