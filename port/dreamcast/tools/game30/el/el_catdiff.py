#!/usr/bin/env python3
"""el_catdiff.py <A cat file> <B cat file> <A name> <B name>: category deltas of two el_cat.py outputs (lane el)."""
import re, sys
def parse(fn):
    out = {}; cur = None
    for l in open(fn):
        m = re.match(r'== (\S+) (\w+): cEmMgr::move ([\d.]+)', l)
        if m:
            cur = (m.group(1), m.group(2)); out[cur] = {}; continue
        if cur and l.strip() and not l.startswith(('category', 'calls', 'per ')):
            p = re.split(r'\s{2,}', l.strip())
            try: out[cur][p[0]] = float(p[1])
            except (ValueError, IndexError): pass
    return out
A = parse(sys.argv[1]); B = parse(sys.argv[2])
for m in ('drawn', 'skip'):
    x = A[(sys.argv[3], m)]; y = B[(sys.argv[4], m)]
    print('%s -> %s %s' % (sys.argv[3], sys.argv[4], m))
    for k in sorted(set(x) | set(y), key=lambda k: -x.get(k, 0)):
        print('   %-34s %7.3f %7.3f %+7.3f' % (k, x.get(k, 0), y.get(k, 0), y.get(k, 0) - x.get(k, 0)))
