#!/usr/bin/env python3
"""Audit full PS2 CH23 ESL records and emit a PRIVATE fresh-read patch table.

Input GC records are big endian; PS2 records are little endian. All 32 bytes
are retained, matching le_mirror.py's existing ESL conversion. No original
game bytes, generated headers, or per-record audit files belong in Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

FORMAT = "BBBBIHBB3h3hHh4s"
ROW_SIZE = 32
TARGETS = {1: {0x10F, 0x11D, 0x11E, 0x11F, 0x200}, 2: {0x200}}
ROOM_INDEX = 14
FIELD_NAMES = ("be_flag", "id", "type", "set", "flag", "hp", "emset_no",
               "Character", "pos_x", "pos_y", "pos_z", "rot_x", "rot_y",
               "rot_z", "room", "Guard_r", "reserved")
QUAL_SCHEMA = "re4dc-ps2-enemy-activation-v1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode(data: bytes, endian: str) -> list[tuple]:
    if not data or len(data) > 0x2000 or len(data) % ROW_SIZE:
        raise ValueError("ESL size must be a nonzero multiple of 32, at most 8192")
    return list(struct.iter_unpack(endian + FORMAT, data))


def as_le(row: tuple) -> bytes:
    return struct.pack("<" + FORMAT, *row)


def fields(row: tuple) -> dict:
    return {name: (value.hex() if isinstance(value, bytes) else value)
            for name, value in zip(FIELD_NAMES, row)}


def audit_list(list_no: int, gc: bytes, ps2: bytes) -> tuple[dict, list, list, dict]:
    old, new = decode(gc, ">"), decode(ps2, "<")
    if len(old) != len(new):
        raise ValueError(f"list {list_no}: source row counts differ")
    baseline, replacement, records, held = [], [], [], {}
    for index, (before, after) in enumerate(zip(old, new)):
        old_room, new_room = before[ROOM_INDEX], after[ROOM_INDEX]
        if old_room not in TARGETS[list_no] and new_room not in TARGETS[list_no]:
            continue
        if old_room != new_room:
            raise ValueError(f"list {list_no} row {index}: room identity changed")
        room = f"r{new_room:03x}"
        old_bytes, new_bytes = as_le(before), as_le(after)
        baseline.append((index, old_bytes))
        if old_bytes != new_bytes:
            replacement.append((index, new_bytes))
        before_fields, after_fields = fields(before), fields(after)
        changed = [name for name in FIELD_NAMES if before_fields[name] != after_fields[name]]
        alive_changed = bool((before[0] ^ after[0]) & 1)
        if alive_changed:
            held.setdefault(room, []).append(index)
        records.append({"index": index, "room": room, "before": before_fields,
                        "after": after_fields, "changed_fields": changed,
                        "alive_changed": alive_changed,
                        "gc_le_sha256": sha256(old_bytes), "ps2_sha256": sha256(new_bytes)})
    missing = TARGETS[list_no] - {int(row["room"][1:], 16) for row in records}
    if missing:
        raise ValueError(f"list {list_no}: missing target rooms {sorted(missing)}")
    return ({"list_no": list_no, "source_rows": len(old), "gc_sha256": sha256(gc),
             "gc_le_sha256": sha256(b"".join(map(as_le, old))), "ps2_sha256": sha256(ps2),
             "selected_rows": len(baseline), "changed_rows": len(replacement),
             "records": records}, baseline, replacement, held)


def verified_file(entry: dict, label: str) -> dict:
    if not isinstance(entry, dict) or not entry.get("path") or not entry.get("sha256"):
        raise ValueError(f"{label}: path and sha256 are required")
    path = Path(entry["path"]).resolve(strict=True)
    digest = sha256(path.read_bytes())
    if digest != entry["sha256"]:
        raise ValueError(f"{label}: sha256 mismatch: {path}")
    return {"path": str(path), "sha256": digest}


def qualify(manifest: dict | None, held: dict, ps2_rel: Path | None) -> dict:
    if manifest is None:
        raise ValueError("room activation qualification is missing")
    if manifest.get("schema") != QUAL_SCHEMA:
        raise ValueError("unsupported activation qualification schema")
    if ps2_rel is None:
        raise ValueError("--ps2-rel is required for activation qualification")
    rel = verified_file(manifest.get("source_rel"), "source REL")
    if Path(rel["path"]) != ps2_rel.resolve(strict=True):
        raise ValueError("qualification source REL differs from --ps2-rel")
    result = {"schema": QUAL_SCHEMA, "source_rel": rel, "rooms": {}}
    for room, indices in sorted(held.items()):
        entry = manifest.get("rooms", {}).get(room, {})
        if entry.get("status") != "source-qualified":
            raise ValueError(f"{room}: activation is not source-qualified")
        if sorted(entry.get("held_indices", [])) != sorted(indices):
            raise ValueError(f"{room}: activation index coverage differs from full-record audit")
        implementation = verified_file(entry.get("implementation"), f"{room} implementation")
        evidence = entry.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{room}: source callback/area evidence is missing")
        result["rooms"][room] = {"status": "source-qualified", "held_indices": indices,
                                  "implementation": implementation,
                                  "evidence": [verified_file(e, f"{room} evidence") for e in evidence]}
    return result


def emit_header(lists: list[tuple]) -> str:
    lines = ["/* PRIVATE generated game data. Do not commit or publish. */",
             "/* Generated by ps2_enemy_ch23.py after activation qualification. */"]
    for list_no, baseline, replacement in lists:
        for name, rows in (("baseline", baseline), ("replacement", replacement)):
            if not rows:
                continue
            lines.append(f"static const Ps2EnemyCh23Row ps2_enemy_ch23_{name}_{list_no}[] = {{")
            for index, data in rows:
                values = ",".join(f"0x{value:02x}" for value in data)
                lines.append(f"    {{{index}, {{{values}}}}},")
            lines.append("};")
    lines.append("static const Ps2EnemyCh23List ps2_enemy_ch23_lists[] = {")
    for list_no, baseline, replacement in lists:
        new = f"ps2_enemy_ch23_replacement_{list_no}" if replacement else "NULL"
        lines.append(f"    {{{list_no}, ps2_enemy_ch23_baseline_{list_no}, {len(baseline)}, {new}, {len(replacement)}}},")
    lines.extend(("};", ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gc-dir", type=Path, required=True, help="directory containing emleonNN.esl")
    parser.add_argument("--ps2-dir", type=Path, required=True, help="directory containing ps2_emleonNN.esl")
    parser.add_argument("--audit-json", type=Path, required=True, help="PRIVATE output")
    parser.add_argument("--header", type=Path, help="PRIVATE ps2_enemy_ch23_data.inc output")
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--ps2-rel", type=Path)
    args = parser.parse_args(argv)
    audit = {"schema": "re4dc-ps2-enemy-ch23-v1", "record_bytes": ROW_SIZE,
             "fields": list(FIELD_NAMES), "lists": [], "qualification": None,
             "header_eligible": False}
    lists, held = [], {}
    try:
        for no in sorted(TARGETS):
            gc_path = args.gc_dir / f"emleon{no:02d}.esl"
            ps2_path = args.ps2_dir / f"ps2_emleon{no:02d}.esl"
            info, baseline, replacement, held_here = audit_list(no, gc_path.read_bytes(), ps2_path.read_bytes())
            info.update({"gc_path": str(gc_path.resolve()), "ps2_path": str(ps2_path.resolve())})
            audit["lists"].append(info)
            lists.append((no, baseline, replacement))
            for room, indices in held_here.items():
                held.setdefault(room, []).extend(indices)
        manifest = json.loads(args.qualification.read_text()) if args.qualification else None
        try:
            audit["qualification"] = qualify(manifest, held, args.ps2_rel)
            audit["header_eligible"] = True
        except (ValueError, OSError) as error:
            audit["qualification_error"] = str(error)
        audit["held_indices_requiring_activation"] = held
        if args.header and audit["header_eligible"]:
            header = emit_header(lists).encode("ascii")
            args.header.parent.mkdir(parents=True, exist_ok=True)
            args.header.write_bytes(header)
            audit["header"] = {"path": str(args.header.resolve()), "sha256": sha256(header)}
        args.audit_json.parent.mkdir(parents=True, exist_ok=True)
        args.audit_json.write_text(json.dumps(audit, indent=2) + "\n")
        print(json.dumps({"audit": str(args.audit_json), "header_eligible": audit["header_eligible"],
                          "lists": [{k: row[k] for k in ("list_no", "selected_rows", "changed_rows")}
                                    for row in audit["lists"]],
                          "qualification_error": audit.get("qualification_error")}))
        return 2 if args.header and not audit["header_eligible"] else 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"PS2_ENEMY_CH23: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
