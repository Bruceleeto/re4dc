#!/usr/bin/env python3
"""fx12-ms.py EVIDENCE_ROOT [--skip N]: the FX_LEVEL ms table from the fx12-ms-<seg>-<arm> W runs (fx12-gates.sh ms).

Per run: the PACE vmu windows (one per ~60 vblanks) after the first N (default 4: warp load and settle), averaged:
FPS, CPU % (the page), GPU ms (gpu_avg_us: TA/render time the game measures on the emulated PVR), plus the effect
sprite counters (queued per frame, missing, capped). These are Flycast hw-model numbers (MODELLED, not console).
Delta columns are against the control arm c (test 11 recipe, fx12 knobs off) of the same segment.
"""
import re
import sys
from pathlib import Path

SEGS = (('h2', 'r100 fight (H2)'), ('bell', 'r101 bell'), ('r106', 'r106'))
ARMS = ('c', 'l0', 'l1', 'l2')
PACE = re.compile(r'PACE vmu t=(\d+) .*?gpu_avg_us=(\d+).*?page=FPS ([\d.]+)\|SPD \d+%\|CPU (\d+)%')
FXS = re.compile(r'native effect sprites: frame=(\d+) queued=(\d+) direct=\d+ missing=(\d+) dropped=\d+ capped=(\d+)')


def summarize(path, skip):
    rows = [m.groups() for m in map(PACE.search, path.read_text(errors='replace').splitlines()) if m][skip:]
    if not rows:
        return None
    n = len(rows)
    fps = sum(float(r[2]) for r in rows) / n
    cpu = sum(int(r[3]) for r in rows) / n
    gpu = sum(int(r[1]) for r in rows) / n / 1000.0
    fx = [m.groups() for m in map(FXS.search, path.read_text(errors='replace').splitlines()) if m]
    per = miss = cap = 0.0
    if len(fx) >= 2:
        (f0, q0, m0, c0), (f1, q1, m1, c1) = fx[0], fx[-1]
        frames = max(1, int(f1) - int(f0))
        per, miss, cap = (int(q1) - int(q0)) / frames, int(m1) - int(m0), int(c1) - int(c0)
    return dict(n=n, fps=fps, cpu=cpu, frame_ms=1000.0 / fps if fps else 0.0, gpu=gpu, per=per, miss=miss, cap=cap)


def main():
    root = Path(sys.argv[1])
    skip = int(sys.argv[sys.argv.index('--skip') + 1]) if '--skip' in sys.argv else 4
    print('| Scene | Arm | windows | FPS | frame ms | CPU % | GPU ms | d GPU ms vs c | sprites/frame | missing | capped |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    for seg, name in SEGS:
        base = None
        for arm in ARMS:
            f = root / f'fx12-ms-{seg}-{arm}' / 'capture' / 'run-output.txt'
            s = summarize(f, skip) if f.exists() else None
            if not s:
                print(f'| {name} | {arm} | (no run) |||||||||')
                continue
            if arm == 'c':
                base = s
            d = f"{s['gpu'] - base['gpu']:+.2f}" if base else '-'
            print(f"| {name} | {arm} | {s['n']} | {s['fps']:.1f} | {s['frame_ms']:.1f} | {s['cpu']:.0f} | {s['gpu']:.2f} | {d} "
                  f"| {s['per']:.1f} | {s['miss']:.0f} | {s['cap']:.0f} |")
    print('\nMODELLED (Flycast hw-model runner); console factor not applied. Same warp, same fixture data per segment.')


if __name__ == '__main__':
    main()
