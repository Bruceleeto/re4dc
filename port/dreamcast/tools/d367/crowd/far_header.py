#!/usr/bin/env python3
"""Lane crowd: the far-tier header for CROWD_FAR (crowd.mk).

far_header.py <cast_bundle.py header> <out ganado_far_runtime.h>

The input is a cast_bundle.py ganado_cast_runtime.h (the far level, e.g. LEVEL=lean). The output holds the same
tables in namespace ganadocast::far, reusing the near header's Weight / Chunk / Signature / Texture types (so
coarse_ganado_cast.cpp treats a far chunk exactly like a near one). It must be included after the near
ganado_cast_runtime.h. The far bundle must use the near bundle's appearance order, bind and texture: the build
checks the appearance names and bind with static data compares at first use (coarse_ganado_cast.cpp far_check).
The output is a private generated asset (game data); never commit it.
"""
import re
import sys

src, out = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read().splitlines()
drop = re.compile(r"^(#pragma once|#include <cstdint>|struct (Weight|Chunk|Signature|Texture) \{.*\};)\s*$")
body, opened, closed = [], False, False
for line in text:
    if drop.match(line):
        continue
    if line.strip() == "namespace ganadocast {":
        if opened:
            sys.exit("two namespace openings")
        opened = True
        body.append("namespace ganadocast { namespace far {")
        continue
    body.append(line)
# The last line closing the namespace.
while body and not body[-1].strip():
    body.pop()
if not opened or body[-1].strip() != "}":
    sys.exit("unexpected header layout (namespace ganadocast { ... } expected)")
body[-1] = "}}"
for t in ("struct Weight", "struct Chunk", "struct Signature", "struct Texture"):
    if any(l.startswith(t) for l in body):
        sys.exit(t + " left in the far header")
head = ["// Private generated asset (lane crowd far_header.py from %s). Do not commit." % src,
        "// The far tier for CROWD_FAR: include after ganado_cast_runtime.h.",
        "#pragma once"]
open(out, "w", encoding="utf-8", newline="\n").write("\n".join(head + body) + "\n")
print("far header %s: %d lines" % (out, len(body)))
