"""fs_sheet.py <out.png> <cols> <img>... : simple contact sheet with file-name labels."""
import sys
from PIL import Image, ImageDraw
out, cols, files = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
ims = [Image.open(f).convert("RGB") for f in files]
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
S = Image.new("RGB", (cols * w, rows * (h + 16)), (20, 20, 20))
d = ImageDraw.Draw(S)
for i, (f, im) in enumerate(zip(files, ims)):
    x, y = (i % cols) * w, (i // cols) * (h + 16)
    S.paste(im.resize((w, h)), (x, y + 16))
    d.text((x + 4, y + 2), f.replace("\\", "/").split("/")[-1], fill=(255, 255, 0))
S.save(out)
