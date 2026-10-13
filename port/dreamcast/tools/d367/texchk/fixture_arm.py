#!/usr/bin/env python3
"""Retarget a route fixture's REL overlays (dc/*.ovl) to the arm under test.

Usage: fixture_arm.py <in.json> <out.json> <arm-label> [--warp <warp.txt>]

Overlays are relocated against the game ELF they were built with. A fixture that pins
dc/em2f.ovl (or pl0f/em22/em2b/pl11) from another arm's programs/candidate-route<X>/ links
that module against the wrong symbol table: the room boots, and the first call into the
module jumps to a stale address (lakerig 2026-10-13: st-lake FAULT in the em2f thread at
pc=00121e40 and in EspTrans after pl0f; texchk N-lake / L-lake / L-lake2). Rooms that never
load those modules (h2, square, r103) hide the mismatch.

Every dc/*.ovl entry is rewritten to programs/candidate-route<arm>/<name>.ovl; the script
refuses if that file does not exist. --warp replaces dc/warp.txt.
"""
import json, os, re, sys

HW = ('/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/'
      'continuation-20260927/playability-r11-r1/programs')


def main(argv):
    if len(argv) < 4:
        print(__doc__); return 2
    src, dst, arm = argv[1], argv[2], argv[3]
    warp = None
    if '--warp' in argv:
        warp = argv[argv.index('--warp') + 1]
    d = json.load(open(src))
    rep = d['replace']
    cand = os.path.join(HW, 'candidate-route' + arm)
    n = 0
    for k in sorted(rep):
        if re.fullmatch(r'dc/[a-z0-9_]+\.ovl', k):
            new = os.path.join(cand, os.path.basename(k))
            if not os.path.isfile(new):
                print('fixture_arm: missing %s' % new); return 1
            if rep[k] != new:
                print('fixture_arm: %s %s -> %s' % (k, rep[k], new)); n += 1
            rep[k] = new
    if warp:
        rep['dc/warp.txt'] = warp
    d.setdefault('provenance', {})['fixture_arm'] = {'src': src, 'arm': arm, 'ovl_retargeted': n}
    json.dump(d, open(dst, 'w'), indent=1)
    print('fixture_arm: %s retargeted=%d' % (dst, n))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
