# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFont
im = Image.open(r"E:\SKM_C550i26061215010.jpg").convert("RGB")
W, H = im.size
# scale to width 1200 for readability
scale = 1200.0 / W
im = im.resize((1200, int(H * scale)))
W, H = im.size
d = ImageDraw.Draw(im)
try:
    font = ImageFont.truetype("arial.ttf", 16)
except Exception:
    font = ImageFont.load_default()
for x in range(0, W, 50):
    c = (255, 0, 0) if x % 100 == 0 else (255, 170, 170)
    d.line([(x, 0), (x, H)], fill=c, width=1)
    if x % 100 == 0:
        d.text((x + 2, 2), str(x), fill=(200, 0, 0), font=font)
for y in range(0, H, 50):
    c = (0, 120, 255) if y % 100 == 0 else (170, 210, 255)
    d.line([(0, y), (W, y)], fill=c, width=1)
    if y % 100 == 0:
        d.text((2, y + 2), str(y), fill=(0, 80, 200), font=font)
im.save(r"E:\grid_overlay.png")
print("grid", W, H)
