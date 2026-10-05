#!/usr/bin/env python3
"""iv_sub.py <hwmodel dir> <drawn|skip> <regex> [top]: lane iv. Inclusive hw ms per tick of the outermost call-tree
nodes whose function matches <regex>, calls per tick, and the subtree's self ms by function (top N)."""
import os, re, sys
sys.argv, args = sys.argv[:1] + [sys.argv[1], sys.argv[2]], sys.argv
E, mode, rx = args[1], args[2], re.compile(args[3])
TOP = int(args[4]) if len(args) > 4 else 20
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, 'iv_incl.py')).read().split('\nfor mode in MODES:')[0]
exec(src)
nodes, kids, fn, nfr = load(mode)
K = 200000.0 * nfr
t, c, sub = subtree(nodes, kids, fn, rx)
print('== %s %s /%s/: %.3f ms/tick, %.2f calls/tick (%d ticks)' % (os.path.basename(E.rstrip('/')), mode, args[3], t / K, c / nfr, nfr))
for f_, v in sub.most_common(TOP):
    print('   %-44s %.3f' % (f_[:44], v / K))
