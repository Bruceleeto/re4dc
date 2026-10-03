#!/usr/bin/env python3
"""hwwork.py: hwproject results for same-binary A/B arms (tools/d367/README.md "Late activation").

  hwwork.py cost <hwmodel-name>...                  work ms per tick = total minus the wait rows main,
                                                    re4dc_pace_end, re4dc_vi_retrace_count; low-high; top areas
  hwwork.py strict <ref> <cand> [A:B] [--diff PY]   logic-trace comparison of two LOGIC_TRACE=1 hwproject runs:
                                                    frame window A:B (default 1450:1569), 1300:1399, and room 0x100

Names are hwmodel dirs under $HWM_EVROOT (default /mnt/c/Flycast-Evidence/re4-dreamcast/hwm-c) without the
"hwmodel-" prefix. The trace logs (UTF-16 from PowerShell) are normalised into $HWWORK_LOGS (default ./hwwork-logs).
--diff names logic_trace_diff.py (default $LOGIC_TRACE_DIFF).
"""
import csv, json, os, subprocess, sys
from pathlib import Path

E = Path(os.environ.get('HWM_EVROOT', '/mnt/c/Flycast-Evidence/re4-dreamcast/hwm-c'))
L = Path(os.environ.get('HWWORK_LOGS', 'hwwork-logs'))
WAIT = {'main', 're4dc_pace_end', 're4dc_vi_retrace_count'}


def cost(n):
    rows = list(csv.DictReader((E / f'hwmodel-{n}/proj/rep/functions.tsv').open(encoding='utf-8'), delimiter='\t'))
    work = [r for r in rows if r['func'] not in WAIT]
    areas = {}
    for r in work:
        areas[r['area']] = areas.get(r['area'], 0) + float(r['hw_ms'])
    return dict(work=sum(float(r['hw_ms']) for r in work), wait=sum(float(r['hw_ms']) for r in rows if r['func'] in WAIT),
                low=sum(float(r['wi_low']) for r in work), high=sum(float(r['wi_high']) for r in work),
                areas=dict(sorted(((k, round(v, 3)) for k, v in areas.items()), key=lambda x: -x[1])),
                funcs={r['func']: float(r['hw_ms']) for r in work})


def log(n):
    raw = (E / f'hwmodel-{n}/trace/run-output.txt').read_bytes()
    enc = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    L.mkdir(parents=True, exist_ok=True)
    p = L / f'{n}.log.txt'
    p.write_text(raw.decode(enc), encoding='utf-8')
    return p


def strict(diff, a, b, lo=None, hi=None):
    pa, pb = log(a), log(b)
    j = L / f'tdiff-{a}-vs-{b}-{lo or "room"}-{hi or ""}.json'
    win = ['--align', 'frame', '--from', str(lo), '--to', str(hi)] if lo is not None else ['--align', 'room', '--room', '0100']
    subprocess.run([sys.executable, '-B', diff, str(pa), str(pb), '--json', str(j)] + win, capture_output=True, text=True)
    d = json.loads(j.read_text())
    fd = d.get('first_divergence') or {}
    return dict(verdict=d.get('verdict'), compared=d.get('compared'), window=d.get('window'), first=fd.get('ref_frame'),
                fields=list((fd.get('fields') or {}).keys())[:8], gaps=(d.get('ref_gaps'), d.get('cand_gaps')),
                dups=(d.get('ref_duplicates'), d.get('cand_duplicates')))


def main(argv):
    if len(argv) >= 2 and argv[0] == 'cost':
        for n in argv[1:]:
            c = cost(n)
            print(f"{n}: work {c['work']:.4f} ms (low {c['low']:.2f} high {c['high']:.2f}) wait {c['wait']:.3f}")
            print('   ', ' '.join(f'{k}={v}' for k, v in list(c['areas'].items())[:10]))
    elif len(argv) >= 3 and argv[0] == 'strict':
        args = list(argv[1:])
        diff = os.environ.get('LOGIC_TRACE_DIFF')
        if '--diff' in args:
            i = args.index('--diff'); diff = args[i + 1]; del args[i:i + 2]
        if not diff:
            raise SystemExit('pass --diff <logic_trace_diff.py> or set LOGIC_TRACE_DIFF')
        a, b = args[0], args[1]
        lo, hi = args[2].split(':') if len(args) > 2 else ('1450', '1569')
        print('house', json.dumps(strict(diff, a, b, lo, hi)))
        print('pre  ', json.dumps(strict(diff, a, b, '1300', '1399')))
        print('room ', json.dumps(strict(diff, a, b)))
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
