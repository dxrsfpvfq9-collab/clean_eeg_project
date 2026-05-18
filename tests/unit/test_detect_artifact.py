"""Behavior tests for `process.detect_artifact`.

These two tests are written to FAIL on the current buggy code, then
PASS after the fix. Each one pins one of the bugs called out in the
review:

  Bug #1: detect_artifact.py:142 — `np.sqrt(np.std(...))` is not RMS
          (it's sqrt of standard deviation, which has no physical meaning).
          The correct formula lives in `detect_rms` at line 31:
          `np.sqrt(np.mean(np.square(...)))`.

  Bug #2: detect_artifact.py:158 — `artifact_mask = abs(abs_signal - threshold)`
          returns a float array of distances, not a boolean mask of
          threshold crossings. Sibling functions (`detect_delta`,
          `detect_theta`, `detect_band`) all do `abs_signal > threshold`.
"""
import numpy as np
import pytest

from process import detect_artifact, tfcfilters


@pytest.fixture(scope="module")
def alpha_band_filter():
    """Filter coefficients for the alpha band (8–12 Hz) at fs=256.

    `filts.filist(forder)` populates ~14 filter pairs; we only use the
    alpha-band one (`bal/aal/bhal/ahal`).
    """
    f = tfcfilters.filts()
    f.filist(6)
    return f.bal, f.aal, f.bhal, f.ahal


def _sine(freq_hz: float, amplitude: float = 1.0, duration_s: float = 4.0, fs: int = 256) -> np.ndarray:
    """Pure sine wave at `freq_hz`, fs=256 Hz, `duration_s` seconds."""
    t = np.arange(0, duration_s, 1.0 / fs)
    return amplitude * np.sin(2 * np.pi * freq_hz * t)


def test_detect_band_with_rms_returns_correct_rms(alpha_band_filter):
    """For a large in-band sine, returned RMS should scale with amplitude.

    Bug #1: the current code returns `sqrt(std(x))` instead of `sqrt(mean(x**2))`.
    The two values happen to be close at unit amplitude, so we use a
    100x amplitude where the gap is unambiguous:
      - true RMS of filtered 100·sin(2π·10·t) ≈ 30–70 (after the filter's
        3-pass attenuation: filtfilt squared + lfilter once)
      - buggy formula: sqrt(std) of that signal ≈ √70 ≈ 8.4

    The threshold of "at least 25% of input RMS" (≈18) cleanly separates
    them: correct code passes, buggy code returns ~8 and fails.
    """
    b, a, bh, ah = alpha_band_filter
    amplitude = 100.0
    signal_in = _sine(freq_hz=10.0, amplitude=amplitude)  # 10 Hz is mid-alpha

    _mask, rms = detect_artifact.detect_band_with_rms(
        b, a, bh, ah, signal_in, len(signal_in)
    )

    input_rms = amplitude / np.sqrt(2)  # ≈ 70.7
    assert rms > 0.25 * input_rms, (
        f"RMS of filtered 100·sin(10Hz) should be on the order of {input_rms:.1f}, "
        f"got {rms:.4f}. Likely cause: detect_band_with_rms uses sqrt(std(x)) "
        "instead of sqrt(mean(x**2)) — see line 142."
    )


def test_detect_band_with_rms_returns_boolean_mask(alpha_band_filter):
    """The returned mask must be a boolean array of threshold crossings.

    Bug #2: the current code does `abs(abs_signal - threshold)`, which
    returns a float array of distances from the threshold (always
    positive, never a clean True/False). We assert dtype==bool so the
    test fails until the line is corrected to `abs_signal > threshold`.
    """
    b, a, bh, ah = alpha_band_filter
    # Big amplitude so threshold=50 is definitely exceeded somewhere.
    signal_in = _sine(freq_hz=10.0, amplitude=100.0)

    mask, _rms = detect_artifact.detect_band_with_rms(
        b, a, bh, ah, signal_in, len(signal_in), threshold=50
    )

    assert mask.dtype == bool, (
        f"artifact_mask should be a boolean array; got dtype={mask.dtype}. "
        "Likely cause: detect_band_with_rms returns "
        "`abs(abs_signal - threshold)` (distance) instead of "
        "`abs_signal > threshold` (mask)."
    )
