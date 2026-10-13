#!/usr/bin/env python3
"""texchk.py <run-output.txt>... : texture presence gate (lane texchk, issue #26).

Reads the "texchk:" lines of a TEX_CHECK=1|2 build (game/Makefile; native_ui.cpp texchk::) plus the texture cache's
own failure lines, and prints one verdict per log and a total:
  TEXCHK PASS  zero failed or refused texture lookups, zero metadata / VRAM-sample changes of a resident texture,
               and coverage (at least one summary line with uploads checked);
  TEXCHK FAIL  otherwise (each failure is listed once by reason and key).
"SKIP" lines (fx-resident-only: the EFFECT_ROOM thrash guard thinning effect sprites by design) are counted, not failed.
Exit status 0 only when every log passes.
"""
import re
import sys
from collections import Counter

FAIL = re.compile(r'texchk: FAIL (\S+) (\S+) (\d+x\d+) fmt=(\d+) frame=(\d+)')
SKIP = re.compile(r'texchk: SKIP (\S+) (\S+)')
CHANGE = re.compile(r'texchk: (META CHANGED (?:header|descriptor)|VRAM CHANGED) (\S+) where=(\S+) frame=(\d+) ptr=(\S+)')
SUMMARY = re.compile(r'texchk: frame=(\d+) fails=(\d+) skips=(\d+) meta_changes=(\d+) vram_changes=(\d+) binds=(\d+) arms=(\d+)')
ROOM = re.compile(r'texchk: room frame=(\d+) fails=(\d+) changes=(\d+)')
# The cache's own failure lines (also logged without TEX_CHECK).
OTHER = (re.compile(r'native UI: upload FAILED'), re.compile(r'native UI: package absent'),
         re.compile(r'native UI: pair missing'), re.compile(r'native UI: package rejected'))


def check(path):
    fails, skips, changes, other = Counter(), Counter(), [], Counter()
    last = None
    rooms = 0
    with open(path, 'rb') as f:
        for raw in f:
            line = raw.decode('latin-1', 'replace')
            if 'texchk:' in line:
                m = FAIL.search(line)
                if m:
                    fails[(m.group(1), m.group(2), m.group(3))] += 1
                    continue
                m = SKIP.search(line)
                if m:
                    skips[m.group(1)] += 1
                    continue
                m = CHANGE.search(line)
                if m:
                    changes.append(m.groups())
                    continue
                m = SUMMARY.search(line)
                if m:
                    last = tuple(int(x) for x in m.groups())
                    continue
                if ROOM.search(line):
                    rooms += 1
                continue
            for r in OTHER:
                if r.search(line):
                    other[r.pattern] += 1
    ok = True
    print('== %s' % path)
    if last is None or last[6] == 0:
        print('  no coverage: no "texchk: frame=" summary with uploads (not a TEX_CHECK build, or the run never drew)')
        ok = False
    else:
        print('  last summary: frame=%d fails=%d skips=%d meta_changes=%d vram_changes=%d binds=%d arms=%d; room ends=%d'
              % (last + (rooms,)))
        if last[1] or last[3] or last[4]:
            ok = False
    for (why, key, shape), n in sorted(fails.items()):
        print('  FAIL %-28s %s %s (first-of-kind lines: %d)' % (why, key, shape, n))
        ok = False
    if changes:
        ok = False
        keys = Counter(c[1] for c in changes)
        print('  %d change lines over %d textures, first at frame %s: %s' % (
            len(changes), len(keys), changes[0][3], ', '.join('%s x%d' % kv for kv in keys.most_common(8))))
        for c in changes[:12]:
            print('  CHANGE %s %s where=%s frame=%s ptr=%s' % c)
    for p, n in other.items():
        print('  cache line /%s/: %d' % (p, n))
        ok = False
    for why, n in skips.items():
        print('  skip (policy, not failed) %s: %d keys' % (why, n))
    print('  TEXCHK %s' % ('PASS' if ok else 'FAIL'))
    return ok


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    results = [check(p) for p in argv[1:]]
    allok = all(results)
    print('TEXCHK %s (%d/%d logs pass)' % ('PASS' if allok else 'FAIL', sum(results), len(results)))
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
