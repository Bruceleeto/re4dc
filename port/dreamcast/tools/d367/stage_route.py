#!/usr/bin/env python3
"""Stage route tracer: the door graph of a stage from the GameCube disc (every room's AEV type-1 door records and
ITA key items) plus the source door gates, and which rooms are required to leave the stage.

    python3 tools/d367/stage_route.py [--iso PATH] [--stage 1] [--json OUT]

AEV (version 0x104) / ITA (0x105): 0x10-byte header (magic, u16 version, u16 count), then SceAtWork records of 0x9C
bytes (include/sce_at.h): type at 0x35 (1 = door), no at 0x36, trigger at 0x38; door payload dstPos 0x5C, dstAngle
0x68, dstStage 0x6C, dstRoom 0x6D, lockType 0x6E, lockFlag 0x6F, dstPart 0x74, doorNo 0x76, fadeEff 0x77; ITA item id
at 0x78. The data is big-endian inside the Yz2-decoded room .das.

The source gates (GATES below) come from the room code (src/st1/r1xx.cpp: SceAtDataSet_exec door overrides,
SceAtDataReset unlocks, SceAtSetEnable, SceSetChapterEnd doors); keep them current when a room's code is read again.
"""
import argparse, json, struct, sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import room_smd  # noqa: E402
from assetpipe.rooms import GcIso  # noqa: E402

DEFAULT_ISO = "/root/work/re4-dreamcast/orig/G4BE08/re4_debug_disc1.iso"
KEYS = {0x3B: "r101->r102 key", 0x3C: "r118->r117 key", 0x3D: "False Eye (r10f->r200)", 0x8B: "r11e->r10f key",
        0xA4: "r104->r107 emblem half", 0xA5: "r104->r107 emblem half", 0xA6: "r104->r107 emblem"}


def ANY(*rooms, why=""):
    return ("any", rooms, why)


def ALL(*rooms, why=""):
    return ("all", rooms, why)


def NEVER(why):
    return ("never", (), why)


# Stage 1 gates: (room, door no) -> requirement. "any"/"all" name rooms that must have been visited first.
GATES = {
    ("r101", 0x00): ANY("r101", why="r101_DoorDontOpen100 until the bell event (r101_Event30 SceAtDataReset(0))"),
    ("r101", 0x02): ANY("r101", why="r101_DoorDontOpen103 until the bell event (r101_Event30 SceAtDataReset(2))"),
    ("r101", 0x01): NEVER("r101_DoorDontOpen3: opened from r105's side (r105_checkDoor)"),
    ("r101", 0x19): ANY("r105", why="key 0x3B (ITA r105), r101_checkDoor102KeyUse"),
    ("r104", 0x00): ANY("r104", why="emblem halves 0xA4 + 0xA5 -> 0xA6 (ITA r104), r104_checkDoor107"),
    ("r105", 0x01): ANY("r105", why="r105_checkDoor opens it from inside (door_unlock 0x02000000)"),
    ("r108", 0x00): NEVER("AEV lockType 1 flag 7 (locked from this side)"),
    ("r118", 0x00): NEVER("AEV lockType 1 flag 7 (locked from this side)"),
    ("r118", 0x04): ANY("r10c", "r118", why="key 0x3C (ITA r10c and r118), r118_checkDoor117"),
    ("r117", 0x0B): ANY("r117", why="AEV lockType 2 flag 7 (opens after r117's event)"),
    ("r10e", 0x01): ANY("r10b", why="disabled until Scenario_flg 0x01000000 (chapter 2-1 start, after r10b's 1-3 end)"),
    ("r113", 0x02): ALL("r113", "r117", why="Ashley's shoulder ride (door_unlock 0x08000000); Ashley joins in r117"),
    ("r11d", 0x01): ANY("r11d", why="r11d_checkDoor opens it from inside (door_unlock 0x00010000)"),
    ("r11e", 0x01): ANY("r11e", why="key 0x8B (ITA r11e), r11e_checkDoor"),
    ("r10f", 0x00): NEVER("r10f_DoorClose until r11d opens its side"),
    ("r10f", 0x03): NEVER("r10f_DoorClose until r11e opens its side"),
    ("r10f", 0x02): ANY("r11f", why="False Eye 0x3D (ITA r11f), r10f_checkFalseEyeUse"),
}
JUMPS = [("r120", "r100", "r120 SceAtExecRoomJump(0x100) after the intro movie")]
CHAPTERS = [("1-1", "r106", "SceSetChapterEnd(0, 3): door 3 -> r104"),
            ("1-2", "r105", "SceSetChapterEnd(CHAPTER_1_2, -1)"),
            ("1-3", "r10b", "SceSetChapterEnd(CHAPTER_1_3, 6): door 6 -> r11b"),
            ("2-1", "r117", "SceSetChapterEnd(CHAPTER_2_1, -1)"),
            ("2-2", "r11c", "SceSetChapterEnd(CHAPTER_2_2, -1)"),
            ("2-3", "r10f", "door 2 -> r200 (stage 2)")]


def records(arc, magic, version):
    pos = arc.find(magic + b"\0")
    while pos >= 0:
        ver, num = struct.unpack_from(">HH", arc, pos + 4)
        if ver == version and 0 < num < 256:
            return [pos + 0x10 + i * 0x9C for i in range(num)]
        pos = arc.find(magic + b"\0", pos + 4)
    return []


def scan(iso, stage):
    rooms = {}
    for room, rel in iso.rooms():
        if not room.startswith("r%x" % stage):
            continue
        arc = room_smd.decode_das(iso.read(rel))
        doors = []
        for w in records(arc, b"AEV", 0x104):
            if arc[w + 0x35] != 1:
                continue
            x, y, z, ang = struct.unpack_from(">4f", arc, w + 0x5C)
            st, rm, lt, lf = struct.unpack_from(">4B", arc, w + 0x6C)
            part, _se, dno, fade = struct.unpack_from(">BbBB", arc, w + 0x74)
            doors.append({"no": arc[w + 0x36], "trigger": arc[w + 0x38], "dst": "r%x%02x" % (st, rm),
                          "part": part, "lock": lt, "lockflag": lf, "doorNo": dno, "fade": fade,
                          "pos": [round(x), round(y), round(z)], "angle": round(ang, 3)})
        items = [struct.unpack_from(">H", arc, w + 0x78)[0] for w in records(arc, b"ITA", 0x105)]
        rooms[room] = {"doors": doors, "keys": [k for k in items if k in KEYS], "items": len(items)}
    return rooms


def reach(rooms, start, skip=()):
    edges = [(a, d["no"], d["dst"]) for a, r in rooms.items() for d in r["doors"] if d["dst"] != a]
    edges += [(a, -1, b) for a, b, _ in JUMPS]
    seen, order, changed = {start}, [start], True
    while changed:
        changed = False
        for a, no, b in edges:
            if a not in seen or b in seen or b in skip:
                continue
            g = GATES.get((a, no))
            if g and (g[0] == "never" or not (any if g[0] == "any" else all)(r in seen for r in g[1])):
                continue
            seen.add(b)
            order.append(b)
            changed = True
    return seen, order


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--iso", default=DEFAULT_ISO)
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--start", default="r120")
    ap.add_argument("--exit", default="r200")
    ap.add_argument("--json")
    a = ap.parse_args()
    rooms = scan(GcIso(a.iso), a.stage)
    for room, r in rooms.items():
        print("%s keys=%s" % (room, " ".join("%02x" % k for k in r["keys"]) or "-"))
        for d in r["doors"]:
            g = GATES.get((room, d["no"]))
            print("   door %02x -> %s part %d lock %d/%02x trig %02x%s" % (
                d["no"], d["dst"], d["part"], d["lock"], d["lockflag"], d["trigger"], ("  [" + g[2] + "]") if g else ""))
    seen, _ = reach(rooms, a.start)
    names = sorted(rooms)
    required = [r for r in names if r != a.start and a.exit not in reach(rooms, a.start, skip=(r,))[0]]
    print("\n%s reached from %s: %s; unreachable: %s" % (a.exit, a.start, a.exit in seen,
                                                       [r for r in names if r not in seen] or "none"))
    print("required by the door graph (removing the room cuts %s): %s" % (a.exit, " ".join(required)))
    print("chapter ends:", "; ".join("%s %s (%s)" % c for c in CHAPTERS))
    print("optional by the door graph:", " ".join(r for r in names if r not in required and r != a.start))
    if a.json:
        Path(a.json).write_text(json.dumps({"rooms": rooms, "required": required}, indent=1))


if __name__ == "__main__":
    main()
