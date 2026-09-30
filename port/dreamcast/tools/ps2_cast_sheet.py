#!/usr/bin/env python3
"""Look sheet for converted characters (lane ps2cast): several character meshes side by side in the same
views and poses, rendered offline with a z-buffer rasterizer (orthographic).

Rows per model: the runtime look (texture colour only: coarse_ganado_cast.cpp draws cast chunks with
lighting off, a constant colour) in front / side / back / a posed three-quarter view, then flat grey
shading with the triangle edges (geometry density) front and posed. Textures are the shipped packages
decoded (VQ as the runtime uploads it) when given as .re4tex, else PNGs.

Model specs (JSON list) accept:
  {"label": ..., "mesh": <re4dc-approved-render-mesh-1 json>, "texture": <.re4tex | .png>}
  {"label": ..., "cast_source": <cast source.json (GC source infos with parts)>, "textures": <dir of <key>.png>}
Poses: pose-samples.json ('samples'[k]['world'] per bone; skin = world x inverse(rest)); the rest matrices
come from each model's bones (all bind the same GC skeleton).

usage: ps2_cast_sheet.py <spec.json> <out.png> [--poses pose-samples.json --pose K] [--title T]
"""
import argparse, json, math, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HEADER = struct.Struct("<8s10I")
TEXTURE = struct.Struct("<64s8I")


def untwiddle_index(w, h):
    m = min(w, h)

    def spread(v):
        r = np.zeros_like(v)
        for b in range(10):
            r |= (v & (1 << b)) << b
        return r
    y, x = np.mgrid[0:h, 0:w]
    return (spread(y & (m - 1)) | (spread(x & (m - 1)) << 1)) + (x // m) * m * m + (y // m) * m * m


def decode_re4tex(path):
    """RE4DCTX first texture -> RGBA (character-prototype g_re4tex.py, RGB565 / VQ / twiddled)."""
    b = Path(path).read_bytes()
    magic, ver, hsize, tsize, count, toff, doff, dlen, crc, nimg, _ = HEADER.unpack_from(b, 0)
    name, w, h, fmt, off, size, flags, payload, _ = TEXTURE.unpack_from(b, toff)
    raw = b[off:off + size]
    if payload == 2:
        cb = np.frombuffer(raw[:2048], dtype="<u2").reshape(256, 4)
        idx = np.frombuffer(raw[2048:2048 + (w // 2) * (h // 2)], dtype=np.uint8)
        blocks = cb[idx[untwiddle_index(w // 2, h // 2)]]
        t = np.zeros((h, w), dtype=np.uint16)
        t[0::2, 0::2] = blocks[..., 0]; t[1::2, 0::2] = blocks[..., 1]
        t[0::2, 1::2] = blocks[..., 2]; t[1::2, 1::2] = blocks[..., 3]
    else:
        t = np.frombuffer(raw, dtype="<u2")[:w * h]
        if payload == 1:
            t = t[untwiddle_index(w, h)]
        t = t.reshape(h, w)
    t = t.astype(np.uint32)
    assert fmt == 0, 'RGB565 only'
    r, g, bb = (t >> 11) & 31, (t >> 5) & 63, t & 31
    return np.stack([r * 255 // 31, g * 255 // 63, bb * 255 // 31, np.full_like(r, 255)], -1).astype(np.uint8)


def load_texture(p):
    p = Path(p)
    return decode_re4tex(p) if p.suffix == '.re4tex' else np.asarray(Image.open(p).convert('RGBA'))


def load_model(spec):
    """-> dict(pos (N,3), weights [[(b,w)]], tris (T,3), uv (T,3,2), tex_of_tri (T,), textures [RGBA], rest (34,4,4))"""
    if 'mesh' in spec:
        m = json.loads(Path(spec['mesh']).read_text())
        tris = np.asarray([[c['vertex'] for c in t['corners']] for t in m['triangles']])
        uv = np.asarray([[c['uv'] for c in t['corners']] for t in m['triangles']], float)
        return dict(pos=np.asarray(m['positions_mm'], float), weights=m['weights'], tris=tris, uv=uv,
                    tex_of_tri=np.zeros(len(tris), int), textures=[load_texture(spec['texture'])],
                    rest=np.asarray([b['rest'] for b in m['bones']]), label=spec['label'])
    s = json.loads(Path(spec['cast_source']).read_text())
    pos, weights, tris, uv, tt, keys = [], [], [], [], [], []
    for info in s['infos']:
        base = len(pos)
        pos += info['positions']
        weights += [info['weights'][p] for p in info['palette_ids']]
        for part in info['parts']:
            if part['texture'] not in keys:
                keys.append(part['texture'])
            for t in part['triangles']:
                tris.append([base + c[0] for c in t])
                uv.append([info['uv'][str(c[2])] for c in t])
                tt.append(keys.index(part['texture']))
    tex = [np.asarray(Image.open(Path(spec['textures']) / f'{k}.png').convert('RGBA')) for k in keys]
    return dict(pos=np.asarray(pos, float), weights=weights, tris=np.asarray(tris), uv=np.asarray(uv, float),
                tex_of_tri=np.asarray(tt), textures=tex, rest=np.asarray([b['rest'] for b in s['bones']]), label=spec['label'])


def posed(model, world):
    if world is None:
        return model['pos']
    mats = np.asarray(world) @ np.linalg.inv(model['rest'])
    h = np.c_[model['pos'], np.ones(len(model['pos']))]
    out = np.zeros_like(model['pos'])
    for i, w in enumerate(model['weights']):
        m = sum(v * mats[b] for b, v in w)
        out[i] = (m @ h[i])[:3]
    return out


def view_matrix(yaw_deg, pitch_deg=0):
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    rx = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]])
    return rx @ ry


def render(model, pos, R, size, scale, center, mode='texture'):
    W, H = size
    img = np.zeros((H, W, 3), np.float32) + np.array([58, 62, 70], np.float32)
    zb = np.full((H, W), -np.inf, np.float32)
    v = (pos - center) @ R.T
    sx = W / 2 + v[:, 0] * scale
    sy = H / 2 - v[:, 1] * scale
    sz = v[:, 2]
    light = np.array([0.35, 0.55, 0.75]); light /= np.linalg.norm(light)
    edges = []
    for ti, t in enumerate(model['tris']):
        x = sx[t]; y = sy[t]; z = sz[t]
        area = (x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0])
        if abs(area) < 1e-9:
            continue
        x0, x1 = max(int(math.floor(x.min())), 0), min(int(math.ceil(x.max())), W - 1)
        y0, y1 = max(int(math.floor(y.min())), 0), min(int(math.ceil(y.max())), H - 1)
        if x0 > x1 or y0 > y1:
            continue
        gy, gx = np.mgrid[y0:y1 + 1, x0:x1 + 1] + 0.5
        w0 = ((x[1] - gx) * (y[2] - gy) - (x[2] - gx) * (y[1] - gy)) / area
        w1 = ((x[2] - gx) * (y[0] - gy) - (x[0] - gx) * (y[2] - gy)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        m = inside & (zz > sub)
        if not m.any():
            continue
        sub[m] = zz[m]
        if mode == 'texture':
            tex = model['textures'][model['tex_of_tri'][ti]]
            th, tw = tex.shape[:2]
            uv = model['uv'][ti]
            u = (w0 * uv[0, 0] + w1 * uv[1, 0] + w2 * uv[2, 0])[m]
            vv = (w0 * uv[0, 1] + w1 * uv[1, 1] + w2 * uv[2, 1])[m]
            px = np.clip((u * tw).astype(int), 0, tw - 1)
            py = np.clip((vv * th).astype(int), 0, th - 1)
            img[y0:y1 + 1, x0:x1 + 1][m] = tex[py, px, :3]
        else:
            p3 = v[t]
            n = np.cross(p3[1] - p3[0], p3[2] - p3[0]); n /= (np.linalg.norm(n) or 1)
            c = 60 + 170 * abs(float(n @ light))
            img[y0:y1 + 1, x0:x1 + 1][m] = c
            edges.append((ti, t))
    out = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    if mode != 'texture':
        d = ImageDraw.Draw(out)
        for ti, t in edges:
            pts = [(float(sx[k]), float(sy[k])) for k in t]
            # draw only edges of front-facing, visible-ish triangles: test the centroid depth
            cx, cy = int(sum(p[0] for p in pts) / 3), int(sum(p[1] for p in pts) / 3)
            if 0 <= cx < W and 0 <= cy < H and abs(zb[cy, cx] - sz[t].mean()) < 25:
                d.line(pts + [pts[0]], fill=(20, 20, 20), width=1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec', type=Path); ap.add_argument('out', type=Path)
    ap.add_argument('--poses'); ap.add_argument('--pose', type=int, default=0); ap.add_argument('--title', default='')
    a = ap.parse_args()
    specs = json.loads(a.spec.read_text())
    models = [load_model(s) for s in specs]
    world = json.loads(Path(a.poses).read_text())['samples'][a.pose]['world'] if a.poses else None
    W, H, scale = 240, 470, 0.235
    views = [('front', 0, 0, None), ('side', 90, 0, None), ('back', 180, 0, None), ('posed 3/4', 35, 8, world)]
    geo = [('front', 0, 0, None), ('posed 3/4', 35, 8, world)]
    try:
        font = ImageFont.truetype('arial.ttf', 15); small = ImageFont.truetype('arial.ttf', 12)
    except OSError:
        font = small = ImageFont.load_default()
    label_w = 190
    sheet = Image.new('RGB', (label_w + W * (len(views) + len(geo)), 34 + H * len(models)), (30, 32, 36))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), a.title, fill=(235, 235, 235), font=font)
    for c, (name, *_rest) in enumerate(views + geo):
        d.text((label_w + c * W + 6, 18), name + (' (texture)' if c < len(views) else ' (geometry)'), fill=(200, 200, 200), font=small)
    for r, m in enumerate(models):
        rest_pos = m['pos']
        center = np.array([0.0, (rest_pos[:, 1].min() + rest_pos[:, 1].max()) / 2, 0.0])
        for c, (name, yaw, pitch, wv) in enumerate(views + geo):
            p = posed(m, wv)
            cen = center if wv is None else np.array([p[:, 0].mean(), center[1], p[:, 2].mean()])
            im = render(m, p, view_matrix(yaw, pitch), (W, H), scale, cen, 'texture' if c < len(views) else 'geometry')
            sheet.paste(im, (label_w + c * W, 34 + r * H))
        lines = m['label'].split('\n')
        for k, line in enumerate(lines):
            d.text((8, 34 + r * H + 10 + 18 * k), line, fill=(235, 235, 235), font=font if k == 0 else small)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(a.out)
    print('sheet', a.out, sheet.size)


if __name__ == '__main__':
    main()
