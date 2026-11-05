"""tools/edf_power.posterior_peak: a peak must be a peak."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
from edf_power import posterior_peak  # noqa: E402

F = np.arange(0, 45.25, 0.25)


def slope():
    return 20.0 / np.maximum(F, 0.25)


def bump(hz, width, height):
    return 1 + height * np.exp(-0.5 * ((F - hz) / width) ** 2)


def test_clear_alpha_is_found():
    assert abs(posterior_peak(F, slope() * bump(10.0, 0.6, 8)) - 10.0) < 0.1


def test_falling_spectrum_with_no_bump_has_no_peak():
    assert posterior_peak(F, slope()) is None


def test_small_wobble_is_not_a_peak():
    assert posterior_peak(F, slope() * bump(7.5, 0.4, 0.2)) is None


def test_narrow_real_alpha_is_kept():
    assert abs(posterior_peak(F, slope() * bump(9.5, 0.3, 10)) - 9.5) < 0.1     # about 0.7 Hz wide


def test_one_bin_spike_gives_way_to_alpha():
    p = slope() * bump(10.0, 0.6, 5)
    p[F == 8.0] *= 40
    assert abs(posterior_peak(F, p) - 10.0) < 0.1


def test_peak_on_the_window_edge_is_refused():
    assert posterior_peak(F, slope() * bump(7.0, 0.5, 5)) is None
