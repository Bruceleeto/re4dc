#!/usr/bin/env python3
"""pt_check.py <run-output.txt> [--rooms 100,101] [--min-headers N]: punch-through blend machine check (test 9).

Reads the "pt_audit:" lines of a MCHECK_PT=1 build (mcheck.mk; needs TA_HASH>=1). Each line is one scene: the
punch-through polygon / sprite headers the TA received (PCW list type 4) and how many of them did NOT blend
SRCALPHA / INVSRCALPHA. On PVR hardware a ONE / ZERO punch-through header draws the cut-out texels as solid (the
test 8 branch-tip cards, issue #26; PT_BLEND_FIX). Flycast hides it, so this check reads the headers instead.

Lines are attributed to the room of the latest "room enter <id>" / "room lifecycle: phase=enter room=<id>" line.
PASS: no bad header in any scene, and every --rooms room logged at least --min-headers punch-through headers
(coverage: an empty view proves nothing). Clean scenes are logged every 30th frame (sampled counts); every scene
with a bad header is logged (first 400). Exit 0 PASS, 1 FAIL, 2 no data.
"""
import argparse
import re
import sys

BLEND = ['ZERO', 'ONE', 'DESTCOLOR', 'INVDESTCOLOR', 'SRCALPHA', 'INVSRCALPHA', 'DESTALPHA', 'INVDESTALPHA']
PT = re.compile(r'pt_audit: frame=(\d+) present=(\d) pt_hdr=(\d+) bad=(\d+) w0=([0-9a-f]+) w2=([0-9a-f]+) ra=(\S+)')
ROOM = re.compile(r'(?:warp: room enter |room enter |room lifecycle: phase=enter room=)([0-9a-fA-F]{3})\b')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--rooms', default='', help='comma list of rooms that must show punch-through headers, e.g. 100,101')
    ap.add_argument('--min-headers', type=int, default=1)
    a = ap.parse_args()
    room = '???'
    per = {}
    samples = []
    with open(a.log, 'rb') as f:
        for raw in f:
            line = raw.decode('latin-1')
            m = ROOM.search(line)
            if m:
                room = m.group(1).lower()
                continue
            m = PT.search(line)
            if not m:
                continue
            fr, pres, hdr, bad, w0, w2, ra = m.groups()
            s = per.setdefault(room, [0, 0, 0, 0])
            s[0] += 1
            s[1] += int(hdr)
            s[2] += int(bad)
            s[3] += 1 if int(bad) else 0
            if int(bad) and len(samples) < 5:
                v = int(w2, 16)
                samples.append('room %s frame %s: %s of %s PT headers bad; first w0=%s w2=%s blend src=%s dst=%s caller=%s'
                               % (room, fr, bad, hdr, w0, w2, BLEND[v >> 29], BLEND[(v >> 26) & 7], ra))
    if not per:
        print('PT-BLEND NODATA: no pt_audit lines in %s (build with MCHECK_PT=1 TA_HASH=2)' % a.log)
        return 2
    fail = []
    for r in sorted(per):
        lines, hdr, bad, badscenes = per[r]
        print('room %s: %d logged scenes, %d PT headers, %d bad headers in %d scenes' % (r, lines, hdr, bad, badscenes))
        if bad:
            fail.append('room %s has %d ONE/ZERO-style PT headers' % (r, bad))
    for want in [x.strip().lower() for x in a.rooms.split(',') if x.strip()]:
        if per.get(want, [0, 0])[1] < a.min_headers:
            fail.append('room %s: no punch-through coverage (%d headers < %d)' % (want, per.get(want, [0, 0])[1],
                                                                                 a.min_headers))
    for s in samples:
        print('  ' + s)
    if fail:
        print('PT-BLEND FAIL: ' + '; '.join(fail))
        return 1
    print('PT-BLEND PASS: every punch-through header blends SRCALPHA/INVSRCALPHA')
    return 0


if __name__ == '__main__':
    sys.exit(main())
