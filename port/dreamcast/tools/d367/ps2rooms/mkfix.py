"""Copy a tour fixture with its r100 PS2-world package swapped for another package dir (absolute sources)."""
import json, os, sys
from pathlib import Path
tour, name, pkg, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
room = sys.argv[5] if len(sys.argv) > 5 else 'r100'
d = json.loads((tour / name).read_text())
old_pkg = None
rep = {}
for k, v in d['replace'].items():
    src = os.path.normpath(str((tour / v))) if not v.startswith('/') else v
    if k.startswith(f'dc/native/{room}/'):
        old_pkg = Path(src).parent
        continue
    rep[k] = src
dropped = [k for k, v in list(rep.items()) if old_pkg and v.startswith(str(old_pkg) + '/tex/')]
for k in dropped:
    del rep[k]
for f in ('ps2-world.re4mesh', 'ps2-world.r4pw'):
    rep[f'dc/native/{room}/{f}'] = str(pkg / f)
added = 0
for t in sorted((pkg / 'tex').glob('*.re4tex')):
    rep[f'dc/tex/{t.name[0]}/{t.name}'] = str(t)
    added += 1
d['replace'] = rep
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(d, indent=1))
print('old package', old_pkg, 'dropped tex', len(dropped), 'added tex', added, 'entries', len(rep))
