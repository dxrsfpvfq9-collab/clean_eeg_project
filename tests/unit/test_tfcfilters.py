"""Behavior tests for `process.tfcfilters`.

Unlike test_detect_artifact, these are NOT targeted at known bugs —
they exist as regression guards before we touch the filter chain.
Two pending concerns covered here:

  - The double-filter (`filtfilt` then `lfilter` at tfcfilters.py:34–35)
    is suspicious but changing it would alter every downstream output;
    we want a test that captures *current* attenuation behavior so we
    can compare before/after when the question is revisited.

  - `fs=256` is hardcoded at tfcfilters.py:45. These tests document the
    assumption so a future parameterization can't silently break it.
"""
import numpy as np
import pytest

from process import tfcfilters


FS = 256
DURATION_S = 4.0


@pytest.fixture(scope="module")
def filter_bank():
    """All filter pairs from `filts.filist(forder=6)`."""
    f = tfcfilters.filts()
    f.filist(6)
    return f


def _sine(freq_hz: float, amplitude: float = 1.0) -> np.ndarray:
    t = np.arange(0, DURATION_S, 1.0 / FS)
    return amplitude * np.sin(2 * np.pi * freq_hz * t)


def _rms_steady_state(x: np.ndarray) -> float:
    """RMS of x with the first/last 10% trimmed to avoid edge transients."""
    edge = len(x) // 10
    core = x[edge:-edge]
    return float(np.sqrt(np.mean(core ** 2)))


def test_get_statistics_of_constant_signal():
    """Constant input → mean == value, std == 0. Trivial sanity check."""
    mean, median, std = tfcfilters.get_statistics([5.0] * 100)

    assert mean == pytest.approx(5.0)
    assert median == pytest.approx(5.0)
    assert std == pytest.approx(0.0)


def test_get_statistics_of_known_sine():
    """For sin(2π·10·t), fs=256, ≥4s: mean ≈ 0, std ≈ 1/√2 ≈ 0.707."""
    x = _sine(freq_hz=10.0, amplitude=1.0)
    mean, _median, std = tfcfilters.get_statistics(x.tolist())

    assert abs(mean) < 0.01
    assert std == pytest.approx(1.0 / np.sqrt(2), abs=0.01)


def test_alpha_filter_passes_in_band(filter_bank):
    """A 10 Hz sine through the alpha (8-12 Hz) filter should survive
    with most of its amplitude intact."""
    f = filter_bank
    sig = _sine(freq_hz=10.0, amplitude=1.0)

    out = tfcfilters.tfcfilterall(f.bal, f.aal, f.bhal, f.ahal, sig, len(sig))

    rms_in = _rms_steady_state(sig)
    rms_out = _rms_steady_state(out)
    assert rms_out > 0.5 * rms_in, (
        f"alpha filter attenuated an in-band 10 Hz signal too much: "
        f"rms_in={rms_in:.3f}, rms_out={rms_out:.3f}"
    )


def test_alpha_filter_attenuates_out_of_band(filter_bank):
    """A 60 Hz sine through the alpha (8-12 Hz) filter should be
    heavily attenuated. This is the regression guard for any future
    filter-chain refactor."""
    f = filter_bank
    sig = _sine(freq_hz=60.0, amplitude=1.0)

    out = tfcfilters.tfcfilterall(f.bal, f.aal, f.bhal, f.ahal, sig, len(sig))

    rms_in = _rms_steady_state(sig)
    rms_out = _rms_steady_state(out)
    assert rms_out < 0.05 * rms_in, (
        f"alpha filter failed to attenuate 60 Hz out-of-band signal: "
        f"rms_in={rms_in:.3f}, rms_out={rms_out:.3f}"
    )
