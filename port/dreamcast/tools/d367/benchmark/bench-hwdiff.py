#!/usr/bin/env python3
"""bench-hwdiff.py BASE_HWMODEL_DIR ARM_HWMODEL_DIR [--top N] [--per K]: where a lever's hw ms land (lane crowd12, 2026-10-14).

Both dirs are bench-hw.sh outputs (hwmodel-<name>, proj/rep/functions.tsv) of the same benchmark scene and window.
Prints the bench-split.py subsystem buckets side by side (base, arm, delta), then the functions with the largest
hw ms change (all areas, then per bucket for actor submit and world submit). With --per K the delta is also divided
by K (e.g. --per 12 for "ms per Ganado" when the arm has 12 fewer Ganados alive).
All numbers are the SH-4 hardware model (MODELLED, console-calibrated), hw ms per drawn frame.
"""
import csv
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('bench_split', HERE / 'bench-split.py')
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)


def arg(name, default, cast=int):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def funcs(d):
    rows = {}
    with open(Path(d) / 'proj/rep/functions.tsv', newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            rows[r['func']] = (bs.bucket(r['func'], r.get('file', '')), float(r['hw_ms']))
    return rows


def main():
    pos = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith('--') and sys.argv[i - 1] not in ('--top', '--per')]
    base, arm = pos[0], pos[1]
    top, per = arg('--top', 25), arg('--per', 0, float)
    fb, fa = funcs(base), funcs(arm)
    bb, ba = bs.split(Path(base))[0], bs.split(Path(arm))[0]
    print(f'base {base}\narm  {arm}\n(SH-4 hw model, MODELLED, hw ms per drawn frame)')
    if True:
        print('| bucket | base | arm | delta |' + (f' delta/{per:g} |' if per else ''))
        print('|---|---|---|---|' + ('---|' if per else ''))
        for k in bs.ORDER:
            bb.setdefault(k, 0.0)
            d = ba.get(k, 0.0) - bb[k]
            print(f'| {k} | {bb[k]:.2f} | {ba.get(k, 0.0):.2f} | {d:+.2f} |' + (f' {d / per:+.3f} |' if per else ''))
        tb, ta = sum(bb.values()), sum(ba.values())
        print(f'| **total** | {tb:.2f} | {ta:.2f} | {ta - tb:+.2f} |' + (f' {(ta - tb) / per:+.3f} |' if per else ''))
    deltas = []
    for k in (set(fb) | set(fa)) - bs.WAIT:
        a0, m0 = fb.get(k, (fa.get(k, ('?', 0))[0], 0.0))
        a1, m1 = fa.get(k, (a0, 0.0))
        cls = a0 if k in fb else a1
        deltas.append((m1 - m0, m0, m1, cls, k))
    deltas.sort(key=lambda x: x[0])
    print(f'\ntop {top} function changes (arm - base):')
    for d, m0, m1, cls, k in deltas[:top]:
        print(f'{d:+7.3f}  {m0:6.3f} -> {m1:6.3f}  [{cls}] {k[:110]}')
    for want in ('actor submit', 'world submit'):
        sel = [x for x in deltas if x[3] == want]
        if not sel:
            continue
        print(f'\n{want}: scales with the arm change (largest drops) / stays (largest unchanged costs):')
        for d, m0, m1, cls, k in sel[:12]:
            print(f'  {d:+7.3f}  {m0:6.3f} -> {m1:6.3f}  {k[:100]}')
        stay = sorted(sel, key=lambda x: -min(x[1], x[2]))[:8]
        for d, m0, m1, cls, k in stay:
            print(f'  stays {min(m0, m1):6.3f} ({d:+.3f})  {k[:100]}')


if __name__ == '__main__':
    main()
