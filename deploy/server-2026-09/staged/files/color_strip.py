"""Colour strips drawn as one LineCollection instead of one Line2D per segment.

The component viewer draws three strips (the colour bar under the waveform,
the Bath Water Graph and the Log FFT Waterfall) as runs of short horizontal
segments, each coloured by its own value. They used to be drawn with one
ax.plot() call per segment: ~50,000 Line2D artists per component page, about
19 of the page's 24 s in a profile, and every one of them redrawn when the
page is composited. One LineCollection carries the same segments, colours and
width as a single artist.

The look is kept: capstyle 'projecting' is Line2D's default for solid lines
(LineCollection defaults to 'butt'), so each segment still reaches half a
linewidth past its ends and adjacent segments overlap exactly as before; and
autolim=True updates the data limits the way each plot() call did, so an
autoscaled axis lands on the same limits. Display only -- no metric reads
these artists.
"""
import numpy as np
from matplotlib.collections import LineCollection


def add_color_strip(ax, x, y, colors, linewidth):
    """Draw segments (x[j], y[j]) -> (x[j+1], y[j]) for j in 0..len(x)-2.

    `y` is a scalar (one row) and `colors` holds at least len(x)-1 RGBA rows,
    segment j taking colors[j] -- the same pairing the per-segment loops used.
    """
    x = np.asarray(x, dtype=float)
    n = len(x) - 1
    if n <= 0:
        return None
    segs = np.empty((n, 2, 2))
    segs[:, 0, 0] = x[:-1]
    segs[:, 1, 0] = x[1:]
    segs[:, :, 1] = float(y)
    lc = LineCollection(segs, colors=np.asarray(colors)[:n],
                        linewidths=linewidth, capstyle='projecting')
    ax.add_collection(lc, autolim=True)
    ax.autoscale_view()
    return lc
