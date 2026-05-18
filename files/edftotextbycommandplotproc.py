import os 
import files.file_svc
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import numpy as np
import files.file_svc
import files.edftotextbynameplotproc
selstring = np.zeros(16)
global selstring2
global filestring
global globaldirname
global added_dirname
global database_name
global excel_file_path

# dirname is the full path to the  file to be processed

def edf_to_text_by_command_plot_proc(filepath):
    global selstring2
    global filestring
    global added_dirname
    global added_paths
    global database_name
    global excel_file_path
    
    print("got file path:", filepath)
    dirpath = os.path.dirname(filepath)
    print("directory path is:", dirpath)
    file = os.path.basename(filepath)
    print("file name is:", file)
 
# NO GUI FOR THIS AUTOMATIC PROCESSING
# SET SELSTRING AND DATABASE NAME FOR ICA LINKED EARS, REPORT, LOCAL DATABASE

    database_name = ""
    globaldirname = dirpath
    excel_file_path = "EC_191.out_file.icale.xlsx"
    selstring = np.zeros(16)
    selstring[6] = 1
    selstring[8] = 1

    print ('SELSTRING CREATED:', selstring)
    print('EXCEL FILE CHOSEN: ', excel_file_path)
#    outname = globaldirname+"/Review"
    outname = globaldirname+"/"
  
    if not os.path.exists(outname):
        os.mkdir(outname)
        print("Had to create output dir:   ", outname)
    
    dirtouse = filepath
    dirtouse1 = dirtouse[:-4]
#    outputdir = globaldirname+"/Review/"+file
    outputdir = globaldirname+"/"+file
    outputdir1 = outputdir[:-4]
    print("DIRTOUSE1", dirtouse1)
    print("OUTPUTDIR1", outputdir1)

    plot_number = 1

    print("Processing file:  " + dirtouse + "   outputdir:  " + outputdir)

#  USE OF MONTAGE CODES IS AS FOLLOWS
# 0 LINKED EARS
# 1 AVERAGE
# 2 LAPLACIAN
# 3 LONGITUDINAL BIPOLAR DOUBLE BANANA
# 4 ICA
# 5 PCA
# 6 USE ICA TO SELECT AND RECOMPOSE, THEN MAKE LE REPORTS

    if selstring[0] == 1:
            freturn, outfile, excel_file = files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(dirtouse1, outputdir1, plot_number,2560, 0, selstring, outname, database_name, excel_file_path)
    if selstring[1] == 1:
            freturn, outfile, excel_file = files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(dirtouse1, outputdir1, plot_number,2560, 1, selstring, outname, database_name, excel_file_path)
    if selstring[2] == 1:
            freturn, outfile, excel_file = files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(dirtouse1, outputdir1, plot_number,2560, 2, selstring, outname, database_name, excel_file_path)
    if selstring[3] == 1:
            freturn, outfile, excel_file = files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(dirtouse1, outputdir1, plot_number,2560, 3, selstring, outname, database_name, excel_file_path)
    if selstring[4] == 1:
            freturn, outfile, excel_file = files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(dirtouse1, outputdir1, plot_number,2560, 4, selstring, outname, database_name, excel_file_path)
    if selstring[5] == 1:
            freturn, outfile, excel_file = files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(dirtouse1, outputdir1, plot_number,2560, 5, selstring, outname, database_name, excel_file_path)
    if selstring[6] == 1:
            try:
              freturn, outfile, excel_file = files.edftotextbynameplotproc.edf_to_text_by_name_plot_proc(dirtouse1, outputdir1, plot_number,2560, 6, selstring, outname, database_name, excel_file_path)
            except TypeError:
               pass
    
    if selstring[9] == 1:
       files.file_svc.histogram_to_excel_file(outfile)
       if selstring[6] == 1:
        files.file_svc.histograms_to_comps_file(excel_file)
