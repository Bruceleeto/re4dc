#!/usr/bin/env python3
"""tools/d367/objs_lib.py: put lane objs room-object packages into the shared PS2 library (ps2lib, user 2026-10-14:
"it should be preconverted"). One call per room:

  objs_lib.py add --lib <ps2lib> --room rNNN --dar <objects .dar> --report <ps2_objects report.json>
                  --converter ps2_objects.py@<commit> [--gate PASS:<run>|FAIL:<run>|UNGATED] [--owner objs]

Writes ps2lib/objects/<room>/<room>.dar (byte copy, sha256 checked), one file per converted model
(<room>/models/<id>.bin: the little-endian model bytes exactly as staged in the dar payload) and replaces this room's
`objects` rows in ps2lib/INDEX.tsv (columns: class room gc_id ps2_source dc_format converter sha256 bytes gate
owner_lane):
  - one package row (gc_id <room>.dar),
  - one row per room model the source model path draws (room-archive BINs + ETM etc BINs), classified as the census
    (objs_census.py) does against le_mirror(GC):
      PS2    rebuilt from the PS2 BIN named in ps2_source
      WORLD  emptied: the PS2 version draws it in its scenario SMD (ps2_source = rNNN.dat:SMD(world package))
      GC     still the GameCube model: ps2_source = NONE (no PS2 counterpart), NONE:placeholder@... (the PS2 model is a
             1-triangle placeholder) or the PS2 entry with gate FAIL:kept-GC (a counterpart exists but is not used),
             the reason from objs_census.KNOWN.
Never edits an output; re-running replaces the room's rows.
"""
import argparse, hashlib, json, shutil, struct, sys
from pathlib import Path
T = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(T), str(T / 'd367'), str(T.parents[2] / 'tools')]
import ps2_objects as po, ps2_bin as pb, room_smd as rs  # noqa
from assetpipe.rooms import GcIso  # noqa
from objs_census import KNOWN  # noqa

COLS = ['class', 'room', 'gc_id', 'ps2_source', 'dc_format', 'converter', 'sha256', 'bytes', 'gate', 'owner_lane']
NO_PS2 = {  # GC models with no usable PS2 counterpart: why (ps2_source column)
    'et0000.bin': 'NONE:placeholder@{room}.dat:ETM/et0000.bin',
    'et2500.bin': 'NONE:placeholder@{room}.dat:ETM/et2500.bin',
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def ps2_etm_names(room):
    idx = pb.afs_index(po.PS2_ISO)
    pd = pb.afs_read(po.PS2_ISO, room + '.dat', idx)
    pbm = next((b for i, t, b in pb.dat_entries(pd) if t == 'ETM'), None)
    return {nm.lower() for nm, s, e in po.etm_entries(pbm, '<')} if pbm else set()


def add(a):
    lib = Path(a.lib); room = a.room
    out = lib / 'objects' / room; (out / 'models').mkdir(parents=True, exist_ok=True)
    dar = Path(a.dar).read_bytes(); rep = json.loads(Path(a.report).read_text())
    if rep.get('dar_out_sha256') and rep['dar_out_sha256'] != sha(dar):
        sys.exit('%s: sha256 %s != report dar_out_sha256 %s' % (a.dar, sha(dar), rep['dar_out_sha256']))
    shutil.copyfile(a.report, out / 'report.json')
    tex = None
    if a.tex_report:
        # ps2_objects_tex.py output: the same geometry with PS2 pictures (record keys rewritten) + its packages
        tex = json.loads(Path(a.tex_report).read_text())
        if tex['dar_in_sha256'] != sha(dar):
            sys.exit('tex report input %s is not this geometry dar %s' % (tex['dar_in_sha256'], sha(dar)))
        dar = Path(tex['dar_out'] if Path(tex['dar_out']).exists() else a.tex_dar).read_bytes()
        if tex['dar_out_sha256'] != sha(dar):
            sys.exit('textured dar sha256 mismatch')
        shutil.copyfile(a.tex_report, out / 'tex-report.json')
        (out / 'tex').mkdir(exist_ok=True)
        for f in (out / 'tex').glob('*.re4tex'):
            f.unlink()
        for f in Path(a.texdir).glob('*.re4tex'):
            shutil.copyfile(f, out / 'tex' / f.name)
    (out / ('%s.dar' % room)).write_bytes(dar)
    kind, size, dest, off = struct.unpack_from('<4I', dar, 0x20)
    pay = dar[off:off + size]
    g = GcIso(po.GC_ISO); gd = g.read(dict(g.rooms())[room])
    if gd[:32] == rs.CONTAINER_MAGIC:
        gd = rs.decode_das(gd)
    ge = rs.tagged_entries(gd, '>'); le = rs.tagged_entries(pay, '<')
    arcs = {o['gc_arc']: o['ps2_arc'] for o in rep['objects'] if o.get('gc_arc')}
    froms = {o['name'].lower(): o['ps2_from'] for o in rep['objects'] if o.get('ps2_from')}
    etm_ps2 = ps2_etm_names(room)
    fmt = 'GC ModelData LE (le_mirror) in st1/%s.dar payload; GC TPL textures' % room
    tex_ok = {}
    if tex:
        for m in tex['models']:
            tex_ok[str(m['name']).lower()] = m.get('ok'), m.get('why')
    rows = [dict(gc_id='%s.dar' % room, ps2_source='%s.dat' % room, dc_format='native room payload st1/%s.dar' % room,
                 sha256=sha(dar), bytes=len(dar), gate=a.gate)]
    n = {'PS2': 0, 'WORLD': 0, 'GC': 0}
    for i, (tag, s, e) in enumerate(ge):
        t = tag.rstrip(b'\0')
        models = []
        if t == b'BIN' and e > s:
            models.append(('BIN#%02x' % (i + 4), gd[s:e], pay[le[i][1]:le[i][2]], hex(i + 4), None))
        if t == b'ETM':
            lb = pay[le[i][1]:le[i][2]]
            for (nm, gs, gend), (lnm, ls, lend) in zip(po.etm_entries(gd[s:e], '>'), po.etm_entries(lb, '<')):
                if nm.lower().endswith('.bin'):
                    models.append(('ETM/' + nm.lower(), gd[s:e][gs + 0x40:gend], lb[ls + 0x40:lend], None, nm.lower()))
        for gid, gbin, cur, arc, nm in models:
            src = po.to_le(gbin, gid).rstrip(b'\0'); c = cur.rstrip(b'\0')
            if c != src:
                empty = len(c) < 0.05 * len(src)
                st = 'WORLD' if empty else 'PS2'
                if arc:
                    p = arcs.get(arc)
                    ps2 = '%s.dat:SMD(world package)' % room if p == 'world' else '%s.dat:BIN#%02x' % (room, int(p, 16))
                else:
                    ps2 = froms.get(nm) or '%s.dat:ETM/%s' % (room, nm)
                gate = a.gate
            else:
                st = 'GC'
                why = KNOWN.get('%s@%s' % (nm, room)) or KNOWN.get(nm or '') or 'not converted'
                if nm in NO_PS2:
                    ps2 = NO_PS2[nm].format(room=room)
                elif nm and nm not in etm_ps2:
                    ps2 = 'NONE'
                else:
                    ps2 = ('%s.dat:ETM/%s' % (room, nm)) if nm else ('%s.dat:BIN#%02x?' % (room, int(arc, 16)))
                gate = 'FAIL:kept-GC(%s)' % why
            n[st] += 1
            fn = out / 'models' / (gid.replace('/', '_').replace('#', '') + ('' if gid.endswith('.bin') else '.bin'))
            fn.write_bytes(cur)
            f_ = fmt
            if tex and st == 'PS2':
                ok, why = tex_ok.get(nm or arc, (None, 'not in the texture pass'))
                f_ = fmt.replace('GC TPL textures', 'PS2 pictures (dc/tex packages, records re-keyed)' if ok else
                                 'GC TPL textures (%s)' % why)
            rows.append(dict(gc_id='%s.das:%s' % (room, gid), ps2_source=ps2,
                             dc_format=(f_ if st != 'GC' else 'GameCube model (not converted), ' + fmt),
                             sha256=sha(cur), bytes=len(cur), gate=gate))
    for im in (tex or {}).get('images', []):
        rows.append(dict(gc_id='%s.das:%s image %d (was %s)' % (room, im['model'], im['image'], im['old_key']),
                         ps2_source='PS2 image %d of the model\'s PS2 TPL (%s)' % (im.get('ps2_image', im['image']),
                                                                               im['ps2'].get('orient', '')),
                         dc_format='dc/tex/%s.re4tex %dx%d %s fmt %d%s' % (
                             im['key'], im['ps2']['width'], im['ps2']['height'], im['ps2']['payload'], im['ps2']['format'],
                             ' (self-key record)' if im['ps2'].get('selfkey_record') else ''),
                         sha256=im['sha256'], bytes=im['bytes'], gate=a.gate))
    idx = lib / 'INDEX.tsv'
    lines = idx.read_text().splitlines() if idx.exists() else ['\t'.join(COLS)]
    keep = [l for l in lines if not (l.split('\t')[:2] == ['objects', room])]
    for r in rows:
        keep.append('\t'.join(str(x) for x in ['objects', room, r['gc_id'], r['ps2_source'], r['dc_format'], a.converter,
                                                r['sha256'], r['bytes'], r['gate'], a.owner]))
    idx.write_text('\n'.join(keep) + '\n')
    print('%s %s PS2=%d WORLD=%d GC=%d dar %s' % (room, out, n['PS2'], n['WORLD'], n['GC'], sha(dar)[:16]))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('add')
    p.add_argument('--lib', required=True); p.add_argument('--room', required=True); p.add_argument('--dar', required=True)
    p.add_argument('--report', required=True); p.add_argument('--converter', required=True)
    p.add_argument('--gate', default='UNGATED'); p.add_argument('--owner', default='objs')
    p.add_argument('--tex-report'); p.add_argument('--tex-dar'); p.add_argument('--texdir')
    a = ap.parse_args()
    add(a)


if __name__ == '__main__':
    main()
