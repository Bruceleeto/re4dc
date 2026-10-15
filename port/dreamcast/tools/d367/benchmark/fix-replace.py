#!/usr/bin/env python3
"""fix-replace.py <fixture.json> <warp.txt>: apply the warp file's "# bench-replace <disc path>=<source>" lines to a
t11-fix.py fixture (lane crowd12, 2026-10-14), so a benchmark scene can swap one package (for example the objs lane's
r101 objects fixture: "# bench-replace st1/r101.dar=/mnt/c/.../objs-20261014/r101o/r101.dar"). No lines: unchanged."""
import json
import os
import sys

fix, warp = sys.argv[1], sys.argv[2]
pairs = []
for line in open(warp, errors="replace"):
    if line.startswith("# bench-replace "):
        key, _, src = line[len("# bench-replace "):].strip().partition("=")
        if not key or not src or not os.path.isfile(src):
            sys.exit(f"fix-replace: bad line or missing source: {line.strip()}")
        pairs.append((key, src))
if pairs:
    d = json.load(open(fix))
    for key, src in pairs:
        d["replace"][key] = src
        print(f"fix-replace: {key} <- {src}")
    json.dump(d, open(fix, "w"), indent=1)
