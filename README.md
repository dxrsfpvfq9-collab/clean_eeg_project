# Clean EEG Project

EEG analysis pipeline that generates the **BrainML (Machine Learning)
Brain Panel Report** PDF — a 3-page quantitative review of 19/20-channel
EEG recordings against a 192-file reference population
(`EC_191.out_file.icale.xlsx`).

The pipeline reads an EDF file, runs Butterworth band-power filtering and
ICA decomposition, computes 48 EEG quality metrics, and produces:

- Page 1 — metrics table with color-coded bars and z-scores against
  the reference population
- Page 2 — plain-English findings summary
- Page 3 — clinical paragraph, raw 19-channel EEG waveforms, FFT power
  spectrum with per-channel peak-frequency legend

## Requirements

- Python 3.12 or 3.13 (production uses 3.12)
- See `requirements.txt` for runtime dependencies
- See `requirements-dev.txt` for additional dev dependencies (pytest)

Install:

```
py -m pip install -r requirements.txt        # runtime
py -m pip install -r requirements-dev.txt    # runtime + dev
```

## Running

**Single-file unattended mode** (used by the file-watcher):

```
py module7.py "C:/path/to/recording.edf"
```

Output PDF lands next to the source EDF as `<name>.icale.rep.pdf`.

**Directory + GUI mode** (used in production):

```
run.bat
```

This invokes `py module61.py`, which scans the current directory for
`.edf` files and presents a Tkinter selection dialog.

**File watcher daemon** — `py tomwatchdog.py` monitors a hardcoded
directory and spawns `module7.py` for each new EDF.

**IMG cascade mode** — `py test_imagecascade.py "C:/path/to/recording.edf"`
runs the standard pipeline and *also* writes
`<name>.imagecascade.pdf`, a multi-page PDF dedicated to per-ICA-component
inspection (overview + summary table + one component+brain-view pair per
component, sorted by component % descending). See the "IMG cascade output
mode" section in `CLAUDE.md` for details.

**PLTS mode** — `py test_plts.py "C:/path/to/recording.edf"` runs the
standard pipeline and *also* writes `<name>.ica.plts.pdf`, a multi-page
PDF that walks through the recording in 10-second windows showing 19
EEG waveforms, per-band artifact-amplitude traces, comodulation
ellipses, and FFT peak-frequency labels. See the "PLTS output mode"
section in `CLAUDE.md` for details.

## Tests

```
py -m pytest -v
```

Test suite is in `tests/unit/`. Runs in ~1 second.

## Project structure

```
module7.py / module61.py        Entry points
tomwatchdog.py                   File-watcher daemon
process/
    tfcfilters.py                Butterworth filter bank (fs=256 Hz)
    detect_artifact.py           Band-power detectors + ICA component screening
    Source_Localization.py       PyVista 3D brain visualization
files/
    edftotextbynameplotproc.py   Main pipeline (1000 lines)
    edftotextbycommandplotproc.py  module7 wrapper
    edftotextbydirectoryplotproc.py  module61 GUI wrapper
    file_svc.py                  Excel report generation (openpyxl)
    create_report_pdf.py         PDF report generation (reportlab)
    Montage_6.py                 ICA orchestration for montage=6 (ICALE)
    Component_selector.py        Tk ICA-component review GUI
    dummy_gui.py                 Tk component viewer + 3D brain trigger
    allocate_data_array.py       Trivial helper
plot/
    plot_svc.py                  Matplotlib waveform/spectrum drawing
tests/
    unit/                        pytest tests
CLAUDE.md                        Project guide (architecture, quirks, gotchas)
```

See `CLAUDE.md` for detailed architecture notes and important
environment-specific gotchas (notably a numpy 2.0 vs 1.x integer-dtype
dependency that affects 4 of the 48 metrics).
