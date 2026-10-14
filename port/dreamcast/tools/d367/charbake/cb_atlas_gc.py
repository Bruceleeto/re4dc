#!/usr/bin/env python3
"""cb_atlas_gc.py: Leon's play atlases with every source tile re-made from the GameCube originals (issue #22).

Leon's 512x512 RGB565 atlas (ec255e66-76812316, and the pl08 atlas 7506e95f-68cf2211, which shares the face, hair,
gloves and belt tiles) was assembled from the character prototype's source PNGs (character-prototype-20260925
textures/<key>.png). Those PNGs are the decoded Dreamcast VQ packages of the GameCube textures, not the GameCube
textures: each PNG equals its VQ package's decode exactly (face dde6f32a: inf dB against the VQ decode, 35.9 dB against
the GameCube 256x128 CMPR face). The atlas then resampled them into its 2-texel-guttered tiles, so the play face carries
the VQ blocking plus one more resample: 34.2 dB against the GameCube face, below the PS2's own 128x128 face (35.3 dB).

This tool rebuilds a tile from the GameCube texture (the decoded CMPR / IA8 TPL image, leon_sources' gc-*.png): one
Lanczos resample to the tile's inner size, RGB565 with serpentine Floyd-Steinberg (cb_tex.quant565 'fs'), the gutter
re-made by the rule the atlas already uses (checked per tile: wrap). Same key, size, format and layout: the UVs, the
VRAM (524,288 bytes) and the draw cost are unchanged; only the texels change. The face goes from 34.2 to 41.6 dB.

usage: cb_atlas_gc.py <atlas.re4tex> <out.re4tex> --gc-dir <dir of gc-plXXX-N.png> --tiles <leon-4k asset-report.json>
                      [--only-equal-to <pl00 atlas.re4tex>] [--report <out.json>] [--pak <tex.pak> <out.pak> <key>]
  --only-equal-to: rebuild only the tiles whose texels equal that atlas's (the pl08 atlas: its pl08-only body tiles
                   have no GameCube pl00 source here and are kept).
  --pak: also write a copy of <tex.pak> with the package under <key> (crc-fnv) replaced (cb_tex.pak_with).
Windows Python (numpy + PIL), like the rest of charbake. Inputs and outputs are private game assets.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cb_tex as T  # noqa: E402

# atlas source tile (prototype PNG name) -> the GameCube texture it was converted from (pl00.drs TPL images, wep02 for
# the gloves: matched by size and PSNR against the VQ decode, 33..41 dB, the next candidate below 21 dB)
GC_SOURCE = {'15f7e18c-11dc93e0.png': 'gc-pl005-3.png', '1f625c95-7aed4809.png': 'gc-pl005-0.png',
             '23f6b950-9ea131c1.png': 'gc-pl005-2.png', '2a8a368f-76c02b02.png': 'gc-pl005-7.png',
             '7a9de1fd-0e415f15.png': 'gc-pl007-2.png', '878b23c0-e7038833.png': 'gc-pl005-5.png',
             'ac381b1a-3ade84b1.png': 'gc-pl007-0.png', 'cd026c6d-3a54bfa9.png': 'gc-pl011-0.png',
             'dde6f32a-0b7cfdcf.png': 'gc-pl007-4.png'}


def psnr(a, b):
    m = ((a.astype(float) - b.astype(float)) ** 2).mean()
    return 99.0 if m == 0 else float(10 * np.log10(255 ** 2 / m))


def rgb(tex16):
    return T.expand16(tex16, T.RGB565)[..., :3]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('atlas', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--gc-dir', type=Path, required=True)
    ap.add_argument('--tiles', type=Path, required=True)
    ap.add_argument('--only-equal-to', type=Path)
    ap.add_argument('--report', type=Path)
    ap.add_argument('--pak', nargs=3, metavar=('PAK', 'OUT', 'KEY'))
    a = ap.parse_args(argv)
    blob = a.atlas.read_bytes()
    p = T.read_package(blob)
    if (p['width'], p['height'], p['format'], p['payload']) != (512, 512, T.RGB565, T.TWIDDLED):
        raise SystemExit('expected a 512x512 RGB565 twiddled atlas')
    w = h = 512
    data = blob[p['data_offset']:p['data_offset'] + p['data_size']]
    tex = np.frombuffer(data, '<u2', w * h)[T.twiddle_index(w, h)].copy()     # [y, x], image rows
    ref = None
    if a.only_equal_to:
        rb = a.only_equal_to.read_bytes(); rp = T.read_package(rb)
        ref = np.frombuffer(rb[rp['data_offset']:rp['data_offset'] + rp['data_size']], '<u2', w * h)[T.twiddle_index(w, h)]
    tiles = json.loads(a.tiles.read_text())['source_uv_tiles']
    report = {}
    for _, t in sorted(tiles.items()):
        name = t['source_image']
        x, y, tw_, th, iw, ih = t['x'], t['y'], t['width'], t['height'], t['inner_width'], t['inner_height']
        yy = h - y - th                                    # the image rows run opposite to the Blender tile layout
        old = tex[yy:yy + th, x:x + tw_].copy()
        row = dict(tile=[x, y, tw_, th], inner=[iw, ih])
        if ref is not None and not np.array_equal(old, ref[yy:yy + th, x:x + tw_]):
            report[name] = dict(row, kept='differs from --only-equal-to (no GameCube source here)')
            continue
        inner = old[2:2 + ih, 2:2 + iw]
        rules = {m: float((np.pad(inner, 2, mode=m) == old).mean()) for m in ('wrap', 'edge')}
        rule = max(rules, key=rules.get)
        if rules[rule] < 0.99:
            raise SystemExit('%s: gutter rule not recognised %s' % (name, rules))
        gc = np.asarray(Image.open(a.gc_dir / GC_SOURCE[name]).convert('RGB'))
        # orientation: the one under which the current tile matches the GameCube image better
        small = [np.asarray(Image.fromarray(g).resize((iw, ih), Image.LANCZOS)) for g in (gc, gc[::-1])]
        flip = psnr(rgb(inner), small[1]) > psnr(rgb(inner), small[0])
        new_inner = T.quant565(small[flip].astype(np.float64), 'fs')
        tex[yy:yy + th, x:x + tw_] = np.pad(new_inner, 2, mode=rule)
        src = gc[::-1] if flip else gc
        up = lambda t16: np.asarray(Image.fromarray(rgb(t16)).resize((gc.shape[1], gc.shape[0]), Image.BICUBIC))
        row.update(gc=GC_SOURCE[name], gutter=rule, flipped=bool(flip),
                   before_db=round(psnr(up(inner), src), 2), after_db=round(psnr(up(new_inner), src), 2))
        report[name] = row
        print('%s <- %s: %.2f -> %.2f dB vs GameCube' % (name, GC_SOURCE[name], row['before_db'], row['after_db']))
    out = T.replace_texels16(blob, tex)
    a.out.write_bytes(out)
    print('wrote %s (%d bytes, sha256 %s)' % (a.out, len(out), T.sha256(out)))
    if a.report:
        a.report.write_text(json.dumps(dict(atlas=str(a.atlas), out=str(a.out), sha256=T.sha256(out), tiles=report),
                                       indent=1))
    if a.pak:
        pak, pout, key = a.pak
        Path(pout).write_bytes(T.pak_with(pak, {T.parse_key(key): out}))
        print('wrote %s' % pout)


if __name__ == '__main__':
    main()
