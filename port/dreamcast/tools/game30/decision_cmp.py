#!/usr/bin/env python3
"""decision_cmp.py <ref run-output.txt> <test run-output.txt> [--align frame|room] [--room 0100] [--from K] [--to K]
[--json out.json]

Lane fm (2026-10-05) decision-level comparison of two LOGIC_TRACE=1 GAME_DECISION_TRACE=1 runs, for last-bit FP
changes: d367-agents look-gaps dtcmpc.py (the dtcmp used for GAME_PWC_KERNEL=3 / the skeleton lanes) with file
arguments, logic_trace_diff.py's frame / room alignment and a window.

Per aligned tick (LT / LU / LX records joined by Frame_cnt minus the alignment anchor):
  must match: RNG (r), System / Stop / Status / Room / Scenario flags (sy sp st rf sc), room (rm), player / enemy /
              object discrete hashes (ps es os), motion state (ms), alive counts (e o), and the decision hashes
              with their counts: em-em collision results (ec), area checks (sa), damage hit tests (dm), line query
              answers (lq), effect slots / generators' discrete fields (ep eg);
  reported:   scenery line candidate tests (sl), line query hit points (lp), the sound system's own queries (sq:
              follow audio timing, vary run to run), the continuous hashes (p a mf pf pm ef em of om c), and the
              drift of the player position and of every alive enemy position (LP records, world units).
Verdict: MUST-IDENTICAL when every must-match row is identical on every compared tick, else MUST-DIFFER (first
differing tick and fields listed).
"""
import argparse, json, re, struct, sys

LT = re.compile(r"LT t=(\d+) n=(\d+) r=(\w+) sy=(\w+) sp=(\w+) st=(\w+) rf=(\w+) sc=(\w+) rm=(\w+) "
                r"p=(\w+),(\w+),(\w+) a=(\w+),(\w+),(\w+) m=(\w+)/(\w+) ps=(\w+) pf=(\w+) pm=(\w+)")
LU = re.compile(r"LU t=(\d+) n=(\d+) e=(\d+) es=(\w+) ef=(\w+) em=(\w+) o=(\d+) os=(\w+) of=(\w+) om=(\w+) c=(\w+)")
LX = re.compile(r"LX t=(\d+) n=(\d+) ec=(\w+)/(\d+) sl=(\w+)/(\d+) sa=(\w+)/(\d+) dm=(\w+)/(\d+)"
                r"(?: lq=(\w+)/(\d+) lp=(\w+))?(?: sq=(\w+)/(\d+))?(?: ep=([\w-]+)(?:/(\d+))?)?(?: eg=([\w-]+)(?:/(\d+))?)?")
LP = re.compile(r"LP t=(\d+) k=(\d+) (\w\w):(\w{8}),(\w{8}),(\w{8}) (\w\w):(\w{8}),(\w{8}),(\w{8}) (\w\w):(\w{8}),(\w{8}),(\w{8})")

MUST = ["r", "sy", "sp", "st", "rf", "sc", "rm", "ms", "ps", "e", "es", "o", "os", "ec", "sa", "dm", "lq", "ep", "eg"]
INFO = ["sl", "lp", "sq", "p", "a", "mf", "pf", "pm", "ef", "em", "of", "om", "c"]


def f32(h):
    return struct.unpack("<f", struct.pack("<I", int(h, 16)))[0]


def load(path):
    txt = open(path, errors="replace").read()
    rec = {}
    for m in LT.finditer(txt):
        g = m.groups()
        rec.setdefault(int(g[0]), {}).update(r=g[2], sy=g[3], sp=g[4], st=g[5], rf=g[6], sc=g[7], rm=g[8],
                                             p=(g[9], g[10], g[11]), a=(g[12], g[13], g[14]), mf=g[15], ms=g[16],
                                             ps=g[17], pf=g[18], pm=g[19])
    for m in LU.finditer(txt):
        g = m.groups()
        rec.setdefault(int(g[0]), {}).update(e=g[2], es=g[3], ef=g[4], em=g[5], o=g[6], os=g[7], of=g[8],
                                             om=g[9], c=g[10])
    for m in LX.finditer(txt):
        g = m.groups()
        rec.setdefault(int(g[0]), {}).update(ec=g[2] + "/" + g[3], sl=g[4] + "/" + g[5], sa=g[6] + "/" + g[7],
                                             dm=g[8] + "/" + g[9], lq=(g[10] or "-") + "/" + (g[11] or "0"),
                                             lp=g[12] or "-", sq=(g[13] or "-") + "/" + (g[14] or "0"),
                                             ep=(g[15] or "-") + "/" + (g[16] or "0"),
                                             eg=(g[17] or "-") + "/" + (g[18] or "0"))
    pos = {}
    for m in LP.finditer(txt):
        g = m.groups()
        t, k = int(g[0]), int(g[1])
        for j in range(3):
            i, x, y, z = g[2 + 4 * j: 6 + 4 * j]
            if i.lower() == "ff" and x == "00000000":
                continue
            pos[(t, k + j)] = (i, f32(x), f32(y), f32(z))
    return rec, pos


def anchor(rec, room):
    for t in sorted(rec):
        r = rec[t]
        if r.get("rm", "").lower() == room and r.get("p") not in (None, ("00000000", "00000000", "00000000")):
            return t
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref"); ap.add_argument("test")
    ap.add_argument("--align", default="frame", choices=["frame", "room"])
    ap.add_argument("--room", default=None)
    ap.add_argument("--from", dest="lo", type=int, default=None)
    ap.add_argument("--to", dest="hi", type=int, default=None)
    ap.add_argument("--json")
    a = ap.parse_args()
    A, pa = load(a.ref)
    B, pb = load(a.test)
    out = dict(ref=a.ref, test=a.test, align=a.align, ref_records=len(A), test_records=len(B))
    da = db = 0
    if a.align == "room":
        last = max((t for t in A if "rm" in A[t]), default=None)
        room = (a.room or (A[last]["rm"] if last is not None else "")).lower()
        ta, tb = anchor(A, room), anchor(B, room)
        out.update(room=room, ref_anchor=ta, test_anchor=tb)
        if ta is None or tb is None:
            out["verdict"] = "UNUSABLE (room never reached)"
            print(json.dumps(out, indent=1)); return 2
        da, db = ta, tb
        if a.lo is None:
            a.lo = 0
    AA = {t - da: v for t, v in A.items()}
    BB = {t - db: v for t, v in B.items()}
    ticks = sorted(k for k in set(AA) & set(BB)
                   if all(f in AA[k] and f in BB[k] for f in MUST)
                   and (a.lo is None or k >= a.lo) and (a.hi is None or k <= a.hi))
    out["compared"] = len(ticks)
    if not ticks:
        out["verdict"] = "UNUSABLE (no complete common ticks)"
        print(json.dumps(out, indent=1)); return 2
    out["window"] = [ticks[0], ticks[-1]]
    rows = {}
    first = None
    for k in MUST + INFO:
        bad = [t for t in ticks if AA[t].get(k) != BB[t].get(k)]
        rows[k] = dict(differ=len(bad), first=(bad[0] + da) if bad else None)
        if k in MUST and bad and (first is None or bad[0] < first[0]):
            first = (bad[0], k)
    dec = {k: 0 for k in ("ec", "sl", "sa", "dm", "lq")}
    for t in ticks:
        for k in dec:
            dec[k] += int(AA[t][k].split("/")[1])
    mp = 0.0
    for t in ticks:
        for j in range(3):
            mp = max(mp, abs(f32(AA[t]["p"][j]) - f32(BB[t]["p"][j])))
    PA = {(t - da, s): v for (t, s), v in pa.items()}
    PB = {(t - db, s): v for (t, s), v in pb.items()}
    keys = sorted(k for k in set(PA) & set(PB) if (a.lo is None or k[0] >= a.lo) and (a.hi is None or k[0] <= a.hi))
    me, worst, idm, n = 0.0, None, 0, 0
    for key in keys:
        (i1, *v1), (i2, *v2) = PA[key], PB[key]
        if i1 != i2:
            idm += 1
            continue
        n += 1
        d = max(abs(x - y) for x, y in zip(v1, v2))
        if d > me:
            me, worst = d, key
    out.update(rows=rows, decisions=dict(em_em=dec["ec"], line_queries=dec["lq"] // 2,
                                         line_candidate_tests=dec["sl"], area_checks=dec["sa"],
                                         damage_tests=dec["dm"]),
               drift=dict(player_max=mp, enemy_samples=n, enemy_max=me,
                          enemy_worst=[worst[0] + da, worst[1]] if worst else None, slot_id_mismatches=idm))
    out["verdict"] = "MUST-IDENTICAL" if first is None else "MUST-DIFFER"
    if first is not None:
        t = first[0]
        out["first_must_difference"] = dict(ref_frame=t + da, test_frame=t + db,
                                            fields={k: [AA[t].get(k), BB[t].get(k)] for k in MUST
                                                    if AA[t].get(k) != BB[t].get(k)})
    print("%s vs %s (%s%s): %d ticks %s, verdict %s" % (a.ref, a.test, a.align,
          (" room %s anchors %s/%s" % (out.get("room"), da, db)) if a.align == "room" else "", len(ticks),
          out["window"], out["verdict"]))
    print("  must: " + " ".join("%s=%s" % (k, "ok" if rows[k]["differ"] == 0 else "%d@%d" % (rows[k]["differ"], rows[k]["first"])) for k in MUST))
    print("  info: " + " ".join("%s=%s" % (k, "ok" if rows[k]["differ"] == 0 else "%d@%d" % (rows[k]["differ"], rows[k]["first"])) for k in INFO))
    print("  decisions: em-em %d, line queries %d (candidate tests %d), area %d, damage %d" % (
        dec["ec"], dec["lq"] // 2, dec["sl"], dec["sa"], dec["dm"]))
    print("  drift: player max %.6g; enemies %d samples, max %.6g at %s, slot id mismatches %d" % (
        mp, n, me, out["drift"]["enemy_worst"], idm))
    if first is not None:
        print("  first must difference: %s" % json.dumps(out["first_must_difference"]))
    if a.json:
        open(a.json, "w").write(json.dumps(out, indent=1))
    return 0 if first is None else 1


if __name__ == "__main__":
    sys.exit(main())
