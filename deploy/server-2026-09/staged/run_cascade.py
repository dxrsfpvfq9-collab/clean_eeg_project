# run_cascade.py
# Render ONLY the image cascade for one EDF: <edfname>.imagecascade.pdf.
#
#     py run_cascade.py "<path-to-edf>"
#
# This is the second half of the two-pass server flow. module7.py writes the
# brain panel and nothing else (selstring[12] = 0); the watchdog then runs this
# to add the cascade. Two reasons for the split:
#
#   1. The panel appears in seconds instead of after the ~8 minute cascade
#      render, which is what practitioners are waiting on.
#   2. Isolation. The cascade's Tk/ImageGrab and (where enabled) VTK work can
#      fail in ways Python cannot trap -- VTK aborts the process outright. In
#      one process that took the panel down with it. In two, the panel is
#      already on disk before this starts.
#
# The cost is one extra ICA + metrics pass, well under a minute against the
# cascade's own runtime. FastICA is seeded (random_state=0), so this pass
# reproduces the decomposition the panel was built from -- the cascade still
# explains that panel.
#
# selstring[8] stays 0 here so the report is NOT written a second time.
# Honours CLEANEEG_NO_BRAIN=1 (skip the 3D source-localization pages).

import os
import sys

import numpy as np

import files.allocate_data_array
import files.edftotextbynameplotproc


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: py run_cascade.py "<path-to-edf>"')
    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        sys.exit("no such file: " + filepath)

    print("CASCADE PASS:", filepath)

    current_data = files.allocate_data_array.allocate_data_array(20, 512)
    files.allocate_data_array.process_data_array(current_data)

    dirpath = os.path.dirname(filepath)
    file = os.path.basename(filepath)
    outname = dirpath + "/"
    dirtouse1 = filepath[:-4]
    outputdir1 = (dirpath + "/" + file)[:-4]

    selstring = np.zeros(16)
    selstring[6] = 1    # ICALE montage
    selstring[8] = 0    # no report -- module7.py already wrote it
    selstring[12] = 1   # IMG cascade

    try:
        files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(
            dirtouse1, outputdir1, 1, 2560, 6,
            selstring, outname, "", "EC_191.out_file.icale.xlsx",
        )
    except TypeError:
        pass  # this path returns None; matches test_imagecascade.py

    cascade = outputdir1 + ".imagecascade.pdf"
    if os.path.exists(cascade):
        print("CASCADE OK: %s (%d bytes)" % (cascade, os.path.getsize(cascade)))
        return 0
    print("CASCADE MISSING: expected " + cascade)
    return 1


if __name__ == "__main__":
    sys.exit(main())
