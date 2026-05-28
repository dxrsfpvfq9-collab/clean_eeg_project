# test_discriminant.py
# One-off invocation of the ICALE pipeline that produces the discriminant
# variant of the Brain Panel report -- the standard 3-page report plus
# the Collura et al. (2026) Likelihood-of-Findings block on page 2.
# Output filename: <edfname>.icale.disc.rep.pdf (alongside the usual
# .icale.rep.pdf).
#
# Usage: py test_discriminant.py "<path-to-edf>"
# Defaults to the smallest sample EDF if no argument is given.

import os
import sys
import numpy as np

import files.allocate_data_array
import files.edftotextbynameplotproc


DEFAULT_EDF = r"C:\BrainPanel\edf file samples\raw_130399.edf"


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EDF
    print("Testing discriminant report on:", filepath)

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
    selstring[6] = 1    # ICALE montage
    selstring[8] = 1    # standard report PDF (for parity / comparison)
    selstring[13] = 1   # discriminant report PDF -- the mode under test

    print("SELSTRING:", selstring)
    print("dirtouse1:", dirtouse1)
    print("outputdir1:", outputdir1)

    try:
        files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(
            dirtouse1, outputdir1, 1, 2560, 6,
            selstring, outname, database_name, excel_file_path,
        )
    except TypeError:
        pass

    disc_pdf = outputdir1 + ".icale.disc.rep.pdf"
    if os.path.exists(disc_pdf):
        size = os.path.getsize(disc_pdf)
        print(f"\nDiscriminant PDF created: {disc_pdf} ({size} bytes)")
    else:
        print(f"\nWARNING: expected {disc_pdf} but it was not created.")


if __name__ == "__main__":
    main()
