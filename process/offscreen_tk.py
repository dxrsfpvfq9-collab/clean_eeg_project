"""Render the component-viewer page without a screen.

WHY
---
The cascade's component page is built as a Tk window and then captured with
`ImageGrab.grab(bbox=...)`, which copies raw pixels off the *desktop*. That ties
every cascade to a live, unlocked, composited interactive session: the render
dies when the workstation sleeps, when an RDP client disconnects, when the lock
screen appears, and it cannot run as a service or over SSM at all. It also makes
the output depend on the screen resolution, because the page is sized from
`winfo_screenwidth()`.

Nothing about the page actually needs a screen. It is ten matplotlib figures and
a handful of labels, buttons, a listbox and a grey side panel, every one placed
at absolute pixel coordinates, and every figure created with an explicit
`figsize` and `dpi=100` -- so each one's pixel size is known before it is drawn.

So this module stands in for the small slice of tkinter that `dummy_gui` uses,
records what gets placed where, and composites the page with matplotlib's Agg
backend and PIL. Same figures, same coordinates, no desktop.

This is the same move `process/brain_render.py` already made for the brain page,
which replaced VTK/OpenGL with numpy + Agg. A previous attempt at the component
page went the other way -- Win32 `PrintWindow` into an off-screen DC -- and was
reverted because PrintWindow captures Tk-native widgets but misses the bitmap
blits matplotlib makes into its own `tk.PhotoImage`. That failure does not apply
here: this does not photograph Tk, it bypasses Tk.

HOW TO USE
----------
Set `CLEANEEG_OFFSCREEN=1`. `files/dummy_gui.py` then binds its widget names to
this module instead of tkinter, and `save_gui_screenshot` returns the composited
image rather than grabbing the screen.

The page size comes from `CLEANEEG_PAGE_SIZE` ("WxH", default "1920x1080") and
is fixed regardless of the actual display, so output is reproducible across
machines.

NOT A TKINTER IMPLEMENTATION
----------------------------
Only what `dummy_gui` touches is real. Unknown attributes resolve to a no-op via
`_Widget.__getattr__`, so a call this module has never heard of is ignored
rather than raising -- the page is a drawing, and a widget method that does not
affect the drawing does not matter. The risk that trades against is a silent
omission, which is why `render()` is verified by diffing against a Tk-rendered
page rather than by inspection.
"""

import io
import os

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PIL import Image, ImageDraw, ImageFont

# Tk on Windows measures font sizes in points against a 96 dpi desktop; PIL
# wants pixels.
_PT_TO_PX = 96.0 / 72.0

_FONT_FILES = {
    ("helvetica", False): "arial.ttf",
    ("helvetica", True): "arialbd.ttf",
    ("arial", False): "arial.ttf",
    ("arial", True): "arialbd.ttf",
    ("courier", False): "cour.ttf",
    ("courier", True): "courbd.ttf",
}
_FONT_CACHE = {}


def _load_font(family, size_px, bold):
    key = (family.lower(), size_px, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    name = _FONT_FILES.get((family.lower(), bold), "arialbd.ttf" if bold else "arial.ttf")
    try:
        f = ImageFont.truetype(name, size_px)
    except Exception:
        try:
            f = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                                "Fonts", name), size_px)
        except Exception:
            f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _parse_font(spec):
    """Tk font spec -> (family, pixel size, bold).

    Accepts 'Helvetica 15', ('Helvetica', 50, 'bold'), a shim Font object, or
    None. Note 'Helveica 15' appears in dummy_gui -- a typo Tk silently falls
    back on, so unknown families must fall back rather than raise.
    """
    family, size_pt, bold = "Helvetica", 12, False
    if spec is None:
        pass
    elif isinstance(spec, Font):
        family, size_pt, bold = spec.family, spec.size, spec.bold
    elif isinstance(spec, (tuple, list)):
        if len(spec) > 0:
            family = str(spec[0])
        if len(spec) > 1:
            try:
                size_pt = int(spec[1])
            except (TypeError, ValueError):
                pass
        if len(spec) > 2:
            bold = "bold" in str(spec[2]).lower()
    elif isinstance(spec, str):
        parts = spec.split()
        if parts:
            family = parts[0]
        for p in parts[1:]:
            if p.isdigit():
                size_pt = int(p)
            elif p.lower() == "bold":
                bold = True
    return family, max(1, int(round(size_pt * _PT_TO_PX))), bold


def _as_text(value):
    """Tk renders a tuple argument to text= as its str(); reproduce that.

    dummy_gui does `text=("Component:", idx)`, which Tk shows as
    `Component: 3` -- space separated, no parentheses.
    """
    if isinstance(value, tuple):
        return " ".join(str(v) for v in value)
    return str(value)


class Font(object):
    """Stand-in for tkinter.font.Font (used for the listbox)."""

    def __init__(self, size=12, family="Helvetica", weight="normal", **kw):
        self.size = size
        self.family = family
        self.bold = str(weight).lower() == "bold"

    def __getattr__(self, name):
        return lambda *a, **k: None


class _Widget(object):
    """Base for every fake widget: records placement, ignores the rest."""

    kind = "widget"

    def __init__(self, master=None, **kw):
        self.master = master if isinstance(master, OffscreenWindow) else None
        self.kw = kw
        self.x = self.y = 0
        self.width = self.height = None
        self.lines = []

    def place(self, x=0, y=0, width=None, height=None, **kw):
        self.x, self.y = int(x), int(y)
        if width is not None:
            self.width = int(width)
        if height is not None:
            self.height = int(height)
        if self.master is not None:
            self.master.items.append(self)
        return self

    def configure(self, **kw):
        """Post-creation updates MUST land.

        dummy_gui builds `lab` and `reason_lab` empty and fills them later via
        .config(text=..., fg=..., bg=...). Letting __getattr__ swallow that
        silently dropped the Keep/Remove status and its reason from every page
        -- caught by diffing an offscreen page against a Tk one, not by reading
        the code, which is why that diff is part of the process.
        """
        self.kw.update(kw)
        return self

    config = configure

    # Anything this module does not model cannot affect the drawing.
    def __getattr__(self, name):
        return lambda *a, **k: None


class Label(_Widget):
    kind = "label"


class Button(_Widget):
    kind = "button"


class Canvas(_Widget):
    kind = "canvas"


class Listbox(_Widget):
    kind = "listbox"

    def insert(self, index, value):
        self.lines.append(_as_text(value))


_STYLES = {}


class Style(object):
    """Records ttk style definitions so Button can read its colours back."""

    def __init__(self, *a, **k):
        pass

    def configure(self, name=None, **kw):
        if name:
            _STYLES.setdefault(name, {}).update(kw)
        return None

    def map(self, *a, **k):
        return None

    def theme_use(self, *a, **k):
        return None

    def __getattr__(self, name):
        return lambda *a, **k: None


class _TkWidgetProxy(object):
    """What FigureCanvasTkAgg.get_tk_widget() returns: only .place matters."""

    def __init__(self, owner):
        self._owner = owner

    def place(self, x=0, y=0, **kw):
        self._owner.x, self._owner.y = int(x), int(y)
        if self._owner.master is not None:
            self._owner.master.items.append(self._owner)
        return self

    def __getattr__(self, name):
        return lambda *a, **k: None


class FigureCanvasTkAgg(object):
    """Stand-in for the Tk-embedded canvas: holds the figure until compositing."""

    kind = "figure"

    def __init__(self, figure, master=None):
        self.figure = figure
        self.master = master if isinstance(master, OffscreenWindow) else None
        self.x = self.y = 0
        self._widget = _TkWidgetProxy(self)

    def get_tk_widget(self):
        return self._widget

    def draw(self):
        return None

    def __getattr__(self, name):
        return lambda *a, **k: None


class OffscreenWindow(object):
    """Stand-in for tk.Tk(): a page to draw on, with no window behind it."""

    def __init__(self, *a, **kw):
        w, h = 1920, 1080
        spec = os.environ.get("CLEANEEG_PAGE_SIZE", "")
        if "x" in spec.lower():
            try:
                pw, ph = spec.lower().split("x", 1)
                w, h = int(pw), int(ph)
            except ValueError:
                pass
        self._w, self._h = w, h
        self.bg = "white"
        self.items = []

    # -- geometry queries dummy_gui makes -----------------------------------
    def winfo_screenwidth(self):
        return self._w

    def winfo_screenheight(self):
        return self._h

    def winfo_width(self):
        return self._w

    def winfo_height(self):
        return self._h

    def winfo_rootx(self):
        return 0

    def winfo_rooty(self):
        return 0

    def configure(self, **kw):
        if "bg" in kw:
            self.bg = kw["bg"]
        if "background" in kw:
            self.bg = kw["background"]

    config = configure

    def geometry(self, spec=None):
        if spec and "x" in spec:
            try:
                pw, ph = spec.split("+")[0].split("x", 1)
                self._w, self._h = int(pw), int(ph)
            except ValueError:
                pass

    # -- everything else is a no-op -----------------------------------------
    def __getattr__(self, name):
        return lambda *a, **k: None

    # -- the point of the whole module --------------------------------------
    def render_offscreen(self):
        """Composite everything placed on this window into a PIL image."""
        page = Image.new("RGB", (self._w, self._h), self.bg or "white")
        draw = ImageDraw.Draw(page)

        for item in self.items:
            try:
                self._draw_item(page, draw, item)
            except Exception as exc:      # one bad panel must not lose the page
                print("[offscreen] could not draw %s at (%s,%s): %r"
                      % (getattr(item, "kind", "?"),
                         getattr(item, "x", "?"), getattr(item, "y", "?"), exc))
        return page

    def _draw_item(self, page, draw, item):
        kind = getattr(item, "kind", "widget")

        if kind == "figure":
            fig = item.figure
            FigureCanvasAgg(fig)
            fig.canvas.draw()
            buf = np.asarray(fig.canvas.buffer_rgba())
            im = Image.fromarray(buf, "RGBA")
            page.paste(im, (item.x, item.y), im)
            return

        kw = item.kw
        bg = kw.get("bg", kw.get("background"))
        fg = kw.get("fg", kw.get("foreground", "black"))
        family, px, bold = _parse_font(kw.get("font"))
        font = _load_font(family, px, bold)

        if kind == "canvas":
            w = item.width or kw.get("width", 0)
            h = item.height or kw.get("height", 0)
            draw.rectangle([item.x, item.y, item.x + w, item.y + h],
                           fill=bg or "#d9d9d9")
            return

        if kind == "button":
            w = item.width or 120
            h = item.height or 30
            # ttk styles carry the colour (RED./GREEN./GRAY.TButton); the style
            # engine is not modelled, so take the hint from the style name.
            # The Windows ttk themes (vista/xpnative) IGNORE `background` on a
            # TButton -- the face stays system grey and only the border carries
            # the style's colour. Reproducing the declared background as a solid
            # fill made the buttons look nothing like the real page, so take the
            # colour to the outline instead and read it from the recorded style.
            style_kw = _STYLES.get(str(kw.get("style", "")), {})
            edge = style_kw.get("background", "#7a7a7a")
            face = "#f0f0f0"
            sfam, spx, sbold = _parse_font(style_kw.get("font", kw.get("font")))
            btn_font = _load_font(sfam, spx, sbold)
            draw.rectangle([item.x, item.y, item.x + w, item.y + h],
                           fill=face, outline=edge, width=2)
            text = _as_text(kw.get("text", ""))
            tw, th = _text_size(draw, text, btn_font)
            draw.text((item.x + (w - tw) / 2, item.y + (h - th) / 2),
                      text, font=btn_font, fill=style_kw.get("foreground", "black"))
            return

        if kind == "listbox":
            w = item.width or 125
            h = item.height or 200
            draw.rectangle([item.x, item.y, item.x + w, item.y + h],
                           fill="white", outline="#7a7a7a")
            # Tk gives a listbox row the font's line height plus ~2px, not the
            # tight bounding box of the glyphs, so rows here would bunch up.
            row_h = int(px * 1.35) + 2
            ly = item.y + 2
            for line in item.lines:
                tw, _ = _text_size(draw, line, font)
                justify = str(kw.get("justify", "left")).lower()
                tx = item.x + (w - tw) / 2 if justify == "center" else item.x + 3
                draw.text((tx, ly), line, font=font, fill="black")
                ly += row_h
                if ly > item.y + h:
                    break
            return

        # label (and anything else with text)
        text = _as_text(kw.get("text", ""))
        if not text:
            return
        tw, th = _text_size(draw, text, font)
        if bg:
            draw.rectangle([item.x, item.y, item.x + tw, item.y + th], fill=bg)
        draw.text((item.x, item.y), text, font=font, fill=fg or "black")


def _text_size(draw, text, font):
    try:
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        return r - l, b - t
    except AttributeError:          # very old PIL
        return draw.textsize(text, font=font)


# `tk.Tk()` in dummy_gui resolves here.
Tk = OffscreenWindow

# dummy_gui does `import tkinter.font as font` then `font.Font(...)`; give it a
# module-like object exposing Font.
class _FontModule(object):
    Font = Font

    def __getattr__(self, name):
        return lambda *a, **k: None


font = _FontModule()


class _TtkModule(object):
    Style = Style
    Button = Button
    Label = Label

    def __getattr__(self, name):
        return lambda *a, **k: None


ttk = _TtkModule()

# tkinter constants dummy_gui references.
END = "end"
