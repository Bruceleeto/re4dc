#!/usr/bin/env python3
"""PRIVATE full32 CH22/r11a ESL adoption, qualified independently per room.

The seven PS2 r11c additions may populate only verified all-zero source slots.
No extracted bytes or generated tables belong in Git. Runtime patches apply
only to fresh reads; all selected baselines are validated before any write.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import ps2_enemy_ch23 as common

TARGETS = {0: {0x100, 0x104}, 1: {0x111, 0x112, 0x113, 0x11a, 0x11c}}
QUAL_SCHEMA = "re4dc-ps2-enemy-ch22-activation-v1"
ADDITIONS = {1: {index: 0x11c for index in range(153, 160)}}


def audit_list(list_no, gc, ps2):
    old, new = common.decode(gc, ">"), common.decode(ps2, "<")
    if len(old) != len(new):
        raise ValueError(f"list {list_no}: source row counts differ")
    baseline, replacement, records, needs = [], [], [], {}
    for index, (before, after) in enumerate(zip(old, new)):
        old_room, new_room = before[common.ROOM_INDEX], after[common.ROOM_INDEX]
        if old_room not in TARGETS[list_no] and new_room not in TARGETS[list_no]:
            continue
        old_bytes, new_bytes = common.as_le(before), common.as_le(after)
        populated = old_room != new_room
        if populated and not (ADDITIONS.get(list_no, {}).get(index) == new_room
                              and old_bytes == bytes(common.ROW_SIZE)
                              and after[0] == 0 and after[1] == 0x13):
            raise ValueError(f"list {list_no} row {index}: unqualified room identity change")
        room = f"r{new_room:03x}"
        baseline.append((index, old_bytes))
        before_fields, after_fields = common.fields(before), common.fields(after)
        changed = [key for key in common.FIELD_NAMES if before_fields[key] != after_fields[key]]
        alive_changed = bool((before[0] ^ after[0]) & 1)
        if changed:
            replacement.append((index, new_bytes))
            requirement = needs.setdefault(room, {"changed_indices": [], "activation_indices": [], "populated_indices": []})
            requirement["changed_indices"].append(index)
            if populated or alive_changed:
                requirement["activation_indices"].append(index)
            if populated:
                requirement["populated_indices"].append(index)
        records.append({"index": index, "room": room, "before": before_fields,
                        "after": after_fields, "changed_fields": changed,
                        "alive_changed": alive_changed, "populated_from_zero": populated,
                        "gc_le_sha256": common.sha256(old_bytes), "ps2_sha256": common.sha256(new_bytes)})
    missing = TARGETS[list_no] - {int(row["room"][1:], 16) for row in records}
    if missing:
        raise ValueError(f"list {list_no}: missing target rooms {sorted(missing)}")
    return ({"list_no": list_no, "source_rows": len(old), "gc_sha256": common.sha256(gc),
             "gc_le_sha256": common.sha256(b"".join(map(common.as_le, old))),
             "ps2_sha256": common.sha256(ps2), "selected_rows": len(baseline),
             "changed_rows": len(replacement), "records": records}, baseline, replacement, needs)


def qualify(manifest, needs):
    if not isinstance(manifest, dict) or manifest.get("schema") != QUAL_SCHEMA:
        raise ValueError("CH22 per-room activation qualification is missing or unsupported")
    result = {"schema": QUAL_SCHEMA, "rooms": {}}
    for room, requirement in sorted(needs.items()):
        entry = manifest.get("rooms", {}).get(room, {})
        if entry.get("status") != "source-qualified":
            raise ValueError(f"{room}: room source is not qualified")
        for key, indices in requirement.items():
            if sorted(entry.get(key, [])) != indices:
                raise ValueError(f"{room}: {key} coverage differs from full-record audit")
        proof = {"status": "source-qualified", **requirement,
                 "source_rel": common.verified_file(entry.get("source_rel"), f"{room} source REL"),
                 "implementation": common.verified_file(entry.get("implementation"), f"{room} implementation")}
        evidence = entry.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{room}: source callback/field evidence is missing")
        proof["evidence"] = [common.verified_file(item, f"{room} evidence") for item in evidence]
        result["rooms"][room] = proof
    return result


def emit_header(lists):
    return common.emit_header(lists).replace("Ch23", "Ch22").replace("ch23", "ch22")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gc-dir", type=Path, required=True)
    parser.add_argument("--ps2-dir", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--header", type=Path, help="PRIVATE output; refused until every changed room is qualified")
    args = parser.parse_args(argv)
    audit = {"schema": "re4dc-ps2-enemy-ch22-v1", "record_bytes": common.ROW_SIZE,
             "fields": list(common.FIELD_NAMES), "lists": [], "header_eligible": False}
    lists, needs = [], {}
    try:
        for no in sorted(TARGETS):
            gc_path = args.gc_dir / f"emleon{no:02d}.esl"
            ps2_path = args.ps2_dir / f"ps2_emleon{no:02d}.esl"
            info, baseline, replacement, requirements = audit_list(no, gc_path.read_bytes(), ps2_path.read_bytes())
            info.update(gc_path=str(gc_path.resolve()), ps2_path=str(ps2_path.resolve()))
            audit["lists"].append(info)
            lists.append((no, baseline, replacement))
            if set(needs).intersection(requirements):
                raise ValueError("a qualified room cannot span multiple enemy lists")
            needs.update(requirements)
        audit["qualification_required"] = needs
        manifest = json.loads(args.qualification.read_text()) if args.qualification else None
        try:
            audit["qualification"] = qualify(manifest, needs)
            audit["header_eligible"] = True
        except (ValueError, OSError) as error:
            audit["qualification_error"] = str(error)
        if args.header and audit["header_eligible"]:
            header = emit_header(lists).encode("ascii")
            args.header.parent.mkdir(parents=True, exist_ok=True)
            args.header.write_bytes(header)
            audit["header"] = {"path": str(args.header.resolve()), "sha256": common.sha256(header)}
        args.audit_json.parent.mkdir(parents=True, exist_ok=True)
        args.audit_json.write_text(json.dumps(audit, indent=2) + "\n")
        print(json.dumps({"audit": str(args.audit_json), "header_eligible": audit["header_eligible"],
                          "qualification_required": needs, "qualification_error": audit.get("qualification_error")}))
        return 2 if args.header and not audit["header_eligible"] else 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"PS2_ENEMY_CH22: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
