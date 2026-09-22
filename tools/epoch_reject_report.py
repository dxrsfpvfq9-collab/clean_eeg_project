"""Report which 10 s epochs an "any bad channel rejects the epoch" rule drops.

REPORT ONLY -- reads EDFs, prints what would be rejected, writes nothing and
changes no metric. The point is to measure the rejection rate across a corpus
BEFORE deciding whether to act on it, because acting on it in the metrics path
means rebuilding the EC_191 reference database.

Usage:
    py tools/epoch_reject_report.py "<file.edf>" ["<more.edf>" ...]
    py tools/epoch_reject_report.py "<directory>"            # recurses for *.edf
    py tools/epoch_reject_report.py <paths> --csv out.csv
    py tools/epoch_reject_report.py <paths> --amp 150 --rms-k 3 --quiet

Signals are taken in ELECTRODE space, unscaled microvolts, straight from the
EDF -- the same thing `mysigs` holds in the pipeline before montage 6 replaces
it with ICA components and rescales it.
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import mne

from process.epoch_reject import screen, summarize, REASONS, FLAT_UV, AMP_UV, RMS_K, LINE_FRAC

mne.set_log_level("ERROR")

NON_EEG = ("ekg", "ecg", "emg", "eog", "resp", "pulse", "trigger", "event",
           "status", "a1", "a2", "m1", "m2")


def read_edf(path, max_channels):
    """Read exactly the way the pipeline does.

    edftotextbynameplotproc uses mne.io.read_raw_edf(..., encoding='latin1')
    and scales by 1e6 to reach microvolts. It does NOT use pyedflib for report
    or cascade modes -- that open is skipped when selstring[8] or [12] is set --
    which is why pyedflib rejects as "not EDF(+) compliant" several files the
    pipeline processes without complaint.
    """
    raw = mne.io.read_raw_edf(path, encoding="latin1", preload=True)
    labels = list(raw.ch_names)
    keep = [i for i, lab in enumerate(labels)
            if not any(tok in lab.strip().lower() for tok in NON_EEG)]
    if not keep:
        keep = list(range(len(labels)))
    keep = keep[:max_channels]
    sigs = 1000000.0 * raw[:][0][keep]        # volts -> microvolts, as line 110
    return sigs, [labels[i].strip() for i in keep], float(raw.info["sfreq"])


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                out += [os.path.join(root, fn) for fn in sorted(files)
                        if fn.lower().endswith(".edf")]
        else:
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--epoch-seconds", type=float, default=10.0)
    ap.add_argument("--max-channels", type=int, default=19)
    ap.add_argument("--flat", type=float, default=FLAT_UV)
    ap.add_argument("--amp", type=float, default=AMP_UV)
    ap.add_argument("--rms-k", type=float, default=RMS_K)
    ap.add_argument("--line-frac", type=float, default=LINE_FRAC)
    ap.add_argument("--csv")
    ap.add_argument("--quiet", action="store_true", help="corpus totals only")
    a = ap.parse_args()

    files = collect(a.paths)
    if not files:
        sys.exit("no EDF files found")

    print("rule: reject a %.0f s epoch if ANY channel trips ANY test" % a.epoch_seconds)
    print("      flat < %.2f uV | excursion > %.0f uV | RMS > %.1fx channel median"
          " | 60 Hz share > %.2f\n" % (a.flat, a.amp, a.rms_k, a.line_frac))

    rows, tot_ep, tot_rej, failed = [], 0, 0, 0
    reason_tot = {r: 0 for r in REASONS}

    for path in files:
        name = os.path.basename(path)
        try:
            sigs, labels, fs = read_edf(path, a.max_channels)
            length = int(round(a.epoch_seconds * fs))
            s = summarize(screen(sigs, fs=fs, length=length, flat_uv=a.flat,
                                 amp_uv=a.amp, rms_k=a.rms_k,
                                 line_frac=a.line_frac), labels)
        except Exception as exc:
            failed += 1
            print("  SKIP %-58s %s: %s" % (name[:58], type(exc).__name__, exc))
            continue

        tot_ep += s["n_epoch"]
        tot_rej += s["rejected"]
        for r in REASONS:
            reason_tot[r] += s["by_reason"][r]
        rows.append((name, s))

        if not a.quiet:
            print("%s" % name)
            print("  %d channels @ %.0f Hz, %d epochs -> REJECT %d (%.1f%%)"
                  % (s["n_chan"], fs, s["n_epoch"], s["rejected"], s["pct"]))
            print("  by reason: " + "  ".join(
                "%s=%d" % (r, s["by_reason"][r]) for r in REASONS))
            if s["channels"]:
                worst = "  ".join("%s:%d" % (c[0], c[1]) for c in s["channels"][:6])
                print("  worst channels: " + worst)
            if s["persistent"]:
                print("  *** PERSISTENT BAD ELECTRODE(S): %s -- bad in >50%% of"
                      " epochs. Epoch rejection cannot fix this; the channel"
                      " itself needs excluding." % ", ".join(s["persistent"]))
            print()

    print("=" * 72)
    print("%d file(s) read, %d skipped" % (len(rows), failed))
    if tot_ep:
        print("epochs: %d    rejected: %d (%.1f%%)"
              % (tot_ep, tot_rej, 100.0 * tot_rej / tot_ep))
        print("epochs tripping each test: " + "  ".join(
            "%s=%d" % (r, reason_tot[r]) for r in REASONS))
        wipe = [n for n, s in rows if s["pct"] >= 99.0]
        pers = [n for n, s in rows if s["persistent"]]
        print("files losing ~every epoch: %d" % len(wipe))
        print("files with a persistent bad electrode: %d" % len(pers))
        if rows:
            pcts = sorted(s["pct"] for _, s in rows)
            q = lambda p: pcts[min(len(pcts) - 1, int(p * len(pcts)))]
            print("per-file rejection %%: median %.1f  p90 %.1f  max %.1f"
                  % (q(0.5), q(0.9), pcts[-1]))

    if a.csv:
        import csv as _csv
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["file", "channels", "epochs", "rejected", "pct"]
                       + list(REASONS) + ["persistent_bad_channels"])
            for name, s in rows:
                w.writerow([name, s["n_chan"], s["n_epoch"], s["rejected"],
                            "%.1f" % s["pct"]]
                           + [s["by_reason"][r] for r in REASONS]
                           + ["|".join(s["persistent"])])
        print("\nwrote %s" % a.csv)


if __name__ == "__main__":
    main()
