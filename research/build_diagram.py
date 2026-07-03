# -*- coding: utf-8 -*-
import math, fitz
from PIL import Image

W, H = 1440, 1040
S = []
def add(x): S.append(x)

FONT = "Helvetica, Arial, sans-serif"
INK = "#1f2937"
def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def text(x, y, t, size=16, anchor="middle", fill=INK, weight="normal", italic="normal", ff=FONT):
    add('<text x="%s" y="%s" font-family="%s" font-size="%s" text-anchor="%s" fill="%s" font-weight="%s" font-style="%s">%s</text>'
        % (x, y, ff, size, anchor, fill, weight, italic, esc(t)))
def rrect(x, y, w, h, rx, fill, stroke, sw=2):
    add('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" ry="%s" fill="%s" stroke="%s" stroke-width="%s"/>'
        % (x, y, w, h, rx, rx, fill, stroke, sw))
def rect(x, y, w, h, fill):
    add('<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (x, y, w, h, fill))
def line(x1, y1, x2, y2, stroke=INK, sw=2.4):
    add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s" stroke-linecap="round"/>'
        % (x1, y1, x2, y2, stroke, sw))
def circle(cx, cy, r, fill, stroke="none", sw=0):
    add('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" stroke-width="%s"/>' % (cx, cy, r, fill, stroke, sw))
def ellipse(cx, cy, rx, ry, fill, stroke="none", sw=0):
    add('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s" stroke="%s" stroke-width="%s"/>' % (cx, cy, rx, ry, fill, stroke, sw))
def path(d, fill="none", stroke=INK, sw=2.4):
    add('<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"/>' % (d, fill, stroke, sw))

CABLE = "#334155"
def arrowhead(x, y, ang, size=12, fill=CABLE):
    a1 = ang + math.radians(150); a2 = ang - math.radians(150)
    p1 = (x + size * math.cos(a1), y + size * math.sin(a1))
    p2 = (x + size * math.cos(a2), y + size * math.sin(a2))
    add('<path d="M %.1f %.1f L %.1f %.1f L %.1f %.1f Z" fill="%s"/>' % (x, y, p1[0], p1[1], p2[0], p2[1], fill))
def cable(pts, sw=2.6, both=False, color=CABLE):
    d = "M " + " L ".join("%.1f %.1f" % (x, y) for x, y in pts)
    add('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"/>' % (d, color, sw))
    (x2, y2) = pts[-1]; (x1, y1) = pts[-2]
    arrowhead(x2, y2, math.atan2(y2 - y1, x2 - x1), fill=color)
    if both:
        (x1, y1) = pts[0]; (x2, y2) = pts[1]
        arrowhead(x1, y1, math.atan2(y1 - y2, x1 - x2), fill=color)
def node(cx, cy, fill=CABLE): circle(cx, cy, 5, fill)
def clabel(cx, cy, ch):
    circle(cx, cy, 15, "#ffffff", "#334155", 2)
    text(cx, cy + 6, ch, size=18, weight="bold", fill="#0f172a")
def step(cx, cy, n):
    circle(cx, cy, 16, "#16a34a", "#ffffff", 2.5)
    text(cx, cy + 6, str(n), size=18, weight="bold", fill="#ffffff")

add('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s">' % (W, H, W, H))
rect(0, 0, W, H, "#ffffff")

# title
rect(0, 0, W, 104, "#f1f5f9")
rect(0, 104, W, 4, "#2563eb")
text(720, 62, "ROVER  w/  EEG CONTROL  VIA  ATLANTIS", size=42, weight="bold", fill="#0f172a")
text(1392, 40, "6 / 12 / 26", size=20, anchor="end", fill="#475569")

# SUBJECT
sx, sy = 180, 470
ellipse(sx, sy, 72, 80, "#ffe7c7", "#b45309", 2.5)
ellipse(sx, sy - 12, 74, 52, "#dbeafe", "#2563eb", 2.5)
path("M %s %s Q %s %s %s %s" % (sx - 60, sy - 22, sx, sy - 78, sx + 60, sy - 22), stroke="#2563eb", sw=2.5)
for dx in (-44, -22, 0, 22, 44):
    circle(sx + dx, sy - 30 - (0 if dx == 0 else 4), 5, "#2563eb")
circle(sx - 26, sy + 14, 5, "#1f2937"); circle(sx + 26, sy + 14, 5, "#1f2937")
path("M %s %s L %s %s L %s %s" % (sx, sy + 18, sx - 8, sy + 34, sx + 4, sy + 34), stroke="#92400e", sw=2)
path("M %s %s Q %s %s %s %s" % (sx - 22, sy + 52, sx, sy + 66, sx + 22, sy + 52), stroke="#92400e", sw=2.5)
text(sx, sy + 108, "SUBJECT", size=20, weight="bold", fill="#0f172a")
text(sx, sy + 130, "EEG  19/20 ch", size=15, fill="#475569")
node(sx + 64, sy)

# ATLANTIS
ax, ay, aw, ah = 430, 400, 300, 250
rrect(ax, ay, aw, ah, 14, "#eff6ff", "#2563eb", 2.6)
rrect(ax, ay, aw, 46, 14, "#2563eb", "#2563eb", 2.6)
rect(ax, ay + 30, aw, 16, "#2563eb")
text(ax + aw / 2, ay + 31, "ATLANTIS  (ATL)", size=22, weight="bold", fill="#ffffff")
text(ax + aw / 2, ay + 74, "Acquisition Hub", size=14, italic="italic", fill="#1e3a8a")
p_eeg = (ax, 560); p_usbb = (560, ay + ah); p_stim = (ax + aw, 470); p_aux = (ax + aw, 520); p_phot = (ax + aw, 600)
node(*p_eeg); text(p_eeg[0] + 14, p_eeg[1] + 5, "EEG 2CH", size=14, anchor="start", fill="#1e3a8a")
node(*p_usbb); text(p_usbb[0], p_usbb[1] - 12, "USBB", size=14, fill="#1e3a8a")
node(*p_stim); text(p_stim[0] - 14, p_stim[1] + 5, "STIM OUT", size=14, anchor="end", fill="#1e3a8a")
node(*p_aux); text(p_aux[0] - 14, p_aux[1] + 5, "AUX 1/2", size=14, anchor="end", fill="#1e3a8a")
node(*p_phot); text(p_phot[0] - 14, p_phot[1] + 5, "PHOTIC L/R", size=14, anchor="end", fill="#1e3a8a")

# ROVER
rx, ry, rw, rh = 900, 360, 270, 210
rrect(rx, ry, rw, rh, 14, "#f5f3ff", "#7c3aed", 2.6)
rrect(rx, ry, rw, 46, 14, "#7c3aed", "#7c3aed", 2.6)
rect(rx, ry + 30, rw, 16, "#7c3aed")
text(rx + rw / 2, ry + 31, "ROVER", size=22, weight="bold", fill="#ffffff")
text(rx + rw / 2, ry + 74, "AVS Stim Generator", size=14, italic="italic", fill="#5b21b6")
p_stimin = (rx, 470); p_bio = (rx, 520); p_audio = (1010, ry)
node(*p_stimin); text(p_stimin[0] + 14, p_stimin[1] + 5, "STIM IN", size=14, anchor="start", fill="#5b21b6")
node(*p_bio); text(p_bio[0] + 14, p_bio[1] + 5, "BIOMOD OUT", size=14, anchor="start", fill="#5b21b6")
node(*p_audio); text(1010, 498, "AUDIO OUT", size=14, anchor="middle", fill="#5b21b6")

# PC
px, py, pw, ph = 430, 770, 300, 170
rrect(px, py, pw, ph, 14, "#ecfeff", "#0891b2", 2.6)
rrect(px, py, pw, 46, 14, "#0891b2", "#0891b2", 2.6)
rect(px, py + 30, pw, 16, "#0891b2")
text(px + pw / 2, py + 31, "PC  -  BRAIN AVATAR", size=20, weight="bold", fill="#ffffff")
text(px + pw / 2, py + 88, "e.g. cross-frequency", size=15, italic="italic", fill="#155e75")
text(px + pw / 2, py + 112, "coupling software", size=15, italic="italic", fill="#155e75")
p_usba = (560, py)
node(*p_usba); text(p_usba[0], p_usba[1] + 22, "USBA", size=14, fill="#155e75")

# HEADPHONES
hx, hy = 1240, 210
path("M %s %s A 58 58 0 0 1 %s %s" % (hx - 58, hy, hx + 58, hy), stroke="#334155", sw=8)
rrect(hx - 70, hy - 6, 26, 52, 9, "#334155", "#1f2937", 2)
rrect(hx + 44, hy - 6, 26, 52, 9, "#334155", "#1f2937", 2)
text(hx, hy + 104, "HEADPHONES", size=18, weight="bold", fill="#0f172a")
node(hx, hy + 50, "#334155")

# PHOTIC GLASSES
gx, gy = 1255, 600
rrect(gx - 66, gy - 24, 52, 48, 12, "#fee2e2", "#dc2626", 2.5)
rrect(gx + 14, gy - 24, 52, 48, 12, "#fee2e2", "#dc2626", 2.5)
line(gx - 14, gy, gx + 14, gy, stroke="#dc2626", sw=4)
line(gx - 66, gy - 14, gx - 92, gy - 22, stroke="#dc2626", sw=4)
line(gx + 66, gy - 14, gx + 92, gy - 22, stroke="#dc2626", sw=4)
text(gx, gy + 52, "PHOTIC GLASSES", size=18, weight="bold", fill="#0f172a")
node(gx - 66, gy, "#dc2626")

# cables
cable([(sx + 64, sy), (340, sy), (340, 560), p_eeg])
text(310, 455, "EEG", size=14, weight="bold", fill="#334155")
step(300, 430, 1)
cable([p_usbb, (560, py)], both=True)
clabel(560, 710, "D"); step(620, 720, 4)
cable([p_stim, p_stimin]); clabel(815, 470, "C")
cable([p_bio, p_aux]); clabel(815, 520, "B")
cable([p_phot, (845, 600), (gx - 66, gy)]); clabel(792, 600, "A")
cable([p_audio, (1010, 300), (hx, 300), (hx, hy + 50)]); step(1010, 322, 3)
step(410, py + 22, 2)

# legend
lx, ly, lw, lh = 60, 660, 330, 360
rrect(lx, ly, lw, lh, 12, "#f8fafc", "#cbd5e1", 2)
text(lx + 18, ly + 34, "CABLE KEY", size=17, weight="bold", anchor="start", fill="#0f172a")
keys = [("A", "Photic drive: ATL Photic L/R to glasses"),
        ("B", "BioMod out: Rover to ATL Aux 1/2"),
        ("C", "Stim: ATL to Rover Stim In"),
        ("D", "USB link: ATL USBB to PC USBA")]
yy = ly + 64
for ch, desc in keys:
    clabel(lx + 30, yy - 5, ch)
    text(lx + 56, yy, desc, size=14, anchor="start", fill="#334155")
    yy += 34
text(lx + 18, yy + 14, "SEQUENCE", size=17, weight="bold", anchor="start", fill="#0f172a")
steps = [("1", "Acquire EEG from subject"),
         ("2", "Process in Brain Avatar PC"),
         ("3", "Audio stim to headphones"),
         ("4", "USB control link to Atlantis")]
yy += 44
for n, desc in steps:
    step(lx + 30, yy - 5, int(n))
    text(lx + 56, yy, desc, size=14, anchor="start", fill="#334155")
    yy += 33

add('</svg>')

svg = "\n".join(S)
open(r"E:\rover_eeg_atlantis.svg", "w", encoding="utf-8").write(svg)
doc = fitz.open(r"E:\rover_eeg_atlantis.svg")
pix = doc[0].get_pixmap(dpi=200)
pix.save(r"E:\rover_eeg_atlantis.png")
im = Image.open(r"E:\rover_eeg_atlantis.png").convert("RGB")
im.save(r"E:\rover_eeg_atlantis.jpg", quality=94)
print("done", pix.width, pix.height)
