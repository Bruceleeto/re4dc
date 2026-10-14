#!/usr/bin/env python3
"""t11-fix.py NEW_LABEL OUT.json [--data a,b,...] [--set DEST=SRC]... [--rm DEST]... [--texdir DIR]...
              [--warp FILE] [--pad FILE] [--qtxt FILE] [--base FIXTURE --base-label LABEL]
Test 11 fixtures: a copy of the test 10 package fixture (test10s fix/pkg-t10stP.json: the 9.1 fixture + the GC-atlas
tex.pak + the hands package) with the program label swapped and the test 11 data added.
  --data NAMES  named test 11 data sets (DATA below; each is disc data only, staged by the recipe)
  --set D=S     stage file S at disc path D (replaces); --rm D drops D from the disc
  --texdir DIR  every <crc>-<fnv>.re4tex under DIR as a loose dc/tex/<c>/<name> (the runtime reads a key that is not
                in dc/tex.pak from its loose file; native_ui.cpp texpack kNotInPack)
Every staged file must exist; its sha256 prefix is recorded in provenance.t11."""
import json, sys, hashlib, os, re
from pathlib import Path

BASE = '/root/probe/lanes-20261014/t10s/fix/pkg-t10stP.json'
BASE_LABEL = 't10stP'
PRIV = '/mnt/c/Game Dev/Emulators/re4-assets-private'
T11D = '/root/probe/lanes-20261014/t11/data'
# Named data sets: disc path -> source (a directory value under 'tex' = loose textures). Filled in as each is proven.
DATA = {
    # A1 r119 dark block: the r119 objects package with only the BIN 0x22 pair (docs/lanes/look.md section 2)
    'r119c': {'st1/r119.dar': PRIV + '/look-20261013/r119c/r119.dar'},
    # A2 r106 bats (em29): Codex's composite pair package (color 8721b93e-a420c9ed, mask c3ad3454-e7b41714;
    # codex-ps2-assets-20261013/r106-em29-v1), missing from the test 10 disc
    'em29': {'dc/tex/b/b8420096-5d9dc3c4.re4tex': PRIV + '/t11-20261014/pairs/b8420096-5d9dc3c4.re4tex'},
    # A3 chapter 2-1 results picture: pair color c050cf4e-216cd784 + mask ec97f64b-dab43d54 (em11.drs, built by lane
    # r117 pairs-em11 on 10-10 and never staged)
    'fbec': {'dc/tex/f/fbec854a-b7656a09.re4tex': PRIV + '/t11-20261014/pairs/fbec854a-b7656a09.re4tex'},
    # A4 r100 SMX + tr4 overlays (needs game PS2_R100_SMX=1 PS2_R100_TR4=1: the interior cell checks the package CRCs)
    'r100tr4': {'dc/native/r100/ps2-world.re4mesh': PRIV + '/t11-20261014/r100-smx-tr4/ps2-world.re4mesh',
                'dc/native/r100/ps2-world.r4pw': PRIV + '/t11-20261014/r100-smx-tr4/ps2-world.r4pw',
                'dc/native/r100/ps2-world.ids': PRIV + '/t11-20261014/r100-smx-tr4/ps2-world.ids',
                'dc/native/r100/interior.cell': PRIV + '/t11-20261014/r100-smx-tr4/interior.cell',
                'tex': PRIV + '/t11-20261014/r100-smx-tr4/tex'},
    # A5 Codex SMX-only meshes (asset-only-smx-r103-r101-v1: sidecar, ids and textures byte-identical to the staged ones)
    'smx101': {'dc/native/r101/ps2-world.re4mesh': PRIV + '/t11-20261014/r101-smx/ps2-world.re4mesh'},
    'smx103': {'dc/native/r103/ps2-world.re4mesh': PRIV + '/t11-20261014/r103-smx/ps2-world.re4mesh'},
    # A6 r10b with --cutout-max-alpha 224 (p2pt-cutout-20261012/r10b = the audit rebuild; mesh unchanged, its 3 cutout
    # textures are already in tex.pak)
    'r10bcut': {'dc/native/r10b/ps2-world.r4pw': PRIV + '/t11-20261014/r10b-cut/ps2-world.r4pw',
                'dc/native/r10b/ps2-world.ids': PRIV + '/t11-20261014/r10b-cut/ps2-world.ids'},
}
ALL_A = 'r119c,em29,fbec,r100tr4,smx101,smx103,r10bcut'
# D black faces (lane t11-bk, docs/lanes/t11-bk.md): the 0xa0000000 scenery BINs lit offline. blackps2 = the PS2 run-time
# rule measured in PCSX2 (--a0-light ps2, default); blackgc = the GameCube static room lights (--a0-light gc). 15 rooms
# (r102-r10b, r117-r11b; not r100 / r101). Each set's r10b is built with cutout 224 and its r103 with the SMX rule, so it
# replaces r10bcut / smx103 (do not stage those with it). Re-keyed textures are loose files (newtex).
BLACK_ROOMS = 'r102 r103 r104 r105 r106 r107 r108 r109 r10a r10b r117 r118 r119 r11a r11b'.split()
for _s in ('blackps2', 'blackgc'):
    DATA[_s] = {'dc/native/%s/ps2-world.%s' % (r, x): PRIV + '/t11-20261014/%s/%s/ps2-world.%s' % (_s, r, x)
                for r in BLACK_ROOMS for x in ('re4mesh', 'r4pw', 'ids')}
    DATA[_s]['tex'] = PRIV + '/t11-20261014/%s/newtex' % _s
CLASH = [('blackps2', 'r10bcut'), ('blackps2', 'smx103'), ('blackgc', 'r10bcut'), ('blackgc', 'smx103'), ('blackps2', 'blackgc')]
# Leon light (lane lp2, d44c3059): LEON_LIGHT_HEADROOM=1 needs Leon's 15 atlas / hair / pl08 packages at 2x in tex.pak
# (cb_headroom.py over the test 10 GC-atlas pak; same keys, sizes, formats; sha256 1eb18ec4...). Without it Leon draws
# at half brightness; never stage it with a knob-off binary (2x bright).
DATA['leonhr'] = {'dc/tex.pak': '/root/probe/lanes-20261014/lp2/hr/tex-gcatlas-hr.pak'}
T11_DATA = 'r119c,em29,fbec,r100tr4,smx101,blackgc'  # the test 11 recipe (user 10-14: GC light bake; Leon flat, leonhr only with the probe knobs)
NAME = re.compile(r'^([0-9a-f]{8})-([0-9a-f]{8})\.re4tex$')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]


def texdir(d, r, rec):
    n = 0
    for p in sorted(Path(d).rglob('*.re4tex')):
        if NAME.match(p.name.lower()):
            k = 'dc/tex/%s/%s' % (p.name[0].lower(), p.name.lower())
            if k in r and r[k] != str(p) and sha(r[k]) != sha(str(p)):
                raise SystemExit('texture %s staged twice with different bytes: %s / %s' % (k, r[k], p))
            r[k] = str(p); n += 1
    rec.append('texdir %s %d' % (d, n))


def main():
    a = sys.argv[1:]
    new, out = a[:2]
    pairs = list(zip(a[2::2], a[3::2]))
    opt = {}
    for k, v in pairs:
        opt.setdefault(k, []).append(v)
    base = opt.get('--base', [BASE])[0]
    old = opt.get('--base-label', [BASE_LABEL])[0]
    d = json.load(open(base))
    s = json.dumps(d).replace('candidate-route' + old + '/', 'candidate-route' + new + '/')
    d = json.loads(s)
    r = d['replace']
    rm = set(d.get('remove', []))
    rec = []
    names = [x for v in opt.get('--data', []) for x in v.split(',') if x]
    for a_, b_ in CLASH:
        assert not (a_ in names and b_ in names), 'data sets %s and %s replace the same files' % (a_, b_)
    for nm in names:
        for k, v in DATA[nm].items():
            if k == 'tex':
                for t in (v if isinstance(v, list) else [v]):
                    texdir(t, r, rec)
                continue
            assert os.path.exists(v), (nm, k, v)
            r[k] = v; rm.discard(k); rec.append('%s %s %s' % (nm, k, sha(v)))
    for kv in opt.get('--set', []):
        k, v = kv.split('=', 1)
        assert os.path.exists(v), v
        r[k] = v; rm.discard(k); rec.append('set %s %s' % (k, sha(v)))
    for k in opt.get('--rm', []):
        r.pop(k, None); rm.add(k); rec.append('rm ' + k)
    for t in opt.get('--texdir', []):
        texdir(t, r, rec)
    for k, f in (('--warp', 'dc/warp.txt'), ('--pad', 'dc/padscript.txt'), ('--qtxt', 'dc/quality.txt')):
        if k in opt:
            r[f] = opt[k][0]
            rm.discard(f)
    d['remove'] = sorted(rm)
    d.setdefault('provenance', {})['t11'] = {'base': base, 'label': [old, new], 'data': names, 'staged': rec,
                                             'opts': {k: v for k, v in opt.items()}}
    left = [k for k, v in r.items() if isinstance(v, str) and 'candidate-route' in v and 'candidate-route' + new + '/' not in v]
    assert not left, left
    json.dump(d, open(out, 'w'), indent=1, sort_keys=True)
    print('fixture', out, 'data', ','.join(names) or '-', 'staged', len(rec), 'warp', r.get('dc/warp.txt'),
          'pad', r.get('dc/padscript.txt'))


if __name__ == '__main__':
    main()
