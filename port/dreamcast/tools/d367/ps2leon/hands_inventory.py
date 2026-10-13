#!/usr/bin/env python3
"""ps2leon hands (issue #26, 2026-10-13): inventory of every model Leon's hand slots can show.

  hands_inventory.py <out.json>

The game swaps Leon's right / left hand model infos (cPlBody pRight / pLeft) through cPlLeon::setRightHand /
setLeftHand (src/game/pl_leon.cpp): right 0 = player arc 0x12, 1 = Body->pWepHand (each weapon's initWepHand:
a BIN of its own wepNN archive, or player arc 0x12 / 0x15), else a model pointer (r10f room arc 0x22); left 0..5 =
player arcs 0x14..0x19. The boat (pl0f) and pl0e set pWepHand from their own archive (arc 8 / 7).

For each candidate GC BIN (pl00 / pl08 arcs 0x12..0x19, every BIN of every GC wepNN.drs / pl0e / pl0f whose weights
use only hand bones) this lists: the runtime key (position count, normal count, palette count and the FNV-1a of the
first 64 bytes of the little-endian positions: coarse_actor.cpp fingerprint() over ModelData::vtxOrig on the DC),
the side (right: bones 9 / 10, left: 15 / 16), the GC sha256, and whether the PS2 disc has the same file and arc
with a BIN (the PS2 counterpart).
"""
import hashlib, json, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import leon_sources as ls  # noqa: E402
import drs  # noqa: E402
import ps2_bin as pb  # noqa: E402

RIGHT, LEFT = {9, 10}, {15, 16}
HAND_BONES = RIGHT | LEFT | {0, 1, 100}


def word(b, o):
    return struct.unpack_from('>I', b, o)[0]


def half(b, o):
    return struct.unpack_from('>H', b, o)[0]


def swap16(b):
    o = bytearray(b); o[::2] = b[1::2]; o[1::2] = b[::2]; return bytes(o)


def fnv64(b):
    h = 2166136261
    for x in b[:64]:
        h = ((h ^ x) * 16777619) & 0xffffffff
    return h


def gc_key(d):
    nv, nn = half(d, 56), half(d, 58)
    nw, ext = d[24], half(d, 42)
    pos = swap16(d[word(d, 48):word(d, 48) + nv * 8])
    w = d[word(d, 20):word(d, 20) + nw * 8]
    bones = {w[i] for i in range(len(w))}
    return dict(positions=nv, normals=nn, palette=ext if ext > 255 else nw, vertex_hash=fnv64(pos)), bones


def side(bones):
    if bones & RIGHT and not bones & LEFT:
        return 'right'
    if bones & LEFT and not bones & RIGHT:
        return 'left'
    return None


def main():
    from assetpipe.rooms import GcIso
    iso = GcIso(ls.GC_ISO)
    names = ['pl00', 'pl08', 'pl0e', 'pl0f'] + ['wep%02d' % i for i in range(64)]
    ps2_index = {n.lower() for n in pb.afs_index(ls.PS2_ISO)} if hasattr(pb, 'afs_index') else set()
    out = []
    for n in names:
        try:
            data = iso.read(iso.find('em/%s.drs' % n))
        except Exception:
            continue
        g = drs.Drs(data)
        ps2 = None
        try:
            ps2 = {i: (t, b) for i, t, b in pb.dat_entries(pb.afs_read(ls.PS2_ISO, '%s.dat' % n))}
        except Exception:
            ps2 = None
        for k, ent in enumerate(g.entries):
            arc = k + 4
            tag, d = ent[0], ent[1]
            if not str(tag).startswith('BIN') and tag != b'BIN':
                if not (isinstance(tag, (bytes, str)) and 'BIN' in str(tag)):
                    continue
            if n in ('pl00', 'pl08') and not 0x12 <= arc <= 0x19:
                continue
            try:
                key, bones = gc_key(d)
            except Exception:
                continue
            s = side(bones)
            if not s or not bones <= HAND_BONES or key['positions'] > 600:
                continue
            p = ps2.get(arc - 4) if ps2 else None
            out.append(dict(file=n, arc=arc, side=s, key=key, gc_sha256=hashlib.sha256(d).hexdigest(), gc_bytes=len(d),
                            ps2=bool(p and p[0] == 'BIN'), ps2_bytes=len(p[1]) if p else 0))
            print(n, hex(arc), s, key, 'ps2' if out[-1]['ps2'] else '-')
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
