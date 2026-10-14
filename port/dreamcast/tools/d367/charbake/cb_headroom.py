#!/usr/bin/env python3
"""cb_headroom.py: Leon's textures at 2x for LEON_LIGHT_HEADROOM=1 (lane lp2, 2026-10-14).

The PVR's MODULATE maps vertex colour 255 to 1.0x, so a lit Leon can never be brighter than his texture. The GameCube
TEV scales Leon's lit colour by x2 (r100) / x1 (r101) / x4 (r10b), and the PS2 GS by up to 2x (0x80 = 1.0). This tool
stores Leon's texels at 2x (clamped). LEON_LIGHT_HEADROOM=1 halves every Leon vertex colour: the flat constant 255
becomes 128, and the lit colour matrix is multiplied by 0.5. So the flat image is unchanged, and lit vertices can
reach 2.0x of the original texel. Same keys, sizes and formats: 0 bytes of VRAM, 0 ms.

Doubling works on the stored integer levels:
  RGB565             r5, g6, b5 -> min(2v, max)
  ARGB4444/ARGB1555  RGB only; alpha kept
  VQ                 the codebook entries; indices kept
There is no resample and no new dithering: each level becomes the level at twice its value, and the expanded 8-bit
value is within 1 of twice the original.

Keys: every Leon atlas, hair colour and hair pair key of charbake_variants.h (all CHARBAKE_TOGGLE variants), plus the
pl08 atlas (7506e95f-68cf2211). Keys absent from the pak are listed and skipped.

A pak made by this tool is ONLY for LEON_LIGHT_HEADROOM=1 binaries. With a knob-off binary, Leon draws 2x too bright;
a headroom binary with a normal pak draws Leon at half brightness.

usage: cb_headroom.py <tex.pak> <out.pak> [--variants <charbake_variants.h>] [--report <out.json>]
Python 3 with numpy (Windows Python, like the rest of charbake). Inputs and outputs are private game assets; never
commit them.
"""
from __future__ import annotations

import argparse, json, re, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cb_tex as T  # noqa: E402

PL08 = (0x7506e95f, 0x68cf2211)


def leon_keys(header: Path) -> list:
    """Leon atlas, hair colour and hair pair keys of every variant row (not the Ganado columns)."""
    keys = [PL08]
    for row in re.findall(r'\{"\w+",(.*?)\}\},', header.read_text()):
        n = [int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]+)U?', row)]
        # leon crc, fnv, ganado crc, fnv, hair_colour_crc[2], hair_colour_fnv[2], hair_pair_crc[2], hair_pair_fnv[2]
        assert len(n) == 12, row
        keys += [(n[0], n[1]), (n[4], n[6]), (n[5], n[7]), (n[8], n[10]), (n[9], n[11])]
    out = []
    for k in keys:
        if k not in out:
            out.append(k)
    return out


def double16(v: np.ndarray, fmt: int):
    """uint16 texels -> (texels with RGB levels doubled and clamped, bool mask of texels where a channel clipped)."""
    v = v.astype(np.uint32)
    if fmt == T.RGB565:
        f = [(11, 31), (5, 63), (0, 31)]; keep = np.zeros_like(v)
    elif fmt == T.ARGB1555:
        f = [(10, 31), (5, 31), (0, 31)]; keep = v & 0x8000
    elif fmt == T.ARGB4444:
        f = [(8, 15), (4, 15), (0, 15)]; keep = v & 0xF000
    else:
        raise ValueError('format %d' % fmt)
    out = keep.copy()
    clip = np.zeros(v.shape, bool)
    for sh, mx in f:
        c = (v >> sh) & mx
        clip |= 2 * c > mx
        out |= np.minimum(2 * c, mx) << sh
    return out.astype('<u2'), clip


def double_package(blob: bytes):
    p = T.read_package(blob)
    w, h, fmt = p['width'], p['height'], p['format']
    out = bytearray(blob)
    off = p['data_offset']
    if p['payload'] == T.TWIDDLED:
        new, clip = double16(np.frombuffer(blob, '<u2', w * h, off), fmt)
        out[off:off + w * h * 2] = new.tobytes()
        frac = float(clip.mean())
    elif p['payload'] == T.VQ:
        new, clip = double16(np.frombuffer(blob, '<u2', 1024, off), fmt)
        out[off:off + 2048] = new.tobytes()
        idx = np.frombuffer(blob, np.uint8, (w // 2) * (h // 2), off + 2048)
        frac = float(clip.reshape(256, 4)[idx].mean())        # texel share, weighted by codebook use
    else:
        raise ValueError('payload %d not handled' % p['payload'])
    res = T._finish(out, p)
    return res, dict(name=p['name'], size=[w, h], format=fmt, payload=p['payload'], clipped_texels=round(frac, 5),
                     mean_before=round(float(T.decode(blob)[1][..., :3].mean()), 2),
                     mean_after=round(float(T.decode(res)[1][..., :3].mean()), 2))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('pak')
    ap.add_argument('out')
    ap.add_argument('--variants', type=Path,
                    default=Path(__file__).resolve().parents[3] / 'game' / 'charbake_variants.h')
    ap.add_argument('--report', type=Path)
    a = ap.parse_args(argv)
    index = T.pak_index(a.pak)
    changes, report, absent = {}, {}, []
    for k in leon_keys(a.variants):
        if k not in index:
            absent.append(T.key_str(k)); continue
        new, row = double_package(T.pak_get(a.pak, k))
        changes[k] = new; report[T.key_str(k)] = row
        print('%s %-12s %dx%d fmt %d payload %d: mean %.1f -> %.1f, clipped %.2f%% of texels' % (
            T.key_str(k), row['name'], *row['size'], row['format'], row['payload'], row['mean_before'],
            row['mean_after'], 100 * row['clipped_texels']))
    if absent:
        print('absent from the pak (skipped):', ' '.join(absent))
    data = T.pak_with(a.pak, changes)
    Path(a.out).write_bytes(data)
    print('wrote %s (%d bytes, sha256 %s)' % (a.out, len(data), T.sha256(data)))
    if a.report:
        a.report.write_text(json.dumps(dict(pak=str(a.pak), out=str(a.out), sha256=T.sha256(data), gain=2,
                                            packages=report, absent=absent), indent=1))


if __name__ == '__main__':
    main()
