#!/usr/bin/env python3
"""add_cell.py: stage the PS2_INTERIOR_CULL cell file in a disc fixture.

    add_cell.py <fixture.json> <out.json>

A fixture that stages the r100 PS2 world (dc/native/r100/ps2-world.re4mesh) gets dc/native/r100/interior.cell =
this directory's interior-r100.cell (absolute path). Relative sources are resolved against the input fixture's
directory, so <out.json> may live anywhere. Without the file on the disc the runtime simply does not cull
(PCCULL cell file missing). room_fixture.py adds it for r100 itself.
"""
import json, sys
from pathlib import Path

CELL = Path(__file__).resolve().parent / 'interior-r100.cell'
KEY = 'dc/native/r100/interior.cell'


def add(fix: dict, base: Path) -> dict:
    rep = {k: (v if Path(v).is_absolute() else str((base / v).resolve())) for k, v in fix['replace'].items()}
    if 'dc/native/r100/ps2-world.re4mesh' not in rep:
        raise SystemExit('the fixture does not stage the r100 PS2 world; nothing to add')
    rep[KEY] = str(CELL)
    remove = [k for k in (fix.get('remove') or []) if k != KEY]
    return dict(fix, replace=rep, remove=remove)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    out = add(json.loads(src.read_text()), src.resolve().parent)
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1) + '\n')
    print(sys.argv[2], len(out['replace']), 'replaced; +', KEY)
