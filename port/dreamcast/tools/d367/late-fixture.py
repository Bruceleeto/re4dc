#!/usr/bin/env python3
"""late-fixture.py <fixture.json> <out dir> <mask> [<mask>...] [--tick N] [--room 0xRRR] [--name STEM]

Same-binary A/B arms (tools/d367/README.md "Late activation"): for each mask, writes <out dir>/<stem>-late-<mm>.json,
a copy of <fixture.json> whose dc/warp.txt is the fixture's own warp.txt with any `arch`/`late` line replaced by
`late 0x<mm> <tick> 0x<room>` (fixed width, so every arm's warp.txt has the same length). Replacement sources are
written as absolute paths. Example (H2):
  late-fixture.py .../spikes/fixtures/arch-spike-base.json /root/probe/x/fixtures 0x00 0x04 --name h2
"""
import argparse, json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('fixture', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('masks', nargs='+', type=lambda s: int(s, 0))
    ap.add_argument('--tick', type=int, default=1400)
    ap.add_argument('--room', type=lambda s: int(s, 0), default=0x100)
    ap.add_argument('--name')
    a = ap.parse_args()
    d = json.loads(a.fixture.read_text())
    base = a.fixture.parent
    rep = {k: str((base / v).resolve()) for k, v in d['replace'].items()}
    if 'dc/warp.txt' not in rep:
        raise SystemExit('the fixture stages no dc/warp.txt')
    lines = [l for l in Path(rep['dc/warp.txt']).read_text().splitlines()
             if l.split()[:1] not in (['arch'], ['late'])]
    stem = a.name or a.fixture.stem
    a.out.mkdir(parents=True, exist_ok=True)
    for m in a.masks:
        w = a.out / ('%s-late-%02x-warp.txt' % (stem, m))
        w.write_text('\n'.join(lines) + '\nlate 0x%02x %d 0x%03x\n' % (m, a.tick, a.room))
        arm = dict(d, replace=dict(rep, **{'dc/warp.txt': str(w)}))
        f = a.out / ('%s-late-%02x.json' % (stem, m))
        f.write_text(json.dumps(arm, indent=1) + '\n')
        print(f, len(w.read_bytes()), 'bytes of warp.txt')


if __name__ == '__main__':
    main()
