#!/usr/bin/env python3
"""Room SMD scenery for any room: BIN extraction, placement scales and the
native-mesh release contract (D367 W9).

A room's static scenery is its SMD (game/scroll.cpp cSmd): a 16-byte header
(version, flags, work count, BIN / TPL / FCV table offsets), optional group
counts, one 72-byte SmdWork per placement (pos, rot, scale, binNo, tplNo,
motNo, id, ..., flags at +0x44; flags bit 4 = BIN and TPL from the common SMD)
and the tables. Table entries are offsets from the table itself.

  room_smd.py extract <room.das|tagged archive|.SMD> <outdir>
      Local (non-common) BINs as <outdir>/NNNN.BIN in source byte order, plus
      placements.json and scales.json (largest |scale| per BIN, the form
      convert_room_bins.py --scales takes, owner 0xff).
  room_smd.py release <room.arc|room.dar|block.dat> <identity>[,<identity>..] <out>
                      [--common <identity>[,<identity>..]]
      The release contract below, applied to a converted (little-endian)
      room archive, its .dar container or a scroll block file (st1/r100_0N.dat:
      a tagged archive holding one SMD); writes <out>.json with per-BIN
      savings. An identity is a convert_room_bins.py summary (.re4mesh.json,
      its "release" list) or the R4IM package itself (.re4mesh). Several
      identities (e.g. the Original and the Standard package of one owner:
      whichever the runtime opens binds the released BIN) release only the
      BINs that all of them cover with the same source identity. A room
      archive's second SMD is its common SMD (game.cpp SmdInit); --common
      gives its identities (the COMMON package), otherwise it is kept. The
      output is checked as `check` does before it is written.
  room_smd.py check <source> <released>
      Proves that <released> differs from <source> only by the release
      contract: every released BIN is exactly release_bin() of its source,
      every other byte is unchanged or moved with its sub-file, and every
      rebased index record (NTR, ESQ) points at unchanged bytes.

Release contract. A BIN that a native R4IM package covers completely (every
source part, single node, rigid, no shape table; convert_room_bins.py lists
these in its summary under "release") is never drawn from its GX data. Its
render payload leaves the archive and the BIN keeps only what the game still
reads (model.cpp getBoundingBox / calcModelAddr, trans.cpp part walk and
shaderSetup, scroll.cpp SmdSetParam, model_bridge.cpp):
  - header, joint heads (pHead), weights, blend/flip tables: unchanged;
  - vertices: 2 records, the source box corners (min, max; so getBoundingBox
    and the light/cull bounds are unchanged), nVtx = 2;
  - normals: 1 record (nNrm = 1); UVs: 1 record;
  - CLR0: unchanged, still directly followed by the UV array (the bridge
    bounds vertex alpha over pClr..pTex);
  - parts: every 32-byte part header, in order, with its stream size set to 0
    and no stream, so parts stay 32-byte aligned and the walk steps 32 bytes.
The runtime (native_static.cpp) recognises nVtx == 2 with a zero stream size
as released and matches parts by index (offset / 32) instead of by source
offset and size. A released part never falls back to GX data: any path that
would (no package, reserve failure) draws nothing. The released archive is
therefore only valid together with its packages and NATIVE_MESH=1.

Scroll block files (block.cpp) hold one SMD each; cBlock::checkBlockMemory
sizes the block pool from the file sizes, so a released block file shrinks the
pool with no code change. A room archive with prepared indexes keeps them
valid: NTR (texture identities) and ESQ (effect sequences) hold absolute
archive offsets; both are rebased and re-checksummed, and a record inside a
released BIN region is refused.
"""
import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

WORK_SIZE = 72
COMMON_FLAG = 0x10
RELEASED_VERTICES = 2  # instanced_mesh.hpp kReleasedVertices
# releasable() reasons that also keep a BIN off the native mesh path
# (model_bridge.cpp static_geometry); other reasons only block the release.
RENDER_UNQUALIFIED = ("multi-node", "shape", "skinned", "version", "empty")
CONTAINER_MAGIC = b"\xca\xb6\xbe\x20" * 8


def align(n, a=32):
    return (n + a - 1) & ~(a - 1)


# ---- containers -------------------------------------------------------------
def tagged_entries(data, e):
    """Tagged archive (u32 count, 12 bytes, u32 offsets[count], tags[count][4])
    -> [(tag, start, end)] in index order; ends follow the next larger offset."""
    n = struct.unpack_from(e + "I", data, 0)[0]
    if not 0 < n <= 0x100 or 0x10 + 8 * n > len(data):
        raise ValueError("not a tagged archive")
    offs = struct.unpack_from(e + "%dI" % n, data, 0x10)
    tags = [bytes(data[0x10 + 4 * n + 4 * i:0x14 + 4 * n + 4 * i]) for i in range(n)]
    out = []
    for i in range(n):
        later = [o for o in offs if o > offs[i]]
        out.append((tags[i], offs[i], min(later) if later else len(data)))
    return out


def archive_endian(data):
    for e in (">", "<"):
        n = struct.unpack_from(e + "I", data, 0)[0]
        if 0 < n <= 0x100 and 0x10 + 8 * n <= len(data) and not any(data[4:16]):
            first = struct.unpack_from(e + "I", data, 0x10)[0]
            if 0x10 + 8 * n <= first <= len(data):
                return e
    raise ValueError("not a tagged archive")


def decode_das(data):
    """Room DVD container -> its decoded (source byte order) tagged archive."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from decode_yz2 import decode
    payloads = []
    for pos in range(0x20, 0x400, 0x20):
        kind, size, _, offset = struct.unpack_from(">4I", data, pos)
        if kind == 0xFFFFFFFF:
            break
        if kind == 0:
            payloads.append((offset, size))
    if len(payloads) != 1:
        raise ValueError("expected one type-0 room payload")
    offset, size = payloads[0]
    return bytes(decode(data[offset:offset + size]))


def load_smd(path):
    """-> (smd bytes, byte order '>' or '<') from a .das, a tagged archive or an SMD."""
    data = Path(path).read_bytes()
    if data[:32] == CONTAINER_MAGIC:
        data = decode_das(data)
    try:
        e = archive_endian(data)
    except ValueError:
        return data, smd_endian(data)
    smd = [(s, t) for tag, s, t in tagged_entries(data, e) if tag == b"SMD\0"]
    if len(smd) != 1:
        raise ValueError("%s: expected one SMD, found %d" % (path, len(smd)))
    return data[smd[0][0]:smd[0][1]], e


def smd_endian(data):
    for e in (">", "<"):
        count = struct.unpack_from(e + "H", data, 2)[0]
        tables = struct.unpack_from(e + "3I", data, 4)
        if count and all(0x10 <= t <= len(data) for t in tables):
            return e
    raise ValueError("not an SMD")


# ---- SMD --------------------------------------------------------------------
class Smd:
    def __init__(self, data, e=">"):
        self.data, self.e = bytes(data), e
        self.flag = data[1]
        self.count = struct.unpack_from(e + "H", data, 2)[0]
        self.tables = list(struct.unpack_from(e + "3I", data, 4))
        work = 0x10
        if self.flag & 1:
            work = 0x14 + 4 * struct.unpack_from(e + "I", data, 0x10)[0]
        self.work = work
        self.placements = []
        for i in range(self.count):
            p = work + i * WORK_SIZE
            f = struct.unpack_from(e + "9f", data, p)
            b, t, m, ident = data[p + 36:p + 40]
            flags = struct.unpack_from(e + "I", data, p + 0x44)[0]
            self.placements.append(dict(work=i, pos=f[0:3], rot=f[3:6], scale=f[6:9], bin=b, tpl=t, mot=m,
                                        id=ident, flags=flags, common=bool(flags & COMMON_FLAG)))

    def used(self):
        return [p for p in self.placements if p["id"] != 0xFF]

    def local_bins(self):
        return sorted({p["bin"] for p in self.used() if not p["common"]})

    def bin_table(self):
        """-> (table offset, [BIN start] for indices 0..max local, region end)."""
        local = self.local_bins()
        base = self.tables[0]
        n = max(local) + 1 if local else 0
        starts = [base + struct.unpack_from(self.e + "I", self.data, base + 4 * i)[0] for i in range(n)]
        later = [t for t in self.tables[1:] if t > base]
        end = min(later) if later else len(self.data)
        return base, starts, end

    def bins(self):
        """Local BINs -> {index: bytes}; a body ends at the next BIN start or the region end."""
        base, starts, end = self.bin_table()
        cuts = sorted(set(starts + [end]))
        out = {}
        for i in self.local_bins():
            s = starts[i]
            if not base < s < end:
                raise ValueError("BIN %d outside the BIN region" % i)
            out[i] = self.data[s:min(c for c in cuts if c > s)]
        return out

    def scales(self, owner=0xFF):
        out = {}
        for p in self.used():
            if p["common"]:
                continue
            key = "%d:%d" % (owner, p["bin"])
            out[key] = max(out.get(key, 0.0), max(abs(s) for s in p["scale"]))
        return out


# ---- BIN layout -------------------------------------------------------------
BIN_POINTERS = (("head", 0), ("clr", 12), ("tex", 16), ("weight", 20), ("parts", 28), ("shape", 44),
                ("vtx", 48), ("nrm", 52))


def bin_layout(b, e):
    """ModelData fields and pointer regions (each region runs to the next pointer)."""
    u32 = lambda o: struct.unpack_from(e + "I", b, o)[0]
    u16 = lambda o: struct.unpack_from(e + "H", b, o)[0]
    version = u32(60)
    ptr = {k: u32(o) for k, o in BIN_POINTERS}
    if version == 0x20030818:
        ptr.update(blend=u32(64), flip=u32(68))
    head = 72 if version == 0x20030818 else 64
    starts = sorted({v for v in ptr.values() if v} | {len(b)})
    region = {k: (v, min(s for s in starts if s > v)) for k, v in ptr.items() if v}
    return dict(version=version, head_bytes=head, ptr=ptr, region=region, nw=b[24], nj=b[25], nd=u16(26),
                flags=u32(32), ext=u16(42), nv=u16(56), nn=u16(58))


def part_headers(b, e, lay):
    """-> [(offset from the first part header, stream size)] in source order."""
    out, cur = [], lay["ptr"]["parts"]
    for _ in range(lay["nd"]):
        size = struct.unpack_from(e + "I", b, cur + 0x18)[0]
        out.append((cur - lay["ptr"]["parts"], size))
        cur += 0x20 + size
    return out


def releasable(b, e):
    """None when the release stub is exact for this BIN, else the reason."""
    lay = bin_layout(b, e)
    if lay["version"] not in (0x20010801, 0x20030818):
        return "version"
    if lay["nj"] != 1:
        return "multi-node"
    if lay["ptr"]["shape"]:
        return "shape"
    if lay["nw"] > 1 or lay["ext"] > 0xFF:
        return "skinned"
    if not lay["nv"] or not lay["nn"]:
        return "empty"
    order = sorted((v, k) for k, v in lay["ptr"].items() if v)
    names = [k for _, k in order]
    if "clr" in names and names[names.index("clr") + 1:names.index("clr") + 2] != ["tex"]:
        return "CLR0 not followed by UVs"
    for k in ("vtx", "nrm", "tex", "parts"):
        if k not in lay["region"]:
            return "no %s" % k
    heads = part_headers(b, e, lay)
    if heads and heads[-1][0] + 0x20 + heads[-1][1] > lay["region"]["parts"][1] - lay["ptr"]["parts"]:
        return "parts overrun"
    if lay["ptr"]["parts"] % 32 or lay["ptr"]["vtx"] % 4:
        return "alignment"
    return None


def release_bin(b, e):
    """Source BIN (either byte order) -> the release stub (module docstring)."""
    why = releasable(b, e)
    if why:
        raise ValueError("BIN not releasable: " + why)
    lay = bin_layout(b, e)
    nv = lay["nv"]
    vtx = lay["ptr"]["vtx"]
    pos = [struct.unpack_from(e + "3h", b, vtx + 8 * i) for i in range(nv)]
    lo = [min(p[a] for p in pos) for a in range(3)]
    hi = [max(p[a] for p in pos) for a in range(3)]
    nrm_bytes = 4 if lay["flags"] & 0x20000000 else 8
    new = {
        "vtx": struct.pack(e + "4h", *lo, 0) + struct.pack(e + "4h", *hi, 0),
        "nrm": b[lay["ptr"]["nrm"]:lay["ptr"]["nrm"] + nrm_bytes],
        "tex": b[lay["ptr"]["tex"]:lay["ptr"]["tex"] + 4],
    }
    heads = part_headers(b, e, lay)
    parts = bytearray()
    for off, _ in heads:
        h = bytearray(b[lay["ptr"]["parts"] + off:lay["ptr"]["parts"] + off + 0x20])
        struct.pack_into(e + "I", h, 0x18, 0)
        parts += h
    new["parts"] = bytes(parts)
    out = bytearray(b[:min(v for v in lay["ptr"].values() if v)])
    moved = {}
    for start, name in sorted((v, k) for k, v in lay["ptr"].items() if v):
        body = new.get(name, b[lay["region"][name][0]:lay["region"][name][1]])
        # CLR0 keeps its exact length so the UV array follows it directly.
        out += bytes((-len(out)) % (4 if name == "tex" else 32))
        moved[name] = len(out)
        out += body
    out += bytes((-len(out)) % 32)
    for name, o in dict(BIN_POINTERS + (("blend", 64), ("flip", 68))).items():
        if name in moved:
            struct.pack_into(e + "I", out, o, moved[name])
    struct.pack_into(e + "HH", out, 56, RELEASED_VERTICES, 1)
    return bytes(out)


def released_bounds(b, e):
    """getBoundingBox over a BIN's vertex array (for checks)."""
    lay = bin_layout(b, e)
    shift = b[0x28]
    pos = [struct.unpack_from(e + "3h", b, lay["ptr"]["vtx"] + 8 * i) for i in range(lay["nv"])]
    lo = [min(p[a] for p in pos) / (1 << shift) for a in range(3)]
    hi = [max(p[a] for p in pos) / (1 << shift) for a in range(3)]
    return [(lo[a] + hi[a]) / 2 for a in range(3)], [(hi[a] - lo[a]) / 2 for a in range(3)]


def release_smd(smd, e, release):
    """-> (new SMD bytes, report). release: {bin index: package identity dict
    (vertices, parts, part_offsets, part_sizes)}; each BIN is checked against
    it before its payload is dropped."""
    s = Smd(smd, e)
    base, starts, end = s.bin_table()
    first = min(starts) if starts else end
    order = sorted(set(starts))
    # A body runs to the next placed BIN's start: a table word past the placed
    # BINs (an unplaced BIN) would be swallowed by the body before it.
    for k in range(len(starts), (first - base) // 4 if starts else 0):
        v = base + struct.unpack_from(e + "I", smd, base + 4 * k)[0]
        if base < v < end and v not in order:
            raise ValueError("BIN table entry %d: an unplaced BIN inside the BIN region" % k)
    body = {st: smd[st:min([x for x in order if x > st] + [end])] for st in order}
    new_region, where, report = bytearray(), {}, []
    index_of = {}
    for i, st in enumerate(starts):
        index_of.setdefault(st, []).append(i)
    for st in order:
        b = body[st]
        ids = index_of[st]
        want = [i for i in ids if i in release]
        if want:
            ident = release[want[0]]
            lay = bin_layout(b, e)
            heads = part_headers(b, e, lay)
            got = dict(vertices=lay["nv"], parts=lay["nd"], part_offsets=[o for o, _ in heads],
                       part_sizes=[z for _, z in heads])
            for k, v in got.items():
                if k in ident and ident[k] != v:
                    raise ValueError("BIN %d: %s differs from its package" % (want[0], k))
            stub = release_bin(b, e)
            report.append(dict(bin=want[0], source=len(b), resident=len(stub), parts=lay["nd"]))
            b = stub
        new_region += bytes((-(first + len(new_region))) % 32)
        where[st] = first + len(new_region)
        new_region += b
    new_region += bytes((-(first + len(new_region))) % 32)
    delta = (first + len(new_region)) - end
    out = bytearray(smd[:first]) + new_region + smd[end:]
    for i, st in enumerate(starts):
        struct.pack_into(e + "I", out, base + 4 * i, where[st] - base)
    tables = [t + delta if t >= end else t for t in s.tables]
    struct.pack_into(e + "3I", out, 4, *tables)
    return bytes(out), dict(smd_source=len(smd), smd_resident=len(out), saved=len(smd) - len(out), bins=report,
                            bin_region_start=first, bin_region_end=end)


def offset_map(moves):
    """[(region start, region end, delta)] of released BIN regions (absolute
    archive offsets) -> source offset -> released offset. Bytes from a
    region's end on move by its delta; an offset inside a region has no
    counterpart."""
    def where(v):
        d = 0
        for lo, hi, delta in moves:
            if lo <= v < hi:
                raise ValueError("offset 0x%x inside a released BIN region" % v)
            if v >= hi:
                d += delta
        return v + d
    return where


def release_archive(arc, release):
    """Converted room archive or scroll block file -> (archive with its SMDs
    released, report). release: {bin: identity} for an archive with one SMD,
    or one such dict per SMD in archive order (None or {}: that SMD is kept);
    a room archive's second SMD is its common SMD (game.cpp SmdInit)."""
    e = archive_endian(arc)
    entries = tagged_entries(arc, e)
    smd = [i for i, (tag, _, _) in enumerate(entries) if tag == b"SMD\0"]
    if isinstance(release, dict):
        if len(smd) != 1:
            raise ValueError("expected one SMD in the room archive (%d: give one release map per SMD)" % len(smd))
        release = [release]
    if len(release) != len(smd):
        raise ValueError("%d SMDs, %d release maps" % (len(smd), len(release)))
    out, moves, smds = bytearray(arc), [], []
    # Last SMD first: an earlier SMD's offsets stay valid while a later one is replaced.
    for i, rel in sorted(zip(smd, release), key=lambda x: -entries[x[0]][1]):
        _, s, t = entries[i]
        if not rel:
            smds.append(dict(entry=i, kept=True))
            continue
        new_smd, report = release_smd(arc[s:t], e, rel)
        delta = len(new_smd) - (t - s)
        if delta % 32:
            raise ValueError("SMD size change is not 32-byte aligned")
        out[s:t] = new_smd
        # Only the BIN region shrinks: SMD bytes from its end on (TPL / FCV
        # tables) and every later sub-file move by delta.
        moves.append((s + report.pop("bin_region_start"), s + report.pop("bin_region_end"), delta))
        report.update(entry=i)
        smds.append(report)
    where = offset_map(moves)
    for i, (tag, o, _) in enumerate(entries):
        struct.pack_into(e + "I", out, 0x10 + 4 * i, where(o))
    for tag, o, _ in entries:
        if tag == b"NTR\0":
            rebase_native_table(out, where(o), e, where)
        elif tag == b"ESQ\0":
            rebase_effect_table(out, where(o), e, where, len(arc))
    smds.sort(key=lambda r: r["entry"])
    report = dict(smds=smds, saved=len(arc) - len(out), archive_source=len(arc), archive_resident=len(out))
    if len(smds) == 1 and not smds[0].get("kept"):
        report.update({k: v for k, v in smds[0].items() if k != "entry"}, saved=len(arc) - len(out))
    return bytes(out), report


NATIVE_TABLE_MAGIC = b"R4NTBL\0\0"
EFFECT_TABLE_MAGIC = b"R4ESQTBL"


def rebase_native_table(out, at, e, where):
    """prepare_native_ui.py --compact-room NTR index (magic, version, count,
    stride 12, crc32(records), original bytes, resident bytes; records of
    absolute payload / header / TPL offsets): rebase the offsets (where:
    offset_map), set the resident size, recompute the CRC. texture_package.cpp
    SourceIdentityTable rejects the archive otherwise."""
    magic, version, count, stride, _, original, _ = struct.unpack_from(e + "8s6I", out, at)
    if magic != NATIVE_TABLE_MAGIC or version != 1 or stride != 12:
        raise ValueError("unknown NTR index")
    for k in range(3 * count):
        p = at + 32 + 4 * k
        v = struct.unpack_from(e + "I", out, p)[0]
        try:
            struct.pack_into(e + "I", out, p, where(v))
        except ValueError:
            raise ValueError("NTR record inside the released BIN region")
    crc = zlib.crc32(bytes(out[at + 32:at + 32 + 12 * count])) & 0xFFFFFFFF
    struct.pack_into(e + "8s6I", out, at, magic, version, count, stride, crc, original, len(out))


def rebase_effect_table(out, at, e, where, source_bytes):
    """compact_effect_records.py ESQ index (magic, version 1, count, stride 12,
    crc32(records), archive bytes, 0; records: absolute EST sequence offset,
    resident span, record count): rebase the sequence offsets, set the archive
    size, recompute the CRC. native_effect.cpp bind_archive checks all three
    and binds nothing otherwise (the room's effects then read raw records)."""
    magic, version, count, stride, _, size, zero = struct.unpack_from(e + "8s6I", out, at)
    if magic != EFFECT_TABLE_MAGIC or version != 1 or stride != 12 or zero or size != source_bytes:
        raise ValueError("unknown ESQ index")
    for k in range(count):
        p = at + 32 + 12 * k
        v = struct.unpack_from(e + "I", out, p)[0]
        try:
            struct.pack_into(e + "I", out, p, where(v))
        except ValueError:
            raise ValueError("ESQ record inside the released BIN region")
    crc = zlib.crc32(bytes(out[at + 32:at + 32 + 12 * count])) & 0xFFFFFFFF
    struct.pack_into(e + "8s6I", out, at, magic, version, count, stride, crc, len(out), zero)


def release_container(data, release):
    """.dar (converted DVD container, room in the first type-0 slot) or a bare
    converted room archive -> the same form, released (le_mirror.py
    replace_native_payload keeps nested sound entries untouched)."""
    if data[:32] != CONTAINER_MAGIC:
        return release_archive(data, release)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import le_mirror
    slot = le_mirror.native_payload_slot(data)
    _, size, _, offset = struct.unpack_from("<4I", data, slot)
    arc, report = release_archive(data[offset:offset + size], release)
    # replace_native_payload appends; a payload that already ends the
    # container (an earlier native payload) is dropped rather than kept as
    # dead disc bytes. Nested sound entries lie before it and never move.
    others = []
    for pos in range(0x20, 0x400, 0x20):
        kind, _, _, at = struct.unpack_from("<4I", data, pos)
        if kind == 0xFFFFFFFF:
            break
        if pos != slot:
            others.append(at)
    tail = align(offset + size) == len(data) and all(at < offset for at in others)
    if tail and offset % 32 == 0:  # the same slot record replace_native_payload writes
        out = bytearray(data[:offset]) + arc + bytes((-len(arc)) & 31)
        struct.pack_into("<4I", out, slot, 0, len(arc), 0, offset)
        out = bytes(out)
    else:
        out = bytes(le_mirror.replace_native_payload(data, arc))
    le_mirror.native_payload_slot(out)
    report.update(container_source=len(data), container=len(out))
    return out, report


def package_release(summary):
    """convert_room_bins.py summary JSON -> {bin: identity} of releasable BINs."""
    return {int(r["bin"]): r for r in summary.get("release", [])}


# room/instanced_mesh.hpp MeshHeader (80 B), MeshRecord (68 B), MeshPart (36 B); little-endian.
R4IM_HEADER = struct.Struct("<4s15I4I")
R4IM_MESH = struct.Struct("<HBBHHIII12f")
R4IM_PART = struct.Struct("<IIBBBBII4f")
IDENTITY_KEYS = ("vertices", "parts", "part_offsets", "part_sizes")


def package_identities(data, common=False):
    """R4IM package (convert_room_bins.py, v1-v3) -> {bin: identity} of the
    meshes a released BIN binds to at run time: instanced_mesh.hpp
    source_identity accepts nVtx == 2 only when the mesh carries every source
    part (part_count == source_parts), and source_part then takes part k for
    the k-th part header. The identity (source vertices, part count, part
    header offsets and stream sizes) is what release_smd checks against the
    BIN. common: the COMMON SMD's meshes (MeshRecord.common), else the owner's."""
    if len(data) < R4IM_HEADER.size:
        raise ValueError("not an R4IM package")
    h = R4IM_HEADER.unpack_from(data, 0)
    if h[0] != b"R4IM" or h[1] not in (1, 2, 3) or h[2] != len(data):
        raise ValueError("not an R4IM package")
    mesh_count, part_count, mesh_offset, part_offset = h[4], h[5], h[10], h[11]
    if (mesh_offset + R4IM_MESH.size * mesh_count > len(data) or
            part_offset + R4IM_PART.size * part_count > len(data)):
        raise ValueError("R4IM tables outside the package")
    out = {}
    for m in range(mesh_count):
        b, c, _, vertices, parts, _, first, n = R4IM_MESH.unpack_from(data, mesh_offset + R4IM_MESH.size * m)[:8]
        if bool(c) != bool(common) or n != parts or first + n > part_count:
            continue
        if b in out:
            raise ValueError("BIN %d twice in the package" % b)
        heads = [R4IM_PART.unpack_from(data, part_offset + R4IM_PART.size * (first + k))[:2] for k in range(n)]
        out[b] = dict(bin=b, vertices=vertices, parts=parts, part_offsets=[o for o, _ in heads],
                      part_sizes=[z for _, z in heads])
    return out


def load_identities(sources, common=False):
    """Identity sources (convert_room_bins.py summaries or R4IM packages) ->
    ({bin: identity} of the BINs every source covers with the same identity,
    {bin: reason} of the others). Only local BINs are in summaries."""
    maps = []
    for src in sources:
        data = Path(src).read_bytes()
        if data[:4] == b"R4IM":
            maps.append(package_identities(data, common))
        elif common:
            raise ValueError("%s: a summary lists local BINs only; give the COMMON package" % src)
        else:
            maps.append(package_release(json.loads(data)))
    if not maps:
        return {}, {}
    release, skipped = {}, {}
    for b in sorted(set().union(*maps)):
        have = [m[b] for m in maps if b in m]
        if len(have) != len(maps):
            skipped[b] = "not in every identity source"
            continue
        ids = [tuple(json.dumps(r.get(k)) for k in IDENTITY_KEYS) for r in have]
        if any(None in (r.get(k) for k in IDENTITY_KEYS) for r in have) or len(set(ids)) != 1:
            skipped[b] = "identity sources disagree"
            continue
        release[b] = {k: have[0][k] for k in IDENTITY_KEYS}
    return release, skipped


def smd_regions(arc, e):
    """-> [(entry, SMD start, BIN region start, region end, [BIN starts])] (absolute)."""
    out = []
    for i, (tag, s, t) in enumerate(tagged_entries(arc, e)):
        if tag == b"SMD\0":
            sm = Smd(arc[s:t], e)
            base, starts, end = sm.bin_table()
            first = min(starts) if starts else end
            out.append((i, s, s + first, s + end, [s + x for x in starts]))
    return out


def payload_archive(data):
    """.dar container or bare archive -> (tagged archive, byte order)."""
    if data[:32] == CONTAINER_MAGIC:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import le_mirror
        slot = le_mirror.native_payload_slot(data)
        _, size, _, offset = struct.unpack_from("<4I", data, slot)
        data = data[offset:offset + size]
    return data, archive_endian(data)


def diff_release(source, released):
    """Raises ValueError unless <released> is <source> with nothing changed but
    the release contract (module docstring). Both are converted room archives,
    block files or .dar containers. -> report of what differs."""
    if source[:32] == CONTAINER_MAGIC:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import le_mirror
        if released[:32] != CONTAINER_MAGIC:
            raise ValueError("container released into a bare archive")
        a_slot, b_slot = le_mirror.native_payload_slot(source), le_mirror.native_payload_slot(released)
        if a_slot != b_slot:
            raise ValueError("native payload slot moved")
        slots = []
        for pos in range(0x20, 0x400, 0x20):
            ka = struct.unpack_from("<4I", source, pos)
            kb = struct.unpack_from("<4I", released, pos)
            if ka[0] == 0xFFFFFFFF:
                if kb[0] != 0xFFFFFFFF:
                    raise ValueError("container slot list changed")
                break
            if pos == a_slot:
                continue
            if ka != kb or source[ka[3]:ka[3] + ka[1]] != released[kb[3]:kb[3] + kb[1]]:
                raise ValueError("container slot 0x%x changed" % pos)
            slots.append(pos)
        if source[:0x20] != released[:0x20]:
            raise ValueError("container head changed")
        _, sa, _, oa = struct.unpack_from("<4I", source, a_slot)
        _, sb, _, ob = struct.unpack_from("<4I", released, b_slot)
        report = diff_release(source[oa:oa + sa], released[ob:ob + sb])
        report.update(container_source=len(source), container=len(released), other_slots_unchanged=len(slots))
        return report
    e = archive_endian(source)
    if archive_endian(released) != e:
        raise ValueError("byte order changed")
    ea, eb = tagged_entries(source, e), tagged_entries(released, e)
    n = len(ea)
    if [t for t, _, _ in ea] != [t for t, _, _ in eb] or source[:0x10] != released[:0x10]:
        raise ValueError("tag list or archive head changed")
    if source[0x10 + 8 * n:min(s for _, s, _ in ea)] != released[0x10 + 8 * n:min(s for _, s, _ in eb)]:
        raise ValueError("archive head padding changed")
    moves = []
    for (i, sa, lo, hi, _), (_, sb, lo2, hi2, _) in zip(smd_regions(source, e), smd_regions(released, e)):
        if lo2 - sb != lo - sa:
            raise ValueError("SMD %d: BIN region start moved" % i)
        moves.append((lo, hi, (hi2 - lo2) - (hi - lo)))
    where = offset_map(moves)
    released_bins = kept_bins = 0
    for i, ((tag, s, t), (_, s2, t2)) in enumerate(zip(ea, eb)):
        if where(s) != s2:
            raise ValueError("entry %d at 0x%x, expected 0x%x" % (i, s2, where(s)))
        a, b = source[s:t], released[s2:t2]
        name = tag.rstrip(b"\0").decode("latin1")
        if tag == b"SMD\0":
            sm_a, sm_b = Smd(a, e), Smd(b, e)
            base, starts, end = sm_a.bin_table()
            base2, starts2, end2 = sm_b.bin_table()
            first = min(starts) if starts else end
            first2 = min(starts2) if starts2 else end2
            d = (end2 - first2) - (end - first)
            tables = [x + d if x >= end else x for x in sm_a.tables]
            if (a[:4] != b[:4] or tables != sm_b.tables or base != base2 or first != first2 or
                    a[0x10:base] != b[0x10:base2] or a[end:] != b[end2:] or len(starts) != len(starts2) or
                    [starts.index(x) for x in starts] != [starts2.index(x) for x in starts2]):
                raise ValueError("SMD entry %d changed outside its BIN bodies" % i)
            if a[base + 4 * len(starts):first] != b[base2 + 4 * len(starts2):first2]:
                raise ValueError("SMD entry %d: BIN table padding changed" % i)
            order, order2 = sorted(set(starts)), sorted(set(starts2))
            for st, st2 in zip(order, [starts2[starts.index(x)] for x in order]):
                body = a[st:min([x for x in order if x > st] + [end])]
                body2 = b[st2:min([x for x in order2 if x > st2] + [end2])]
                # release_smd pads every body to 32 bytes with zeros
                if body2[:len(body)] == body and not any(body2[len(body):]):
                    kept_bins += 1
                    continue
                stub = release_bin(body, e)
                if body2[:len(stub)] != stub or any(body2[len(stub):]):
                    raise ValueError("SMD entry %d: a BIN is neither its source nor its release stub" % i)
                if released_bounds(body, e) != released_bounds(stub, e):
                    raise ValueError("SMD entry %d: bounds changed" % i)
                released_bins += 1
        elif tag in (b"NTR\0", b"ESQ\0"):
            count = struct.unpack_from(e + "I", a, 12)[0]
            if a[:20] != b[:20] or a[32 + 12 * count:] != b[32 + 12 * count:]:
                raise ValueError("%s index head or tail changed" % name)
            if zlib.crc32(b[32:32 + 12 * count]) & 0xFFFFFFFF != struct.unpack_from(e + "I", b, 20)[0]:
                raise ValueError("%s index CRC" % name)
            for k in range(count):
                ra3 = struct.unpack_from(e + "3I", a, 32 + 12 * k)
                rb3 = struct.unpack_from(e + "3I", b, 32 + 12 * k)
                if tag == b"NTR\0":   # record (>= 32 B), TPL image header (36 B), TPL head (12 B)
                    spans = ((ra3[0], rb3[0], 32), (ra3[1], rb3[1], 36), (ra3[2], rb3[2], 12))
                else:                 # EST sequence (span B), same span and record count
                    if ra3[1:] != rb3[1:]:
                        raise ValueError("ESQ record %d span changed" % k)
                    spans = ((ra3[0], rb3[0], ra3[1]),)
                for x, y, size in spans:
                    if where(x) != y or source[x:x + size] != released[y:y + size]:
                        raise ValueError("%s record %d does not point at its unchanged bytes" % (name, k))
            sizes = struct.unpack_from(e + "2I", b, 24)
            if tag == b"NTR\0" and sizes != (struct.unpack_from(e + "I", a, 24)[0], len(released)):
                raise ValueError("NTR sizes")
            if tag == b"ESQ\0" and sizes != (len(released), 0):
                raise ValueError("ESQ archive size")
        elif a != b:
            raise ValueError("entry %d (%s) changed" % (i, name))
    return dict(released_bins=released_bins, kept_bins=kept_bins, entries=n, source=len(source),
                released=len(released), saved=len(source) - len(released),
                regions=[dict(start=lo, end=hi, delta=d) for lo, hi, d in moves])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("extract")
    x.add_argument("source", type=Path)
    x.add_argument("out", type=Path)
    x.add_argument("--owner", type=lambda v: int(v, 0), default=0xFF)
    r = sub.add_parser("release")
    r.add_argument("archive", type=Path)
    r.add_argument("package", help="identity sources, comma-separated: convert_room_bins.py summaries "
                                   "(.re4mesh.json) or R4IM packages (.re4mesh); a BIN is released only when all "
                                   "of them cover it with the same identity")
    r.add_argument("out", type=Path)
    r.add_argument("--common", help="identity sources of a room archive's common SMD (the COMMON package); "
                                    "without it that SMD is kept")
    c = sub.add_parser("check")
    c.add_argument("source", type=Path)
    c.add_argument("released", type=Path)
    a = ap.parse_args()
    if a.cmd == "extract":
        smd, e = load_smd(a.source)
        s = Smd(smd, e)
        a.out.mkdir(parents=True, exist_ok=True)
        bins = s.bins()
        for i, b in bins.items():
            if e == "<":
                raise ValueError("extract needs source byte order (.das, decoded archive or source SMD)")
            (a.out / ("%04d.BIN" % i)).write_bytes(b)
        (a.out / "placements.json").write_text(json.dumps(s.used(), indent=0))
        (a.out / "scales.json").write_text(json.dumps(s.scales(a.owner), indent=0, sort_keys=True))
        why = {i: releasable(b, e) for i, b in bins.items()}
        print(json.dumps(dict(source=str(a.source), smd_bytes=len(smd), sha256=hashlib.sha256(smd).hexdigest(),
                              placements=len(s.used()), common_placements=sum(p["common"] for p in s.used()),
                              local_bins=len(bins), bin_bytes=sum(len(b) for b in bins.values()),
                              not_releasable={i: w for i, w in why.items() if w})))
    elif a.cmd == "check":
        print(json.dumps(diff_release(a.source.read_bytes(), a.released.read_bytes())))
    else:
        source = a.archive.read_bytes()
        own, skipped = load_identities(a.package.split(","))
        smds = len(smd_regions(*payload_archive(source)))
        if smds == 1 and a.common:
            raise ValueError("%s has one SMD: --common does not apply" % a.archive)
        release = own
        if smds > 1:
            common, skipped_common = load_identities(a.common.split(","), True) if a.common else ({}, {})
            release = [own] + [common] + [None] * (smds - 2)
        out, report = release_container(source, release)
        check = diff_release(source, out)
        if a.out.exists():
            raise FileExistsError(a.out)
        a.out.write_bytes(out)
        report.update(archive=str(a.archive), package=a.package, common=a.common, not_released=skipped,
                      check=check, sha256=hashlib.sha256(out).hexdigest())
        if smds > 1:
            report.update(common_not_released=skipped_common)
        Path(str(a.out) + ".json").write_text(json.dumps(report, indent=1))
        print(json.dumps({k: v for k, v in report.items() if k not in ("bins", "smds")}))


if __name__ == "__main__":
    main()
