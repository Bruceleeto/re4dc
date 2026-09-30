#!/usr/bin/env python3
"""Offline look sheet for a PS2 room package (ps2_room_r4im.py output) against the PS2 source it came from.

Left column: the Dreamcast package as the runtime holds it: R4IM level 0 (grid positions, 16-bit UVs, ARGB1555
prelit corner colours), the R4PW placements (instanced meshes through their affine) and the packed textures
(textures-packed/<entry>.png = the decoded RE4DCTX payload, gain applied), PVR modulate texel * colour, passes
OP / PT (alpha >= 0.5) / TR (back to front, source-over).
Right column: the PS2 source: the JADERLINK OBJ triangles, the TPL textures as decoded (textures-source), the
authored vertex colours as exported (1.0 = GS 0x80) and GS modulate texel * colour clamped to 1, the same passes.
Both are drawn two-sided, without fog, by the same numpy rasteriser (perspective-correct, one mip level per
triangle), so the difference between the columns is the conversion; the rows are the views (a top-down plan,
the door spawns into the room from aev_doors.json, and eye-height views from the room centre).
Not a Flycast frame: no fog, no runtime LOD, no near/far cull, no lighting (the package is prelit).

usage: ps2_room_sheet.py <room> <inputs dir> <package dir> <out.png> [--doors aev_doors.json] [--width 480]
Windows Python (numpy, PIL), like ps2_room_r4im.py (whose scene reader it reuses).
"""
import argparse, importlib.util, json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ps2_room_r4im as R  # noqa: E402

spec = importlib.util.spec_from_file_location('r4im', HERE / 'assetpipe' / 'r4im.py')
r4im = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r4im)

SKY = np.array([96, 104, 112], np.float32)


# ------------------------------------------------------------------------------------------------ textures
class Tex:
    def __init__(self, img):
        a = np.asarray(img.convert('RGBA'), np.float32) / 255
        self.levels = [a]
        while min(a.shape[:2]) > 1:
            h, w = a.shape[0] // 2, a.shape[1] // 2
            a = a[:2 * h, :2 * w].reshape(h, 2, w, 2, 4).mean((1, 3))
            self.levels.append(a)


# ------------------------------------------------------------------------------------------------ scenes
def package_tris(pkg_dir):
    """[(pos (n,3,3), uv (n,3,2), rgba (n,3,4), tex key, pass)] from the package files."""
    pk = r4im.load(pkg_dir / 'ps2-world.re4mesh')
    side = (pkg_dir / 'ps2-world.r4pw').read_bytes()
    import struct
    magic, ver, npl, npa, nme = struct.unpack_from('<4s4I', side)
    assert magic == b'R4PW' and ver == 1
    parts_meta = [struct.unpack_from('<IIHHBBBB', side, 32 + 16 * i) for i in range(npa)]
    off = 32 + 16 * npa
    placements = [struct.unpack_from('<HH12f', side, off + 52 * i) for i in range(npl)]
    rows = json.loads((pkg_dir / 'ps2-world.json').read_text())['texture_rows']
    by_key = {(v['key'][0], v['key'][1]): int(k) for k, v in rows.items()}
    per_mesh = {}
    for k in range(len(pk.meshes)):
        out = []
        for p in pk.mesh_parts(k):
            part = pk.parts[p]
            ulo, vlo, us, vs = part[8:12]
            crc, h2, w, h, pas, cull, _, _ = parts_meta[p]
            tex = by_key[(crc, h2)]
            P, UV, C = [], [], []
            lv = pk.part_levels(p)
            for cl in lv:
                for let in cl['levels'][0][1]:
                    for s in pk.meshlet_strips(let):
                        vv = [pk.vertex(v) for v in s]
                        for j in range(len(s) - 2):
                            a, b, c = (vv[j + 1], vv[j], vv[j + 2]) if j & 1 else (vv[j], vv[j + 1], vv[j + 2])
                            pa, pb, pc = (pk.world(k, *x[:3]) for x in (a, b, c))
                            if pa == pb or pb == pc or pa == pc:
                                continue
                            P.append((pa, pb, pc))
                            UV.append([(ulo + x[3] * us, vlo + x[4] * vs) for x in (a, b, c)])
                            C.append([((x[5] >> 10 & 31) / 31, (x[5] >> 5 & 31) / 31, (x[5] & 31) / 31,
                                       1.0 if x[5] & 0x8000 else 0.0) for x in (a, b, c)])
            if P:
                out.append((np.array(P, np.float64), np.array(UV, np.float64), np.array(C, np.float64), tex, pas))
        per_mesh[k] = out
    batches = []
    for mi, gi, *aff in placements:
        M = np.array(aff, np.float64).reshape(3, 4)
        for P, UV, C, tex, pas in per_mesh[mi]:
            W = P @ M[:, :3].T + M[:, 3]
            batches.append((W, UV, C, tex, pas))
    return batches, dict(placements=npl, meshes=nme, parts=npa)


def source_tris(room, src, pkg_dir, lights):
    groups = R.read_scene(room, src, lights)
    rows = json.loads((pkg_dir / 'ps2-world.json').read_text())['texture_rows']
    batches = []
    for g in groups:
        rgba = np.concatenate([np.clip(g['rgb'], 0, None), g['alpha'][..., None]], -1)
        for t in np.unique(g['tex']):
            m = g['tex'] == t
            fmt = rows[str(int(t))]['format']
            for blend in (False, True):
                mm = m & (g['blend'] == blend)
                if mm.any():
                    batches.append((g['pos'][mm], g['uv'][mm], rgba[mm], int(t), fmt if blend else 0))
    return batches


# ------------------------------------------------------------------------------------------------ raster
class View:
    def __init__(self, name, eye, target, w, h, fov=70.0, ortho=None):
        self.name, self.w, self.h, self.ortho, self.ycut = name, w, h, ortho, math.inf
        self.eye = np.asarray(eye, np.float64)
        f = np.asarray(target, np.float64) - self.eye
        f /= np.linalg.norm(f)
        up = np.array([0, 1.0, 0]) if abs(f[1]) < 0.99 else np.array([0, 0, -1.0])
        r = np.cross(up, f); r /= np.linalg.norm(r)   # screen right (y up, left-handed: x right)
        u = np.cross(f, r)
        self.R = np.stack([r, u, f])
        self.k = (w / 2) / math.tan(math.radians(fov) / 2)
        self.znear = 100.0

    def cam(self, P):
        return (P - self.eye) @ self.R.T


def render(view, batches, textures, colour_fn):
    W, H = view.w, view.h
    rgb = np.broadcast_to(SKY, (H, W, 3)).copy()
    zb = np.full((H, W), np.inf, np.float32)
    trs = []
    stats = dict(tris=0, drawn=0)
    for P, UV, C, tex, pas in batches:
        X = view.cam(P.reshape(-1, 3)).reshape(-1, 3, 3)
        stats['tris'] += len(X)
        if view.ortho:
            keep = P[..., 1].min(1) <= view.ycut
        else:
            keep = X[..., 2].max(1) > view.znear
        for i in np.nonzero(keep)[0]:
            item = (X[i], UV[i], C[i], tex, pas)
            if pas == 2:
                trs.append(item)
            else:
                stats['drawn'] += tri(view, rgb, zb, item, textures, colour_fn, blend=False)
    trs.sort(key=lambda it: -it[0][:, 2].mean())
    for item in trs:
        stats['drawn'] += tri(view, rgb, zb, item, textures, colour_fn, blend=True)
    return np.clip(rgb, 0, 255).astype(np.uint8), stats


def clip_near(X, UV, C, zn):
    poly = list(zip(X, UV, C))
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ia, ib = a[0][2] >= zn, b[0][2] >= zn
        if ia:
            out.append(a)
        if ia != ib:
            t = (zn - a[0][2]) / (b[0][2] - a[0][2])
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
    return out


def tri(view, rgb, zb, item, textures, colour_fn, blend):
    X, UV, C, tex, pas = item
    if not view.ortho and X[:, 2].min() < view.znear:
        poly = clip_near(X, UV, C, view.znear)
        n = 0
        for j in range(1, len(poly) - 1):
            sub = [poly[0], poly[j], poly[j + 1]]
            n += tri(view, rgb, zb, (np.array([s[0] for s in sub]), np.array([s[1] for s in sub]),
                                     np.array([s[2] for s in sub]), tex, pas), textures, colour_fn, blend)
        return n
    W, H = view.w, view.h
    if view.ortho:
        sx = W / 2 + X[:, 0] * view.ortho
        sy = H / 2 - X[:, 1] * view.ortho
        iw = np.ones(3)
        depth = X[:, 2]
    else:
        sx = W / 2 + view.k * X[:, 0] / X[:, 2]
        sy = H / 2 - view.k * X[:, 1] / X[:, 2]
        iw = 1 / X[:, 2]
        depth = X[:, 2]
    x0, x1 = max(0, int(math.floor(sx.min()))), min(W - 1, int(math.ceil(sx.max())))
    y0, y1 = max(0, int(math.floor(sy.min()))), min(H - 1, int(math.ceil(sy.max())))
    if x0 > x1 or y0 > y1:
        return 0
    area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
    if abs(area) < 1e-9:
        return 0
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    l1 = ((gx - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (gy - sy[0])) / area
    l2 = ((sx[1] - sx[0]) * (gy - sy[0]) - (gx - sx[0]) * (sy[1] - sy[0])) / area
    l0 = 1 - l1 - l2
    m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
    if not m.any():
        return 0
    L = np.stack([l0[m], l1[m], l2[m]], -1)
    q = L * iw
    qs = q.sum(-1, keepdims=True)
    wts = q / qs
    z = (wts @ depth) if view.ortho else 1 / qs[:, 0]
    ys, xs = np.nonzero(m)
    ys += y0; xs += x0
    t = textures[tex]
    # mip: texel area over pixel area
    th, tw = t.levels[0].shape[:2]
    tarea = abs((UV[1, 0] - UV[0, 0]) * (UV[2, 1] - UV[0, 1]) - (UV[2, 0] - UV[0, 0]) * (UV[1, 1] - UV[0, 1])) * tw * th
    lvl = int(np.clip(0.5 * math.log2(max(tarea / abs(area), 1e-9)), 0, len(t.levels) - 1))
    img = t.levels[lvl]
    lh, lw = img.shape[:2]
    uv = wts @ UV
    tx = np.floor(uv[:, 0] * lw).astype(np.int64) % lw
    ty = np.floor(uv[:, 1] * lh).astype(np.int64) % lh
    texel = img[ty, tx]
    col = wts @ C
    out, alpha = colour_fn(texel, col)
    if pas == 1:
        keep = alpha >= 0.5
    elif pas == 2:
        keep = alpha > 1 / 255
    else:
        keep = np.ones(len(z), bool)
    zt = z < zb[ys, xs]
    keep &= zt
    if not keep.any():
        return 0
    ys, xs, z, out, alpha = ys[keep], xs[keep], z[keep], out[keep], alpha[keep]
    if blend:
        rgb[ys, xs] = out * 255 * alpha[:, None] + rgb[ys, xs] * (1 - alpha[:, None])
    else:
        rgb[ys, xs] = out * 255
        zb[ys, xs] = z
    return 1


def dc_colour(texel, col):
    return np.clip(texel[:, :3] * col[:, :3], 0, 1), texel[:, 3] * col[:, 3]


def ps2_colour(texel, col):
    return np.clip(texel[:, :3] * col[:, :3], 0, 1), np.clip(texel[:, 3] * col[:, 3], 0, 1)


# ------------------------------------------------------------------------------------------------ views
def rtp_points(path):
    """PS2 route graph (little-endian 'PTR2'): u16 count at 6, 32-byte points from 0x20, x y z floats (mm).
    The enemy route graph runs over the walkable ground, so its points are eye positions on the play space."""
    import struct
    d = Path(path).read_bytes()
    assert d[:4] == b'PTR2', d[:4]
    n = struct.unpack_from('<H', d, 6)[0]
    return np.array([struct.unpack_from('<3f', d, 0x20 + 32 * i) for i in range(n)], np.float64)


def pick_views(room, batches, doors, rtp, w, h, n_route=3):
    """plan + door spawns + n_route route points (farthest-point order from the first spawn), each looking at the
    route point farthest from it. The plan leaves out geometry more than 12 m above the highest route point
    (the sky dome / canopy); returns (views, plan_ycut)."""
    allp = np.concatenate([b[0].reshape(-1, 3) for b in batches])
    walk = rtp if rtp is not None and len(rtp) else allp[::97]
    spawns = []
    if doors:
        for srcroom, rec in sorted(doors.items()):
            for d in rec.get('doors', []):
                if d.get('dst') == room:
                    spawns.append(('spawn from %s door %02d' % (srcroom, d['no']), np.asarray(d['pos'], float)))
    pts = np.concatenate([walk] + [p[None] for _, p in spawns])
    lo, hi = pts.min(0) - 8000, pts.max(0) + 8000
    ctr = (lo + hi) / 2
    span = max(hi[0] - lo[0], hi[2] - lo[2])
    ycut = pts[:, 1].max() + 12000
    views = [View('plan (top-down, %.0f m square around the route + doors; nothing above y %.0f m)' %
                  (span / 1000, ycut / 1000), (ctr[0], ycut + 1000, ctr[2]), (ctr[0], lo[1], ctr[2]), w, h,
                  ortho=min(w, h) / span)]
    for name, pos in spawns:
        far = walk[np.argmax(np.hypot(walk[:, 0] - pos[0], walk[:, 2] - pos[2]))]
        views.append(View(name, (pos[0], pos[1] + 1700, pos[2]), (far[0], pos[1] + 1200, far[2]), w, h))
    chosen = [spawns[0][1]] if spawns else [walk[0]]
    for _ in range(n_route):
        c = np.array(chosen)
        d = np.min(np.hypot(walk[:, None, 0] - c[None, :, 0], walk[:, None, 2] - c[None, :, 2]), 1)
        i = int(np.argmax(d))
        chosen.append(walk[i])
        p = walk[i]
        far = walk[np.argmax(np.hypot(walk[:, 0] - p[0], walk[:, 2] - p[2]))]
        views.append(View('route point %d (%.0f, %.0f, %.0f)' % (i, *p), (p[0], p[1] + 1700, p[2]),
                          (far[0], p[1] + 1200, far[2]), w, h))
    return views, ycut


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('room')
    ap.add_argument('src', type=Path)
    ap.add_argument('pkg', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--doors', type=Path)
    ap.add_argument('--aux', type=Path, help="the room's aux dir from ps2_room_extract.py (its .RTP picks the views)")
    ap.add_argument('--lights', default='0,5')
    ap.add_argument('--width', type=int, default=480)
    a = ap.parse_args()
    w, h = a.width, a.width * 3 // 4
    pkg_b, counts = package_tris(a.pkg)
    src_b = source_tris(a.room, a.src, a.pkg, tuple(int(x) for x in a.lights.split(',')))
    rows = json.loads((a.pkg / 'ps2-world.json').read_text())['texture_rows']
    dc_tex = {int(k): Tex(Image.open(a.pkg / 'textures-packed' / ('%04d.png' % int(k)))) for k in rows}
    ps_tex = {int(k): Tex(Image.open(a.pkg / 'textures-source' / ('%04d.png' % int(k)))) for k in rows}
    doors = json.loads(a.doors.read_text()) if a.doors else None
    rtp = None
    if a.aux:
        found = sorted(a.aux.glob('*.RTP'))
        rtp = rtp_points(found[0]) if found else None
    views, ycut = pick_views(a.room, src_b, doors, rtp, w, h)
    views[0].ycut = ycut
    tiles, report = [], []
    for v in views:
        img_dc, s_dc = render(v, pkg_b, dc_tex, dc_colour)
        img_ps, s_ps = render(v, src_b, ps_tex, ps2_colour)
        diff = float(np.abs(img_dc.astype(int) - img_ps.astype(int)).mean())
        report.append(dict(view=v.name, eye=[round(x) for x in v.eye], dc=s_dc, ps2=s_ps, mean_abs_diff=round(diff, 2),
                           dc_mean=round(float(img_dc.mean()), 1), ps2_mean=round(float(img_ps.mean()), 1)))
        tiles.append((v.name, img_dc, img_ps, diff))
        print(json.dumps(report[-1]))
    pad, head = 6, 18
    sheet = Image.new('RGB', (2 * w + 3 * pad, 30 + len(tiles) * (h + head + pad) + pad), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    dr.text((pad, 8), '%s  left: Dreamcast package (R4IM level 0, packed textures, ARGB1555 prelit)   right: PS2 '
            'source (OBJ + TPL, authored colours)   no fog   %d placements / %d meshes / %d parts' %
            (a.room, counts['placements'], counts['meshes'], counts['parts']), fill=(230, 230, 230))
    y = 30
    for name, dc, ps, diff in tiles:
        dr.text((pad, y), '%s   mean |DC-PS2| %.1f' % (name, diff), fill=(230, 230, 180))
        sheet.paste(Image.fromarray(dc), (pad, y + head))
        sheet.paste(Image.fromarray(ps), (2 * pad + w, y + head))
        y += h + head + pad
    a.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(a.out)
    a.out.with_suffix('.json').write_text(json.dumps(dict(room=a.room, counts=counts, views=report), indent=1))


if __name__ == '__main__':
    main()
