"""Reader for the PS2 r101 world wrapper (full-wrapper-v5, room/ps2_source_package.hpp) and the
generated ps2_world_data.inc tables; reproduces native_ps2_world.cpp's corner, strip and colour rules."""
import math, re, struct

SECTIONS = ("templates", "materials", "authored_batches", "ordered_ranges", "placements", "smd_rows",
            "smx_rows", "ordered_bounds")
STRIDE = (48, 16, 16, 24, 80, 64, 144, 20)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _array(text, name):
    at = text.index(name + "[")
    left = text.index("{", text.index("=", at))
    depth, i = 1, left + 1
    while depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[left + 1:i - 1]


NUM = re.compile(r"-?0x[0-9a-fA-F.]+p[-+]?\d+f|-?0x[0-9a-fA-F]+u?|-?\d+")


def _nums(body):
    out = []
    for t in NUM.findall(body):
        if "p" in t:
            out.append(f32(float.fromhex(t.rstrip("f"))))
        else:
            out.append(int(t.rstrip("u"), 0))
    return out


def _rows(body):
    """Top-level {...} rows of an array body; '{}' rows come back as None."""
    rows, depth, start = [], 0, None
    for i, c in enumerate(body):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                inner = body[start + 1:i].strip()
                rows.append(_nums(inner) if inner else None)
    return rows


def load_tables(inc_path):
    text = open(inc_path).read()
    textures = []
    for r in _rows(_array(text, "ps2_textures")):
        textures.append(None if r is None else dict(crc=r[0], fnv=r[1], width=r[2], height=r[3], alpha=r[4],
                                                    gain=r[5:8]))
    policy = [dict(texture=r[0], pass_=r[1], cull=r[2]) for r in _rows(_array(text, "ps2_policy"))]
    lighting = []
    for r in _rows(_array(text, "ps2_reference_lighting")):
        rot, rest = r[:9], r[9:]
        lights = [dict(pos=rest[k:k + 3], dir=rest[k + 3:k + 6], a=rest[k + 6:k + 9], k=rest[k + 9:k + 12],
                       col=rest[k + 12:k + 15]) for k in (0, 15)]
        lighting.append(dict(rotation=rot, lights=lights))
    ambient = _nums(_array(text, "ps2_ambient"))
    crc = int(re.search(r"ps2_payload_crc=(0x[0-9a-f]+)u", text).group(1), 16)
    assert len(textures) == 98 and len(policy) == 342 and len(lighting) == 22 and len(ambient) == 3
    return dict(textures=textures, policy=policy, lighting=lighting, ambient=ambient, payload_crc=crc)


class Package:
    def __init__(self, path):
        b = open(path, "rb").read()
        self.bytes = b
        self.payload = p = b[224:]
        self.pool_bytes = struct.unpack_from("<I", b, 208)[0]
        self.table = {n: struct.unpack_from("<II", b, 144 + 8 * i) for i, n in enumerate(SECTIONS)}
        self.triangle_count = struct.unpack_from("<I", b, 20)[0] if False else None
        self.templates = [self._template(i) for i in range(self.table["templates"][1])]
        self.placements = [self._placement(i) for i in range(self.table["placements"][1])]
        self.ranges = [struct.unpack_from("<4H4I", p, self.table["ordered_ranges"][0] + 24 * i)
                       for i in range(self.table["ordered_ranges"][1])]

    def _template(self, i):
        o = self.table["templates"][0] + 48 * i
        src, kind, _ = struct.unpack_from("<HBB", self.payload, o)
        spans = [struct.unpack_from("<II", self.payload, o + 4 + 8 * k) for k in range(4)]
        factor, first_batch, batch_count = struct.unpack_from("<fII", self.payload, o + 36)
        return dict(source_bin=src, kind=kind, position=spans[0], uv=spans[1], attribute=spans[2], corner=spans[3],
                    factor=factor)

    def _placement(self, i):
        o = self.table["placements"][0] + 80 * i
        placement, template = struct.unpack_from("<HH", self.payload, o)
        first_range, range_count = struct.unpack_from("<II", self.payload, o + 16)
        affine = struct.unpack_from("<12f", self.payload, o + 32)
        return dict(placement=placement, template=template, first_range=first_range, range_count=range_count,
                    affine=[list(affine[0:4]), list(affine[4:8]), list(affine[8:12])])

    # Pools: positions i16x3, uv i16x2 (/256), attribute (kind 0: u8 rgba /128; kind 1: i16 normal), corners u16x3.
    def corner(self, t, ci):
        p = self.payload
        pi, ui, ai = struct.unpack_from("<3H", p, t["corner"][0] + 6 * ci)
        pos = struct.unpack_from("<3h", p, t["position"][0] + 6 * (pi & 0x7FFF))
        uv = struct.unpack_from("<2h", p, t["uv"][0] + 4 * ui)
        if t["kind"]:
            attr = struct.unpack_from("<3h", p, t["attribute"][0] + 6 * ai)
        else:
            attr = tuple(p[t["attribute"][0] + 4 * ai:t["attribute"][0] + 4 * ai + 4])
        return dict(pos_index=pi & 0x7FFF, end=bool(pi & 0x8000), pos=pos, uv=(uv[0] / 256.0, uv[1] / 256.0),
                    attr=attr, key=(pi & 0x7FFF, ui, ai))

    def range_triangles(self, ri):
        """native_ps2_world.cpp draw(): triangles of range ri in drawn orientation, as corner-index triples.
        The flag on a corner ends its strip after that corner; odd strip positions reverse (c, b, a)."""
        placement, template, material, _, first_group, group_count, first_corner, corner_count = self.ranges[ri]
        t = self.templates[template]
        out = []
        for gi in range(first_group, first_group + group_count):
            fc, cc = struct.unpack_from("<IH", self.payload, self.table["ordered_bounds"][0] + 20 * gi)
            ring, length = [0, 0, 0], 0
            for ci in range(fc, fc + cc):
                ring[length % 3] = ci
                if length >= 2:
                    a, b, c = ring[(length - 2) % 3], ring[(length - 1) % 3], ring[length % 3]
                    out.append((c, b, a) if length & 1 else (a, b, c))
                length += 1
                if struct.unpack_from("<H", self.payload, t["corner"][0] + 6 * ci)[0] & 0x8000:
                    length = 0
        return out


def payload_crc(payload):
    """ps2_source_package.hpp payload_crc: the standard reflected CRC-32."""
    import zlib
    return zlib.crc32(payload)


def clamp(f):
    return 0.0 if f < 0 else 1.0 if f > 1 else f


def normal_light(tables, placement, affine, pos, normal, factor):
    """native_ps2_world.cpp normal_light (reference GC cut0 sun/sky for placements 79..100)."""
    ref = tables["lighting"][placement - 79]
    world = [affine[r][3] + sum(affine[r][c] * (pos[c] * factor) for c in range(3)) for r in range(3)]
    n = [sum(ref["rotation"][r * 3 + c] * normal[c] for c in range(3)) for r in range(3)]
    rgb = list(tables["ambient"])
    norm = math.sqrt(sum(x * x for x in n))
    if norm > 0:
        n = [x / norm for x in n]
    for l in ref["lights"]:
        d = [l["pos"][c] - world[c] for c in range(3)]
        length = math.sqrt(sum(x * x for x in d))
        if length <= 0:
            continue
        d = [x / length for x in d]
        cosine = max(0.0, sum(d[c] * l["dir"][c] for c in range(3)))
        dot = max(0.0, sum(n[c] * d[c] for c in range(3)))
        num = max(0.0, l["a"][0] + l["a"][1] * cosine + l["a"][2] * cosine * cosine)
        den = l["k"][0] + l["k"][1] * length + l["k"][2] * length * length
        if den > 0:
            for c in range(3):
                rgb[c] += l["col"][c] * num / den * dot
    return [clamp(x) for x in rgb]


def corner_rgba(tables, placement, affine, t, corner, gain):
    """Final vertex colour as the r19 renderer computes it (before 8-bit packing): (r, g, b, a) floats."""
    if t["kind"]:
        rgb = normal_light(tables, placement, affine, corner["pos"], corner["attr"], t["factor"])
        a = 1.0
    else:
        rgb = [corner["attr"][j] / 128.0 for j in range(3)]
        a = corner["attr"][3] / 128.0
    return (clamp(rgb[0] * gain[0]), clamp(rgb[1] * gain[1]), clamp(rgb[2] * gain[2]), a)
