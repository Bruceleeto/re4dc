#!/usr/bin/env python3
"""safe_check.py <run-output.txt> [--margin PX] [--allow-unclipped]: speed display visible-area machine check (test 9).

Reads the "safe_area:" lines of a MCHECK_SAFE=1 build (mcheck.mk; RENDER_OPTION=1, staged with quality.txt
speed=screen). Each line gives the speed display's bounding box in screen pixels for one scene, the render size,
the tile grid and the tile rows LETTERBOX_CLIP took the translucent lists from in that scene (bit 0 = the top tile
row, bit 1 = the bottom one). Those tiles render the opaque list only, so on a console the counter vanishes under the
black bar there (issue #26); Flycast still draws it. The visible area of a scene is the frame minus
--margin pixels on every side (default 0: the reporter's TV showed the counter whole at Standard / Fast, where no row
is clipped) minus every clipped tile row.

PASS: every logged scene keeps the rectangle inside its visible area, and at least one logged scene had a clipped row
(the Quality case the check exists for; --allow-unclipped drops that coverage rule, e.g. for LETTERBOX_CLIP=0
builds). Exit 0 PASS, 1 FAIL, 2 no data.
"""
import argparse
import re
import sys

SA = re.compile(r'safe_area: frame=(\d+) present=(\d) speed=(-?\d+),(-?\d+),(-?\d+),(-?\d+) screen=(\d+)x(\d+) '
                r'tiles=(\d+)x(\d+) lbx_rows=(\d+)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--margin', type=int, default=0, help='pixels lost on every side of the frame (overscan)')
    ap.add_argument('--allow-unclipped', action='store_true')
    a = ap.parse_args()
    n = clipped_scenes = 0
    bad = []
    rects = {}
    with open(a.log, 'rb') as f:
        for raw in f:
            m = SA.search(raw.decode('latin-1'))
            if not m:
                continue
            fr, pres, x0, y0, x1, y1, w, h, tw, th, rows = (int(v) for v in m.groups())
            n += 1
            rects[(x0, y0, x1, y1, w, h, rows)] = rects.get((x0, y0, x1, y1, w, h, rows), 0) + 1
            tile_h = h // th if th else h
            vx0, vy0, vx1, vy1 = a.margin, a.margin, w - a.margin, h - a.margin
            if rows & 1:
                vy0 = max(vy0, tile_h)
            if rows & 2:
                vy1 = min(vy1, h - tile_h)
            if rows:
                clipped_scenes += 1
            if x0 < vx0 or y0 < vy0 or x1 > vx1 or y1 > vy1:
                bad.append('frame %d: speed %d,%d..%d,%d outside visible %d,%d..%d,%d (screen %dx%d, clipped rows %d)'
                           % (fr, x0, y0, x1, y1, vx0, vy0, vx1, vy1, w, h, rows))
    if not n:
        print('SPEED-SAFE NODATA: no safe_area lines in %s (MCHECK_SAFE=1 build, quality.txt speed=screen)' % a.log)
        return 2
    for k, c in sorted(rects.items(), key=lambda kv: -kv[1])[:6]:
        print('rect %d,%d..%d,%d screen %dx%d clipped rows %d: %d lines' % (k + (c,)))
    print('%d logged scenes, %d with a clipped tile row, %d outside the visible area' % (n, clipped_scenes, len(bad)))
    for b in bad[:5]:
        print('  ' + b)
    if bad:
        print('SPEED-SAFE FAIL: the speed display leaves the visible area')
        return 1
    if not clipped_scenes and not a.allow_unclipped:
        print('SPEED-SAFE FAIL: no logged scene had a letterbox-clipped tile row (no Quality letterbox coverage)')
        return 1
    print('SPEED-SAFE PASS: the speed display stays inside the visible area')
    return 0


if __name__ == '__main__':
    sys.exit(main())
