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
FOG = None      # --fog: the Dreamcast runtime fog (native_static.cpp re4dc_fog_frame), applied per fragment


def dc_fog(env, far):
    """native_static.cpp re4dc_fog_frame: the GX fog curve of the room's LIT cut (gx_fog: type, start, end; the
    game's setFog passes them straight to GXSetFog) plus the ramp to 100 % over the last 20 % before the far plane
    (FOG_FAR, the play recipe's 25 m, or the room's own far if shorter); geometry beyond the far is culled."""
    typ, start, end = int(env['fog_type']), float(env['fog_start']), float(env['fog_end'])
    col = np.array([int(env['fog_rgba'][k:k + 2], 16) for k in (0, 2, 4)], np.float32)
    far = min(far, end) if end > 1 else far

    def amount(z):
        if not end > start:
            f = (z >= end).astype(np.float64)
        else:
            t = np.clip((z - start) / (end - start), 0, 1)
            k = typ & 7
            f = (1 - 2 ** (-8 * t) if k == 4 else 1 - 2 ** (-8 * t * t) if k == 5 else
                 2 ** (-8 * (1 - t)) if k == 6 else 2 ** (-8 * (1 - t) ** 2) if k == 7 else t)
        ramp = np.clip((z - 0.8 * far) / (0.2 * far), 0, 1)
        s = ramp * ramp * (3 - 2 * ramp)
        return np.where(ramp > 0, f + (1 - f) * s, f)
    return dict(amount=amount, colour=col / 255, far=far, typ=typ, start=start, end=end)


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
    sky = FOG['colour'] * 255 if FOG and not view.ortho else SKY
    rgb = np.broadcast_to(sky, (H, W, 3)).copy()
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
    if FOG and not view.ortho:
        f = FOG['amount'](z)[:, None]
        out = out * (1 - f) + FOG['colour'][None, :] * f
        alpha = np.where(z > FOG['far'], 0.0, alpha)            # culled beyond the far plane
        if pas == 0:
            alpha = np.where(z > FOG['far'], 0.0, 1.0)
            pas = 1                                               # (opaque: alpha only marks the cull)
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


def scenery_mask(h, w):
    """Reference rows: leave out Leon (over the shoulder, left of centre) and the HUD ring (bottom right) of the GC
    frame, so the brightness / colour statistics compare scenery with scenery (same box for every column)."""
    m = np.ones((h, w), bool)
    m[int(0.25 * h):, int(0.08 * w):int(0.62 * w)] = False
    m[int(0.62 * h):, int(0.76 * w):] = False
    return m


def img_stats(img, mask):
    px = img[mask].astype(float)
    luma = px @ np.array([0.299, 0.587, 0.114])
    return dict(luma=round(float(luma.mean()), 1), rgb=[int(round(x)) for x in px.mean(0)],
                p90=round(float(np.percentile(luma, 90)), 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('room')
    ap.add_argument('src', type=Path)
    ap.add_argument('pkg', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--doors', type=Path)
    ap.add_argument('--aux', type=Path, help="the room's aux dir from ps2_room_extract.py (its .RTP picks the views)")
    ap.add_argument('--ref', action='append', help='label;x,y,z;yaw[;reference png[;back;up;pitch;fov]] (repeatable)')
    ap.add_argument('--pkg2', type=Path, help='a second package dir drawn as another column (e.g. --color-light gc)')
    ap.add_argument('--pkg2-label', default='package 2')
    ap.add_argument('--label', default='DC package')
    ap.add_argument('--lights', default='0,5')
    ap.add_argument('--width', type=int, default=480)
    ap.add_argument('--fog', type=Path, help="a LIT cut json (gc_room_lit.py): draw the Dreamcast runtime fog of that "
                                            "cut on every rendered column (perspective views)")
    ap.add_argument('--fog-far', type=float, default=25000.0, help='--fog: the far plane (FOG_FAR, play recipe 25 m)')
    a = ap.parse_args()
    global FOG
    if a.fog:
        FOG = dc_fog(json.loads(a.fog.read_text())['env'], a.fog_far)
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
    refs = {}
    hb = round(w * 336 / 512)                                  # Dolphin raw XFB band (512 x 336 of 512 x 448)
    for spec in a.ref or []:
        f = spec.split(';')
        if f[1] == 'cam':
            # label;cam;ex,ey,ez;tx,ty,tz;fov;png: an explicit camera (e.g. fitted to a Dolphin frame)
            eye = [float(x) for x in f[2].split(',')]
            tgt = [float(x) for x in f[3].split(',')]
            v = View(f[0], eye, tgt, w, hb, fov=float(f[4]))
            png = f[5] if len(f) > 5 else ''
        else:
            # label;x,y,z;yaw[;png[;back_mm;up_mm;pitch_deg;fov_deg]]: Leon at x,y,z facing yaw (forward = sin, cos),
            # the camera back_mm behind him and up_mm above his feet (GC over-the-shoulder rig approximated)
            p = np.array([float(x) for x in f[1].split(',')])
            yaw = float(f[2])
            back, up, pitch, fov = (float(x) for x in (f[4:8] if len(f) >= 8 else (1300, 1700, -8, 60)))
            fwd = np.array([math.sin(yaw), 0, math.cos(yaw)])
            eye = p - fwd * back + np.array([0, up, 0])
            tgt = eye + fwd * 10000 + np.array([0, 10000 * math.tan(math.radians(pitch)), 0])
            v = View(f[0], eye, tgt, w, hb, fov=fov)
            png = f[3] if len(f) > 3 else ''
        views.insert(1 + len(refs), v)
        if png:
            refs[f[0]] = Path(png)
    pkg2 = None
    if a.pkg2:
        pkg2_b, counts2 = package_tris(a.pkg2)
        rows2 = json.loads((a.pkg2 / 'ps2-world.json').read_text())['texture_rows']
        tex2 = {int(k): Tex(Image.open(a.pkg2 / 'textures-packed' / ('%04d.png' % int(k)))) for k in rows2}
        pkg2 = (pkg2_b, tex2)
    tiles, report = [], []
    for v in views:
        cols = []
        img_dc, s_dc = render(v, pkg_b, dc_tex, dc_colour)
        img_ps, s_ps = render(v, src_b, ps_tex, ps2_colour)
        cols.append((a.label, img_dc))
        cols.append(('PS2 source', img_ps))
        diff = float(np.abs(img_dc.astype(int) - img_ps.astype(int)).mean())
        row = dict(view=v.name, eye=[round(x) for x in v.eye], dc=s_dc, ps2=s_ps, mean_abs_diff=round(diff, 2))
        if pkg2:
            img2, s2 = render(v, pkg2[0], pkg2[1], dc_colour)
            cols.append((a.pkg2_label, img2))
            row['pkg2'] = s2
        if v.name in refs:
            im = Image.open(refs[v.name]).convert('RGB')
            if im.size == (512, 448):                          # Dolphin raw XFB: keep the letterbox band
                im = im.crop((0, 56, 512, 392))
            im = im.resize((w, v.h), Image.BILINEAR)
            cols.append(('GC (Dolphin)', np.asarray(im)))
            row['ref'] = str(refs[v.name])
        mask = scenery_mask(v.h, w) if v.name in refs else np.ones((v.h, w), bool)
        row['stats'] = {lab: img_stats(img, mask) for lab, img in cols}
        report.append(row)
        tiles.append((v.name, cols, row['stats'], v.h))
        print(json.dumps(dict(view=v.name, stats=row['stats'])))
    pad, head = 6, 30
    ncol = max(len(c) for _, c, _, _ in tiles)
    total_h = 30 + sum(hh + head + pad for *_, hh in tiles) + pad
    sheet = Image.new('RGB', (ncol * w + (ncol + 1) * pad, total_h), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    fog_txt = ('DC fog: type %d, %.0f..%.0f m, far %.0f m' % (FOG['typ'], FOG['start'] / 1000, FOG['end'] / 1000,
                                                               FOG['far'] / 1000)) if FOG else 'no fog'
    dr.text((pad, 8), '%s   columns: %s   %s   %d placements / %d meshes / %d parts (first package)' %
            (a.room, ' | '.join(lab for lab, _ in max((c for _, c, _, _ in tiles), key=len)), fog_txt,
             counts['placements'], counts['meshes'], counts['parts']), fill=(230, 230, 230))
    y = 30
    for name, cols, st, hh in tiles:
        dr.text((pad, y), name, fill=(230, 230, 180))
        for k, (lab, img) in enumerate(cols):
            s = st[lab]
            dr.text((pad + k * (w + pad), y + 13), '%s: luma %.1f rgb %d/%d/%d' % (lab, s['luma'], *s['rgb']),
                    fill=(200, 200, 200))
            sheet.paste(Image.fromarray(img), (pad + k * (w + pad), y + head))
        y += hh + head + pad
    a.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(a.out)
    a.out.with_suffix('.json').write_text(json.dumps(dict(room=a.room, counts=counts, fog=fog_txt, views=report), indent=1))


if __name__ == '__main__':
    main()
