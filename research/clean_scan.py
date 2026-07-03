# -*- coding: utf-8 -*-
# Clean up the SUBMITTED scan itself: flatten background to white, darken the
# pencil strokes, remove paper noise.  No redrawing, no rearranging.
import numpy as np
from PIL import Image, ImageFilter

src = r"E:\SKM_C550i26061215010.jpg"   # upright original scan
im = Image.open(src).convert("L")       # grayscale
g = np.asarray(im).astype(np.float32)

# 1) Flat-field: estimate paper background with a large blur, then divide so
#    uneven lighting / shadows become uniform white.
bg = im.filter(ImageFilter.GaussianBlur(radius=35))
bgf = np.asarray(bg).astype(np.float32)
bgf = np.clip(bgf, 1, 255)
norm = g / bgf * 255.0
norm = np.clip(norm, 0, 255)

# 2) Levels: pull paper (highlights) to pure white, deepen the strokes.
#    Map [white_pt..black_pt] -> [255..0] with a gentle gamma.
white_pt = 200.0   # anything brighter than this becomes pure white
black_pt = 70.0    # anything darker than this becomes pure black
lv = (norm - black_pt) / (white_pt - black_pt)
lv = np.clip(lv, 0, 1)
lv = lv ** 0.85    # gamma: slightly darken mid grays (strokes)
out = (lv * 255.0).astype(np.uint8)

res = Image.fromarray(out, "L")
res.save(r"E:\rover_cleaned_gray.jpg", quality=95)

# Optional crisp high-contrast variant (near black-and-white)
hc = np.clip((norm - 150.0) / (190.0 - 150.0), 0, 1)
Image.fromarray((hc * 255).astype(np.uint8), "L").save(r"E:\rover_cleaned_bw.jpg", quality=95)
print("done", res.size)
