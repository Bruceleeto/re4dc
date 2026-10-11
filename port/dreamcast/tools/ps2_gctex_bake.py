#!/usr/bin/env python3
"""ps2_gctex_bake.py: bake GameCube textures onto a PS2 cast mesh's own UV layout (lane ps2cast-3, 2026-10-11).

The PS2 cast conversions (tools/ps2_cast.py) draw the PS2 mesh with the PS2 TPL (4/8-bit CLUT, often lower resolution
and lower contrast than the GC textures). The PS2 and GC meshes share the skeleton and the rest pose (ps2_cast.py
validation: PS2 -> GC surface median 0.0 mm), so the GC texture can be transferred texel by texel: for every texel of
the PS2 atlas covered by a PS2 triangle (2x2 supersamples), the rest-pose surface point is projected to the closest GC
triangle (normal-agreeing candidates first), its GC UV interpolated and the GC TPL image of that triangle's material
sampled (bilinear, wrapped). This is Blender's "selected to active" bake (ray distance = closest surface) done in
numpy, deterministic for given inputs. Islands are dilated so bilinear filtering and VQ never read the gutter.

Outputs (in <out>): atlas.png (RGB, same size as the PS2 atlas unless --size), mask.png (the GC alpha-mask channel
sampled the same way: 255 = keep, 0 = punched; written when a GC material has an alpha texture or an alpha channel),
bake.json (inputs, sha256, counts, distance stats, per GC material texel counts).

Usage (Windows Python with numpy + PIL; paths are files):
  python ps2_gctex_bake.py <gc em.drs> <bin arcs, e.g. 5,6> <tpl arc> <ps2 cast dir (mesh.json, atlas.png)> <out>
         [--size WxH] [--ss 2] [--dilate 8] [--section-map 0:0,1:1]
--section-map: PS2 triangle source_info -> GC bin index in the list (default: same index; one GC bin = all).
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[2] / 'tools')]
import convert_character as cc  # noqa: E402
import convert_tpl  # noqa: E402
import drs  # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest()


def gc_section(bin_bytes, tpl_images):
    (positions, pal, ws, norm, normpal, ds, dn, nc, uv, indices, batches, bindings, *_rest) = cc.parse_geometry(bin_bytes)
    P = np.asarray(positions, float)
    src = np.asarray(ds, int)
    UV = np.asarray(uv, float)
    idx = np.asarray(indices, int).reshape(-1, 3)
    mat = np.zeros(len(idx), int)
    alpha = np.full(len(idx), -1, int)
    for (first, count, material, part), b in zip(batches, bindings):
        mat[first // 3:(first + count) // 3] = b.color_image
        alpha[first // 3:(first + count) // 3] = -1 if b.alpha_image is None else b.alpha_image
    return dict(v=P[src[idx]], uv=UV[idx], mat=mat, alpha=alpha)


def closest_point_tri(p, a, b, c):
    """Vectorised Ericson closest point on triangles; p (N,3), a/b/c (N,3) -> (q, bary (N,3))."""
    ab, ac, ap = b - a, c - a, p - a
    d1 = (ab * ap).sum(1); d2 = (ac * ap).sum(1)
    bp = p - b; d3 = (ab * bp).sum(1); d4 = (ac * bp).sum(1)
    cp = p - c; d5 = (ab * cp).sum(1); d6 = (ac * cp).sum(1)
    va = d3 * d6 - d5 * d4; vb = d5 * d2 - d1 * d6; vc = d1 * d4 - d3 * d2
    n = len(p)
    bary = np.zeros((n, 3))
    denom = va + vb + vc
    with np.errstate(divide='ignore', invalid='ignore'):
        v = vb / denom; w = vc / denom
    bary[:] = np.stack([1 - v - w, v, w], 1)
    # region tests (later assignments win in reverse priority order)
    with np.errstate(divide='ignore', invalid='ignore'):
        m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
        t = (d4 - d3) / ((d4 - d3) + (d5 - d6)); bary[m] = np.stack([0 * t, 1 - t, t], 1)[m]
        m = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
        t = d2 / (d2 - d6); bary[m] = np.stack([1 - t, 0 * t, t], 1)[m]
        m = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
        t = d1 / (d1 - d3); bary[m] = np.stack([1 - t, t, 0 * t], 1)[m]
    m = (d6 >= 0) & (d5 <= d6); bary[m] = [0, 0, 1]
    m = (d3 >= 0) & (d4 <= d3); bary[m] = [0, 1, 0]
    m = (d1 <= 0) & (d2 <= 0); bary[m] = [1, 0, 0]
    bary = np.nan_to_num(bary, nan=1 / 3)
    q = bary[:, :1] * a + bary[:, 1:2] * b + bary[:, 2:] * c
    return q, bary


def sample(img, uv):
    """Bilinear wrapped sample of an (H, W, C) float image at normalised uv (N, 2)."""
    h, w = img.shape[:2]
    x = (uv[:, 0] % 1.0) * w - 0.5; y = (uv[:, 1] % 1.0) * h - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
    x0 %= w; y0 %= h; x1 = (x0 + 1) % w; y1 = (y0 + 1) % h
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) +
            img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('drs'); ap.add_argument('bins'); ap.add_argument('tpl'); ap.add_argument('cast'); ap.add_argument('out')
    ap.add_argument('--size'); ap.add_argument('--ss', type=int, default=2); ap.add_argument('--dilate', type=int, default=8)
    ap.add_argument('--section-map', default=''); ap.add_argument('--k', type=int, default=24)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    db = Path(a.drs).read_bytes(); g = drs.Drs(db)
    bins = [int(x, 0) for x in a.bins.split(',')]
    tplb = g.entries[int(a.tpl, 0) - 4][1]
    tims = convert_tpl.parse_tpl(tplb)
    imgs = [np.asarray(convert_tpl.decode_image(t), float).reshape(t.height, t.width, 4) for t in tims]
    secs = [gc_section(g.entries[b - 4][1], tims) for b in bins]
    cast = Path(a.cast)
    mesh = json.loads((cast / 'mesh.json').read_text())
    patlas = Image.open(cast / 'atlas.png')
    W, H = (map(int, a.size.split('x')) if a.size else patlas.size)
    smap = {int(k): int(v) for k, v in (x.split(':') for x in a.section_map.split(',') if x)}
    PV = np.asarray(mesh['positions_mm'], float)
    # GC triangle pool per section, with centroid search
    gv = [s['v'] for s in secs]
    acc = np.zeros((H, W, 4)); msk = np.zeros((H, W)); cnt = np.zeros((H, W)); dist_all = []
    mat_hits = {}
    any_alpha = any((s['alpha'] >= 0).any() for s in secs) or any((im[..., 3] < 255).any() for im in imgs)
    tris_by_sec = {}
    for t in mesh['triangles']:
        tris_by_sec.setdefault(int(t['source_info']), []).append(t)
    for si, tl in sorted(tris_by_sec.items()):
        gi = smap.get(si, si if si < len(secs) else 0)
        S = secs[gi]
        cen = S['v'].mean(1)
        gn = np.cross(S['v'][:, 1] - S['v'][:, 0], S['v'][:, 2] - S['v'][:, 0])
        gn /= np.linalg.norm(gn, axis=1, keepdims=True) + 1e-12
        pts, nrm, tex = [], [], []
        for t in tl:
            c = t['corners']
            v = PV[[k['vertex'] for k in c]]
            n = np.asarray([k['normal'] for k in c], float)
            uv = np.asarray([k['uv'] for k in c], float) * [W * a.ss, H * a.ss]
            x0, y0 = np.floor(uv.min(0)).astype(int) - 1; x1, y1 = np.ceil(uv.max(0)).astype(int) + 1
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            q = np.stack([xs.ravel(), ys.ravel()], 1)
            T = np.array([[uv[1, 0] - uv[0, 0], uv[2, 0] - uv[0, 0]], [uv[1, 1] - uv[0, 1], uv[2, 1] - uv[0, 1]]])
            if abs(np.linalg.det(T)) < 1e-9:
                continue
            l = np.linalg.solve(T, (q - uv[0]).T).T
            b = np.stack([1 - l[:, 0] - l[:, 1], l[:, 0], l[:, 1]], 1)
            inside = (b >= -1e-6).all(1)
            # conservative coverage: also texels whose centre is within half a texel of the triangle (edge seams)
            if not inside.any():
                bc = np.clip(b, 0, None); bc /= bc.sum(1, keepdims=True)
                near = np.linalg.norm((bc @ uv) - q, axis=1) < 0.71
                inside = near; b = bc
            b = b[inside]; q = q[inside]
            b = np.clip(b, 0, None); b /= b.sum(1, keepdims=True)
            pts.append(b @ v); nrm.append(b @ n); tex.append(q)
        if not pts:
            continue
        pts = np.concatenate(pts); nrm = np.concatenate(nrm); tex = np.concatenate(tex)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        # candidate GC triangles: k nearest centroids (chunked brute force on centroids)
        best_d = np.full(len(pts), np.inf); best_t = np.zeros(len(pts), int); best_b = np.zeros((len(pts), 3))
        for s0 in range(0, len(pts), 4096):
            p = pts[s0:s0 + 4096]; pn = nrm[s0:s0 + 4096]
            d2 = ((p[:, None, :] - cen[None, :, :]) ** 2).sum(2)
            kk = min(a.k, len(cen))
            cand = np.argpartition(d2, kk - 1, axis=1)[:, :kk]
            for j in range(kk):
                ti = cand[:, j]
                qpt, bb = closest_point_tri(p, S['v'][ti, 0], S['v'][ti, 1], S['v'][ti, 2])
                d = np.linalg.norm(qpt - p, axis=1)
                # penalise back-facing candidates (inner / outer shells of thin parts)
                agree = (gn[ti] * pn).sum(1)
                d = d + np.where(agree < 0, 50.0, 0.0)
                better = d < best_d[s0:s0 + 4096]
                best_d[s0:s0 + 4096][better] = d[better]; best_t[s0:s0 + 4096][better] = ti[better]
                best_b[s0:s0 + 4096][better] = bb[better]
        guv = (best_b[:, :, None] * S['uv'][best_t]).sum(1)
        col = np.zeros((len(pts), 4)); al = np.full(len(pts), 255.0)
        for m in np.unique(S['mat'][best_t]):
            sel = S['mat'][best_t] == m
            col[sel] = sample(imgs[m], guv[sel])
            mat_hits[f'{gi}:{m}'] = int(sel.sum())
        for am in np.unique(S['alpha'][best_t]):
            if am < 0:
                continue
            sel = S['alpha'][best_t] == am
            ai = imgs[am]
            # GC alpha textures: an I4/I8/IA image whose intensity (or alpha) is the mask
            av = sample(ai, guv[sel])
            al[sel] = np.minimum(av[:, 3], av[:, :3].mean(1)) if (ai[..., 3] < 255).any() else av[:, :3].mean(1)
        al = np.minimum(al, col[:, 3])
        tx = (tex[:, 0] // a.ss).astype(int).clip(0, W - 1); ty = (tex[:, 1] // a.ss).astype(int).clip(0, H - 1)
        np.add.at(acc, (ty, tx), col); np.add.at(msk, (ty, tx), al); np.add.at(cnt, (ty, tx), 1)
        dist_all.append(best_d)
    cov = cnt > 0
    rgb = np.zeros((H, W, 3)); rgb[cov] = acc[cov, :3] / cnt[cov, None]
    am = np.full((H, W), 255.0); am[cov] = msk[cov] / cnt[cov]
    # dilation: grow covered texels into the gutter (4-neighbour average), a.dilate rings
    filled = cov.copy()
    for _ in range(a.dilate):
        nb = np.zeros((H, W, 3)); nm = np.zeros((H, W)); nc = np.zeros((H, W))
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sf = np.roll(filled, (dy, dx), (0, 1)); nb += np.roll(rgb, (dy, dx), (0, 1)) * sf[..., None]
            nm += np.roll(am, (dy, dx), (0, 1)) * sf; nc += sf
        grow = (~filled) & (nc > 0)
        rgb[grow] = nb[grow] / nc[grow, None]; am[grow] = nm[grow] / nc[grow]; filled |= grow
    base = np.asarray(patlas.convert('RGB').resize((W, H), Image.BILINEAR), float)
    rgb[~filled] = base[~filled]
    Image.fromarray(np.clip(rgb + 0.5, 0, 255).astype(np.uint8), 'RGB').save(out / 'atlas.png')
    d = np.concatenate(dist_all) if dist_all else np.zeros(1)
    rep = dict(tool='ps2_gctex_bake.py', drs_sha256=sha(db), bins=[hex(b) for b in bins], tpl=a.tpl,
               tpl_images=[dict(index=i, width=t.width, height=t.height, format=t.format) for i, t in enumerate(tims)],
               cast=str(cast), mesh_sha256=sha((cast / 'mesh.json').read_bytes()), size=[W, H], ss=a.ss, dilate=a.dilate,
               covered_texels=int(cov.sum()), samples=int(len(d)),
               distance_mm=dict(median=float(np.median(d)), p95=float(np.percentile(d, 95)), max=float(d.max())),
               gc_material_samples=mat_hits, mask=bool(any_alpha))
    if any_alpha:
        Image.fromarray(np.clip(am + 0.5, 0, 255).astype(np.uint8), 'L').save(out / 'mask.png')
        rep['mask_punched_texels'] = int(((am < 128) & cov).sum())
    (out / 'bake.json').write_text(json.dumps(rep, indent=1) + '\n')
    print(json.dumps({k: rep[k] for k in ('covered_texels', 'samples', 'distance_mm', 'mask')}))


if __name__ == '__main__':
    main()
