#!/usr/bin/env python3
"""key_owner.py <fixture.json> <keys.txt|key...> (lane resident16, 2026-10-16; read only)

Who owns a texture key on the fixture's disc: the PS2 world packages (dc/native/<room>/ps2-world.r4pw lists the keys of
its parts), the PS2 cast registries (dc/native/<room>/registry.re4nmr / partner.re4nmr), effect pictures
(ps2lib effects-tex/KEYS.tsv), loose files (the data set directory they come from) and known atlases. A plain byte
search of the 8-byte key (little-endian crc, fnv) or its text form; a key found nowhere is reported as such."""
import json, struct, sys
from pathlib import Path

KNOWN = {'7506e95f-68cf2211': 'Leon pl08 atlas (no jacket)', 'ec255e66-76812316': 'Leon atlas (pl00)'}
KEYS_TSV = Path('/mnt/c/Game Dev/Emulators/re4-assets-private/ps2lib/effects-tex/KEYS.tsv')


def main(a):
    fix = json.load(open(a[0]))
    keys = []
    for x in a[1:]:
        keys += [l.split()[0] for l in open(x) if l.strip() and not l.startswith('#')] if Path(x).exists() else [x]
    r = fix['replace']
    blobs = {}
    for dest, src in r.items():
        if not isinstance(src, str):
            continue
        if dest.startswith('dc/native/') or dest.startswith('em/') or dest.startswith('st1/'):
            try:
                blobs[dest] = Path(src).read_bytes()
            except OSError:
                pass
    fx = {}
    if KEYS_TSV.exists():
        for ln in KEYS_TSV.read_text().splitlines()[1:]:
            f = ln.split('\t')
            fx.setdefault(f[0], []).append('%s:%s' % (f[1], f[2]))
    for k in keys:
        crc, fnv = (int(x, 16) for x in k.split('-'))
        b8 = struct.pack('<2I', crc, fnv)
        bb = struct.pack('>2I', crc, fnv)
        own = []
        if k in KNOWN:
            own.append(KNOWN[k])
        if k in fx:
            own.append('fx ' + ','.join(fx[k][:3]))
        for dest, blob in blobs.items():
            if b8 in blob or bb in blob or k.encode() in blob:
                own.append(dest)
        loose = r.get('dc/tex/%s/%s.re4tex' % (k[0], k))
        if loose:
            own.append('loose ' + str(Path(loose).parent))
        print(k, '|', '; '.join(own) or 'not found (base disc / GameCube archive)')


if __name__ == '__main__':
    main(sys.argv[1:])
