#!/usr/bin/env python3
"""fx_room_gate.py <run-output.txt>... [--pak tex.pak --lib ps2lib]: per room (room lifecycle phase=enter markers), the
texture refusals of one run: uploads FAILED, "no contiguous block", texchk FAIL lines, absent packages, palette-bank
refusals, texture loads, and the effect sprites queued / missing (the frame counters' last values in the room), plus
HALT / FAULT / MISSING. With --lib, also how many of the room's loaded keys came from ps2lib/effects-tex (proof the
converted assets are the ones loaded). Prints one row per room visit; exit 1 if any refusal or halt was counted."""
import re, sys
from pathlib import Path

ENTER = re.compile(r'room lifecycle: phase=enter room=([0-9a-f]+) generation=(\d+)')
LOAD = re.compile(r'native UI: load \S*/([0-9a-f]{8}-[0-9a-f]{8})\.re4tex')
FX = re.compile(r'native effect sprites: frame=\d+ queued=(\d+) direct=\d+ missing=(\d+)')
COUNT = {'upload_failed': 'upload FAILED', 'no_contig': 'no contiguous block', 'texchk_fail': 'texchk: FAIL',
         'absent': 'package absent', 'palette': 'palette bank', 'halt': 'HALT', 'fault': 'FAULT', 'missing_sym': 'MISSING'}


def main():
    a = sys.argv[1:]
    lib = None
    if '--lib' in a:
        i = a.index('--lib'); lib = Path(a[i + 1]); del a[i:i + 2]
    libkeys = {}
    if lib:
        for f in (lib / 'effects-tex').rglob('*.re4tex'):
            libkeys[f.stem] = f.parent.name
    bad = 0
    print('| run | room | gen | loads | lib-key loads | fx queued/missing | upload FAILED | no contiguous | texchk FAIL | absent | halt/fault |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    for run in a:
        rows, cur = [], None
        for line in open(run, errors='replace'):
            m = ENTER.search(line)
            if m:
                cur = dict(room='r' + m.group(1), gen=m.group(2), loads=0, lib=0, fx=None, fx0=None,
                           **{k: 0 for k in COUNT})
                rows.append(cur)
                continue
            if cur is None:
                continue
            m = LOAD.search(line)
            if m:
                cur['loads'] += 1
                cur['lib'] += m.group(1) in libkeys
            m = FX.search(line)
            if m:
                v = (int(m.group(1)), int(m.group(2)))
                if cur['fx0'] is None:
                    cur['fx0'] = v
                cur['fx'] = v
            for k, s in COUNT.items():
                if s in line and not (k == 'missing_sym' and 'missing=' in line):
                    cur[k] += 1
        name = Path(run).parent.parent.name
        for r in rows:
            fx = '%d/%d' % r['fx'] if r['fx'] else '-'
            refusals = r['upload_failed'] + r['no_contig'] + r['texchk_fail'] + r['absent'] + r['palette']
            bad += refusals + r['halt'] + r['fault']
            print('| %s | %s | %s | %d | %d | %s | %d | %d | %d | %d | %d/%d |' % (
                name, r['room'], r['gen'], r['loads'], r['lib'], fx, r['upload_failed'], r['no_contig'],
                r['texchk_fail'], r['absent'], r['halt'], r['fault']))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
