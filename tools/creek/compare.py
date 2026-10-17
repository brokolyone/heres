"""Side-by-side and difference metrics: python3 compare.py reference.png render.png out.png"""
import sys
import numpy as np
from PIL import Image, ImageFilter

ref = Image.open(sys.argv[1]).convert("RGB")
ren = Image.open(sys.argv[2]).convert("RGB").resize(ref.size, Image.LANCZOS)
a = np.asarray(ref).astype(float) / 255
b = np.asarray(ren).astype(float) / 255
# structure at a blurred scale (what the eye compares first), plus per-channel mean/std
bl = lambda im: np.asarray(im.filter(ImageFilter.GaussianBlur(6))).astype(float) / 255
d = np.abs(bl(ref) - bl(ren))
print("mean abs diff (blurred): %.4f" % d.mean())
print("ref mean rgb", a.reshape(-1, 3).mean(0).round(3), "std", a.reshape(-1, 3).std(0).round(3))
print("ren mean rgb", b.reshape(-1, 3).mean(0).round(3), "std", b.reshape(-1, 3).std(0).round(3))
gy, gx = 4, 8
h, w = a.shape[:2]
for j in range(gy):
    row = []
    for i in range(gx):
        sl = (slice(j * h // gy, (j + 1) * h // gy), slice(i * w // gx, (i + 1) * w // gx))
        row.append("%+.2f" % (b[sl].mean() - a[sl].mean()))
    print(" ".join(row))
heat = Image.fromarray((np.clip(d.mean(2) * 4, 0, 1) * 255).astype(np.uint8)).convert("RGB")
out = Image.new("RGB", (ref.width, ref.height * 3))
out.paste(ref, (0, 0))
out.paste(ren, (0, ref.height))
out.paste(heat, (0, ref.height * 2))
out.save(sys.argv[3])
