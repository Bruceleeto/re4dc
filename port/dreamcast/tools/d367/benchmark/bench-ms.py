#!/usr/bin/env python3
"""bench-ms.py RUN_OUTPUT... [--from F] [--to T] [--ref RUN_OUTPUT]: the benchmark window summary (lane crowd12, 2026-10-14).

Reads the game log of a benchmark run (benchmark-<scene> warp, W arm: DBG_WARP=1 PC_SAMPLER=1, the recipe's pacing) and
reports the measuring window, room frames F..T (default 300..1200 = 30 s of game time after a 10 s settle):
  fps        drawn frames per emulated second (PACE vmu windows whose tick lies in the window)
  frame ms   1000 / fps
  CPU drawn  ms of work per drawn tick (PACE t= lines inside the window: draw_us, weighted by drawn)
  CPU skip   ms of work per skipped tick (logic only: skip_us)
  CPU %      the VMU page's CPU % (work per tick / 33.367 ms)
  GPU ms     gpu_avg_us (render-done interrupts). Flycast does not model PVR fill: this column is NOT a GPU model.
  speed %    game speed
  alive      Ganados alive (alivelog) min..max in the window
PACE t counts room frames (the pace state resets at room entry), so the window is selected by t.
Numbers are Flycast (dynarec charge model) = MODELLED, not console. For hw ms use bench-hw.sh (SH-4 model).
Several runs: one row each, then the spread of fps and CPU drawn (repeatability: within a few % = valid).
"""
import re
import sys
from pathlib import Path

T_LINE = re.compile(r'^PACE t=(\d+) win=(\d+) drawn=(\d+) skip=(\d+) fps=([\d.]+) speed=([\d.]+).*?draw_us=(\d+) skip_us=(\d+)')
V_LINE = re.compile(r'^PACE vmu t=(\d+) win_vb=(\d+) drawn=(\d+) gpu_n=(\d+) gpu_avg_us=(\d+).*?CPU (\d+)%')
ALIVE = re.compile(r'^warp: alive (\d+) room [0-9a-f]+ frame (\d+)')


def arg(name, default):
    return int(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def summarize(path, lo, hi):
    lines = Path(path).read_text(errors='replace').splitlines()
    ts = [m.groups() for m in map(T_LINE.match, lines) if m]
    ts = [t for t in ts if lo < int(t[0]) <= hi]
    vs = [m.groups() for m in map(V_LINE.match, lines) if m]
    vs = [v for v in vs if lo < int(v[0]) <= hi]
    if not ts or not vs:
        return None
    drawn = sum(int(t[2]) for t in ts)
    skip = sum(int(t[3]) for t in ts)
    cpu_d = sum(int(t[2]) * int(t[6]) for t in ts) / max(1, drawn) / 1000.0
    cpu_s = sum(int(t[3]) * int(t[7]) for t in ts) / max(1, skip) / 1000.0
    vb = sum(int(v[1]) for v in vs)
    vd = sum(int(v[2]) for v in vs)
    fps = vd * 59.94 / vb if vb else 0.0
    gn = sum(int(v[3]) for v in vs)
    gpu = sum(int(v[3]) * int(v[4]) for v in vs) / max(1, gn) / 1000.0
    cpu_pct = sum(int(v[5]) * int(v[1]) for v in vs) / max(1, vb)
    speed = sum(float(t[5]) for t in ts) / len(ts)
    alive = [int(m.group(1)) for m in map(ALIVE.match, lines) if m and lo <= int(m.group(2)) <= hi]
    return dict(fps=fps, frame_ms=1000.0 / fps if fps else 0.0, cpu_d=cpu_d, cpu_s=cpu_s, cpu_pct=cpu_pct, gpu=gpu,
                speed=speed, drawn=drawn, skip=skip, vwin=len(vs), twin=len(ts),
                alive=(min(alive), max(alive)) if alive else None)


def main():
    lo, hi = arg('--from', 300), arg('--to', 1200)
    runs = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith('--') and sys.argv[i - 1] not in ('--from', '--to')]
    print(f'window room frames {lo}..{hi} (MODELLED: Flycast dynarec charge model; GPU column is not a PVR fill model)')
    print('| run | fps | frame ms | CPU ms/drawn | CPU ms/skip | CPU % | GPU ms | speed % | drawn/skip | alive |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    got = []
    for r in runs:
        s = summarize(r, lo, hi)
        name = Path(r).parent.parent.name if Path(r).parent.name == 'capture' else r
        if not s:
            print(f'| {name} | (no PACE lines in window) |||||||||')
            continue
        got.append(s)
        al = f"{s['alive'][0]}..{s['alive'][1]}" if s['alive'] else '-'
        print(f"| {name} | {s['fps']:.2f} | {s['frame_ms']:.1f} | {s['cpu_d']:.2f} | {s['cpu_s']:.2f} | {s['cpu_pct']:.0f} | "
              f"{s['gpu']:.2f} | {s['speed']:.1f} | {s['drawn']}/{s['skip']} | {al} |")
    if len(got) >= 2:
        for k in ('fps', 'cpu_d'):
            v = [g[k] for g in got]
            print(f'spread {k}: {min(v):.2f}..{max(v):.2f} ({(max(v) - min(v)) / (sum(v) / len(v)) * 100:.1f}%)')


if __name__ == '__main__':
    main()
