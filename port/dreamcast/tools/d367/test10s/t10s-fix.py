#!/usr/bin/env python3
"""t10s-fix.py SRC.json OLD_LABEL NEW_LABEL OUT.json [--pak 9.1|gc] [--hands 0|1] [--warp FILE] [--pad FILE] [--qtxt FILE]
Test 10 (small) fixtures: a copy of a 9.1-era fixture with the program label swapped, the test 10 data:
  --pak gc   dc/tex.pak = tex-gcatlas.pak (Leon's two atlases rebuilt from the GC textures; else identical to tex-t9.pak)
  --hands 1  dc/native/pl00/leon_hands_pl00.re4hp (LEON_HAND_PACK package, sha d752aac5)
and optional warp / padscript / quality files for test runs."""
import json, sys, hashlib
PAK = {'9.1': '/root/probe/lanes-20261012/test9/rel9/fix/tex-t9.pak',
       'gc': '/root/probe/lanes-20261014/oldvis-work/tex-gcatlas.pak'}
PAKSHA = {'9.1': '533b8204dda457cb', 'gc': '7137e9e58bd43a01'}
HANDS = '/root/probe/lanes-20261013/hands2-work/pkg/leon_hands_pl00.re4hp'
HSHA = 'd752aac59ae99256'
a = sys.argv[1:]
src, old, new, out = a[:4]
opt = dict(zip(a[4::2], a[5::2]))
d = json.load(open(src))
s = json.dumps(d).replace('candidate-route' + old + '/', 'candidate-route' + new + '/')
d = json.loads(s)
r = d['replace']
rm = set(d.get('remove', []))
if '--pak' in opt:
    p = PAK[opt['--pak']]
    assert hashlib.sha256(open(p, 'rb').read()).hexdigest().startswith(PAKSHA[opt['--pak']]), p
    r['dc/tex.pak'] = p
if opt.get('--hands') == '1':
    assert hashlib.sha256(open(HANDS, 'rb').read()).hexdigest().startswith(HSHA)
    r['dc/native/pl00/leon_hands_pl00.re4hp'] = HANDS
elif opt.get('--hands') == '0':
    r.pop('dc/native/pl00/leon_hands_pl00.re4hp', None)
for k, f in (('--warp', 'dc/warp.txt'), ('--pad', 'dc/padscript.txt'), ('--qtxt', 'dc/quality.txt')):
    if k in opt:
        r[f] = opt[k]
        rm.discard(f)
d['remove'] = sorted(rm)
d.setdefault('provenance', {})['t10s'] = {'src': src, 'label': [old, new], 'opts': opt}
left = [k for k, v in r.items() if isinstance(v, str) and 'candidate-route' in v and 'candidate-route' + new + '/' not in v]
assert not left, left
json.dump(d, open(out, 'w'), indent=1, sort_keys=True)
print('fixture', out, 'tex.pak', r.get('dc/tex.pak'), 'hands', 'dc/native/pl00/leon_hands_pl00.re4hp' in r,
      'warp', r.get('dc/warp.txt'), 'pad', r.get('dc/padscript.txt'))
