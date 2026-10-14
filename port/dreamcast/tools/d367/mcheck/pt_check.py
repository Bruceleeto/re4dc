#!/usr/bin/env python3
"""Check packet-aware MCHECK_PT v2 records for PT blend and decoder validity.

Each completed scene reports actual PT headers, not independent 32-byte words.
Clean scenes are sampled every 30 native frames; every bad/invalid/incomplete
scene is logged. PASS covers the logged scenes and requires positive v2 header
coverage in every requested room. It does not certify an unlogged capture tail.
Legacy bad rows remain FAIL evidence; legacy clean rows cannot establish v2
packet-boundary coverage. Truncated, malformed, unknown or mixed schemas fail.
"""
import argparse
import re
import sys

BLEND = ['ZERO', 'ONE', 'DESTCOLOR', 'INVDESTCOLOR', 'SRCALPHA', 'INVSRCALPHA', 'DESTALPHA', 'INVDESTALPHA']
FIELDS = (r'frame=(?P<frame>\d+) present=(?P<present>[01]) pt_hdr=(?P<headers>\d+) bad=(?P<bad>\d+)')
WORDS = r'w0=(?P<w0>[0-9a-fA-F]{8}) w2=(?P<w2>[0-9a-fA-F]{8}) ra=(?P<ra>\S+)'
PT_V2 = re.compile(r'pt_audit: v=2 ' + FIELDS +
                   r' invalid=(?P<invalid>\d+) incomplete=(?P<incomplete>\d+) why=(?P<why>\d+) ' + WORDS)
PT_LEGACY = re.compile(r'pt_audit: ' + FIELDS + ' ' + WORDS)
ROOM = re.compile(r'(?:warp: room enter |room enter |room lifecycle: phase=enter room=)([0-9a-fA-F]{3})\b')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log')
    ap.add_argument('--rooms', default='', help='rooms requiring v2 PT headers, e.g. 100,101')
    ap.add_argument('--min-headers', type=int, default=1)
    a = ap.parse_args(argv)
    wanted = [x.strip().lower() for x in a.rooms.split(',') if x.strip()]
    if a.min_headers < 1 or any(not re.fullmatch(r'[0-9a-f]{3}', x) for x in wanted):
        ap.error('--min-headers must be positive and --rooms must contain three-digit hexadecimal room IDs')
    room = '???'
    per = {}
    samples, malformed = [], []
    versions = set()
    with open(a.log, 'rb') as f:
        for number, raw in enumerate(f, 1):
            line = raw.decode('latin-1')
            entered = ROOM.search(line)
            if entered:
                room = entered.group(1).lower()
            if 'pt_audit:' not in line:
                continue
            text = line.rstrip('\r\n')
            m = PT_V2.fullmatch(text)
            version = 2
            if not m:
                m = PT_LEGACY.fullmatch(text)
                version = 1
            if not m or not raw.endswith(b'\n'):
                malformed.append(number)
                continue
            d = m.groupdict()
            headers, bad = int(d['headers']), int(d['bad'])
            invalid, incomplete = int(d.get('invalid', 0)), int(d.get('incomplete', 0))
            why = int(d.get('why', 0))
            if bad > headers or (version == 2 and bool(why) != bool(invalid or incomplete)):
                malformed.append(number)
                continue
            versions.add(version)
            s = per.setdefault(room, dict(lines=0, headers=0, bad=0, invalid=0, incomplete=0, v2_headers=0))
            s['lines'] += 1
            s['headers'] += headers
            s['bad'] += bad
            s['invalid'] += invalid
            s['incomplete'] += incomplete
            if version == 2:
                s['v2_headers'] += headers
            if bad and len(samples) < 5:
                v = int(d['w2'], 16)
                samples.append('room %s frame %s (v%d): %d of %d PT headers bad; first w0=%s w2=%s blend %s/%s caller=%s'
                               % (room, d['frame'], version, bad, headers, d['w0'], d['w2'],
                                  BLEND[v >> 29], BLEND[(v >> 26) & 7], d['ra']))
            if (invalid or incomplete) and len(samples) < 5:
                samples.append('room %s frame %s: invalid=%d incomplete=%d reason=%d'
                               % (room, d['frame'], invalid, incomplete, why))
    fail = []
    if malformed:
        fail.append('malformed/truncated/unsupported pt_audit records at lines ' + ','.join(map(str, malformed[:8])))
    if len(versions) > 1:
        fail.append('mixed legacy and v2 diagnostic schemas')
    for r, s in sorted(per.items()):
        print('room %s: %d logged scenes, %d PT headers (%d v2), %d bad, %d invalid, %d incomplete'
              % (r, s['lines'], s['headers'], s['v2_headers'], s['bad'], s['invalid'], s['incomplete']))
        if s['bad']:
            fail.append('room %s has %d PT headers with incorrect blend' % (r, s['bad']))
        if s['invalid'] or s['incomplete']:
            fail.append('room %s has invalid or incomplete packet decoding' % r)
    for sample in samples:
        print('  ' + sample)
    # Never turn historical raw failures into PASS by discarding legacy rows.
    if fail:
        print('PT-BLEND FAIL: ' + '; '.join(fail))
        return 1
    if not per or versions != {2}:
        print('PT-BLEND NODATA: packet-aware MCHECK_PT v2 records required; legacy clean rows are not coverage')
        return 2
    for want in wanted:
        count = per.get(want, {}).get('v2_headers', 0)
        if count < a.min_headers:
            fail.append('room %s: insufficient v2 PT coverage (%d headers < %d)' % (want, count, a.min_headers))
    if not sum(s['v2_headers'] for s in per.values()):
        fail.append('no v2 punch-through header coverage')
    if fail:
        print('PT-BLEND FAIL: ' + '; '.join(fail))
        return 1
    print('PT-BLEND PASS: logged v2 scenes decode completely and every observed PT header blends SRCALPHA/INVSRCALPHA')
    return 0


if __name__ == '__main__':
    sys.exit(main())
