import json, hashlib, os, sys
# srccheck.py: which st1/<room>.dar does the published test 12 package (pkg-t12c2tP.json) ship, vs the gen source dar
pkg = json.load(open('/root/probe/lanes-20261014/t12rc/fix/pkg-t12c2tP.json'))
AO = '/root/probe/lanes-20261009/test/audio-overlay/st1'
LR = '/root/probe/lanes-20261010'
src = {'r102': AO + '/r102.dar', 'r103': '/root/probe/d367-agents/design-r103/w8b-rel/st1/r103.dar'}
for r in ('r104', 'r105', 'r106', 'r107', 'r108', 'r109', 'r10a'):
    src[r] = AO + '/%s.dar' % r
src['r10b'] = '/root/probe/lanes-20261009/r10b/rooms/aica-r10b/st1/r10b.dar'
for r in ('r117', 'r118', 'r119', 'r11a', 'r11b'):
    src[r] = LR + '/%s/rooms/aica-%s/st1/%s.dar' % (r, r, r)
def h(p):
    try:
        return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
    except Exception as e:
        return 'ERR ' + str(e)[:40]
rep = pkg.get('replace', {})
for r, s in sorted(src.items()):
    k = 'st1/%s.dar' % r
    p = rep.get(k)
    print(r, 'src', h(s), 'pkg', (h(p) + ' ' + p) if p else 'not replaced (base disc)', 'removed' if k in pkg.get('remove', []) else '')
