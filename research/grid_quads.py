# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFont
im = Image.open(r"E:\SKM_C550i26061215010.jpg").convert("RGB")
W, H = im.size
scale = 1600.0 / W
im = im.resize((1600, int(H * scale)))
W, H = im.size
d = ImageDraw.Draw(im)
try:
    font = ImageFont.truetype("arial.ttf", 18)
except Exception:
    font = ImageFont.load_default()
for x in range(0, W, 50):
    c = (255, 0, 0) if x % 100 == 0 else (255, 180, 180)
    d.line([(x, 0), (x, H)], fill=c, width=1)
    if x % 100 == 0:
        d.text((x + 2, 2), str(x), fill=(200, 0, 0), font=font)
        d.text((x + 2, H - 22), str(x), fill=(200, 0, 0), font=font)
for y in range(0, H, 50):
    c = (0, 120, 255) if y % 100 == 0 else (180, 215, 255)
    d.line([(0, y), (W, y)], fill=c, width=1)
    if y % 100 == 0:
        d.text((2, y + 2), str(y), fill=(0, 80, 200), font=font)
print("full", W, H)
# quadrants with overlap
crops = {
    "TL": (0, 0, 900, 520),
    "TR": (700, 0, W, 520),
    "BL": (0, 420, 900, H),
    "BR": (700, 420, W, H),
}
for name, box in crops.items():
    im.crop(box).save(r"E:\q_%s.png" % name)
print("done")
