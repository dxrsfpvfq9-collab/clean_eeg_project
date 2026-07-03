# -*- coding: utf-8 -*-
# Straighten / regularize the submitted drawing IN PLACE.  Same objects, same
# positions, same connections as the scan -- only the wavy pencil lines are
# replaced with ruled straight lines and the boxes squared.  Coordinate space
# matches the 1600-wide gridded scan used to measure every element.
import fitz
from PIL import Image

W, H = 1600, 1236
S = []
def add(x): S.append(x)
FONT = "Helvetica, Arial, sans-serif"
INK = "#111111"
def esc(t): return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def label(x, y, t, size=24, anchor="start", italic="normal", weight="normal"):
    add('<text x="%s" y="%s" font-family="%s" font-size="%s" text-anchor="%s" fill="%s" font-weight="%s" font-style="%s">%s</text>'
        % (x, y, FONT, size, anchor, INK, weight, italic, esc(t)))
def box(x, y, w, h, sw=2.4):
    add('<rect x="%s" y="%s" width="%s" height="%s" fill="none" stroke="%s" stroke-width="%s"/>' % (x, y, w, h, INK, sw))
def oval(cx, cy, rx, ry, t):
    add('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="none" stroke="%s" stroke-width="2.2"/>' % (cx, cy, rx, ry, INK))
    label(cx, cy + 7, t, size=20, anchor="middle")
def line(x1, y1, x2, y2, sw=2.4):
    add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s" stroke-linecap="square"/>' % (x1, y1, x2, y2, INK, sw))
def wire(pts, sw=2.4):
    d = "M " + " L ".join("%.1f %.1f" % (x, y) for x, y in pts)
    add('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="miter" stroke-linecap="square"/>' % (d, INK, sw))
def dot(x, y, r=5):
    add('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (x, y, r, INK))
def circle(cx, cy, r, sw=2.4):
    add('<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="%s"/>' % (cx, cy, r, INK, sw))

add('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s">' % (W, H, W, H))
add('<rect x="0" y="0" width="%s" height="%s" fill="#ffffff"/>' % (W, H))

# ---- TITLE ----
label(855, 90, "ROVER   w/   EEG CONTROL   VIA   ATLANTIS", size=44, anchor="middle", weight="bold")
line(225, 123, 1410, 123, sw=3)

# ---- BRAIN AVATAR ----
label(70, 360, "Brain Avatar", size=32)

# ---- PC BOX ----
box(60, 432, 318, 188)
oval(118, 460, 45, 18, "STEP 2")
label(105, 522, "P C", size=30)
oval(115, 605, 45, 18, "STEP 4")
label(168, 612, "USBA", size=24)
dot(208, 600)

# ---- e.g. note ----
label(70, 675, "e.g.", size=26)
label(58, 718, "cross-frequency", size=26)
label(55, 762, "coupling", size=26)
label(95, 808, "sw", size=26)

# ---- ROVER BOX ----
box(630, 220, 290, 290)
oval(815, 258, 58, 22, "STEP 3")
label(700, 345, "Audio", size=28)
label(720, 412, "Rover", size=32, italic="italic")
label(700, 480, "STIM IN", size=26)
dot(820, 220)               # audio out (top)
dot(700, 510)               # stim in (bottom -> C)
dot(920, 455); dot(920, 495)  # biomod out pins (right)
label(935, 500, "BIOMOD", size=24)
label(935, 532, "OUT   (B)", size=24)

# ---- HEADPHONES ----
label(980, 188, "HEADPHONES", size=30, anchor="middle")
wire([(820, 220), (820, 205), (1180, 205), (1180, 258), (1228, 260)])
add('<path d="M 1228 260 Q 1278 208 1328 260" fill="none" stroke="%s" stroke-width="2.4"/>' % INK)
box(1215, 258, 26, 46)
box(1315, 258, 26, 46)

# ---- ATLANTIS : two boxes ----
box(690, 605, 110, 190)     # USBB / ATL
box(800, 605, 165, 190)     # PHOTIC L/R
label(700, 662, "USBB", size=24)
label(705, 697, "ATL", size=24)
label(812, 658, "PHOTIC", size=24)
label(832, 692, "L/R", size=24)
label(815, 752, "AUX", size=22)
label(820, 782, "1/2", size=22)
dot(690, 660)               # USBB  -> (D)
dot(770, 605)               # top   -> (C)
dot(965, 640)               # PHOTIC L/R -> (A)

# ---- STEP 1 ----
oval(985, 700, 52, 21, "STEP 1")

# ---- WIRES ----
# (C) rover STIM IN -> atlantis top
wire([(700, 510), (700, 560), (770, 560), (770, 605)])
label(725, 582, "(C)", size=24)
# (D) PC USBA -> atlantis USBB
wire([(208, 600), (640, 600), (640, 660), (690, 660)])
label(255, 588, "(D)", size=24)
# (A) atlantis PHOTIC L/R -> photic glasses
wire([(965, 640), (1110, 640), (1110, 475), (1130, 475)])

# ---- PHOTIC GLASSES ----
label(975, 430, "PHOTIC GLASSES   (A)", size=26)
box(1130, 456, 52, 38)
box(1202, 456, 52, 38)
line(1182, 475, 1202, 475)
line(1130, 468, 1110, 462)
line(1254, 468, 1290, 470)

# ---- EEG HEAD ----
circle(1330, 580, 92)
label(1180, 540, "EEG", size=26)
dot(1305, 565, 4); dot(1357, 565, 4)
line(1305, 620, 1357, 620)
# EEG cable: head -> down -> across -> up to EEG 2CH -> atlantis bottom
wire([(1330, 672), (1330, 1135), (660, 1135), (660, 985), (720, 985), (720, 795)])
label(595, 1000, "EEG", size=24)
label(595, 1032, "2CH", size=24)

# ---- DATE ----
label(1300, 852, "6 / 12 / 26", size=28, anchor="middle")

add('</svg>')
svg = "\n".join(S)
open(r"E:\rover_regular.svg", "w", encoding="utf-8").write(svg)
doc = fitz.open(r"E:\rover_regular.svg")
pix = doc[0].get_pixmap(dpi=160)
pix.save(r"E:\rover_regular.png")
Image.open(r"E:\rover_regular.png").convert("RGB").save(r"E:\rover_regular.jpg", quality=94)
print("done", pix.width, pix.height)
