#!/usr/bin/env python3
"""model_registry.py <spec.json> <out dir> [--tree <checkout>] [--package-room <hex room>] [--source-normal-length]
(D367 generic native models, 2026-10-03)

--source-normal-length (2026-10-04, default off: the output is byte-identical to before): every cast normal keeps
its direction and takes the length of its SOURCE BIN's normals. GX transforms normals without renormalising and
lights with n.l, and its normal fraction is fixed by the type (s8: 6 bits, s16: 14 bits), so the source's stored
normal length is part of its lighting (the stage-1 animal BINs store s8 normals of length ~127/64 = 1.97); unit cast
normals light the same actor about half as bright. The length is measured from the source BIN (mean of every
normal, recorded per section in registry-manifest.json). Fail closed: a source BIN whose normal lengths are not
uniform (max - min > 0.05), has no normals, or whose length does not fit the s16 / 14-bit encoding (>= 1.9999)
refuses the whole generation; so does a cast normal of zero length.

Generates the private NATIVE_MODEL_REGISTRY bundle (game/native_model_registry.mk) from validated cast packs and
the original archives. PRIVATE output: never commit it or put it in a patch (it holds converted meshes).

Inputs (read only; each copied into <out>/inputs/ with sha256 before / after the copy):
  <spec>                                   descriptors: cast set name, source archive, cModel id, source types
  <cast>/<revision_overlay>/integration-bundle/catalog.json   the explicitly named revision overlay
  <cast>/<name>/<revision>/revision-manifest.json            must agree with the catalog (header sha256)
  <cast>/<name>/manifest.json, source/candidate-revisions.json  the base selection (recorded, preserved)
  <cast>/<name>/source-bindings.json, source.json             source sections, skeleton, rest matrices
  the level's runtime header and every texture package it binds (by source_info)
  the original archives named by <cast>/source/archive-audit.json (sha256 checked)
  <tree>/port/dreamcast/game/actor_material_records.inc       base rows (capacities; fact-extraction self-check)

Fail-closed rules (exit 1, no output dir left behind): catalog / manifest / header / package hash disagreement;
a section whose archive BIN differs from source-bindings (counts, parts, flags, vertex signature); sections that
disagree on the hierarchy or an attach map that is not the identity; header chunks not in source_info order or
not one per section; a weight bone outside the skeleton, a weight set that does not sum to 1, a one-bone weight
other than 1.0; a stream that is not a level-zero FE/v3 blob or does not bound-check (tools mirror of
coarse_actor_preflight.h preflight_chunk); a chunk without a texture package, a package that is paletted /
not one texture / not a supported format; two descriptors with the same (archive, BIN set, TPL) source identity;
a source TPL with a mipmapped / non-base sampler; exceeding the runtime tables' capacities (source blobs <= 32,
role rows <= 64, materials per actor <= 3, chunks per actor <= 8, palette entries per chunk <= 256).
Descriptors whose SOURCE materials need a capability the flat owner path does not implement (bump, mask/alpha
pass) are NOT emitted for runtime; they are listed as contract entries in registry-manifest.json with the reason.

Outputs: native_model_registry.h (namespace nmr), native_model_registry_facts.inc / _roles.inc / _blobs.inc
(source identity rows for coarse_actor_material.inc), tex/<crc>-<fnv>.re4tex, registry-manifest.json (descriptor
<-> rooms, runtime / contract status, hashes, exact revision selections), SHA256SUMS. With --package-room also
package/r<room>/registry.re4nmr (NATIVE_MODEL_REGISTRY_PACK=1: the room-owned package, staged as
dc/native/r<room>/registry.re4nmr; layout in write_package; identical chunk geometry stored once).
"""
import hashlib, json, os, re, shutil, struct, sys, zlib

MATERIAL_ROWS = 64          # actor_lifetime.inc Info::roles mask capacity
SOURCE_BLOBS = 32           # actor_lifetime.inc Asset::templates mask capacity
ACTOR_MATERIALS = 3         # actor_native_owner.h kRe4dcActorMaterials
ACTOR_CHUNKS = 8            # Re4dcActorPlan info[8]
APPEARANCE0 = 0x200         # registry appearances 0x200 + descriptor index (Ganado 0..4, Leon 0x100)
# coarse_actor_material.inc Need bits and what the flat owner path implements for a non-Leon actor
DIFFUSE, SPECULAR, MASK, BUMP, MORPH, SOURCE_LIGHTING, SOURCE_PASS, ATLAS_SAMPLER = 1, 2, 4, 8, 16, 32, 64, 128
FLAT_IMPLEMENTED = DIFFUSE | SOURCE_LIGHTING | ATLAS_SAMPLER | SPECULAR
UNKNOWN = 1 << 16          # a source material program flag outside the certificate's known set (0..7)
NEED_NAMES = {DIFFUSE: 'diffuse', SPECULAR: 'specular', MASK: 'mask/alpha pass', BUMP: 'bump', MORPH: 'morph',
              SOURCE_LIGHTING: 'source lighting', SOURCE_PASS: 'source pass', ATLAS_SAMPLER: 'atlas sampler',
              UNKNOWN: 'an unknown material program (flags outside 0..7)'}


class Fail(Exception):
    pass


def sha(b):
    return hashlib.sha256(b).hexdigest()


def digest(b):
    f = 2166136261
    for x in b:
        f = ((f ^ x) * 16777619) & 0xffffffff
    return [len(b), zlib.crc32(b) & 0xffffffff, f]


def word(b, o):
    return struct.unpack_from('>I', b, o)[0]


def half(b, o):
    return struct.unpack_from('>H', b, o)[0]


def swap16(b):
    if len(b) % 2:
        raise Fail('odd swap16 span')
    o = bytearray(b); o[::2] = b[1::2]; o[1::2] = b[::2]
    return bytes(o)


class Inputs:
    """Copies every input under <out>/inputs (hash before, after and of the copy must agree)."""
    def __init__(self, out):
        self.dir = os.path.join(out, 'inputs'); self.files = {}

    def take(self, path, rel):
        if rel in self.files:
            return self.files[rel][0]
        if not os.path.isfile(path):
            raise Fail(f'missing input {path}')
        dst = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        a = sha(open(path, 'rb').read()); shutil.copy2(path, dst)
        b = sha(open(dst, 'rb').read()); c = sha(open(path, 'rb').read())
        if not a == b == c:
            raise Fail(f'{path} changed while copying (an asset agent is writing): rerun later')
        self.files[rel] = (dst, a, path)
        return dst

    def json(self, path, rel):
        return json.load(open(self.take(path, rel)))


# ---------------------------------------------------------------- cast header (the cast's packer output)
ARRAY = re.compile(r'alignas\(32\) static (?:const )?unsigned char (i\d+)_(pos|nrm|uv|gx)\[\] = \{(.*?)\};', re.S)
WEIGHTS = re.compile(r'static const Weight (i\d+)_weights\[\] = \{(.*?)\n\};', re.S)
WROW = re.compile(r'\{\{(\d+),(\d+),(\d+)\},(\d+),\{([^}]*)\}\}')
CHUNKS = re.compile(r'static Chunk chunks\[\] = \{(.*?)\n\};', re.S)
CROW = re.compile(r'\{(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(i\d+)_pos,(i\d+)_nrm,(i\d+)_uv,(i\d+)_gx,(i\d+)_weights\}')


def parse_header(path):
    text = open(path).read()
    arrays = {}
    for prefix, kind, body in ARRAY.findall(text):
        vals = [int(x) for x in body.replace('\n', ',').split(',') if x.strip()]
        if any(v < 0 or v > 255 for v in vals):
            raise Fail(f'{path}: {prefix}_{kind} is not a byte array')
        arrays[(prefix, kind)] = bytes(vals)
    weights = {}
    for prefix, body in WEIGHTS.findall(text):
        rows = []
        for b0, b1, b2, n, vals in WROW.findall(body):
            v = [float.fromhex(x.strip().rstrip('f')) for x in vals.split(',')]
            if len(v) != 3:
                raise Fail(f'{path}: {prefix} weight row has {len(v)} values')
            rows.append(((int(b0), int(b1), int(b2)), int(n), v))
        weights[prefix] = rows
    m = CHUNKS.search(text)
    if not m:
        raise Fail(f'{path}: no chunk table')
    chunks = []
    for row in CROW.findall(m.group(1)):
        info, npos, nnrm, npal, tris, sbytes = (int(x) for x in row[:6])
        prefix = row[6]
        if set(row[6:]) != {prefix}:
            raise Fail(f'{path}: chunk arrays of different infos')
        chunks.append(dict(source_info=info, position_count=npos, normal_count=nnrm, palette_count=npal,
                           triangles=tris, stream_bytes=sbytes, prefix=prefix))
    bm = re.search(r'static constexpr unsigned bone_count=(\d+);', text)
    if not bm:
        raise Fail(f'{path}: no bone_count')
    for c in chunks:
        p = c['prefix']
        for k in ('pos', 'nrm', 'uv', 'gx'):
            if (p, k) not in arrays:
                raise Fail(f'{path}: {p}_{k} missing')
        if p not in weights:
            raise Fail(f'{path}: {p}_weights missing')
        c['positions'], c['normals'] = arrays[(p, 'pos')], arrays[(p, 'nrm')]
        c['uv'], c['stream'], c['weights'] = arrays[(p, 'uv')], arrays[(p, 'gx')], weights[p]
        if len(c['stream']) != c['stream_bytes']:
            raise Fail(f'{path}: {p} stream {len(c["stream"])} B != {c["stream_bytes"]}')
    return chunks, int(bm.group(1))


def u16(b, o):
    return b[o] | (b[o + 1] << 8)


def f32le(b, o):
    return struct.unpack_from('<f', b, o)[0]


def preflight_chunk(c, bones):
    """tools mirror of coarse_actor_preflight.h preflight_chunk (the runtime proof runs again on target)"""
    np_, nn, npal = c['position_count'], c['normal_count'], c['palette_count']
    if not (0 < np_ <= 65535 and 0 < nn <= 65535 and 0 < npal <= 256 and 0 < bones <= 256):
        return 'Array'
    if len(c['positions']) < np_ * 8 or len(c['normals']) < nn * 8 or not c['uv'] or len(c['uv']) % 4 or len(c['weights']) != npal:
        return 'Array'
    for (bs, n, v) in c['weights']:
        if not 1 <= n <= 3:
            return 'Weights'
        s = 0.0
        for k in range(n):
            if bs[k] >= bones or not (0.0 <= v[k] <= 1.0):
                return 'Weights'
            s += v[k]
        if abs(struct.unpack('<f', struct.pack('<f', s))[0] - 1.0) > 0.0001:
            return 'Weights'
    if any(u16(c['positions'], i * 8 + 6) >= npal for i in range(np_)):
        return 'Palette'
    if any(u16(c['normals'], i * 8 + 6) >= npal for i in range(nn)):
        return 'Palette'
    s = c['stream']
    if len(s) < 32 or len(s) > 1 << 20:
        return 'Header'
    if s[0] != 0xfe or s[1] != 3 or (s[2] & 0x83) or s[3] or u16(s, 12) or u16(s, 14):
        return 'Header'
    if f32le(s, 28) < 0:
        return 'Header'
    nm, rec, idx = u16(s, 4), u16(s, 8) * 4, u16(s, 10) * 4
    if not nm or len(s) < 32 + nm * 8 or rec < 32 + nm * 8 or idx < rec or idx > len(s):
        return 'Table'
    records = indices = triangles = 0
    for m in range(nm):
        t = 32 + m * 8
        counts = struct.unpack_from('<I', s, t)[0]
        nv, ni, nt = counts & 255, (counts >> 8) & 4095, counts >> 20
        if not nv or nv > 128 or not ni or ni > 1024 or not nt or u16(s, t + 4) != records or u16(s, t + 6) != indices:
            return 'Table'
        if (records + nv) * 6 > idx - rec or idx + indices + ni > len(s):
            return 'Table'
        for v in range(nv):
            r = rec + (records + v) * 6
            if u16(s, r) >= np_ or u16(s, r + 2) >= nn or u16(s, r + 4) * 4 >= len(c['uv']):
                return 'Record'
        ln = tris = 0
        for j in range(ni):
            index = s[idx + indices + j]
            ln += 1
            if (index & 127) >= nv or ln > 64:
                return 'Strip'
            if index & 128:
                if ln < 3:
                    return 'Strip'
                tris += ln - 2; ln = 0
        if ln or tris != nt:
            return 'Count'
        records += nv; indices += ni; triangles += nt
    if triangles != c['triangles']:
        return 'Count'
    return None


def skin_stream_bytes(weights):
    """coarse_skin.h coarse_group_build's stream size (16 B per group header, 24 B per entry)"""
    if len(weights) > 256:
        raise Fail('more than 256 palette entries')
    done, groups, entries = [False] * len(weights), 0, 0
    for j, (bj, nj, vj) in enumerate(weights):
        if done[j]:
            continue
        groups += 1
        for i in range(j, len(weights)):
            bi, ni, vi = weights[i]
            if done[i] or ni != nj or bi[:nj] != bj[:nj]:
                continue
            if nj == 1 and vi[0] != 1.0:
                raise Fail('a one-bone palette entry with weight != 1 (coarse_group_build copies it)')
            done[i] = True; entries += 1
    return groups * 16 + entries * 24


# ---------------------------------------------------------------- original archives (identity facts)
def archive_facts(tree):
    sys.path[:0] = [os.path.join(tree, 'tools'), os.path.join(tree, 'port/dreamcast/tools')]
    from motion import archive  # noqa: E402  (repo tools)
    from convert_tpl import parse_tpl  # noqa: E402
    import le_mirror  # noqa: E402
    return archive, parse_tpl, le_mirror


def bin_facts(arc, le_mirror, name, no):
    """actor-material-r1 inspect_archives.py model() + actor-lifetime-r2 normalized digest, verbatim rules"""
    ent = arc.entry(no - 4)
    if ent.tag != 'BIN':
        raise Fail(f'{name} entry {no} is {ent.tag}, not BIN')
    b = ent.data
    flags = word(b, 32); nv = half(b, 56); nn = half(b, 58); nw = b[24]; ext = half(b, 42)
    if ext > 255:
        raise Fail(f'{name}/{no}: weight_ext_num {ext} (extended palettes unsupported)')
    pos = swap16(b[word(b, 48):word(b, 48) + nv * 8])
    nrm = b[word(b, 52):word(b, 52) + nn * (4 if flags & 0x20000000 else 8)]
    if not flags & 0x20000000:
        nrm = swap16(nrm)
    # The stored normal length (GX's fixed normal fraction: s8 6 bits, s16 14 bits), for --source-normal-length.
    if flags & 0x20000000:
        lens = [((nrm[i] ^ 128) - 128) ** 2 + ((nrm[i + 1] ^ 128) - 128) ** 2 + ((nrm[i + 2] ^ 128) - 128) ** 2
                for i in range(0, nn * 4, 4)]
        lens = [l ** 0.5 / 64.0 for l in lens]
    else:
        lens = [sum(v * v for v in struct.unpack_from('<3h', nrm, i)) ** 0.5 / 16384.0 for i in range(0, nn * 8, 8)]
    normal_length = [sum(lens) / len(lens), min(lens), max(lens)] if lens else None
    w = b[word(b, 20):word(b, 20) + nw * 8]
    parts = []; at = word(b, 28); maxuv = -1
    for _ in range(half(b, 26)):
        h = b[at:at + 32]; n = word(h, 24); stream = b[at + 32:at + 32 + n]; x = 0
        stride = 8 if flags & 0x80000000 else 6
        while x < n:
            op = stream[x]; x += 1
            if op == 0:
                continue
            if op not in (0x80, 0x90, 0x98):
                raise Fail(f'{name}/{no}: display list opcode {op:#x}')
            count = half(stream, x); x += 2
            for v in range(count):
                maxuv = max(maxuv, half(stream, x + v * stride + stride - 2))
            x += count * stride
        parts.append([h[11:24].hex(), n, word(h, 28), *digest(stream)[1:]])
        at += 32 + n
    uv = swap16(b[word(b, 16):word(b, 16) + (maxuv + 1) * 4])
    nb = bytearray(b); s = le_mirror.Swapper(nb, f'{name}/{no}')
    with s.bounded(0, len(nb)):
        le_mirror.fmt_bin(s, 0, len(nb), f'{name}/{no}')
    return {'sha256': sha(b), 'header': [flags, b[40], b[25], nv, nn, word(b, 36), nw, ext, half(b, 26), word(b, 60)],
            'positions': digest(pos), 'normals': digest(nrm), 'weights': digest(w), 'uv': digest(uv), 'parts': parts,
            'normalized': digest(bytes(nb)), 'normalized_sha256': sha(bytes(nb)), 'positions_le_first64': pos[:64],
            'normal_length': normal_length}


def tpl_facts(arc, parse_tpl, name, no):
    ent = arc.entry(no - 4)
    if ent.tag != 'TPL':
        raise Fail(f'{name} entry {no} is {ent.tag}, not TPL')
    b = ent.data; desc = word(b, 8); rows = []
    for k, im in enumerate(parse_tpl(b)):
        th = word(b, desc + 8 * k); pal = im.palette_data or b''
        key = digest(struct.pack('<5I', im.width, im.height, im.format,
                                 im.palette_format if im.palette_format is not None else 0xffffffff, len(pal)) + im.data + pal)[1:]
        rows.append({'key': key, 'whf': [im.width, im.height, im.format],
                     'sampler': [word(b, th + 12), word(b, th + 16), word(b, th + 20), word(b, th + 24), word(b, th + 28),
                                 b[th + 32], b[th + 33], b[th + 34]],
                     'palette': None if not pal else [im.palette_format, *digest(pal)]})
    return {'sha256': sha(b), 'textures': rows}


def material_needs(model, texture_count):
    """coarse_actor_material.inc info(): the Need bits a section's part materials require (or a Fail reason)"""
    need = 0
    for material, *_ in model['parts']:
        mat = bytes.fromhex(material); f = mat[0]
        if mat[1] >= texture_count:
            return None, 'colour texture index outside the TPL'
        if f & 4:
            if mat[3] >= texture_count:
                return None, 'mask texture index outside the TPL'
            need |= MASK | SOURCE_PASS
        if f & 1:
            if mat[2] >= texture_count:
                return None, 'bump texture index outside the TPL'
            need |= BUMP
        if f & 0x13:
            need |= SPECULAR
        if f & ~7:
            need |= UNKNOWN   # the runtime certificate declines (Error::Material): a contract, not a data fault
    return need, None


def need_names(bits):
    return [n for b, n in sorted(NEED_NAMES.items()) if bits & b]


# ---------------------------------------------------------------- base tables (capacities, self-check)
def base_records(tree):
    text = open(os.path.join(tree, 'port/dreamcast/game/actor_material_records.inc')).read()
    roles = re.search(r'static const Role roles\[\] = \{(.*?)\n\};', text, re.S).group(1)
    blobs = re.search(r'static const SourceBlob source_blobs\[\] = \{(.*?)\n\};', text, re.S).group(1)
    nroles = len(re.findall(r'^\{', roles, re.M)); nblobs = len(re.findall(r'^\{', blobs, re.M))
    tex = {}
    for name, body in re.findall(r'static const Texture t_(\w+)\[\] = \{(.*?)\n\};', text, re.S):
        tex[name] = [[int(x) for x in re.findall(r'(\d+)u', row)] for row in body.strip().splitlines()]
    models = {}
    for name, body in re.findall(r'static const Model m_(\w+) = \{(.*?)\};', text):
        models[name] = [int(x) for x in re.findall(r'(\d+)u', body)]
    blobrows = {m: [int(x) for x in re.findall(r'(\d+)u', rest)] for m, rest in re.findall(r'^\{&m_(\w+),(.*)\},$', blobs, re.M)}
    return nroles, nblobs, tex, models, blobrows


def self_check(tree, archive, parse_tpl, le_mirror, audit, inputs, cast):
    """Re-derive the committed em12 appearance-0 rows with this tool's extraction: identical or fail."""
    _, _, tex, models, blobrows = base_records(tree)
    a = audit['em12']
    path = a['source']
    if sha(open(path, 'rb').read()) != a['sha256']:
        raise Fail(f'{path}: sha256 differs from archive-audit.json')
    arc = archive.Archive(path)
    for no in (472, 474, 448, 453):
        f = bin_facts(arc, le_mirror, 'em12', no)
        want = models[f'em12_{no}']
        got = f['header'] + f['positions'] + f['normals'] + f['weights'] + f['uv']
        if want != got:
            raise Fail(f'self-check: em12/{no} model row differs from actor_material_records.inc')
        if blobrows[f'em12_{no}'][-3:] != f['normalized'] or blobrows[f'em12_{no}'][:2] != [2, no]:
            raise Fail(f'self-check: em12/{no} normalized digest differs from source_blobs')
    t = tpl_facts(arc, parse_tpl, 'em12', 473)
    got = [x['key'] + x['whf'] + x['sampler'] + [(x['palette'] or [0xffffffff])[0]] + (x['palette'] or [0, 0, 0, 0])[1:] for x in t['textures']]
    if got != tex['em12_473']:
        raise Fail('self-check: em12/473 texture rows differ from actor_material_records.inc')
    return 'em12 BIN 472/474/448/453 + TPL 473 re-derived identically (model rows, normalized digests, texture rows)'


# ---------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    tree = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
    if '--tree' in args:
        i = args.index('--tree'); tree = os.path.abspath(args[i + 1]); del args[i:i + 2]
    package_room = None
    if '--package-room' in args:
        i = args.index('--package-room'); package_room = int(args[i + 1], 16); del args[i:i + 2]
        if not 0x100 <= package_room <= 0x7ff:
            sys.exit('model_registry: --package-room is the hex room number, e.g. 103')
    source_normal_length = '--source-normal-length' in args
    if source_normal_length:
        args.remove('--source-normal-length')
    if len(args) != 2:
        sys.exit(__doc__)
    spec_path, out = os.path.abspath(args[0]), os.path.abspath(args[1])
    if os.path.exists(out):
        sys.exit(f'model_registry: {out} exists (a bundle is never rewritten in place: new selection, new dir)')
    tmp = out + '.tmp-%d' % os.getpid()
    os.makedirs(tmp)
    try:
        report = generate(spec_path, tmp, tree, package_room, source_normal_length)
    except Fail as e:
        shutil.rmtree(tmp)
        sys.exit(f'model_registry: FAIL {e}')
    os.rename(tmp, out)
    print(json.dumps(report, indent=1))


def source_length_normals(name, c, src):
    """--source-normal-length: the chunk's s16 / 14-bit normals rescaled to the source BIN's stored normal length
    (direction kept, palette word untouched). Returns (normals, manifest record)."""
    if not src:
        raise Fail(f'{name} chunk {c["source_info"]}: the source BIN has no normals (no source length to keep)')
    mean, lo, hi = src
    if hi - lo > 0.05:
        raise Fail(f'{name} chunk {c["source_info"]}: source normal lengths {lo:.4f}..{hi:.4f} are not uniform '
                   '(one stored length per BIN is the only supported source mode)')
    if not 0.0 < mean < 1.9999:
        raise Fail(f'{name} chunk {c["source_info"]}: source normal length {mean:.4f} does not fit s16 / 14 bits')
    out = bytearray(c['normals']); cast = []
    for i in range(c['normal_count']):
        x, y, z = struct.unpack_from('<3h', out, i * 8)
        l = (x * x + y * y + z * z) ** 0.5
        if not l:
            raise Fail(f'{name} chunk {c["source_info"]}: cast normal {i} has zero length')
        cast.append(l / 16384.0)
        k = mean * 16384.0 / l
        v = [int(round(t * k)) for t in (x, y, z)]
        if any(abs(t) > 32767 for t in v):
            raise Fail(f'{name} chunk {c["source_info"]}: rescaled normal {i} overflows s16')
        struct.pack_into('<3h', out, i * 8, *v)
    return bytes(out), dict(source_mean=round(mean, 6), source_min=round(lo, 6), source_max=round(hi, 6),
                            cast_mean_before=round(sum(cast) / len(cast), 6), mode='source BIN mean length')


def generate(spec_path, out, tree, package_room=None, source_normal_length=False):
    inputs = Inputs(out)
    spec = inputs.json(spec_path, 'spec.json')
    cast = spec['cast_dir']; level = spec['level']; overlay_rel = spec['revision_overlay'].strip('/')
    archive, parse_tpl, le_mirror = archive_facts(tree)
    audit = inputs.json(os.path.join(cast, spec['archive_audit']), 'cast/' + spec['archive_audit'])
    selfcheck = self_check(tree, archive, parse_tpl, le_mirror, audit, inputs, cast)
    catalog = {e['name']: e for e in inputs.json(os.path.join(cast, overlay_rel, 'integration-bundle/catalog.json'),
                                                   f'cast/{overlay_rel}/integration-bundle/catalog.json')}
    base_revisions = inputs.json(os.path.join(cast, 'source/candidate-revisions.json'), 'cast/source/candidate-revisions.json')
    nroles0, nblobs0, _, _, _ = base_records(tree)
    arcs, bins, tpls = {}, {}, {}
    runtime, contracts, seen_identity = [], [], {}
    textures = []  # (crc, fnv, w, h, package path)
    for d in spec['descriptors']:
        name = d['name']
        if name not in catalog:
            raise Fail(f'{name}: not in the {overlay_rel} catalog (no implicit fallback to an older revision)')
        e = catalog[name]; rev = e['revision']
        rm = inputs.json(os.path.join(cast, name, rev, 'revision-manifest.json'), f'cast/{name}/{rev}/revision-manifest.json')
        L, RL = e['levels'][level], rm['levels'][level]
        if rm['revision'] != rev or RL['header_sha256'] != L['header_sha256'] or RL['runtime_header'] != L['runtime_header']:
            raise Fail(f'{name}: catalog and revision manifest disagree (mid-publish?)')
        if rm['texture_packages'] != e['texture_packages']:
            raise Fail(f'{name}: catalog and revision manifest texture packages disagree')
        base = inputs.json(os.path.join(cast, name, 'manifest.json'), f'cast/{name}/manifest.json')
        base_rev = base_revisions.get(name, {}).get('revision', base['revision'])
        if e.get('previous_revision') not in (None, base_rev):
            raise Fail(f'{name}: overlay {rev} follows {e.get("previous_revision")}, the base selection is {base_rev}')
        hdr = inputs.take(os.path.join(cast, L['runtime_header']), 'cast/' + L['runtime_header'])
        if sha(open(hdr, 'rb').read()) != L['header_sha256']:
            raise Fail(f'{name}: {L["runtime_header"]} sha256 differs from the catalog')
        binds = inputs.json(os.path.join(cast, name, 'source-bindings.json'), f'cast/{name}/source-bindings.json')
        src = inputs.json(os.path.join(cast, name, 'source.json'), f'cast/{name}/source.json')
        # The spec's model id / source types are the cast's own, not a label: a descriptor never claims another
        # appearance's selection (the cow type 0 vs type 1 TPLs share one BIN).
        if int(d['model_id'], 16) != src.get('source_model_id') or sorted(d['source_types'] or []) != sorted(src.get('types') or []):
            raise Fail(f'{name}: spec model_id/source_types {d["model_id"]}/{d["source_types"]} differ from source.json '
                       f'{src.get("source_model_id")}/{src.get("types")}')
        arcname = d['archive']
        if arcname not in audit or src.get('source_archive_sha256', audit[arcname]['sha256']) != audit[arcname]['sha256']:
            raise Fail(f'{name}: archive {arcname} not in archive-audit.json or source.json names another archive')
        if arcname not in arcs:
            p = audit[arcname]['source']
            if sha(open(p, 'rb').read()) != audit[arcname]['sha256']:
                raise Fail(f'{p}: sha256 differs from archive-audit.json')
            arcs[arcname] = archive.Archive(p)
        arc = arcs[arcname]
        # ---- skeleton (one per model; every section's bone table agrees)
        pb = binds[0]['part_bindings']
        bones = len(pb)
        if any(p['id'] != i or p['attach'] != i for i, p in enumerate(pb)):
            raise Fail(f'{name}: attach map is not the identity (a local attachment index needs its own map)')
        parents = [p['parent'] for p in pb]
        if any([p['parent'] for p in b['part_bindings']] != parents for b in binds):
            raise Fail(f'{name}: sections disagree on the hierarchy')
        if parents[0] != -1 or any(not (-1 <= q < i) for i, q in enumerate(parents)):
            raise Fail(f'{name}: parents are not a forest in index order')
        sbones = src.get('bones') or []
        if len(sbones) != bones or any(b.get('id') != i or 'rest' not in b or b.get('parent') != parents[i] for i, b in enumerate(sbones)):
            raise Fail(f'{name}: source.json skeleton differs from source-bindings ({len(sbones)} vs {bones})')
        bind = []
        for b in sbones:
            m = b['rest']; R = [row[:3] for row in m[:3]]; t = [m[0][3], m[1][3], m[2][3]]
            det = (R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1]) - R[0][1] * (R[1][0] * R[2][2] - R[1][2] * R[2][0])
                   + R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0]))
            if abs(det) < 1e-6:
                raise Fail(f'{name}: singular rest matrix')
            inv = [[(R[(j + 1) % 3][(i + 1) % 3] * R[(j + 2) % 3][(i + 2) % 3] - R[(j + 1) % 3][(i + 2) % 3] * R[(j + 2) % 3][(i + 1) % 3]) / det
                    for j in range(3)] for i in range(3)]
            ti = [-sum(inv[r][k] * t[k] for k in range(3)) for r in range(3)]
            bind.append([inv[0][0], inv[0][1], inv[0][2], ti[0], inv[1][0], inv[1][1], inv[1][2], ti[1],
                         inv[2][0], inv[2][1], inv[2][2], ti[2]])
        # ---- sections against the archive
        sections, need, contract = [], 0, []
        for i, b in enumerate(binds):
            key = (arcname, b['bin'])
            if key not in bins:
                bins[key] = bin_facts(arc, le_mirror, arcname, b['bin'])
            f = bins[key]
            h = f['header']
            if (h[3], h[4], h[6], h[2], h[1]) != (b['positions'], b['normals'], b['palettes'], b['parts'], b['shift']) or \
                    int(b['flags'], 16) != h[0]:
                raise Fail(f'{name} section {i}: archive BIN {b["bin"]} differs from source-bindings (counts/flags)')
            if b['parts'] != bones:
                raise Fail(f'{name} section {i}: BIN has {b["parts"]} parts, the skeleton {bones}')
            # the runtime signature (coarse_ganado_cast.cpp fingerprint): FNV-1a of the first 64 bytes of the LE positions
            if '%08x' % digest(f['positions_le_first64'])[2] != b['source_vertex_fnv64_le']:
                raise Fail(f'{name} section {i}: vertex signature {b["source_vertex_fnv64_le"]} does not match BIN {b["bin"]}')
            tkey = (arcname, b['tpl'])
            if tkey not in tpls:
                tpls[tkey] = tpl_facts(arc, parse_tpl, arcname, b['tpl'])
            t = tpls[tkey]
            for x in t['textures']:
                if x['sampler'] != [1, 1, 1, 1, 0, 0, 0, 0]:
                    raise Fail(f'{name}: TPL {b["tpl"]} has a non-base / mipmapped sampler {x["sampler"]}')
            n, why = material_needs(f, len(t['textures']))
            if why:
                raise Fail(f'{name} section {i}: {why}')
            need |= n
            sections.append(dict(role=i, kind=b['role'], bin=b['bin'], tpl=b['tpl'], bin_sha256=f['sha256'],
                                 normalized_sha256=f['normalized_sha256'], tpl_sha256=t['sha256'], needs=need_names(n)))
        identity = (arcname, tuple(s['bin'] for s in sections), tuple(s['tpl'] for s in sections))
        if identity in seen_identity:
            raise Fail(f'{name}: source identity {identity} is ambiguous with {seen_identity[identity]}')
        seen_identity[identity] = name
        # ---- chunks
        chunks, hbones = parse_header(hdr)
        if hbones != bones:
            raise Fail(f'{name}: header bone_count {hbones} != skeleton {bones}')
        if [c['source_info'] for c in chunks] != list(range(len(sections))):
            raise Fail(f'{name}: header chunks {[c["source_info"] for c in chunks]} are not one per source section in order')
        if len(chunks) > ACTOR_CHUNKS:
            raise Fail(f'{name}: {len(chunks)} chunks > {ACTOR_CHUNKS}')
        skin = 0
        for c in chunks:
            err = preflight_chunk(c, bones)
            if err:
                raise Fail(f'{name} chunk {c["source_info"]}: preflight {err}')
            if source_normal_length:
                c['normals'], sections[c['source_info']]['normal_length'] = source_length_normals(
                    name, c, bins[(arcname, sections[c['source_info']]['bin'])]['normal_length'])
            c['skin_bytes'] = skin_stream_bytes(c['weights']); skin += c['skin_bytes']
            tp = e['texture_packages'].get(str(c['source_info']))
            if not tp:
                raise Fail(f'{name} chunk {c["source_info"]}: no texture package bound to this source_info')
            if tp['format'] not in ('RGB565', 'ARGB4444', 'ARGB1555'):
                raise Fail(f'{name}: texture format {tp["format"]} unsupported (paletted or unknown)')
            pkg = inputs.take(tp['package'], 'cast/' + tp['package'].split('/cast-20260925/', 1)[-1])
            if sha(open(pkg, 'rb').read()) != tp['package_sha256']:
                raise Fail(f'{name}: texture package {tp["key"]} sha256 differs from the manifest')
            crc, fnv = (int(x, 16) for x in tp['key'].split('-'))
            w, h_ = tp['rectangle'][2], tp['rectangle'][3]
            tk = (crc, fnv, w, h_)
            if tk not in [x[:4] for x in textures]:
                textures.append(tk + (pkg, tp['package_sha256'], tp['format']))
            c['texture'] = [x[:4] for x in textures].index(tk)
        materials = sorted({c['texture'] for c in chunks})
        if len(materials) > ACTOR_MATERIALS:
            raise Fail(f'{name}: {len(materials)} materials > {ACTOR_MATERIALS}')
        entry = dict(name=name, revision=rev, base_revision=base_rev, level=level, archive=arcname,
                     archive_sha256=audit[arcname]['sha256'], model_id=int(d['model_id'], 16), source_types=d['source_types'],
                     bones=bones, parents=parents, bind=bind, sections=sections, chunks=chunks, skin_bytes=skin,
                     header=L['runtime_header'], header_sha256=L['header_sha256'], rooms=e.get('rooms', []),
                     needs=need_names(need), category=e.get('category'), status=e.get('status'), spec=d)
        missing = need & ~FLAT_IMPLEMENTED
        if missing:
            entry['contract'] = (f'source materials need {", ".join(need_names(missing))}; the flat owner path implements '
                                 f'{", ".join(need_names(FLAT_IMPLEMENTED))} only: needs a renderer material contract '
                                 '(and a user look decision for any approximation)')
            contracts.append(entry)
        else:
            runtime.append(entry)
    # ---- capacities
    blobs = sorted({(s_arc, s_bin) for r in runtime for (s_arc, s_bin) in [(r['archive'], s['bin']) for s in r['sections']]})
    nrows = sum(len(r['sections']) for r in runtime)
    if nblobs0 + len(blobs) > SOURCE_BLOBS:
        raise Fail(f'source blobs {nblobs0}+{len(blobs)} > {SOURCE_BLOBS} (actor_lifetime.inc templates mask)')
    if nroles0 + nrows > MATERIAL_ROWS:
        raise Fail(f'role rows {nroles0}+{nrows} > {MATERIAL_ROWS} (actor_lifetime.inc Info::roles mask)')
    if not runtime:
        raise Fail('no descriptor is admissible for the flat owner path')
    for i, r in enumerate(runtime):
        r['appearance'] = APPEARANCE0 + i
    used_tex = sorted({c['texture'] for r in runtime for c in r['chunks']})
    write_outputs(out, spec, runtime, contracts, textures, used_tex, bins, tpls, blobs, nroles0, nblobs0)
    package = None
    if package_room is not None:
        # spec "room_packages" (optional): {"<hex room>": {"descriptors": [names], "evidence": "..."}} names the runtime
        # descriptors the room's own source spawns (its enemy list / script, by model type); each must be a runtime
        # descriptor whose cast lists the room. Appearances are renumbered from APPEARANCE0 in runtime order (they are
        # scoped to one room generation). Without an entry for the room every runtime descriptor is packaged (as before).
        sel = spec.get('room_packages', {}).get('%x' % package_room)
        if sel is None:
            pr, pk_tex, pk_blobs = runtime, used_tex, blobs
        else:
            names = sel['descriptors']; known = {r['name'] for r in runtime}; rname = 'r%x%02x' % (package_room >> 8, package_room & 255)
            for n in names:
                if n not in known:
                    raise Fail(f'room package {rname}: {n} is not a runtime descriptor (contract or unknown)')
            pr = [dict(r, appearance=APPEARANCE0 + i) for i, r in enumerate(x for x in runtime if x['name'] in names)]
            for r in pr:
                if rname not in r['rooms']:
                    raise Fail(f'room package {rname}: the cast of {r["name"]} does not list {rname} ({r["rooms"]})')
            if len(pr) != len(set(names)):
                raise Fail(f'room package {rname}: duplicate names in {names}')
            pk_tex = sorted({c['texture'] for r in pr for c in r['chunks']})
            pk_blobs = sorted({(r['archive'], s['bin']) for r in pr for s in r['sections']})
        package = write_package(out, package_room, spec, pr, textures, pk_tex, bins, tpls, pk_blobs)
        package['descriptors'] = [dict(name=r['name'], appearance='0x%x' % r['appearance'], archive=r['archive'],
                                       source_types=r['source_types'], sections=[dict(bin=s['bin'], tpl=s['tpl']) for s in r['sections']])
                                  for r in pr]
        if sel is not None:
            package['selection_evidence'] = sel.get('evidence')
    manifest = dict(registry=spec['registry'], generator=os.path.relpath(__file__, tree), generator_sha256=sha(open(__file__, 'rb').read()),
                    tree_head=os.popen(f'git -C "{tree}" rev-parse HEAD').read().strip(), cast_dir=cast,
                    revision_overlay=overlay_rel, level=level, lighting=spec.get('lighting'), self_check=selfcheck,
                    capacities=dict(role_rows=f'{nroles0}+{nrows}/{MATERIAL_ROWS}', source_blobs=f'{nblobs0}+{len(blobs)}/{SOURCE_BLOBS}'),
                    inputs={rel: dict(sha256=v[1], source=v[2]) for rel, v in sorted(inputs.files.items())},
                    **({'normals': 'source BIN normal length (--source-normal-length; per section in descriptors[].sections)'}
                       if source_normal_length else {}),
                    descriptors=[summary(r, 'runtime') for r in runtime] + [summary(c, 'contract') for c in contracts],
                    textures=[dict(key=f'{t[0]:08x}-{t[1]:08x}', width=t[2], height=t[3], format=t[6], package_sha256=t[5],
                                   runtime=i in used_tex) for i, t in enumerate(textures)])
    if package:
        manifest['room_package'] = package
    json.dump(manifest, open(os.path.join(out, 'registry-manifest.json'), 'w'), indent=1)
    sums = []
    for root, _, files in os.walk(out):
        for f in sorted(files):
            p = os.path.join(root, f)
            sums.append(f'{sha(open(p, "rb").read())}  {os.path.relpath(p, out)}')
    open(os.path.join(out, 'SHA256SUMS'), 'w').write('\n'.join(sorted(sums, key=lambda s: s[66:])) + '\n')
    return dict(runtime=[(r['name'], hex(r['appearance']), r['bones'], [c['triangles'] for c in r['chunks']]) for r in runtime],
                contracts=[(c['name'], c['contract']) for c in contracts], textures=len(used_tex), self_check=selfcheck,
                package={k: package[k] for k in ('disc_path', 'bytes', 'arena', 'geometry')} if package else None)


def summary(r, status):
    s = dict(name=r['name'], status=status, revision=r['revision'], base_revision=r['base_revision'], level=r['level'],
             archive=r['archive'], archive_sha256=r['archive_sha256'], model_id=hex(r['model_id']), source_types=r['source_types'],
             bones=r['bones'], sections=r['sections'], header=r['header'], header_sha256=r['header_sha256'], rooms=r['rooms'],
             source_needs=r['needs'], cast_status=r['status'],
             chunks=[dict(source_info=c['source_info'], triangles=c['triangles'], palettes=c['palette_count'],
                          positions=c['position_count'], normals=c['normal_count'], stream_bytes=c['stream_bytes'],
                          skin_bytes=c['skin_bytes'], texture=c['texture']) for c in r['chunks']])
    if status == 'runtime':
        s['appearance'] = hex(r['appearance'])
    else:
        s['contract'] = r['contract']
    return s


def cbytes(b):
    rows = [','.join(str(x) for x in b[i:i + 24]) for i in range(0, len(b), 24)]
    return ',\n'.join(rows)


def cfloat(v):
    return float(v).hex() + 'f' if v else '0.0f'


def write_outputs(out, spec, runtime, contracts, textures, used_tex, bins, tpls, blobs, nroles0, nblobs0):
    L = ['// Private generated asset (tools/d367/model_registry.py, registry %s). Do not commit.' % spec['registry'],
         '#pragma once', 'namespace nmr {',
         'struct Weight { unsigned char bone[3], count; float value[3]; };',
         'struct Chunk { unsigned source_info, position_count, normal_count, palette_count, triangles, stream_bytes; '
         'const unsigned char *positions, *normals, *uv; unsigned char *stream; const Weight *weights; unsigned uv_bytes, texture, skin_bytes; };',
         'struct Texture { unsigned crc, fnv, width, height; };',
         'struct Descriptor { const char* name; unsigned appearance, model_id, bones, sections, first_chunk, skin_bytes; '
         'const signed char* parents; const float (*bind)[12]; };']
    tex_index = {t: i for i, t in enumerate(used_tex)}
    chunk_rows, desc_rows, first = [], [], 0
    for di, r in enumerate(runtime):
        ns = f'd{di}'
        L.append(f'namespace {ns} {{  // {r["name"]} {r["revision"]} {r["level"]}')
        for c in r['chunks']:
            p = f'i{c["source_info"]}'
            L.append(f'alignas(32) static const unsigned char {p}_pos[] = {{\n{cbytes(c["positions"])}\n}};')
            L.append(f'alignas(32) static const unsigned char {p}_nrm[] = {{\n{cbytes(c["normals"])}\n}};')
            L.append(f'alignas(32) static const unsigned char {p}_uv[] = {{\n{cbytes(c["uv"])}\n}};')
            L.append(f'alignas(32) static unsigned char {p}_gx[] = {{\n{cbytes(c["stream"])}\n}};')
            L.append(f'static const Weight {p}_weights[] = {{')
            for bs, n, v in c['weights']:
                L.append('{{%d,%d,%d},%d,{%s}},' % (bs[0], bs[1], bs[2], n, ','.join(cfloat(x) for x in v)))
            L.append('};')
            chunk_rows.append('{%d,%d,%d,%d,%d,%d,%s::%s_pos,%s::%s_nrm,%s::%s_uv,%s::%s_gx,%s::%s_weights,%d,%d,%d},' % (
                c['source_info'], c['position_count'], c['normal_count'], c['palette_count'], c['triangles'], c['stream_bytes'],
                ns, p, ns, p, ns, p, ns, p, ns, p, len(c['uv']), tex_index[c['texture']], c['skin_bytes']))
        L.append('static const signed char parents[] = {%s};' % ','.join(str(x) for x in r['parents']))
        L.append('static const float bind[][12] = {')
        for row in r['bind']:
            L.append('{%s},' % ','.join(cfloat(x) for x in row))
        L.append('};')
        L.append('}')
        desc_rows.append('{"%s",%du,%du,%du,%du,%du,%du,%s::parents,%s::bind},' % (
            r['name'], r['appearance'], r['model_id'], r['bones'], len(r['sections']), first, r['skin_bytes'], ns, ns))
        first += len(r['chunks'])
    L.append('static Chunk chunks[] = {'); L += chunk_rows; L.append('};')
    L.append('static const Texture textures[] = {')
    for t in used_tex:
        crc, fnv, w, h = textures[t][:4]
        L.append('{0x%08xu,0x%08xu,%du,%du},' % (crc, fnv, w, h))
    L.append('};')
    L.append('static const Descriptor descriptors[] = {'); L += desc_rows; L.append('};')
    L.append(f'constexpr unsigned descriptor_count={len(runtime)}, chunk_count={first}, texture_count={len(used_tex)}, '
             f'skin_stream_bytes={sum(r["skin_bytes"] for r in runtime)}, max_bones={max(r["bones"] for r in runtime)}, '
             f'appearance_first=0x{APPEARANCE0:x}u;')
    L.append(f'constexpr unsigned base_role_rows={nroles0}, base_source_blobs={nblobs0};')
    L.append('}')
    open(os.path.join(out, 'native_model_registry.h'), 'w').write('\n'.join(L) + '\n')
    # ---- source identity rows (coarse_actor_material.inc types; names prefixed g_)
    F = ['// Private generated source identity rows (tools/d367/model_registry.py, registry %s). Do not commit.' % spec['registry']]
    done_t, done_m = set(), set()
    for r in runtime:
        for s in r['sections']:
            tk = (r['archive'], s['tpl'])
            if tk not in done_t:
                done_t.add(tk)
                F.append('static const Texture t_g_%s_%d[] = {' % tk)
                for x in tpls[tk]['textures']:
                    pal = x['palette'] or [0xffffffff, 0, 0, 0]
                    F.append('{' + ','.join(str(v) + 'u' for v in x['key'] + x['whf']) + ',{' + ','.join(str(v) + 'u' for v in x['sampler']) +
                             '},' + str(pal[0]) + 'u,{' + ','.join(str(v) + 'u' for v in pal[1:]) + '}},')
                F.append('};')
            mk = (r['archive'], s['bin'])
            if mk not in done_m:
                done_m.add(mk); m = bins[mk]
                F.append('static const Part p_g_%s_%d[] = {' % mk)
                for material, size, poly, crc, fnv in m['parts']:
                    F.append('{{' + ','.join(str(v) + 'u' for v in bytes.fromhex(material)) + '},' + ','.join(str(v) + 'u' for v in (size, poly, crc, fnv)) + '},')
                F.append('};')
                F.append('static const Model m_g_%s_%d = {' % mk + ','.join(
                    '{' + ','.join(str(v) + 'u' for v in m[k]) + '}' for k in ('header', 'positions', 'normals', 'weights', 'uv')) +
                    ',p_g_%s_%d};' % mk)
    open(os.path.join(out, 'native_model_registry_facts.inc'), 'w').write('\n'.join(F) + '\n')
    R = ['// Private generated role rows: appearance, role (source info order), source BIN, source TPL.']
    for r in runtime:
        for s in r['sections']:
            R.append('{%du,%du,%du,%du,&m_g_%s_%d,t_g_%s_%d,%du},' % (r['appearance'], s['role'], s['bin'], s['tpl'], r['archive'], s['bin'],
                                                                 r['archive'], s['tpl'], len(tpls[(r['archive'], s['tpl'])]['textures'])))
    open(os.path.join(out, 'native_model_registry_roles.inc'), 'w').write('\n'.join(R) + '\n')
    B = ['// Private generated source blobs (family 2: enemy archives): normalized BIN digests.']
    for a, b in blobs:
        B.append('{&m_g_%s_%d,2u,%du,{%s}},' % (a, b, b, ','.join(str(v) + 'u' for v in bins[(a, b)]['normalized'])))
    open(os.path.join(out, 'native_model_registry_blobs.inc'), 'w').write('\n'.join(B) + '\n')
    os.makedirs(os.path.join(out, 'tex'))
    for t in used_tex:
        crc, fnv, w, h, pkg = textures[t][:5]
        shutil.copy2(pkg, os.path.join(out, 'tex', f'{crc:08x}-{fnv:08x}.re4tex'))


# ---------------------------------------------------------------- room package (NATIVE_MODEL_REGISTRY_PACK=1)
# package/r<room>/registry.re4nmr: the same runtime descriptors, chunks, textures and source identity rows as the
# compiled outputs above, as one versioned little-endian file with no pointers (coarse_actor_registry_pack.inc
# validates every field below before it publishes anything). Identical chunk geometry (positions, normals, UV, stream,
# weights, counts and bone count, compared as exact bytes) is stored once and referenced by every descriptor section
# that uses it; textures and source identity rows stay per descriptor.
PACK_MAGIC = b'RE4NMR1\0'
PACK_VERSION = 1
PACK_HEADER = 64
PACK_SECTIONS = ('desc', 'ref', 'geom', 'blob', 'tex', 'parents', 'bind', 'fmodel', 'fpart', 'ftex', 'role', 'sblob')
PACK_RECORD = dict(desc=48, ref=16, geom=64, blob=1, tex=16, parents=1, bind=48, fmodel=96, fpart=32, ftex=68, role=32, sblob=32)
PACK_MAX_BYTES = 192 * 1024  # coarse_actor_registry_pack_check.inc kPackMaxBytes (package + skin arena)
# coarse_actor_owner_registry.inc kReg* and coarse_actor_registry_pack_check.inc kPack* capacities; role rows and
# source blobs are bounded by the lifetime masks (MATERIAL_ROWS / SOURCE_BLOBS minus the reviewed rows, checked above).
PACK_BONES = 48
PACK_CAPACITY = dict(desc=16, ref=32, geom=32, tex=16, fmodel=8, fpart=32, ftex=16)


def align32(n):
    return (n + 31) & ~31


def pack_crc_fnv(b):
    d = digest(b)
    return d[1], d[2]


def weights_bytes(rows):
    return b''.join(struct.pack('<3BB3f', bs[0], bs[1], bs[2], n, *v) for bs, n, v in rows)


def write_package(out, room, spec, runtime, textures, used_tex, bins, tpls, blobs):
    tex_index = {t: i for i, t in enumerate(used_tex)}
    geoms, gkey, refs, desc, parents, bind = [], {}, [], [], bytearray(), []
    blob = bytearray()

    def put(b):
        nonlocal blob
        at = len(blob); blob += b; blob += bytes(align32(len(blob)) - len(blob)); return at
    for r in runtime:
        first_ref, parents_at, bind_first = len(refs), len(parents), len(bind)
        for c in r['chunks']:
            w = weights_bytes(c['weights'])
            key = (r['bones'], c['position_count'], c['normal_count'], c['palette_count'], c['triangles'], c['skin_bytes'],
                   bytes(c['positions']), bytes(c['normals']), bytes(c['uv']), bytes(c['stream']), w)
            if key not in gkey:
                gkey[key] = len(geoms)
                at = [put(c['positions']), put(c['normals']), put(c['uv']), put(c['stream']), put(w)]
                crc, fnv = pack_crc_fnv(bytes(c['positions']) + bytes(c['normals']) + bytes(c['uv']) + bytes(c['stream']) + w)
                geoms.append(dict(counts=(c['position_count'], c['normal_count'], c['palette_count'], c['triangles'],
                                          len(c['stream']), len(c['uv']), c['skin_bytes'], r['bones']), at=at, crc=crc, fnv=fnv,
                                  bytes=len(c['positions']) + len(c['normals']) + len(c['uv']) + len(c['stream']) + len(w),
                                  users=[]))
            g = gkey[key]; geoms[g]['users'].append(f'{r["name"]}/{c["source_info"]}')
            refs.append((g, tex_index[c['texture']], c['source_info'], 0))
        parents += bytes(p & 0xff for p in r['parents']); bind += r['bind']
        name = r['name'].encode()
        if len(name) > 15:
            raise Fail(f'{r["name"]}: descriptor name longer than 15 bytes')
        desc.append(name.ljust(16, b'\0') + struct.pack('<8I', r['appearance'], r['model_id'], r['bones'], len(r['sections']),
                                                         first_ref, parents_at, bind_first, 0))
    # source identity facts, in first-use order
    fmodel, fpart, ftex, fm_index, ft_index, roles = [], [], [], {}, {}, []
    for r in runtime:
        for s in r['sections']:
            mk, tk = (r['archive'], s['bin']), (r['archive'], s['tpl'])
            if mk not in fm_index:
                m = bins[mk]; fm_index[mk] = len(fmodel)
                fmodel.append(struct.pack('<24I', *m['header'], *m['positions'], *m['normals'], *m['weights'], *m['uv'],
                                          len(fpart), len(m['parts'])))
                if len(m['parts']) != m['header'][8]:
                    raise Fail(f'{mk}: {len(m["parts"])} part rows, header displist_num {m["header"][8]}')
                for material, size, poly, crc, fnv in m['parts']:
                    fpart.append(bytes.fromhex(material).ljust(16, b'\0') + struct.pack('<4I', size, poly, crc, fnv))
            if tk not in ft_index:
                ft_index[tk] = (len(ftex), len(tpls[tk]['textures']))
                for x in tpls[tk]['textures']:
                    pal = x['palette'] or [0xffffffff, 0, 0, 0]
                    ftex.append(struct.pack('<17I', *x['key'], *x['whf'], *x['sampler'], *pal))
            roles.append(struct.pack('<8I', r['appearance'], s['role'], s['bin'], s['tpl'], fm_index[mk], *ft_index[tk], 0))
    sblob = [struct.pack('<8I', fm_index[(a, b)], 2, b, *bins[(a, b)]['normalized'], 0, 0) for a, b in blobs]
    tex = [struct.pack('<4I', *textures[t][:4]) for t in used_tex]
    geom = [struct.pack('<16I', *g['counts'], *g['at'], g['crc'], g['fnv'], 0) for g in geoms]
    body = dict(desc=b''.join(desc), ref=b''.join(struct.pack('<4I', *x) for x in refs), geom=b''.join(geom), blob=bytes(blob),
                tex=b''.join(tex), parents=bytes(parents), bind=b''.join(struct.pack('<12f', *row) for row in bind),
                fmodel=b''.join(fmodel), fpart=b''.join(fpart), ftex=b''.join(ftex), role=b''.join(roles), sblob=b''.join(sblob))
    counts = dict(desc=len(desc), ref=len(refs), geom=len(geoms), blob=len(blob), tex=len(tex), parents=len(parents),
                  bind=len(bind), fmodel=len(fmodel), fpart=len(fpart), ftex=len(ftex), role=len(roles), sblob=len(sblob))
    for k, cap in PACK_CAPACITY.items():
        if counts[k] > cap:
            raise Fail(f'package {k}: {counts[k]} records > the loader capacity {cap} (coarse_actor_registry_pack_check.inc)')
    if max(r['bones'] for r in runtime) > PACK_BONES:
        raise Fail(f'package: {max(r["bones"] for r in runtime)} bones > the loader capacity {PACK_BONES}')
    at = align32(PACK_HEADER + 16 * len(PACK_SECTIONS)); table, payload = [], bytearray()
    for i, k in enumerate(PACK_SECTIONS):
        if len(body[k]) != counts[k] * PACK_RECORD[k]:
            raise Fail(f'package section {k}: {len(body[k])} B for {counts[k]} records')
        table.append(struct.pack('<4I', i + 1, at, len(body[k]), counts[k]))
        payload += body[k] + bytes(align32(len(body[k])) - len(body[k])); at += align32(len(body[k]))
    skin = sum(g['counts'][6] for g in geoms)
    after = b''.join(table); after += bytes(align32(PACK_HEADER + len(after)) - PACK_HEADER - len(after))
    rest = after + bytes(payload)
    total = PACK_HEADER + len(rest)
    if align32(total) + skin > PACK_MAX_BYTES:
        raise Fail(f'package {total} B + skin {skin} B > {PACK_MAX_BYTES} (runtime arena capacity)')
    pcrc, pfnv = pack_crc_fnv(rest)
    head = bytearray(PACK_MAGIC + struct.pack('<14I', PACK_VERSION, PACK_HEADER, total, len(PACK_SECTIONS), PACK_HEADER, skin, room,
                                                pcrc, pfnv, 0, APPEARANCE0, max(r['bones'] for r in runtime), 0, 0))
    struct.pack_into('<I', head, 44, zlib.crc32(bytes(head)) & 0xffffffff)
    data = bytes(head) + rest
    d = os.path.join(out, 'package', 'r%x%02x' % (room >> 8, room & 255))
    os.makedirs(d)
    open(os.path.join(d, 'registry.re4nmr'), 'wb').write(data)
    chunk_bytes = sum(len(c['positions']) + len(c['normals']) + len(c['uv']) + len(c['stream']) + len(weights_bytes(c['weights']))
                      for r in runtime for c in r['chunks'])
    return dict(path=os.path.relpath(os.path.join(d, 'registry.re4nmr'), out), disc_path='dc/native/r%x%02x/registry.re4nmr' % (room >> 8, room & 255),
                room='%04x' % room, version=PACK_VERSION, bytes=total, sha256=sha(data), skin_arena=skin,
                arena=align32(total) + skin, capacity=PACK_MAX_BYTES, counts=counts,
                sections=[dict(kind=k, offset=struct.unpack_from('<4I', t)[1], bytes=struct.unpack_from('<4I', t)[2]) for k, t in zip(PACK_SECTIONS, table)],
                geometry=dict(chunk_refs=len(refs), unique=len(geoms), chunk_bytes=chunk_bytes,
                              unique_bytes=sum(g['bytes'] for g in geoms), saved_bytes=chunk_bytes - sum(g['bytes'] for g in geoms),
                              shared=[g['users'] for g in geoms if len(g['users']) > 1]))


if __name__ == '__main__':
    main()
