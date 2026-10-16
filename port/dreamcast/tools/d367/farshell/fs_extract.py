"""fs_extract.py <room pkg dir> <tex.pak> <out dir>: world triangles (npz) + decoded textures (PNG by key)."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
import fs_common as fc

pkg, pak, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
(out / "tex").mkdir(exist_ok=True)
T, info = fc.world_tris(pkg)
np.savez_compressed(out / "world.npz", **T)
tp = fc.TexPak(pak)
tp.loose = sys.argv[4] if len(sys.argv) > 4 else None
keys = sorted({tuple(int(x) for x in k) for k in T["key"]})
texinfo = {}
for k in keys:
    rgba, meta = fc.decode_re4tex(tp.get(k))
    name = "%08x-%08x" % k
    Image.fromarray(rgba).save(out / "tex" / (name + ".png"))
    texinfo[name] = meta
P = T["P"]
lo, hi = P.reshape(-1, 3).min(0), P.reshape(-1, 3).max(0)
stats = dict(info, tris=int(len(P)), by_pass={int(p): int((T["pass_"] == p).sum()) for p in np.unique(T["pass_"])},
             textures=len(keys), bounds_mm=[lo.tolist(), hi.tolist()])
(out / "extract.json").write_text(json.dumps(dict(stats=stats, textures=texinfo), indent=1))
print(json.dumps(stats))
