#!/usr/bin/env python3
"""Build private PS2 world cutout candidates from an explicit, hash-pinned policy.

No geometry is converted. Only allowlisted TR parts acquire new content-keyed
ARGB1555 textures and PT pass tags. Existing tex.pak entries are retained.
Requires numpy/Pillow; see docs/PS2_VEGETATION_CANDIDATES.md.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import re
import struct
import zlib

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent


def load_tool(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cb = load_tool("vegetation_cb_tex", HERE / "d367/charbake/cb_tex.py")
texpack = load_tool("vegetation_texpack", HERE / "d367/texpack.py")
POLICY_SCHEMA = "re4dc-ps2-vegetation-policy/1"
SIDECAR = struct.Struct("<4s7I")
PART = struct.Struct("<IIHHBBBB")


class CandidateError(ValueError):
    pass


def require(condition, why):
    if not condition:
        raise CandidateError(why)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_pinned(spec, base):
    require(isinstance(spec, dict) and "path" in spec and "sha256" in spec,
            "every source file requires path and sha256")
    path = Path(spec["path"])
    if not path.is_absolute():
        path = base / path
    data = path.read_bytes()
    require(sha(data) == spec["sha256"].lower(), f"source SHA mismatch: {path}")
    return data, path


def key_of_payload(payload):
    fnv = 2166136261
    for value in payload:
        fnv = ((fnv ^ value) * 16777619) & 0xffffffff
    return zlib.crc32(payload) & 0xffffffff, fnv


def parse_key(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{8}", value),
            "texture keys must be lowercase eight-digit CRC-FNV pairs")
    return tuple(int(x, 16) for x in value.split("-"))


def key_string(value):
    return "%08x-%08x" % value


def texture_info(blob, key=None):
    require(len(blob) >= 144, "short RE4DCTX package")
    info = cb.read_package(blob)
    require(info["data_offset"] == 144 and
            info["data_offset"] + info["data_size"] == len(blob), "texture payload extent")
    require(info["payload"] in (1, 2) and info["format"] in (0, 1, 2),
            "unsupported texture encoding")
    w, h = info["width"], info["height"]
    require(8 <= w <= 1024 and 8 <= h <= 1024 and
            w & (w - 1) == 0 and h & (h - 1) == 0, "invalid texture dimensions")
    payload = blob[info["data_offset"]:]
    if key is not None:
        require(key_of_payload(payload) == key, "texture key is not payload CRC/FNV")
    stored = info["header"][8]
    if stored == zlib.crc32(blob[48:]) & 0xffffffff:
        style = "body"
    elif stored == zlib.crc32(payload) & 0xffffffff:
        style = "legacy_payload"
    else:
        raise CandidateError("texture CRC matches neither canonical body nor legacy payload")
    info["crc_style"] = style
    return info


def parse_pack(blob):
    texpack.verify(blob)
    count = struct.unpack_from("<I", blob, 12)[0]
    result = {}
    for i in range(count):
        c, f, off, size = struct.unpack_from("<4I", blob, 2048 + 16 * i)
        result[c, f] = blob[off:off + size]
    return result


def parse_sidecar(data):
    require(len(data) >= 32, "short R4PW")
    h = SIDECAR.unpack_from(data)
    require(h[0] == b"R4PW" and h[1] == 1, "unsupported R4PW")
    require(len(data) == 32 + 16 * h[3] + 52 * h[2], "R4PW size/count mismatch")
    require(zlib.crc32(data[32:]) & 0xffffffff == h[5], "R4PW body CRC mismatch")
    parts = [PART.unpack_from(data, 32 + 16 * i) for i in range(h[3])]
    require(all(p[4] in (0, 1, 2) and p[5] in (0, 1, 2) for p in parts),
            "unsupported sidecar pass/cull")
    placement = data[32 + 16 * h[3]:]
    ids = []
    for i in range(h[2]):
        mesh, pid = struct.unpack_from("<HH", placement, 52 * i)
        require(mesh < h[4], "placement mesh outside R4PW mesh count")
        ids.append(pid)
    return h, parts, placement, ids


def parse_mesh(data, side_header):
    require(len(data) >= 112, "short R4IM")
    magic, version, size, crc, meshes, parts = struct.unpack_from("<4s5I", data)
    require(magic == b"R4IM" and version in (2, 3), "expected R4IM LOD version2/3")
    require(size == len(data) and crc == zlib.crc32(data[80:]) & 0xffffffff,
            "R4IM size or body CRC mismatch")
    require((meshes, parts) == (side_header[4], side_header[3]), "mesh/sidecar counts differ")
    return {"bytes": size, "crc": crc, "sha256": sha(data), "version": version}


def patch_ids(data, side_header, placement_ids, new_crc):
    require(len(data) >= 16 and len(data) % 32 == 0, "R4ID size/alignment")
    magic, version, count, crc = struct.unpack_from("<4s3I", data)
    require(magic == b"R4ID" and version == 1 and crc == side_header[5], "R4ID identity mismatch")
    require(count == max(placement_ids, default=-1) + 1 and
            len(data) == (16 + count + 31) // 32 * 32, "R4ID count/extent mismatch")
    out = bytearray(data)
    struct.pack_into("<I", out, 12, new_crc)
    require(out[:12] == data[:12] and out[16:] == data[16:], "R4ID mapping changed")
    return bytes(out)


def patch_cell(data, room_number, mesh, old_crc, new_crc):
    require(len(data) >= 32, "short PCL1 cell")
    magic, room, mcrc, scrc, mbytes, cells, portals, reserved = struct.unpack_from("<4s7I", data)
    require((magic, room, mcrc, scrc, mbytes, reserved) ==
            (b"PCL1", room_number, mesh["crc"], old_crc, mesh["bytes"], 0), "PCL1 identity mismatch")
    require(len(data) == 32 + 28 * cells + 24 * portals, "PCL1 geometry extent mismatch")
    for i in range(cells):
        values = struct.unpack_from("<6f2H", data, 32 + 28 * i)
        require(all(np.isfinite(values[:6])) and values[7] <= 24 and
                values[6] + values[7] <= portals, "PCL1 cell/portal range")
    out = bytearray(data)
    struct.pack_into("<I", out, 12, new_crc)
    require(out[:12] == data[:12] and out[16:] == data[16:], "PCL1 culling geometry changed")
    return bytes(out)


def pack_rgba(rgba, fmt):
    """Same rounding as ps2_room_r4im.pack16, without importing its private helpers."""
    q = np.clip(np.rint(rgba), 0, 255).astype(np.uint32)
    if fmt == 2:
        q = (q * 15 + 127) // 255
        return ((q[..., 3] << 12) | (q[..., 0] << 8) | (q[..., 1] << 4) | q[..., 2]).astype(np.uint16)
    require(fmt == 1, "candidate format must be ARGB1555")
    rgb = (q[..., :3] * 31 + 127) // 255
    return (((q[..., 3] >= 128).astype(np.uint32) << 15) |
            (rgb[..., 0] << 10) | (rgb[..., 1] << 5) | rgb[..., 2]).astype(np.uint16)


def make_texture(material, old_blob, base):
    key = parse_key(material["key"])
    info = texture_info(old_blob, key)
    require(info["format"] == 2 and info["payload"] == 1,
            "only native16 graded-alpha textures qualify; vertex-alpha/VQ cases need separate review")
    require(info["flags"] == 0, "nondefault texture flags need explicit handling")
    require(material.get("class") in ("vegetation", "fence"), "soft/unclassified materials cannot be converted")
    require(material.get("semantic_review") is True, "explicit semantic review required")
    threshold = material.get("threshold")
    require(type(threshold) is int and 1 <= threshold <= 255, "threshold must be1..255")
    source_bytes, source_path = read_pinned(material["source_png"], base)
    with Image.open(BytesIO(source_bytes)) as im:
        require(im.mode == "RGBA", "source PNG must carry explicit RGBA")
        source = np.asarray(im).copy()
    require(source.shape == (info["height"], info["width"], 4), "source texture dimensions differ")
    gain = np.asarray(material.get("rgb_gain"), dtype=np.float64)
    require(gain.shape == (3,) and np.isfinite(gain).all() and (gain > 0).all(),
            "three finite positive original forward texture gains required")
    target = source.astype(np.float64)
    target[..., :3] *= gain
    require(target[..., :3].max() <= 255 + 1e-6, "source RGB gain clips")
    # Prove source image/index/gain against the actual selected texture payload before editing alpha.
    old_words = pack_rgba(target, 2)
    reconstructed = cb.package_twiddled16("baseline proof", old_words, fmt=2)
    require(reconstructed[144:] == old_blob[144:], "source RGB/alpha/gain does not reproduce baseline payload")
    target[..., 3] = np.where(source[..., 3] >= threshold, 255, 0)
    pixels = pack_rgba(target, 1)
    new_blob = cb.package_twiddled16("PS2 PT " + material["key"] + " t" + str(threshold), pixels, fmt=1)
    new_key = key_of_payload(new_blob[144:])
    require(new_key != key, "threshold policy did not create a new texture key")
    require(texture_info(new_blob, new_key)["crc_style"] == "body", "new texture CRC is not canonical")
    _, old_rgba = cb.decode(old_blob)
    _, new_rgba = cb.decode(new_blob)
    require(set(np.unique(new_rgba[..., 3])).issubset({0, 255}), "candidate alpha is not binary")
    old_visible = old_rgba[..., 3] > 0
    current_mass = float(np.sum(old_rgba[..., 3], dtype=np.float64) / 255)
    retained = int(np.sum(new_rgba[..., 3] > 0))
    report = {
        "old_key": key_string(key), "new_key": key_string(new_key),
        "source_texture_index": material["source_texture_index"],
        "class": material["class"], "label": material.get("label", ""),
        "threshold": threshold, "rgb_gain": gain.tolist(),
        "source_png_sha256": sha(source_bytes), "baseline_payload_reproduced": True,
        "baseline_crc_style": info["crc_style"], "old_blob_sha256": sha(old_blob),
        "new_blob_sha256": sha(new_blob), "old_payload_bytes": info["data_size"],
        "new_payload_bytes": len(new_blob) - 144,
        "current_visible_pixel_loss": float(1 - np.sum((new_rgba[..., 3] > 0) & old_visible) /
                                             max(1, np.sum(old_visible))),
        "alpha_coverage_relative_change": retained / max(current_mass, 1) - 1,
        "rgb_requantization_mean_absolute_error": float(np.mean(
            np.abs(old_rgba[..., :3].astype(float) - new_rgba[..., :3])[old_visible])),
    }
    return new_key, new_blob, report


def prove_sidecar_edit(before, after, changed):
    old_h, old_parts, old_place, _ = parse_sidecar(before)
    new_h, new_parts, new_place, _ = parse_sidecar(after)
    require(old_h[:5] == new_h[:5] and old_h[6:] == new_h[6:], "R4PW non-CRC header changed")
    require(old_place == new_place, "placements changed")
    for i, (old, new) in enumerate(zip(old_parts, new_parts)):
        if i in changed:
            require(old[4] == 2 and new[4] == 1 and old[2:4] == new[2:4] and old[5:] == new[5:],
                    "selected part changed beyond key and TR-to-PT pass")
        else:
            require(old == new, "unselected part changed")
        require((old[4] == 0) == (new[4] == 0), "opaque occluder set changed")
    return {"placements_byte_identical": True, "unchanged_parts_byte_identical": True,
            "opaque_part_set_identical": True, "only_selected_keys_and_pass_changed": True,
            "changed_parts": sorted(changed)}


def build_room(room_spec, packages, base):
    room = room_spec["room"]
    require(re.fullmatch(r"r[0-9a-f]{3}", room) is not None, "room must be rNNN")
    side, _ = read_pinned(room_spec["r4pw"], base)
    mesh_bytes, _ = read_pinned(room_spec["mesh"], base)
    ids, _ = read_pinned(room_spec["ids"], base)
    h, parts, placement, placement_ids = parse_sidecar(side)
    mesh = parse_mesh(mesh_bytes, h)
    require("cell" in room_spec or room != "r100", "r100 requires its pinned interior cell")
    output = bytearray(side)
    changed, materials, added = set(), [], {}
    selectors = set()
    for material in room_spec["materials"]:
        old_key = parse_key(material["key"])
        tx = material["source_texture_index"]
        require(type(tx) is int and 0 <= tx <= 255, "invalid source texture index")
        require((old_key, tx) not in selectors, "duplicate material selector")
        selectors.add((old_key, tx))
        selected = [i for i, p in enumerate(parts) if p[:2] == old_key and p[6] == tx and p[4] == 2]
        require(selected, f"no TR parts for {room} texture{tx} key{material['key']}")
        require(all(parts[i][7] == 0 for i in selected), "vertex-alpha marked parts must remain TR")
        require(old_key in packages, "selected baseline texture is missing")
        new_key, new_blob, report = make_texture(material, packages[old_key], base)
        target_pool = packages | added
        if new_key in target_pool:
            existing = target_pool[new_key]
            ex = texture_info(existing, new_key)
            require(ex["crc_style"] == "body", "existing-key reuse needs a canonical texture body CRC")
            ni = texture_info(new_blob, new_key)
            require(all(ex[k] == ni[k] for k in ("width", "height", "format", "flags", "payload")) and
                    existing[144:] == new_blob[144:], "content-key collision has different texture metadata")
            new_blob = existing  # Existing baseline bytes remain immutable, even its descriptor label.
            report["reused_existing_key"] = True
            report["new_blob_sha256"] = sha(existing)
        else:
            added[new_key] = new_blob
            report["reused_existing_key"] = False
        for i in selected:
            require((parts[i][2], parts[i][3]) ==
                    (texture_info(new_blob)["width"], texture_info(new_blob)["height"]),
                    "sidecar/texture dimensions differ")
            struct.pack_into("<II", output, 32 + 16 * i, *new_key)
            output[32 + 16 * i + 12] = 1
            changed.add(i)
        report["parts"] = selected
        materials.append(report)
    require(changed, "room policy contains no candidate changes")
    new_crc = zlib.crc32(output[32:]) & 0xffffffff
    struct.pack_into("<I", output, 20, new_crc)
    proof = prove_sidecar_edit(side, bytes(output), changed)
    new_ids = patch_ids(ids, h, placement_ids, new_crc)
    files = {"ps2-world.re4mesh": mesh_bytes, "ps2-world.r4pw": bytes(output), "ps2-world.ids": new_ids}
    proof.update({"mesh_byte_identical": True, "mesh_sha256": mesh["sha256"],
                  "ids_mapping_byte_identical": True, "old_sidecar_crc": f"0x{h[5]:08x}",
                  "new_sidecar_crc": f"0x{new_crc:08x}", "materials": materials})
    if "cell" in room_spec:
        cell, _ = read_pinned(room_spec["cell"], base)
        files["interior.cell"] = patch_cell(cell, int(room[1:], 16), mesh, h[5], new_crc)
        proof["interior_cell_identity_only"] = True
        proof["interior_cell_geometry_sha256"] = sha(cell[32:])
        proof["required_kPcSidecarUse"] = f"0x{new_crc:08x}"
    new_parts = parse_sidecar(bytes(output))[1]
    merged = packages | added
    for label, part_set, pool in (("before", parts, packages), ("after", new_parts, merged)):
        keys = {p[:2] for p in part_set}
        require(all(k in pool for k in keys), "world texture coverage incomplete")
        proof[label + "_world_unique_payload_bytes"] = sum(texture_info(pool[k])["data_size"] for k in keys)
    proof["file_sha256"] = {name: sha(data) for name, data in files.items()}
    return files, added, proof


def build_policy(policy_path, output, selected_rooms, fixture_prefix=None):
    policy_path, output = Path(policy_path), Path(output)
    require(not output.exists(), "output already exists; use a fresh private directory")
    raw = policy_path.read_bytes()
    policy = json.loads(raw)
    require(policy.get("schema") == POLICY_SCHEMA, "unsupported policy schema")
    base = policy_path.parent
    pack_bytes, pack_path = read_pinned(policy["tex_pak"], base)
    packages = parse_pack(pack_bytes)
    rooms = policy["rooms"]
    require(len({r["room"] for r in rooms}) == len(rooms), "duplicate room in policy")
    require(set(selected_rooms) and set(selected_rooms) <= {r["room"] for r in rooms},
            "explicit room selection must exist in policy")
    room_files, proofs, additions = {}, {}, {}
    # All validation completes in memory before any output is created.
    for room_spec in rooms:
        if room_spec["room"] not in selected_rooms:
            continue
        files, new, proof = build_room(room_spec, packages | additions, base)
        room_files[room_spec["room"]] = files
        proofs[room_spec["room"]] = proof
        for key, value in new.items():
            texpack.add(additions, key, value, room_spec["room"])
    merged = packages | additions
    new_pack, count = texpack.build(merged)
    texpack.verify(new_pack)
    reread = parse_pack(new_pack)
    require(all(reread[k] == v for k, v in packages.items()), "baseline tex.pak entry changed")
    report = {"schema": "re4dc-ps2-vegetation-candidate/1", "status": "OFFLINE_CANDIDATE_NOT_ACCEPTED",
              "policy_sha256": sha(raw), "baseline_tex_pak": str(pack_path),
              "baseline_tex_pak_sha256": sha(pack_bytes), "candidate_tex_pak_sha256": sha(new_pack),
              "baseline_pack_entries_byte_identical": True, "pack_entries": count,
              "new_texture_count": len(additions), "rooms": proofs,
              "runtime_gates_pending": ["matched frame/scene/enemy evidence", "render-only STRICT",
                 "TEX_CHECK", "MCHECK_PT SRCALPHA/INVSRCALPHA", "zero GC fallback",
                 "heap4/VRAM", "r100 PCCULL when applicable", "user approval of matched stills"]}
    output.mkdir(parents=True)
    for room, files in room_files.items():
        folder = output / "rooms" / room
        folder.mkdir(parents=True)
        for name, blob in files.items():
            (folder / name).write_bytes(blob)
            require((folder / name).read_bytes() == blob, "output readback mismatch")
    (output / "textures").mkdir()
    for key, blob in additions.items():
        (output / "textures" / (key_string(key) + ".re4tex")).write_bytes(blob)
    (output / "tex.pak").write_bytes(new_pack)
    require(sha((output / "tex.pak").read_bytes()) == report["candidate_tex_pak_sha256"],
            "candidate tex.pak readback mismatch")
    (output / "policy.json").write_bytes(raw)
    root = fixture_prefix.rstrip("/") if fixture_prefix else output.as_posix()
    replace = {"dc/tex.pak": root + "/tex.pak"}
    for room, files in room_files.items():
        for name in files:
            replace[f"dc/native/{room}/{name}"] = f"{root}/rooms/{room}/{name}"
    (output / "fixture-replace.json").write_text(json.dumps({"replace": replace}, indent=2) + "\n")
    (output / "proof.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("policy", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--room", action="append", required=True, help="explicit room selection, repeat as needed")
    ap.add_argument("--fixture-prefix", help="absolute staging-host path corresponding to output")
    args = ap.parse_args()
    try:
        report = build_policy(args.policy, args.output, args.room, args.fixture_prefix)
    except (CandidateError, OSError, KeyError, ValueError) as e:
        ap.exit(1, f"vegetation candidate rejected: {e}\n")
    print(json.dumps({"status": report["status"], "rooms": sorted(report["rooms"]),
                      "new_texture_count": report["new_texture_count"],
                      "candidate_tex_pak_sha256": report["candidate_tex_pak_sha256"]}))


if __name__ == "__main__":
    main()
