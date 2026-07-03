# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFont
im = Image.open(r"E:\SKM_C550i26061215010.jpg").convert("RGB")
W, H = im.size
scale = 1600.0 / W
im = im.resize((1600, int(H * scale)))
W, H = im.size
d = ImageDraw.Draw(im)
try:
    font = ImageFont.truetype("arial.ttf", 16)
except Exception:
    font = ImageFont.load_default()
for x in range(0, W, 50):
    c = (255, 0, 0) if x % 100 == 0 else (255, 185, 185)
    d.line([(x, 0), (x, H)], fill=c, width=1)
    if x % 100 == 0:
        for yy in range(0, H, 200):
            d.text((x + 2, yy + 2), str(x), fill=(200, 0, 0), font=font)
for y in range(0, H, 50):
    c = (0, 120, 255) if y % 100 == 0 else (185, 218, 255)
    d.line([(0, y), (W, y)], fill=c, width=1)
    if y % 100 == 0:
        for xx in range(0, W, 300):
            d.text((xx + 2, y + 2), str(y), fill=(0, 80, 200), font=font)
# region crops, upscaled x2 for clarity
def crop2(box, name):
    c = im.crop(box)
    c = c.resize((c.width * 2, c.height * 2))
    c.save(r"E:\z_%s.png" % name)
crop2((400, 150, 1250, 360), "head")
crop2((640, 400, 1500, 860), "right")
crop2((520, 380, 1050, 560), "photic")
print("done")
