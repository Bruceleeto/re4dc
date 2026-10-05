#!/usr/bin/env python3
"""tacmp.py A/run-output.txt B/run-output.txt [--from F --to T]: compare TA_HASH=2 lines of two runs.
Frame-aligned (native frame number) equality of the per-list hashes and word counts, plus the multiset view
(scenes of A whose full hash tuple never appears in B and vice versa)."""
import re, sys, collections
pat = re.compile(r'ta_hash: frame=(\d+) present=(\d) op=(\w+)/(\d+) tr=(\w+)/(\d+) pt=(\w+)/(\d+) mod=(\w+)/(\d+),(\w+)/(\d+)')
def load(p, lo, hi):
    d = {}
    for line in open(p, errors='replace'):
        m = pat.search(line)
        if not m: continue
        f = int(m.group(1))
        if f < lo or f > hi: continue
        d[f] = m.groups()[1:]
    return d
args = sys.argv[1:]
lo, hi = 0, 1 << 40
if '--from' in args: i = args.index('--from'); lo = int(args[i + 1]); del args[i:i + 2]
if '--to' in args: i = args.index('--to'); hi = int(args[i + 1]); del args[i:i + 2]
A, B = load(args[0], lo, hi), load(args[1], lo, hi)
common = sorted(set(A) & set(B))
eq = [f for f in common if A[f] == B[f]]
ne = [f for f in common if A[f] != B[f]]
print(f'scenes A={len(A)} B={len(B)} common frames={len(common)} equal={len(eq)} different={len(ne)}')
for f in ne[:8]:
    print('  diff frame', f, 'A', ' '.join(A[f]), '| B', ' '.join(B[f]))
ca, cb = collections.Counter(A.values()), collections.Counter(B.values())
print(f'multiset: A-only {sum((ca - cb).values())} B-only {sum((cb - ca).values())} of {len(A)}/{len(B)}')
