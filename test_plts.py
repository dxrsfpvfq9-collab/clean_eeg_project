# test_plts.py
# One-off invocation of the ICALE pipeline with the PLTS (plots) flag
# enabled (selstring[7] = 1). Produces <edfname>.icale.plts.pdf next to
# the EDF, in addition to the usual .icale.rep.pdf.
#
# Each PDF page covers one `length`-sample window of the recording
# (default 2560 samples = 10 seconds), showing 19 EEG waveforms across
# the top followed by per-band artifact-amplitude trace lines. A
# 10-minute recording produces ~60 pages.
#
# Usage: py test_plts.py "<path-to-edf>"
# Defaults to the smallest sample EDF if no argument is given.
#
# To cap output at the first 2 pages (faster sanity check), set
# selstring[10] = 1 (SHORT mode) below.

import os
import sys
import numpy as np

import files.allocate_data_array
import files.edftotextbynameplotproc
import files.file_svc


DEFAULT_EDF = r"C:\BrainPanel\edf file samples\raw_130399.edf"


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EDF
    print("Testing PLTS mode on:", filepath)

    current_data = files.allocate_data_array.allocate_data_array(20, 512)
    files.allocate_data_array.process_data_array(current_data)

    dirpath = os.path.dirname(filepath)
    file = os.path.basename(filepath)

    database_name = ""
    excel_file_path = "EC_191.out_file.icale.xlsx"
    outname = dirpath + "/"
    if not os.path.exists(outname):
        os.mkdir(outname)

    dirtouse1 = filepath[:-4]
    outputdir1 = (dirpath + "/" + file)[:-4]

    selstring = np.zeros(16)
    selstring[6] = 1   # ICALE montage
    selstring[7] = 1   # PLTS -- the mode under test
    selstring[8] = 1   # report PDF (standard .icale.rep.pdf, for parity)
    # selstring[10] = 1  # uncomment to cap PLTS at 2 pages (SHORT mode)

    print("SELSTRING:", selstring)
    print("dirtouse1:", dirtouse1)
    print("outputdir1:", outputdir1)

    try:
        freturn, outfile, excel_file = (
            files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(
                dirtouse1, outputdir1, 1, 2560, 6,
                selstring, outname, database_name, excel_file_path,
            )
        )
    except TypeError:
        pass

    # Note: under montage 6 (ICALE), Montage_6.py internally calls
    # setup_electrode_names with montage=4, so the PLTS PDF lands at
    # `<name>.ica.plts.pdf` (not `.icale.plts.pdf`).
    for suffix in (".ica.plts.pdf", ".icale.plts.pdf"):
        plts_pdf = outputdir1 + suffix
        if os.path.exists(plts_pdf):
            size = os.path.getsize(plts_pdf)
            print(f"\nPLTS PDF created: {plts_pdf} ({size} bytes)")
            return
    print(f"\nWARNING: expected {outputdir1}.ica.plts.pdf but it was not created.")


if __name__ == "__main__":
    main()
