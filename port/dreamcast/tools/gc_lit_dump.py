#!/usr/bin/env python3
"""Dump a GC room's LIT cut (env + lights) as JSON: the same fields ow_extract.py's scene.json carries
(ambient_scr, fog, lights_cut). Run in WSL (reads the GC .das via port/dreamcast/tools/room_smd.py).
usage: gc_lit_dump.py <room e.g. r100> <out.json> [cut]"""
import json, struct, sys
sys.path.insert(0, "/root/work/re4-dreamcast/port/dreamcast/tools")
import room_smd

room, out = sys.argv[1], sys.argv[2]
CUT = int(sys.argv[3]) if len(sys.argv) > 3 else 0
das = "/root/work/re4-dreamcast/orig/G4BE08/rooms/%s/%s.das" % (room, room)
data = room_smd.decode_das(open(das, "rb").read())
e = room_smd.archive_endian(data)
ents = room_smd.tagged_entries(data, e)
LIT = [data[s:t] for tag, s, t in ents if tag == b"LIT\0"][0]
be32 = lambda d, o: struct.unpack_from(">I", d, o)[0]
fB = lambda d, o: struct.unpack_from(">f", d, o)[0]
cutnum = struct.unpack_from(">H", LIT, 0)[0]
cut_offs = struct.unpack_from(">%dI" % cutnum, LIT, 4)
o = cut_offs[CUT]
env = dict(ambient_scr=list(LIT[o:o + 3]), fog_type=struct.unpack_from(">i", LIT, o + 8)[0], fog_start=fB(LIT, o + 12),
           fog_end=fB(LIT, o + 16), fog_rgba=LIT[o + 0x14:o + 0x18].hex(), contrast=list(struct.unpack_from(">3b", LIT, o + 0xF5)))
lights = []
for j in range(be32(LIT, o + 4)):
    w = o + 0x104 + 0x12C * j
    be, xD, ty, xF = LIT[w:w + 4]
    lights.append(dict(i=j, be=be, xD=xD, type=ty, xF=xF, pos=list(struct.unpack_from(">3f", LIT, w + 4)),
                       R=fB(LIT, w + 0x10), col=list(LIT[w + 0x14:w + 0x18]), intensity=fB(LIT, w + 0x18),
                       n=list(struct.unpack_from(">3f", LIT, w + 0x2C)), A0=fB(LIT, w + 0x38), A1=fB(LIT, w + 0x3C)))
json.dump(dict(room=room, cut=CUT, cuts=cutnum, env=env, lights_cut=lights), open(out, "w"), indent=1)
print(json.dumps(env))
for l in lights:
    print(l["i"], "be", l["be"], "xD", l["xD"], "type", l["type"], "col", l["col"], "I", round(l["intensity"], 3),
          "pos", [round(x) for x in l["pos"]], "n", [round(x, 3) for x in l["n"]], "R", round(l["R"]))
