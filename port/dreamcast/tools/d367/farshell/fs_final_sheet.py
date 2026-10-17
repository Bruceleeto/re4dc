"""fs_final_sheet.py <evidence dir> <out.png> [shot prefix t004]: FARSHELL-SHEET (Full / Short / Short + shell per view)."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ev, out = Path(sys.argv[1]), sys.argv[2]
pre = sys.argv[3] if len(sys.argv) > 3 else "t004"
ROWS = [("r101 cross (benchmark view)", "cross", ["cross-F-1", "cross-S-2", "cross-X3-1"]),
        ("r101 entry walk, frame A (parallax pair 1/2)", "walkA", ["walkA-F-1", "walkA-S-1", "walkA-X3-1"]),
        ("r101 entry walk, frame B, 100 frames later (parallax pair 2/2)", "walkB", ["walkB-F-1", "walkB-S-1", "walkB-X3-1"]),
        ("r100 path toward the house: placed inside a shed, the view out through its window (Short: fog, shell: the village)", "houseF", ["houseF-F-1", "houseF-S-1", "houseF-X3-1"]),
        ("r100 forest start", "forest", ["forest-F-1", "forest-S-1", "forest-X3-1"]),
        ("r100 rope bridge", "bridge", ["bridge-F-1", "bridge-S-1", "bridge-X3-1"]),
        ("r10b lake from the pier", "lake", ["lake-F-1", "lake-S-1", "lake-X3-1"])]
ARMS = ["Full (25 m)", "Short (12.5 m)", "Short + far shell (v3)"]
W, H = 480, 360
S = Image.new("RGB", (3 * W, len(ROWS) * (H + 22) + 30), (16, 16, 16))
d = ImageDraw.Draw(S)
d.text((6, 8), "FAR_SHELL proof of concept 2026-10-16: Flycast frames (same warp, frozen frame; picture shot %s*). Columns: %s"
       % (pre, " | ".join(ARMS)), fill=(255, 255, 255))
for r, (title, _, runs) in enumerate(ROWS):
    y = 30 + r * (H + 22)
    d.text((6, y + 4), title, fill=(255, 230, 120))
    for c, run in enumerate(runs):
        shots = sorted((ev / run / "capture" / "shots").glob(pre + "*"))
        if not shots:
            d.text((c * W + 10, y + 40), "missing " + run, fill=(255, 80, 80))
            continue
        im = Image.open(shots[0] / "frames" / "fb0.png").convert("RGB")
        im = im.crop((0, 60, im.width, im.height - 60)) if im.height >= 480 else im
        S.paste(im.resize((W, H)), (c * W, y + 22))
        d.text((c * W + 6, y + 26), ARMS[c] + "  [" + run + "]", fill=(255, 255, 255))
S.save(out)
print(out, S.size)
