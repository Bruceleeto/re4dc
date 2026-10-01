"""Find the GC source file of native texture keys (route lane, 2026-10-01).

A run log's `native UI: load /cd/dc/tex/<k>/<key>.re4tex` followed by `package rejected: open failed` names a
picture no staged texture set has. This walks GC source files through the same TPL traversal prepare_native_ui.py
uses (le_mirror's TPL observer) and prints every file/context holding a key prefix; build the set with
`prepare_native_ui.py <source root> <manifest naming that file> <out dir>` and stage it.

Usage: python3 find-texture-source.py [--source /root/re4data] [--rooms DIR] [--dirs etc,em,ss,font,evd,op] KEY...
  KEY   key prefixes (e.g. 8fb0fccf). Room archives st*/rNNN.das are read from --rooms (a GC iso-src tree) if given.
First use: r106's 8fb0fccf-d75e4a3f is in em/em2a.drs (contexts #3, #5).
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import prepare_native_ui as P  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('--source', type=Path, default=Path('/root/re4data'))
ap.add_argument('--rooms', type=Path, help='a tree holding st*/rNNN.das (GC originals) to scan too')
ap.add_argument('--dirs', default='etc,em,ss,font,evd,op')
ap.add_argument('keys', nargs='+')
a = ap.parse_args()

hits = []


def observe(file, off, data, ctx):
    if len(data) >= 12 and struct.unpack_from('>II', data) == (P.TPL_MAGIC, 0):
        return
    try:
        images = P.parse_tpl(data)
    except Exception:
        return
    for i, image in enumerate(images):
        key, _ = P.image_identity(image)
        if key.startswith(tuple(a.keys)):
            hits.append(key)
            print(f'{key}  {file}  {ctx}  tpl_offset={off} image={i} {image.width}x{image.height}', flush=True)


dirs = set(a.dirs.split(','))
files = [(str(p.relative_to(a.source)), p) for p in sorted(a.source.rglob('*'))
         if p.is_file() and p.relative_to(a.source).parts[0] in dirs]
if a.rooms:
    files += [(str(p.relative_to(a.rooms)), p) for p in sorted(a.rooms.glob('st*/r*.das'))]
P.mirror.TPL_OBSERVER = observe
for rel, path in files:
    try:
        if rel.endswith('.das') and rel.startswith('st'):
            P.mirror.prepare_room_archive(rel, path.read_bytes())
        else:
            P.mirror.convert_file(rel, bytearray(path.read_bytes()))
    except Exception:
        pass  # files the mirror has no handler for hold no TPLs it can reach
missing = [k for k in a.keys if not any(h.startswith(k) for h in hits)]
print(f'scanned {len(files)} files; not found: {missing or "none"}')
sys.exit(1 if missing else 0)
