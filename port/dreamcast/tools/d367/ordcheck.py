#!/usr/bin/env python3
"""Stale-order check for a LINK_ORDER file (game30.mk; written by ordgen_c3.py).

A link order goes stale as code changes: sections it names disappear (renamed / removed functions; ld ignores
them) and new hot code (new kernels, split functions) is left at its default place in .text. This reports, for
an order file against the objects of a current build and hwproject evidence of the current code:
  - rules naming no current input section (stale rules);
  - per evidence run, the hw ms of the run's functions whose input section the order places ("covered"),
    against the run's total and the part in library / unmapped code (never placeable).
Regenerate with ordgen_c3.py when covered falls well below placeable (2026-10-04: the r101-square order on
r21y code covered 47-57% of the house / fight / square hw ms, the regenerated order 87-88%, placeable ~88%).

usage: ordcheck.py --objdir <OBJDIR of a current build> [--evidence-root D] [--exclude REGEX]
                   <order.ld> <hwproject evidence dir name>..."""
import argparse
import collections
import glob
import os
import re
import subprocess

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("--objdir", required=True)
ap.add_argument("--evidence-root", default=os.environ.get("HWM_EVIDENCE", "/mnt/d/Flycast-Evidence/re4-dreamcast"))
ap.add_argument("--tools", default="/opt/toolchains/dc/sh-elf/bin/sh-elf-")
ap.add_argument("--exclude", default="^(re4dc_pace_end|re4dc_vi_retrace_count)$",
                help="regex of functions (demangled) whose hw ms is not hardware work (the pacing spin)")
ap.add_argument("order")
ap.add_argument("runs", nargs="+")
a = ap.parse_args()


def run(*args):
    return subprocess.run(list(args), capture_output=True, text=True, check=True).stdout


where, secs = {}, set()
for o in sorted(glob.glob(a.objdir + "/**/*.o", recursive=True)):
    base = os.path.basename(o)
    for l in run(a.tools + "objdump", "-t", o).splitlines():
        p = l.split()
        if len(p) >= 5 and p[-3].startswith(".text"):
            where.setdefault(p[-1], (base, p[-3]))
    for l in run(a.tools + "objdump", "-h", o).splitlines():
        p = l.split()
        if len(p) >= 3 and p[1].startswith(".text"):
            secs.add((base, p[1]))

rules, stale = set(), []
for l in open(a.order):
    m = re.match(r"\s*\*(\S+?)\((\S+?)\)", l)
    if m:
        rules.add((m.group(1), m.group(2)))
        if m.group(1) != "_kos_startup.o" and (m.group(1), m.group(2)) not in secs:
            stale.append("%s(%s)" % (m.group(1), m.group(2)))
print("%s: %d rules, %d naming no current section%s" % (
    os.path.basename(a.order), len(rules), len(stale), (": " + " ".join(stale[:8])) if stale else ""))

for name in a.runs:
    E = os.path.join(a.evidence_root, name)
    ELF = E + "/re4dc-game.elf"
    nm = run(a.tools + "nm", ELF).splitlines()
    nmc = run(a.tools + "nm", "-C", ELF).splitlines()
    dem2m = {}
    for m, d in zip(nm, nmc):
        pm, pd = m.split(None, 2), d.split(None, 2)
        if len(pm) == 3 and len(pd) == 3:
            dem2m.setdefault(pd[2], pm[2])
    L = open(E + "/proj/rep/functions.tsv").read().splitlines()
    h = L[0].split("\t")
    fi, hi = h.index("func"), h.index("hw_ms")
    tot = cov = unk = 0.0
    miss = collections.Counter()
    for l in L[1:]:
        f = l.split("\t")
        if a.exclude and re.search(a.exclude, f[fi]):
            continue
        w = float(f[hi])
        tot += w
        s = where.get(dem2m.get(f[fi], ""))
        if s is None:
            unk += w
        elif s in rules or (s[0], ".text") in rules:
            cov += w
        else:
            miss[f[fi]] += w
    print("  %s: covered %.1f of %.1f hw ms (%.0f%%; placeable %.0f%%); hottest unplaced: %s" % (
        name, cov, tot, 100 * cov / max(tot, 1e-9), 100 * (tot - unk) / max(tot, 1e-9),
        ", ".join("%s %.2f" % (k[:40], v) for k, v in miss.most_common(4))))
