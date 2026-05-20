# test_imagecascade.py
# One-off invocation of the ICALE pipeline with the IMG cascade flag enabled
# (selstring[12] = 1). Produces <edfname>.imagecascade.pdf next to the EDF,
# in addition to the usual .icale.rep.pdf.
#
# Usage: py test_imagecascade.py "<path-to-edf>"
# Defaults to the smallest sample EDF if no argument is given.

import os
import sys
import numpy as np

import files.allocate_data_array
import files.edftotextbynameplotproc
import files.file_svc


DEFAULT_EDF = r"C:\BrainPanel\edf file samples\raw_130399.edf"


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EDF
    print("Testing IMG cascade on:", filepath)

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
    selstring[8] = 1   # report PDF
    selstring[12] = 1  # IMG cascade -- the mode under test

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

    cascade_pdf = outputdir1 + ".imagecascade.pdf"
    if os.path.exists(cascade_pdf):
        size = os.path.getsize(cascade_pdf)
        print(f"\nIMG cascade PDF created: {cascade_pdf} ({size} bytes)")
    else:
        print(f"\nWARNING: expected {cascade_pdf} but it was not created.")


if __name__ == "__main__":
    main()
