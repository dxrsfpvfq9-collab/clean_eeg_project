"""Per-epoch quality screening: reject a 10 s epoch if ANY channel is bad.

REPORT-ONLY. Nothing in this module is wired into the metrics path. It exists
so the rejection rate and its causes can be measured across a corpus before any
decision is taken about acting on it.

Why acting on it is a separate decision
---------------------------------------
Dropping epochs changes `numpages` and every aggregate the Brain Panel builds,
and the EC_191 reference database was built from 192 files with no rejection at
all. Applying this to the metrics therefore invalidates every z-score until
that database is rebuilt. Applying it to the ICA input is worse: montage 6
rebuilds the report signals *from* the decomposition, so it moves the panel the
same way the pre-ICA line filter did (39 of 48 z-scores shifted).

Which signal to judge
---------------------
Electrode quality must be measured in ELECTRODE space on unnormalized data --
`mysigs` in edftotextbynameplotproc, i.e. the raw slice in microvolts. By the
time the artifact detectors run, `myfilteredsigs` has been replaced by ICA
components (line ~509) and rescaled by 10/stdmeas (line ~567), so neither its
amplitudes nor its channel identities mean what they say. `myvisualsigs` is no
good either: it is bandpassed 1.5-45 Hz, which removes the 60 Hz that a bad
electrode contact announces itself with.

Criteria, per channel per epoch
-------------------------------
flat        channel is dead/disconnected      std < FLAT_UV
excursion   pop, movement, saturation         max |x - median| > AMP_UV
rms_outlier intermittent noise                epoch RMS > RMS_K x that channel's
                                              own median epoch RMS
line60      bad contact / line pickup         58-62 Hz share of 1-80 Hz power
                                              > LINE_FRAC

The RMS test is relative to each channel's own median across epochs, so it is
scale-free and does not punish a legitimately high-amplitude recording.
"""
import numpy as np

FLAT_UV = 0.5        # std below this microvolts -> dead channel
AMP_UV = 200.0       # peak deviation from the epoch median, microvolts
RMS_K = 4.0          # epoch RMS this many times the channel's median
LINE_FRAC = 0.50     # share of 1-80 Hz power sitting in 58-62 Hz

REASONS = ("flat", "excursion", "rms_outlier", "line60")


def _epochs(sigs, length):
    """(n_chan, n_samp) -> (n_chan, n_epoch, length), dropping any partial tail."""
    n_chan, n_samp = sigs.shape
    n_ep = n_samp // length
    if n_ep < 1:
        return np.empty((n_chan, 0, length))
    return sigs[:, :n_ep * length].reshape(n_chan, n_ep, length)


def screen(sigs, fs=256.0, length=2560, flat_uv=FLAT_UV, amp_uv=AMP_UV,
           rms_k=RMS_K, line_frac=LINE_FRAC):
    """Screen every epoch of every channel.

    `sigs` is (n_chan, n_samp) in microvolts, electrode space, unnormalized.

    Returns a dict:
      reject        (n_epoch,) bool  -- True if ANY channel tripped ANY test
      flags         {reason: (n_chan, n_epoch) bool}
      per_epoch     (n_epoch,) int   -- how many channels tripped
      per_channel   (n_chan,) int    -- how many epochs that channel tripped
      n_epoch, n_chan
    """
    ep = _epochs(np.asarray(sigs, dtype=float), length)
    n_chan, n_ep = ep.shape[0], ep.shape[1]
    if n_ep == 0:
        return dict(reject=np.zeros(0, bool),
                    flags={r: np.zeros((n_chan, 0), bool) for r in REASONS},
                    per_epoch=np.zeros(0, int), per_channel=np.zeros(n_chan, int),
                    n_epoch=0, n_chan=n_chan)

    flags = {}

    # flat / dead
    std = ep.std(axis=2)
    flags["flat"] = std < flat_uv

    # excursion, measured against each epoch's own median so a DC offset on a
    # channel does not read as a pop on every epoch
    med = np.median(ep, axis=2, keepdims=True)
    flags["excursion"] = np.max(np.abs(ep - med), axis=2) > amp_uv

    # RMS outlier relative to the channel's own median epoch
    rms = np.sqrt(np.mean(ep ** 2, axis=2))
    base = np.median(rms, axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(base > 0, rms / base, 0.0)
    flags["rms_outlier"] = ratio > rms_k

    # 60 Hz share of 1-80 Hz power
    spec = np.abs(np.fft.rfft(ep - med, axis=2)) ** 2
    freqs = np.fft.rfftfreq(length, d=1.0 / fs)
    inband = (freqs >= 1.0) & (freqs <= 80.0)
    line = (freqs >= 58.0) & (freqs <= 62.0)
    tot = spec[:, :, inband].sum(axis=2)
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(tot > 0, spec[:, :, line].sum(axis=2) / tot, 0.0)
    flags["line60"] = share > line_frac

    any_bad = np.zeros((n_chan, n_ep), bool)
    for r in REASONS:
        any_bad |= flags[r]

    return dict(reject=any_bad.any(axis=0),
                flags=flags,
                per_epoch=any_bad.sum(axis=0),
                per_channel=any_bad.sum(axis=1),
                n_epoch=n_ep, n_chan=n_chan)


def summarize(res, channel_names=None):
    """Condense a screen() result into a printable dict."""
    n_ep = res["n_epoch"]
    rej = int(res["reject"].sum())
    by_reason = {r: int(res["flags"][r].any(axis=0).sum()) for r in REASONS}

    names = channel_names or ["ch%02d" % (i + 1) for i in range(res["n_chan"])]
    chans = []
    for i, cnt in enumerate(res["per_channel"]):
        if cnt:
            why = {r: int(res["flags"][r][i].sum()) for r in REASONS
                   if res["flags"][r][i].any()}
            chans.append((names[i], int(cnt), why))
    chans.sort(key=lambda c: -c[1])

    # A channel bad in most epochs is an ELECTRODE problem, not an epoch
    # problem: "reject if any channel is bad" would throw the whole recording
    # away. Surface it so that case is handled by excluding the channel.
    persistent = [c[0] for c in chans if n_ep and c[1] > 0.5 * n_ep]

    return dict(n_epoch=n_ep, n_chan=res["n_chan"], rejected=rej,
                pct=(100.0 * rej / n_ep) if n_ep else 0.0,
                by_reason=by_reason, channels=chans, persistent=persistent)
