"""Synthetic append test: three 1 m boxes near the r101 bench eye (-15300, 1721, 2377 mm): A and B identical up to a
translation (B must instance A's mesh), C with other colours (own mesh). OBJ units = world mm / 100."""
import json
cube = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 4, 7, 3)]
out = ['mtllib none']
vt = [(0, 0), (1, 0), (1, 1), (0, 1)]
for u, v in vt:
    out.append('vt %g %g' % (u, v))
base = 0
for name, centre, rgb in (('A', (-4000, 0, 2000), (0.8, 0.7, 0.6)), ('B', (-4000, 0, 4500), (0.8, 0.7, 0.6)),
                          ('C', (-4000, 0, -500), (0.3, 0.4, 0.9))):
    out.append('g BAKE#test#%s#COLOR#' % name)
    out.append('usemtl ' + ('wall2' if name == 'C' else 'wall'))
    for x, y, z in cube:
        out.append('v %.4f %.4f %.4f %.3f %.3f %.3f 1' % ((centre[0] + 1000 * x) / 100, (centre[1] + 1000 * (y + 1)) / 100,
                                                          (centre[2] + 1000 * z) / 100, *rgb))
    for q in quads:
        out.append('f %s' % ' '.join('%d/%d' % (base + i + 1, k + 1) for k, i in enumerate(q)))
    base += 8
open('boxes.obj', 'w').write('\n'.join(out) + '\n')
json.dump({'wall': {'key': '782aed8c-a11abc8a', 'width': 128, 'height': 128, 'pass': 0, 'cull': 0},
           'wall2': {'key': '6d47e0e6-8454336c', 'width': 128, 'height': 128, 'pass': 0, 'cull': 0}},
          open('boxes-mat.json', 'w'), indent=1)
print('ok')
