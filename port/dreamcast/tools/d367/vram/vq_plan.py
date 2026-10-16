#!/usr/bin/env python3
"""vq_plan.py <target bytes> <room>=<census.tsv>[,<census.tsv>...]... [--exclude KEYS.txt] [--out KEYS.txt]
(lane resident16, 2026-10-16; read only)

For each room, the union of its room_census.py tables (one per run) is the room's working set. When the set is larger
than the target, the 16-bit (twiddled / linear) pictures of 16 KiB or more are picked for VQ (vram/vq_pak.py:
2048 + w*h/4 bytes), largest saving first, until the set fits. A key picked for one room counts as VQ in every room
(the pak holds one package per key), so the rooms are planned in order of their size, largest first. Prints per room
the set size before and after and the keys it needs; --out writes the union (one key per line, vq16 list format)."""
import sys


def vq_bytes(w, h):
    return 2048 + w * h // 4


def main(a):
    excl, out = set(), None
    if '--exclude' in a:
        i = a.index('--exclude'); excl = {l.split()[0] for l in open(a[i + 1]) if l.strip() and not l.startswith('#')}; del a[i:i + 2]
    if '--out' in a:
        i = a.index('--out'); out = a[i + 1]; del a[i:i + 2]
    target = int(a[0])
    rooms = {}
    for arg in a[1:]:
        r, files = arg.split('=', 1)
        keys = rooms.setdefault(r, {})
        for f in files.split(','):
            for ln in open(f).read().splitlines()[1:]:
                k, w, h, fmt, kind, b, flags, src, how, n = ln.split('\t')
                keys[k] = (int(w), int(h), kind, int(b))
    chosen = {}
    for r, keys in sorted(rooms.items(), key=lambda kv: -sum(v[3] for v in kv[1].values())):
        size = lambda: sum(vq_bytes(w, h) if k in chosen else b for k, (w, h, kind, b) in keys.items())
        before = sum(v[3] for v in keys.values())
        cand = sorted(((b - vq_bytes(w, h), k) for k, (w, h, kind, b) in keys.items()
                       if kind in ('twiddled', 'linear') and b >= 16384 and k not in excl and k not in chosen), reverse=True)
        need = []
        while size() > target and cand:
            s, k = cand.pop(0)
            chosen[k] = (keys[k][0], keys[k][1], keys[k][3]); need.append(k)
        uses = [k for k in keys if k in chosen]
        print('r%s: %d keys, set %d B -> %d B (target %d)%s; VQ keys used %d (new %d): %s' % (
            r, len(keys), before, size(), target, '' if size() <= target else ' STILL OVER', len(uses), len(need),
            ' '.join(need)))
    tot = sum(b - vq_bytes(w, h) for w, h, b in chosen.values())
    print('union: %d keys, %d B saved per room that holds them all' % (len(chosen), tot))
    if out:
        open(out, 'w').write(''.join('%s\n' % k for k in sorted(chosen)))


if __name__ == '__main__':
    main(sys.argv[1:])
