#!/usr/bin/env python3
"""leongc_check.py <run-output.txt>... : GC Leon machine check (issue #26, 2026-10-13; mcheck.mk MCHECK_LEONGC=1).

The user's rule: Leon is the PS2 model in every pose and room; any frame that leaves the player's model to the
source (GameCube) path is a bug. A MCHECK_LEONGC=1 build logs "LEONGC armed" at its first transaction and one
"LEONGC f=... why=..." line per change of cause (else one per 600 frames, with the running total).

PASS: every log has the armed line and no LEONGC fallback line. Prints the causes otherwise
(why: 1 identity, 2 sticky source choice, 3 second-pass group, 4 no plan, 5 layout, 6 semantics / certificate;
bind: role-binding event 21..30; cert: material certificate error / role). Exit 0 PASS, 1 FAIL, 2 no armed line.
"""
import collections
import re
import sys

LINE = re.compile(r'LEONGC f=(\d+) room=([0-9a-f]+) why=(\d+) a=(\d+) b=(\d+) bind=(\d+) cert=(\d+)/(\d+) total=(\d+)')


def main():
    if len(sys.argv) < 2:
        print('usage: leongc_check.py <run-output.txt>...', file=sys.stderr)
        return 2
    rc = 0
    for path in sys.argv[1:]:
        text = open(path, 'rb').read().decode('latin-1')
        if 'LEONGC armed' not in text:
            print('LEON-GC NODATA %s (not a MCHECK_LEONGC=1 build, or no actor drawn)' % path)
            rc = max(rc, 2)
            continue
        hits = [m.groups() for m in LINE.finditer(text)]
        if not hits:
            print('LEON-GC PASS %s (0 fallback frames)' % path)
            continue
        rc = 1
        total = max(int(h[8]) for h in hits)
        causes = collections.Counter((h[1], h[2], h[5], h[6] + '/' + h[7]) for h in hits)
        print('LEON-GC FAIL %s: %d fallback frames (at least), first f=%s room=%s' % (path, total, hits[0][0], hits[0][1]))
        for (room, why, bind, cert), n in causes.most_common():
            print('  room=%s why=%s bind=%s cert=%s lines=%d' % (room, why, bind, cert, n))
    print('LEON-GC %s' % ('PASS' if rc == 0 else 'FAIL' if rc == 1 else 'NODATA'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
