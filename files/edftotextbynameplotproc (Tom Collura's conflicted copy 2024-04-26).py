# clean_eeg
# edftotextbynameplotproc.py
# does a lot
# begun 2/12/2023
# copyright Thomas F. Collura and BrainMaster Technologies, Inc.

import os
import pyedflib
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
#from matplotlib.widgets import Button
from matplotlib.figure import Figure
from matplotlib.backends.backend_pdf import PdfPages
#import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
import files.file_svc as fs
from files.file_svc import setup_electrode_names
from files.create_report_pdf import create_report_pdf
from files.create_report_pdf import create_report_strings
from files.Montage_6 import montage_6
import process.detect_artifact
import process.tfcfilters
from plot.plot_svc import draw_a_wax_wane
from plot.plot_svc import draw_a_wax_waner
from plot.plot_svc import draw_a_ribbon
from plot.plot_svc import draw_fft_power_spectra
from plot.plot_svc import draw_eeg_waveforms
from plot.plot_svc import draw_artifact_line
#from scipy import signal
import mne
import mne.report
from mne.preprocessing import ICA
import sklearn
from sklearn.decomposition import FastICA, PCA
import tkinter
from tkinter import *


global has_artifact
icabutton = {}
icatext = {}
icatextl = {}
selected_channel_list = []
icatextobj = {}

#  SELSTRING ELEMENTS:  10=SHORT PLOTS, 9=XLFILE, 8=REPORT, 7=PLOTS
def edf_to_text_by_name_plot_proc(name, outputdir1, plot_num, length, montage, selstring, outname, database_name, excel_file_path):
    global selected_channel_list
    global icabutton
    global icatext
    global icatextobj
    global icatextl

#  IDENTIFY LOCATION OF MNE REPORTS FOR BUILD & CREATE NAMES FOR FILES-----------------------------------------------

    print("MNE REPORTS:  ", mne.report.__file__)
    print('outputdir1:', outputdir1)
  
    short_name =name[-30:]
    clean_pos = name.find("clean_eeg_project")
    if clean_pos != -1:
       short_name = name[clean_pos + len("clean_eeg_project"):]
    studies_pos = name.find("Studies")
    if studies_pos != -1:
       short_name = name[studies_pos:]
    sts_pos = name.find("2023")
    if sts_pos != -1:
       short_name = name[sts_pos:]
    print("SHORT NAME:  ", short_name)

    metricsfilename = outputdir1 + ".mts.png"
    print("metricsfile:  ", metricsfilename)

    edf_file = name + ".edf"
    new_pyedf_file = outputdir1 + ".new.edf"
    print("new pyedf file name: ", new_pyedf_file)
    clean1_pyedf_file = outputdir1 + ".clean1.edf"
    clean2_pyedf_file = outputdir1 + ".clean2.edf"
    recon_pyedf_file = outputdir1 + ".recon.edf"
    img_cascade_file = outputdir1 + ".imagecascade.pdf"

    print("sizing:", edf_file)
    file_size = os.path.getsize(edf_file)
    print("file size is:", file_size, "kbytes =:", file_size/1024)

    raw = mne.io.read_raw_edf(edf_file, encoding='latin1')
    
    print("mne opened file")
    print("RAW", raw)
    if ('EO' in name):
        print("Detected EO")
    if ('EC' in name):
        print("Detected EC")

    icamontage = mne.channels.make_standard_montage('standard_1020')
    print('ICA STANDARD MONTAGE: ', icamontage)
    # Get the number of channels in the EDF file---------------------------------------------------------------
    n = len(raw.ch_names)
#    n = f.signals_in_file
    electrode_names = [None] * n
    #n=19#------------------------------------------------------------------=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#    print("file has", n, "signals")
     
    # Get the data for each channel
#    data = [f.readSignal(i) for i in range(n)]
    data = 1000000 * raw[:][0]
    print("Data shape:  ", data.shape)
    print (data[0, :4])
    
    #data = data[:20, :]#=-=--=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
    #print("Data shape:  ", data.shape)
#    data = np.clip(data, -100, 100)
    #print (data[0, :4])

    numsamples = raw.n_times
#    numsamples = f.getNSamples()[0]
    print("numsamples:" + str(numsamples))
    numsamples_skipped = 0
    numsamples_used = numsamples - numsamples_skipped


# Open the EDF file-------------------------------------------------------------------------------------------
    try:
        pyedf_file = pyedflib.EdfReader(edf_file)
        print("pyedflib EDF file opened. File type: ", pyedf_file.getSignalHeaders()[0]['label'])
    except OSError as e:
        print("pyedflib EDF file open Error: ", e)
        return 0  
#  HERE WE HAVE RETURNED WITH NO  FILE FOUND, OR BROKEN FILE AND RECOVER


#  GET READY TO  HAVE AN OUTPUT EDF FILE WITH THE SAME HEADERS
    """
    new_pyedf_signals = [pyedf_file.readSignal(i)for i in range(pyedf_file.signals_in_file)]
    new_pyedf_annotations = pyedf_file.readAnnotations()
    new_pyedf_headers = [pyedf_file.getSignalHeader(i) for i in range(pyedf_file.signals_in_file)]
    new_pyedf_header = pyedf_file.getHeader()

    new_pyedf_file = pyedflib.EdfWriter(new_pyedf_file, n_channels=n, file_type=pyedflib.FILETYPE_EDF)
    new_pyedf_file.setSignalHeaders(new_pyedf_headers)
    new_pyedf_file.setHeader(new_pyedf_header)
    new_pyedf_file.writeSamples(new_pyedf_signals)
    new_pyedf_file.close()
    """
    pyedf_file.close()
 

#  OVERRIDE NUMBER OF SAMPLES TWO PAGE LIMIT TO CUT EVERYTHING DOWN

#    numsamples_used = 2560 * 12

    channel_labels = raw.ch_names

#  NEED TO MAKE SURE THIS IS REALLY A COPY NOT JUST THE SAME ARRAY

    electrode_names_orig =  channel_labels
    print(channel_labels)

#    channel_labels = f.getSignalLabels()  # get all labels in one struct

#  HERE IS WHERE WE BUILD THE FILTER COEFFICIENTS----------------------------------------------------------------------------------------

    forder = 4

    #filt = filts()
    #filt.filist()
    b, a, bh, ah = process.tfcfilters.tfcfilterssetup(1.0, 55.0, forder)
    bv, av, bhv, ahv = process.tfcfilters.tfcfilterssetup(1.5, 45.0, forder)
    bld, ald, bhld, ahld = process.tfcfilters.tfcfilterssetup(0.1, 2.0, forder)
    bd, ad, bhd, ahd = process.tfcfilters.tfcfilterssetup(0.5, 4.0, forder)
    bt, at, bht, aht = process.tfcfilters.tfcfilterssetup(4.0, 8.0, forder)
    bla, ala, bhla, ahla = process.tfcfilters.tfcfilterssetup(7.0, 10.0, forder)
    bal, aal, bhal, ahal = process.tfcfilters.tfcfilterssetup(7.0, 13.0, forder)
    bha, aha, bhha, ahha = process.tfcfilters.tfcfilterssetup(10.0, 13.0, forder)
    blb, alb, bhlb, ahlb = process.tfcfilters.tfcfilterssetup(12.0, 15.0, forder)
    bb, ab, bhb, ahb = process.tfcfilters.tfcfilterssetup(15.0, 25.0, forder)
    bhib, ahib, bhhib, ahhib = process.tfcfilters.tfcfilterssetup(25.0, 30.0, forder)
    bg, ag, bhg, ahg = process.tfcfilters.tfcfilterssetup(38.0, 42.0, forder)
    bhig, ahig, bhhig, ahhig = process.tfcfilters.tfcfilterssetup(42.0, 50.0, forder)
    b60, a60, bh60, ah60 = process.tfcfilters.tfcfilterssetup(55.0, 65.0, forder)
    b61, a61, bh61, ah61 = process.tfcfilters.tfcfilterssetup(65.0, 70.0, forder)

    #print('B:', bv)
    #print('A:', av)
    #print('BH:', bhv)
    #print('AH:', ahv)

#   HERE IS WHERE WE BRING IN THE LABELS AND REMONTAGE AND FILTER THE SIGNALS
#   GET LOCATIONS OF ALL CHANNELS BY CHANNEL ELECTRODE NAME-----------------------------------------------------------------------------------------
   
    channel_labels_short = channel_labels
    print(channel_labels)
    for label in channel_labels:
       if 'FP1' in label.upper():
          fp1i = channel_labels.index(label)
          channel_labels_short[fp1i] = 'FP1'
       if 'FP2' in label.upper():
          fp2i = channel_labels.index(label)
          channel_labels_short[fp2i] = 'FP2'
       if 'F7' in label.upper():
          f7i = channel_labels.index(label)
          channel_labels_short[f7i] = 'F7'
       if 'F8' in label.upper():
          f8i = channel_labels.index(label)
          channel_labels_short[f8i] = 'F8'
       if 'F3' in label.upper():
          f3i = channel_labels.index(label)
          channel_labels_short[f3i] = 'F3'
       if 'F4' in label.upper():
          f4i = channel_labels.index(label)
          channel_labels_short[f4i] = 'F4'
       if 'FZ' in label.upper():
          fzi = channel_labels.index(label)
          channel_labels_short[fzi] = 'FZ'
       if 'C3' in label.upper():
          c3i = channel_labels.index(label)
          channel_labels_short[c3i] = 'C3'
       if 'T3' in label.upper():
          t3i = channel_labels.index(label)
          channel_labels_short[t3i] = 'T3'
       if 'T7' in label.upper(): #NEW_---------
          t7i = channel_labels.index(label)
          channel_labels_short[t7i] = 'T3'
       if 'CZ' in label.upper():
          czi = channel_labels.index(label)
          channel_labels_short[czi] = 'CZ'
       if 'C4' in label.upper():
          c4i = channel_labels.index(label)
          channel_labels_short[c4i] = 'C4'
       if 'T4' in label.upper():
          t4i = channel_labels.index(label)
          channel_labels_short[t4i] = 'T4'
       if 'T8' in label.upper(): #NEW_---------
          t8i = channel_labels.index(label)
          channel_labels_short[t8i] = 'T4'
       if 'T5' in label.upper():
          t5i = channel_labels.index(label)
          channel_labels_short[t5i] = 'T5'
       if 'P7' in label.upper(): #NEW_---------
          p7i = channel_labels.index(label)
          channel_labels_short[p7i] = 'T5'
       if 'P3' in label.upper():
          p3i = channel_labels.index(label)
          channel_labels_short[p3i] = 'P3'
       if 'PZ' in label.upper():
          pzi = channel_labels.index(label)
          channel_labels_short[pzi] = 'PZ'
       if 'P4' in label.upper():
          p4i = channel_labels.index(label)
          channel_labels_short[p4i] = 'P4'
       if 'T6' in label.upper():
          t6i = channel_labels.index(label)
          channel_labels_short[t6i] = 'T6'
       if 'P8' in label.upper(): #NEW_---------
          p8i = channel_labels.index(label)
          channel_labels_short[p8i] = 'T6'
       if 'O1' in label.upper():
          o1i = channel_labels.index(label)
          channel_labels_short[o1i] = 'O1'
       if 'O2' in label.upper():
          o2i = channel_labels.index(label)
          channel_labels_short[o2i] = 'O2'
       if 'A2' in label.upper():
          a2i = channel_labels.index(label)
          channel_labels_short[a2i] = 'A2'
       if 'STATUS' in label.upper(): #NEW_-----------------------------
          sti = channel_labels.index(label)
          channel_labels_short[sti] = 'A2'
       if 'AUX1' in label.upper():
          axi = channel_labels.index(label)
          channel_labels_short[axi] = 'AX1'
       if 'AUX2' in label.upper():
          axi = channel_labels.index(label)
          channel_labels_short[axi] = 'AX2'
       if 'A1' in label.upper() and all(name not in channel_labels_short for name in ['FP1', 'FP2', 'F7', 'F8', 'F3', 'F4', 'FZ', 'C3', 'T3', 'CZ', 'C4', 'T4', 'T5', 'P3', 'PZ', 'P4', 'T6', 'O1', 'O2', 'AUX1', 'AUX2']):
            a1i = channel_labels.index(label)
            channel_labels_short[a1i] = 'A1'   
    print(channel_labels)
    print(channel_labels_short)
    channel_labels_pre = list(channel_labels)


#   LINKED EARS MONTAGE - NO REFORMATTING BUT REORDER TO STANDARD ORDER---------------------------------------------------------------------

#   COMMON AVERAGE REFERENCED MONTAGE
    if montage == 1:
        new_reference = np.mean(data[:19, :], axis=0)
        for i in range(19):
          data[i] -= new_reference
#   LAPLACIAN MONTAGE-------------------------------------------------------------------------------------------------------------------------
    if montage == 2:
       datac = data
       data[0] = datac[fp1i] - (datac[f7i] + datac[f3i] + datac[fzi] + datac[fp2i]) / 4
       data[1] = datac[f7i] - (datac[t3i] + datac[c3i] + datac[f3i] + datac[fp1i]) / 4
       data[2] = datac[t3i] - (datac[f7i] + datac[f3i] + datac[c3i] + datac[t5i]) / 4
       data[3] = datac[t5i] - (datac[t3i] + datac[c3i] + datac[p3i] + datac[o1i]) / 4
       data[4] = datac[o1i] - (datac[t5i] + datac[p3i] + datac[pzi] + datac[o2i]) / 4
       data[5] = datac[f3i] - (datac[f7i] + datac[fp1i] + datac[fzi] + datac[c3i]) / 4
       data[6] = datac[c3i] - (datac[t3i] + datac[f3i] + datac[czi] + datac[p3i]) / 4
       data[7] = datac[p3i] - (datac[t5i] + datac[c3i] + datac[pzi] + datac[o1i]) / 4
       data[8] = datac[fp2i] - (datac[f8i] + datac[f4i] + datac[fzi] + datac[fp1i]) / 4
       data[9] = datac[f8i] - (datac[t4i] + datac[c4i] + datac[f4i] + datac[fp2i]) / 4
       data[10] = datac[t4i] - (datac[f8i] + datac[f4i] + datac[c4i] + datac[t6i]) / 4
       data[11] = datac[t6i] - (datac[t4i] + datac[c4i] + datac[pzi] + datac[o2i]) / 4
       data[12] = datac[o2i] - (datac[t6i] + datac[p4i] + datac[pzi] + datac[o1i]) / 4
       data[13] = datac[f4i] - (datac[f8i] + datac[fp2i] + datac[pzi] + datac[c4i]) / 4
       data[14] = datac[c4i] - (datac[t4i] + datac[f4i] + datac[czi] + datac[p4i]) / 4
       data[15] = datac[p4i] - (datac[t6i] + datac[c4i] + datac[pzi] + datac[o2i]) / 4
       data[16] = datac[fzi] - (datac[f3i] + datac[f4i] + datac[c3i] + datac[c4i] + datac[czi]) / 5
       data[17] = datac[czi] - (datac[fzi] + datac[c3i] + datac[c4i] + datac[pzi]) / 4
       data[18] = datac[pzi] - (datac[czi] + datac[p3i] + datac[p4i] + datac[o1i] + datac[o2i]) / 5
#   DOUBLE BANANA TRANVERSE MONTAGE----------------------------------------------------------------------------------------------------------------
    if montage == 3:
       datac = data
       data[0] = datac[fp1i] - datac[f7i]
       data[1] = datac[f7i] - datac[t3i]
       data[2] = datac[t3i] - datac[t5i]
       data[3] = datac[t5i] - datac[o1i]
       data[4] = datac[fp1i] - datac[f3i]
       data[5] = datac[f3i] - datac[c3i]
       data[6] = datac[c3i] - datac[p3i]
       data[7] = datac[p3i] - datac[t5i]
       data[8] = datac[fp2i] - datac[f8i]
       data[9] = datac[f8i] - datac[t4i]
       data[10] = datac[t4i] - datac[t6i]
       data[11] = datac[t6i] - datac[o2i]
       data[12] = datac[fp2i] - datac[f4i]
       data[13] = datac[f4i] - datac[c4i]
       data[14] = datac[c4i] - datac[p4i]
       data[15] = datac[p4i] - datac[o2i]
       data[16] = datac[fzi] - datac[czi]
       data[17] = datac[czi] - datac[pzi]
       data[18] = datac[fzi] - datac[pzi]


#   READ IN SIGNALS FROM DATA ARRAY AND FILTER INTO FILTERED AND VISUAL SIGNALS------------------------------------------------------------------------
    mysigs = np.zeros((n, numsamples_used))
    myfilteredsigs = np.zeros((n, numsamples_used))
    myvisualsigs = np.zeros((n, numsamples_used))
    for i in range(n):
        mysigs[i] = data[i, numsamples_skipped:numsamples_skipped + numsamples_used]
#       mysigs[i, :numsamples] = f.readSignal(i)
#        electrode_names[i] = f.getSignalLabels()[i]
        electrode_names[i] = channel_labels[i]
        myfilteredsigs[i] = process.tfcfilters.tfcfilterall(b, a, bh, ah, mysigs[i], numsamples_used) 
#        myfilteredsigs[i] = np.clip(myfilteredsigs[i], -100, 100)
        myvisualsigs[i] = process.tfcfilters.tfcfilterall(bv, av, bhv, ahv, mysigs[i], numsamples_used)  
#        myvisualsigs[i] = np.clip(myvisualsigs[i], -100, 100)
#    f.close  # close edf file

    print("Visual sigs original:  ", myvisualsigs[0][:4])
    print('Shape: ', myvisualsigs.shape)
#   APPLY ICA OR PCA HERE TO THE FILTERED SIGNALS
#   INDEPENDENT COMPONENTS ANALYSIS (ICA)
#   MONTAGE=4 MEANS DO ICA REPORT BUT MONTAGE=6 MEANS USE ICA TO RECOMPOSE LE-------------------------------------------------------------------------

    if montage == 4 or montage == 6:
#       method = 'fastica'
#       np.random.seed(0)
       ica = FastICA(n_components=n, max_iter = 1000, random_state=0)
#       ica = ICA(n_components=n, method = method, max_iter = 5000)
       myvisualsigst = myvisualsigs.T
       ica_components = ica.fit_transform(myvisualsigst)
#FIT_TRANSFORM: FITS A MODEL TO THE DATA, TRANSFORMS DATA BASED ON LEARNED MODEL
#       ica_components = ica.fit(myvisualsigst)
#       print("myvisualsignalst shape:  ", myvisualsigst.shape)
     
#       ica.plot_components(inst=myvisualsigst, montage=icamontage, show=True )
#       ica.plot_properties(myvisualsigst, picks=0)

#       ica_components = ica.transform(myvisualsigs)
#       ica_components = ica.components_
#REORDERS CHANNEL LABELS AND ICA MIXING TO STANDARD ORDER---------------------------------------------------------------------------------------------------------       
       ica_mixing = ica.mixing_
       print('Channel Labels Before Sorting: ', channel_labels)
       channel_labels_pre = list(channel_labels)
       specific_order = ['FP1', 'FP2', 'F7', 'F3', 'FZ', 'F4', 'F8', 'T3', 'C3', 'CZ', 'C4', 'T4', 'T5', 'P3', 'PZ', 'P4', 'T6', 'O1', 'O2', 'A1', 'A2', 'AX1', 'AX2']
       string_index_map = {string: index for index, string in enumerate(channel_labels)}
       
       channel_labels.sort(key=lambda x: specific_order.index(x))
       #channel_labels = channel_labels[:19]#=-=-=-=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
       reordered_ica_mixing = []
       
       for string in channel_labels:
            index = string_index_map[string]
            reordered_ica_mixing.append(ica_mixing[index])

       ica_mixing = np.array(reordered_ica_mixing)

       print('Channel Labels After Sorting: ', channel_labels)
       channel_labels_short = channel_labels
       print('Channel Labels Short After Sorting: ', channel_labels_short)
       print('Channel Labels Pre: ', channel_labels_pre)
       
       print("ICA COMP SHAPE:  ", ica_components.shape)
       print("ICA MIX SHAPE:  ", ica_mixing.shape)
       print(ica_mixing)
       col_powers = []
       for col in range(ica_mixing.shape[1]):
          power = np.sum(ica_mixing[:, col]**2)
          col_powers.append(power)
      
       sorted_ind = np.argsort(col_powers)[::-1]        #RESORTING HERE----------------------------------------------------------------------
       print(sorted_ind)
       sorted_matrix = ica_mixing[:, sorted_ind]
       #print('resorted: ', sorted_matrix)
       #ica_mixing = sorted_matrix #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#       approx_waveforms = np.dot(ica_components.T, ica_mixing.T)
#       print("APP WAVE SHAPE:  ", approx_waveforms.shape)

       numcomps = ica_components.shape[1]
#       print("numcomps:  ", numcomps)
       numchans = myvisualsigs.shape[0]
#       print("numchans calc:  ", numchans)

       ica_componentst = ica_components.T
#       print("ica_componentst shape:  ", ica_componentst.shape)

#       comp_arrays = []
       for i in range(numcomps):
#           print("ICA COMP:  ", ica_componentst[i][:4])
           myfilteredsigs[i] = ica_componentst[i] * 1000
           print("My sigs:  ", myfilteredsigs[i][:4])
           print(myfilteredsigs.shape)
#           myfilteredsigs[i] = myvisualsigs[i]
       
       sorted_sigs = myfilteredsigs[sorted_ind, :]
       print(sorted_sigs.shape)
       #myfilteredsigs = sorted_sigs #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=--=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
       #myfilteredsigs = sorted_sigs
#  PRINCIPLE COMPONENTS ANALYSIS (PCA)----------------------------------------------------------------------------------------------------------------
    if montage == 5:
       pca = PCA(n_components = n)
       myvisualsigst = myvisualsigs.T
#       print("myvisualsignalst shape:  ", myvisualsigst.shape)
       pca_components = pca.fit_transform(myvisualsigst)
#       print("PCA COMP SHAPE:  ", pca_components.shape)
       pca_componentst = pca_components.T
#       print("pca_components shape:  ", pca_componentst.shape)
       numcomps = pca_components.shape[1]
#       print("numcomps:  ", numcomps)
       numchans = myvisualsigs.shape[0]
#       print("numchans calc:  ", numchans)
       for i in range(numcomps):
#           print("PCA COMP:  ", pca_componentst[i][:4])
           myvisualsigs[i] = pca_componentst[i]

           print("My sigs:  ", myvisualsigs[i][:4])
           myfilteredsigs[i] = myvisualsigs[i]


#  SET UP ELECTRODE NAMES BASED ON MONTAGE USED----------------------------------------------------------------------------------------------------

    electrode_names, pdf_filename = setup_electrode_names(n, outputdir1, electrode_names, electrode_names_orig, montage)
    print("ELECTRODE NAMES:  ", electrode_names)

#  DISPLAY THE ICA SCREEN AND ALLOW THE USER TO SELECT COMPONENTS
#  AND RECONSTRUCT THE SIGNALS BASED ON REMOVED COMPONENTS
#  MONTAGE=6 MEANS USE ICA FOR SELECTION THEN RECREATE LE-----------------------------------------------------------------------------------------

    if montage == 6:
        electrode_names, pdf_filename, fig, ax, channel_labels_short, n, myvisualsigs, time_range, comp_array, stdorig, stddiffreconorig, stddiffclean1orig, percent, sites_rsi = montage_6(outname, selstring, myfilteredsigs, data, numsamples, ica, ica_components, recon_pyedf_file, clean1_pyedf_file, clean2_pyedf_file, img_cascade_file, n, outputdir1, electrode_names, electrode_names_orig, length, myvisualsigs, icabutton, ica_mixing, short_name, channel_labels_short, numcomps, edf_file, selected_channel_list, icatext, icatextobj, icatextl)
      #electrode_names, pdf_filename = setup_electrode_names(n, outputdir1, electrode_names, electrode_names_orig, 4)

#  NORMALIZED FILTERED SIGNALS TO A STANDARD OVERALL RMS AMPLITUDE THIS WAS WAY ABOVE UNTIL 4/5/2023---------------------------------------------------

    stdmeasraw = np.std(mysigs[:])
    stdmeas = np.std(myfilteredsigs[:])
    stdmeasv = np.std(myvisualsigs[:])
    global_stdmeas = stdmeas
    
    if not montage == 6:
      stdorig = stdmeasraw
      stddiffreconorig = 0
      stddiffclean1orig = 0
      percent = 0
      sites_rsi = 0
    print("total std =  " + str(stdmeas))
    
    myfilteredsigs = myfilteredsigs * 10.0 / stdmeas
    myvisualsigs = myvisualsigs * 10.0 / stdmeasv
    print("Visual sigs standardized:  ", myvisualsigs[0][:4])


#  CALCULATE NUMBER OF PAGES AND TOTAL TIME AND COMPUTE START/STOP TIMES

    if selstring[7] == 1:
      pdf = PdfPages(pdf_filename)   

    print (electrode_names)
    total_time = numsamples / 256.0
    print ("total time:" , total_time)
    each_length = length / 256.0
    print ("each length:  ", each_length)
    numpages = numsamples/length - 1
#   TWO PAGE LIMIT FOR DEVELOPMENT
    print("PAGE COUNT SELSTRING:   ", selstring[10])
    if selstring[10] == 1:
      start_stops = [(int(j * length), int( (j+1) * length)) for j in np.arange(0, 2, 1)]
    else:
      start_stops = [(int(j * length), int( (j+1) * length)) for j in np.arange(0, numpages, 1)]

#    print(start_stops)

#  HERE IS WHERE WE RUN THE ARTIFACT DETECTION ROUTINES ON EACH CHANNEL AND STORE THE FLAGS------------------------------------------------------

    has_artifact = np.zeros((n, numsamples_used))
    lodelta_artifact = np.zeros((n, numsamples_used))
    delta_artifact = np.zeros((n, numsamples_used))
    theta_artifact = np.zeros((n, numsamples_used))
    loalpha_artifact = np.zeros((n, numsamples_used))
    alpha_artifact = np.zeros((n, numsamples_used))
    hialpha_artifact = np.zeros((n, numsamples_used))
    lobeta_artifact =np.zeros((n, numsamples_used))
    beta_artifact =np.zeros((n, numsamples_used))
    hibeta_artifact =np.zeros((n, numsamples_used))
    gamma_artifact =np.zeros((n, numsamples_used))
    higamma_artifact = np.zeros((n, numsamples_used))
    f60hz_artifact = np.zeros((n, numsamples_used))
    f61hz_artifact = np.zeros((n, numsamples_used))

    has_artifact_tot = np.zeros(numsamples_used)
    lodelta_artifact_tot = np.zeros(numsamples_used)
    delta_artifact_tot = np.zeros(numsamples_used)
    theta_artifact_tot = np.zeros(numsamples_used)
    loalpha_artifact_tot = np.zeros(numsamples_used)
    alpha_artifact_tot = np.zeros(numsamples_used)
    hialpha_artifact_tot = np.zeros(numsamples_used)
    lobeta_artifact_tot =np.zeros(numsamples_used)
    beta_artifact_tot =np.zeros(numsamples_used)
    hibeta_artifact_tot =np.zeros(numsamples_used)
    gamma_artifact_tot =np.zeros(numsamples_used)
    higamma_artifact_tot = np.zeros(numsamples_used)
    f60hz_artifact_tot = np.zeros(numsamples_used)
    f61hz_artifact_tot = np.zeros(numsamples_used)   

    has_rms_tot = 0
    lodelta_rms_tot = 0
    delta_rms_tot = 0
    theta_rms_tot = 0
    loalpha_rms_tot = 0
    alpha_rms_tot = 0
    hialpha_rms_tot = 0
    lobeta_rms_tot =0
    beta_rms_tot = 0
    hibeta_rms_tot =0
    gamma_rms_tot =0
    higamma_rms_tot = 0
    f60hz_rms_tot = 0
    f61hz_rms_tot = 0

    comod = np.zeros(256)  
    rms_values_tot = np.zeros(n)
    det_thresh = 0
    newmax = np.max(myfilteredsigs)
    print("MAX:  ", newmax)
    for chanindex in range (0, n):
      has_artifact[chanindex,:] = process.detect_artifact.detect_artifact(myfilteredsigs[chanindex], 10*det_thresh)
      has_artifact[chanindex,:] = process.detect_artifact.detect_rms(myfilteredsigs[chanindex], 10*det_thresh)
      lodelta_artifact[chanindex,:], lodelta_rms_value = process.detect_artifact.detect_band_with_rms(bld, ald, bhld, ahld, myfilteredsigs[chanindex], numsamples, 2*det_thresh)
      delta_artifact[chanindex,:], delta_rms_value = process.detect_artifact.detect_band_with_rms(bd, ad, bhd, ahd, myfilteredsigs[chanindex], numsamples, 2*det_thresh)
      theta_artifact[chanindex,:], theta_rms_value = process.detect_artifact.detect_band_with_rms(bt, at, bht, aht, myfilteredsigs[chanindex], numsamples, 2*det_thresh)
      loalpha_artifact[chanindex,:], loalpha_rms_value = process.detect_artifact.detect_band_with_rms(bla, ala, bhla, ahla, myfilteredsigs[chanindex], numsamples, det_thresh)
      alpha_artifact[chanindex,:], alpha_rms_value = process.detect_artifact.detect_band_with_rms(bal, aal, bhal, ahal, myfilteredsigs[chanindex], numsamples, det_thresh)
      hialpha_artifact[chanindex,:], hialpha_rms_value = process.detect_artifact.detect_band_with_rms(bha, aha, bhha, ahha, myfilteredsigs[chanindex], numsamples, det_thresh)
      lobeta_artifact[chanindex,:], lobeta_rms_value = process.detect_artifact.detect_band_with_rms(blb, alb, bhlb, ahlb, myfilteredsigs[chanindex], numsamples, det_thresh)
      beta_artifact[chanindex,:], beta_rms_value = process.detect_artifact.detect_band_with_rms(bb, ab, bhb, ahb, myfilteredsigs[chanindex], numsamples, 2*det_thresh)
      hibeta_artifact[chanindex,:], hibeta_rms_value = process.detect_artifact.detect_band_with_rms(bhib, ahib, bhhib, ahhib, myfilteredsigs[chanindex], numsamples, 2*det_thresh)
      gamma_artifact[chanindex,:], gamma_rms_value = process.detect_artifact.detect_band_with_rms(bg, ag, bhg, ahg, myfilteredsigs[chanindex], numsamples, 3*det_thresh)
      higamma_artifact[chanindex,:], higamma_rms_value = process.detect_artifact.detect_band_with_rms(bhig, ahig, bhhig, ahhig, myfilteredsigs[chanindex], numsamples, 3*det_thresh)
      f60hz_artifact[chanindex,:], f60hz_rms_value = process.detect_artifact.detect_band_with_rms(b60, a60, bh60, ah60, mysigs[chanindex], numsamples, 4*det_thresh)
      f61hz_artifact[chanindex,:], f61hz_rms_value = process.detect_artifact.detect_band_with_rms(b61, a61, bh61, ah61, mysigs[chanindex], numsamples, 2*det_thresh)

      has_artifact_tot += has_artifact[chanindex]
      lodelta_artifact_tot += lodelta_artifact[chanindex]
      delta_artifact_tot += delta_artifact[chanindex]
      theta_artifact_tot += theta_artifact[chanindex]
      loalpha_artifact_tot += loalpha_artifact[chanindex]
      alpha_artifact_tot += alpha_artifact[chanindex]
      hialpha_artifact_tot += hialpha_artifact[chanindex]
      lobeta_artifact_tot += lobeta_artifact[chanindex]
      beta_artifact_tot += beta_artifact[chanindex]
      hibeta_artifact_tot += hibeta_artifact[chanindex]
      gamma_artifact_tot += gamma_artifact[chanindex]
      higamma_artifact_tot += higamma_artifact[chanindex]
      f60hz_artifact_tot += f60hz_artifact[chanindex]
      f61hz_artifact_tot += f60hz_artifact[chanindex]

      lodelta_rms_tot += lodelta_rms_value
      delta_rms_tot += delta_rms_value
      theta_rms_tot += theta_rms_value
      loalpha_rms_tot += loalpha_rms_value
      alpha_rms_tot += alpha_rms_value
      hialpha_rms_tot += hialpha_rms_value
      lobeta_rms_tot += lobeta_rms_value
      beta_rms_tot += beta_rms_value
      hibeta_rms_tot += hibeta_rms_value
      gamma_rms_tot += gamma_rms_value
      higamma_rms_tot += higamma_rms_value
      f60hz_rms_tot += f60hz_rms_value
      f61hz_rms_tot += f61hz_rms_value

    print('ALPHA ARTIFACT: ', alpha_artifact[:4, :50]) 
#  DEFINE THE COLORS----------------------------------------------------------------------------------------------------------------------------------------------------------

    colorlist = np.array(['Black', 'dimgrey', 'grey', 'purple', 'aqua', 'deepskyblue', 'lightskyblue', 'green', 'orange', 'orange', 'red', 'yellow', 'orange', 'orange'])

#  THIS IS THE PAGE PROCESSING DOING ONE PAGE AT A TIME BETWEEN START AND STOP TIMES
    pageno = 0
    mymetricsa = np.zeros((int(numpages)+1, 55))
    for start,stop in start_stops:
      pageno += 1
      time_range = np.arange(start, stop, 1)
      if selstring[7] == 1:
        #pageno += 1
        print("page: " + str(pageno))
#       plot the whole eeg in 19 channels to view
        fig, ax = plt.subplots(figsize=(12, 15))
#       adjust y_min and y_max and y_increment based on signal size
        y_min = -1000
        y_max = 1000
        y_increment = (y_max - y_min) / (n+20)
#      ax.set_xlim(-1, length)
        ax.set_ylim(y_min, y_max)
        ax.set_xlabel("Time (s)")
#      ax.set_ylabel("Amplitude (uV)")
        ax.set_yticklabels([])
        #time_range = np.arange(start, stop, 1)

# THIS SECTION DRAWS THE EEG WAVEFORMS ACROSS THE TOP OF THE PAGE
        bar_offset = 150
        square_offset = 50
        bar_mult = 5

#  DRAW THE EEG WAVEFORMS AND POWER SQUARES -----------------------------------------------------------------------------------------------------
        for i in range(n):
          y_position = draw_eeg_waveforms(myvisualsigs, i, ax, start, stop, y_max, y_increment, time_range, montage, electrode_names, channel_labels_short, stdmeas, square_offset, bar_mult, colorlist, lodelta_artifact, delta_artifact, theta_artifact, loalpha_artifact, alpha_artifact, hialpha_artifact, lobeta_artifact, beta_artifact, hibeta_artifact, gamma_artifact, higamma_artifact, f60hz_artifact, f61hz_artifact)
#        print(start, stop)

#  COMPUTE TOTAL POWER OF ALL CHANNELS FOR THIS PAGE-------------------------------------------------------------------------------------------
        stdmeasp = np.std(myfilteredsigs[:, start:stop])

#  NOW HAVE DRAWN THE 19 WAVEFORMS IN EEG FORMAT
#  SHOW CORRECT TIME ON BOTTOM HORIZONTAL AXIS
        y_position -= y_increment
        sec_locator = ticker.FixedLocator(np.arange(start, stop, 256))
        sec_formatter = ticker.FixedFormatter(np.arange(start/256, stop/256))
        ax.xaxis.set_major_locator(sec_locator)
        ax.xaxis.set_major_formatter(sec_formatter)
#      ax.xaxis.set_position([0, y_position, 1, 0])
        ax.spines['bottom'].set_position(('data', y_position))

#  NOW DRAW THE EEG WAVEFORMS AS 19 LINES OF A RIBBON-----------------------------------------------------------------------------------------
        colorscale = 20
        y_position -= y_increment
        if selstring[7] == 1:
          draw_a_ribbon(ax, y_position, colorscale, myvisualsigs, n, length, time_range)
        y_position -= 50

#  THIS SECTION DRAWS THE FLAG ARRAYS AS LINES WITH VARIABLE WIDTH AND COLOR
#  DRAW THE FIRST ARTIFACT LINE 1-----------------------------------------------------------------------------------------------------------------

        colorscale = 2
        y_base = y_position - 0.5 * y_increment
        if selstring[7] == 1:
          draw_a_wax_wane(ax, start, stop, length, y_base, bar_offset, bar_mult, "Art:", colorlist[0], has_artifact_tot, time_range)

#  COMPUTE ALL COMODULATIONS

        comod = process.detect_artifact.detect_all_a_causes_b(comod, time_range, has_artifact_tot, 
                  lodelta_artifact_tot, delta_artifact_tot, theta_artifact_tot, 
                  loalpha_artifact_tot, alpha_artifact_tot, hialpha_artifact_tot,
                  lobeta_artifact_tot, beta_artifact_tot, hibeta_artifact_tot, 
                  gamma_artifact_tot, higamma_artifact_tot, f60hz_artifact_tot, f61hz_artifact_tot)
 


        draw_artifact_line(n, stop, start, bar_offset, square_offset, comod, bar_mult, colorlist, y_position, y_increment, ax, length, time_range, lodelta_artifact_tot, lodelta_rms_tot, delta_artifact_tot, delta_rms_tot, theta_artifact_tot, theta_rms_tot, loalpha_artifact_tot, loalpha_rms_tot, alpha_artifact_tot, alpha_rms_tot, hialpha_artifact_tot, hialpha_rms_tot, lobeta_artifact_tot, lobeta_rms_tot, beta_artifact_tot, beta_rms_tot, hibeta_artifact_tot, hibeta_rms_tot, gamma_artifact_tot, gamma_rms_tot, higamma_artifact_tot, higamma_rms_tot, f60hz_artifact_tot, f60hz_rms_tot, y_base)
#      comod[192] = 60hz to tot
#      comod[193] = 60hz to lodelta
#      comod[194] = 60hz to delta
#      comod[195] = 60hz to theta
#      comod[196] = 60hz to alpha1
#      comod[197] = 60hz to alpha
#      comod[198] = 60hz to alpha2
#      comod[199] = 60hz to lobeta
#      comod[200] = 60hz to beta
#      comod[201] = 60hz to hibeta
#      comod[202] = 60hz to gamma
#      comod[203] = 60hz to higamma

#  THE NEXT LINE WILL BE THE EYEBLINK DETECTOR------------------------------------------------------------------------------------------------------------------------------------------------------------------


#  PRINT THE LABELS FOR THE ARTIFACT TYPES ON THE LEFT SIDE OF THE  DISPLAY

        """
        artnames = ['Artifact:', 'Lo Delta', 'Delta:', 'Theta:', 'Alpha1', 'Alpha:', 'Alpha2:', 'LoBeta:', 'Beta:', 'HiBeta:', 'Gamma:', 'HiGamma', '60Hz:', 'Eye Blink:', 'Eye Roll:', 'Lateral Eye:', 'Movement:', 'Clench', 'Cough:', 'EMG:', 'POP:', 'Loose:', 'BVP:', 'Sharp Wave:', 'Spike:', 'Spike/Wave:', 'Sleep Spindle', 'K Complex', 'Beta Spindle', 'Vertex Event', 'Mu Wave', 'IRDA', 'Focal Slow', 'Diff Slow']
        count = 0
        for localname in artnames:
        count += 1
        ax.text(start-400, y_position - (y_increment * ( count/2)), localname)
        """

#  NEED TO SAVE SPECTRA FOR LATER ANALYSIS
#  DRAW FFT POWER SPECTRA OF ALL CHANNELS--------------------------------------------------------------------------------------------------------------------------------------------------------
        draw_fft_power_spectra(n,ax, myvisualsigs, time_range, selstring, start, stop, y_min, montage, electrode_names, channel_labels_pre)

# FINISH UP PLOT AND FINALIZE PDF PAGE---------------------------------------------------------------------------------------------------------------------------------------------------------

#  SHOW CORRECT TIME ON BOTTOM HORIZONTAL AXIS

        sec_locator = ticker.FixedLocator(np.arange(start, stop, 256))
        sec_formatter = ticker.FixedFormatter(np.arange(start/256, stop/256))
        ax.xaxis.set_major_locator(sec_locator)
        ax.xaxis.set_major_formatter(sec_formatter)
      
        plotfname = outputdir1 + " full.png"
        stdstr1 = "{:.1f}".format(stdmeasp)
        stdratio = stdmeasp/global_stdmeas
        stdstr2 = "{:.1f}".format(stdratio)

        if montage == 0:
           ax.set_title("BrainAvatar Pre-Q Scan (LE): " + short_name + "  " + stdstr1 + " " + stdstr2 + "(c) 2023 TF Collura")
        elif montage == 1:
           ax.set_title("BrainAvatar Pre-QScan (AVG): " + short_name + "  " + stdstr1 + " " + stdstr2 + "(c) 2023 TF Collura")
        elif montage == 2:
           ax.set_title("BrainAvatar Pre-Q Scan (LAP)  " + short_name + "  " + stdstr1 + " " + stdstr2 + "(c) 2023 TF Collura")
        elif montage == 3:
           ax.set_title("BrainAvatar Pre-Q Scan (LNGB)  " + short_name + "  " + stdstr1 + " " + stdstr2 + "(c) 2023 TF Collura")
        elif montage == 4:
           ax.set_title("BrainAvatar Pre-Q Scan (ICA)  " + short_name + "  " + stdstr1 + " " + stdstr2 + "(c) 2023 TF Collura")
        elif montage == 5:
           ax.set_title("BrainAvatar Pre-Q Scan (PCA): " + short_name + "  " + stdstr1 + " " + stdstr2 + "(c) 2023 TF Collura")
        elif montage == 6:
           ax.set_title("BrainAvatar Pre-Q Scan (ICA cleaned LE):    " + short_name + "  " + stdstr1 + " " + stdstr2 + "(c) 2023 TF Collura")
        else:
           ax.set_title("BrainAvatar Pre-Q Scan:    " + short_name + "  " + stdstr1 + " " + stdstr2 + "(c) 2023 TF Collura")

        if selstring[7] == 1:
          pdf.savefig(fig)

#  DISPLAY A POPUP WINDOW CONTAINING THE FULL PLOT
#      span = matplotlib.widgets.SpanSelector(ax, onselect, 'horizontal', useblit=True)
#      print("showing plots")
#      plt.show()
        plt.close()

#  HERE IS WHERE WE NEED TO SAVE THIS PAGE'S DATA TO AN EXCEL FILE------------------------------------------------------------------------------------------------------------------------
#  COMPILE SUMMARY INFORMATION TO POST INTO EXCEL FILE FOR TRENDING
#  BEGIN TO COMPILE METRICS INTO METRICS ARRAY FOR EXPORTING TO EXCEL
      name_strings = ["Numsamps", "nchans", "std", "newmax", "std orig", "diff:recon::orig", "diff:clean1::orig", "percent removed",
                      'stdraw', 'global std', "PDR Symm", "PDR Synch", "PDR Reg", "PDR Mag", "PDR Sinus", "PDR MaxPost.", 'PDR FFTWidth', 'PDR Amp', 'PDR BurstWidth',
                      "Beta MaxFront", "Front AlphaAsym", "XS Temp.Alpha", "FastAlpha", 'MidlineBeta', "FocalDelta", "FocalDeltaAmp", 
                      "FocalTheta", "FocalThetaAmp", "FocalHiBeta", "FocalHiBetaAmp", "FocalBeta", "FocalBetaAmp", 'FrontalDelta', 'FrontalTheta', 
                      'FrontalGamma', 'Front GammaAsym', 'DiffuseDelta', 'DiffuseTheta', 'DiffuseHiBeta', 'DiffuseBeta', 'DiffuseGamma', 'Diffuse60Hz',
                      'FractalDimension', 'PDRMoment1', 'PDRMoment2', 'PDRMoment3', 'BetaMoment1', 'BetaMoment2', 'BetaMoment3',
                      'ThetaMoment1', 'ThetaMoment2', 'ThetaMoment3', 'DeltaMoment1', 'DeltaMoment2', 'DeltaMoment3']

#      mymetricsa = np.zeros(27)
      report_strings = create_report_strings()
      index=pageno-1
      mymetricsa[index,0] = numsamples 
      mymetricsa[index,1] = n
      mymetricsa[index,2] = stdmeas
      mymetricsa[index,3] = newmax
      mymetricsa[index,4] = stdorig
      mymetricsa[index,5] = stddiffreconorig
      mymetricsa[index,6] = stddiffclean1orig
      mymetricsa[index,7] = percent
      mymetricsa[index,8] = stdmeasraw
      mymetricsa[index,9] = global_stdmeas
      mymetricsa[index,10], report_strings = process.detect_artifact.detect_pdr_sym(alpha_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,11], report_strings = process.detect_artifact.detect_pdr_sync(alpha_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,12], report_strings = process.detect_artifact.detect_pdr_reg(alpha_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,13], report_strings = process.detect_artifact.detect_pdr_enough(alpha_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,14], report_strings = process.detect_artifact.detect_pdr_sinusoidal(alpha_artifact[:,time_range], beta_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,15], report_strings = process.detect_artifact.detect_pdr_max_post(alpha_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,16] = process.detect_artifact.detect_pdr_freq_epoch(mysigs[:,time_range], channel_labels_pre)
      mymetricsa[index,17] = process.detect_artifact.detect_pdr_amp_epoch(alpha_artifact[:,time_range], channel_labels_pre)
      mymetricsa[index,18] = process.detect_artifact.detect_pdr_epoch_width(alpha_artifact[:,time_range], channel_labels_pre)
      mymetricsa[index,19], report_strings = process.detect_artifact.detect_beta_ftob(beta_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,20], report_strings = process.detect_artifact.detect_phen_frontasym(alpha_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,21], report_strings = process.detect_artifact.detect_phen_xstempalpha(alpha_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,22], report_strings = process.detect_artifact.detect_phen_fastalpha(loalpha_artifact[:,time_range], alpha_artifact[:,time_range], hialpha_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,23], report_strings = process.detect_artifact.detect_phen_spinbeta(beta_artifact[:,time_range], channel_labels_pre, report_strings)

      mymetricsa[index,24], mymetricsa[index,25], report_strings = process.detect_artifact.detect_focal_delta(delta_artifact[:,time_range], channel_labels_pre, report_strings, sites_rsi)
      mymetricsa[index,26], mymetricsa[index,27], report_strings = process.detect_artifact.detect_focal_theta(theta_artifact[:,time_range], channel_labels_pre, report_strings, sites_rsi)
      mymetricsa[index,28], mymetricsa[index,29], report_strings = process.detect_artifact.detect_focal_hibeta(hibeta_artifact[:,time_range], channel_labels_pre, report_strings, sites_rsi)
      mymetricsa[index,30], mymetricsa[index,31], report_strings = process.detect_artifact.detect_focal_hibeta(beta_artifact[:,time_range], channel_labels_pre, report_strings, sites_rsi) #FOCAL BETA
      mymetricsa[index,32], report_strings = process.detect_artifact.detect_frontal_delta(delta_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,33], report_strings = process.detect_artifact.detect_phen_xsfrontslow(theta_artifact[:,time_range], channel_labels_pre, report_strings) #FRONTAL THETA
      mymetricsa[index,34], report_strings = process.detect_artifact.detect_frontal_delta(gamma_artifact[:,time_range], channel_labels_pre, report_strings) #FRONTAL GAMMA
      mymetricsa[index,35], report_strings = process.detect_artifact.detect_phen_frontasym(gamma_artifact[:,time_range], channel_labels_pre, report_strings) #FRONTAL GAMMA ASYM
      
      mymetricsa[index,36], report_strings = process.detect_artifact.detect_diffuse_delta(delta_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,37], report_strings = process.detect_artifact.detect_diffuse_theta(theta_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,38], report_strings = process.detect_artifact.detect_diffuse_hibeta(hibeta_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,39], report_strings = process.detect_artifact.detect_diffuse_hibeta(beta_artifact[:,time_range], channel_labels_pre, report_strings) #DIFFUSE BETA
      mymetricsa[index,40], report_strings = process.detect_artifact.detect_diffuse_delta(gamma_artifact[:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,41], report_strings = process.detect_artifact.detect_diffuse_delta(f60hz_artifact [:,time_range], channel_labels_pre, report_strings)
      mymetricsa[index,42] = process.detect_artifact.detect_fractal_dimension(mysigs[:, time_range], channel_labels_pre, numsamples)

      mymetricsa[index,43], mymetricsa[index,44], mymetricsa[index,45] = process.detect_artifact.detect_drowsiness(alpha_artifact[:,time_range], channel_labels_pre)
      mymetricsa[index,46], mymetricsa[index,47], mymetricsa[index,48] = process.detect_artifact.detect_moments(beta_artifact[:,time_range], channel_labels_pre)
      mymetricsa[index,49], mymetricsa[index,50], mymetricsa[index,51] = process.detect_artifact.detect_moments(theta_artifact[:,time_range], channel_labels_pre)
      mymetricsa[index,52], mymetricsa[index,53], mymetricsa[index,54] = process.detect_artifact.detect_moments(delta_artifact[:,time_range], channel_labels_pre)
     
     
      #mymetricsa[index,30], report_strings = process.detect_artifact.detect_phen_spinbeta(alpha_artifact[:,time_range], channel_labels_short, report_strings)

      if selstring[9] == 1:
        fs.page_metrics_to_excel_file(outputdir1, mymetricsa[index,:], pageno, montage, name_strings)

#  END OF THEPAGE PROCESSING----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

#  POP UP AND SAVE A PLOT OF ALL THE METRICS OVER TIME
    name_strings = ["Numsamps", "nchans", "stdraw", "std", "global std", "newmax",
                    "M6", "M7", "M8", "M9",
                    "PDR Symm", "PDR Synch", "PDR Reg", "PDR Mag", "PDR Sinus", "PDR MaxPost.", 
                    "Beta MaxFront", "Front AlphaAsym", "XS Temp.Alpha", "FastAlpha", "LowV Fast", "Phen Epi", "Phen Difslow", 
                    "Phen Focal", "Phen MixFS", "Phen XSFR Slow", "Phen SpBeta"]

#    figa = Figure(figsize=(5,4), dpi=100)
#    print("MYMETRICSA:   ", mymetricsa)
    mymetricsat = mymetricsa.T
    if selstring[9] == 1:
      figa = Figure(figsize=(5,4), dpi=100)
      axa = figa.add_subplot(1,1,1)

#      figa, axa = plt.subplots()
#  PUT A TITLE ON THE PLOT OF THE METRICS
#      plt.set_yticklabels([])
      for i in range(27):
        if i > 10 and i < 19:
          axa.plot(i+mymetricsat[i], label=name_strings[i])
          axa.text(-0.1, i, name_strings[i])
#      plt.show()
#      time.sleep(5)
      figa.savefig(metricsfilename, dpi=100)
#      plt.close()



#  NOW POUND ON THE DATA TO CREATE A REPORT AND LOAD ADDITIONAL METRICS---------------------------------------------------------------------------------------------------------
    report_strings = create_report_strings()
 #   myreportstrings = ["Beginning of the Report Statements"]

    mymetrics = np.zeros(55)
    mymetrics[0] = numsamples 
    mymetrics[1] = n
    mymetrics[2] = stdmeas
    mymetrics[3] = newmax
    mymetrics[4] = stdorig
    mymetrics[5] = stddiffreconorig
    mymetrics[6] = stddiffclean1orig
    mymetrics[7] = percent
    mymetrics[8] = stdmeasraw
    mymetrics[9] = global_stdmeas
#  max valueS
#   RUN ALL THE TESTS FOR THE DETECTION AND PHENOTYPES
    name_strings = ['STD Raw', 'Global STD', "PDR Symmetry", "PDR Synchrony", "PDR Regulation", "PDR Magnitude", "PDR Sinusoidal", "PDR Max Post.", "PDR FFT Width", 'PDR Max Amplitude', 'PDR Burst Width',
                    "Beta Max Front", "Front Alpha Asym", "XS Temp. Alpha", "Alpha Speed", 'Midline Beta', 'Focal Delta Index', 'Focal Delta Amp.',
                    'Focal Theta Index', 'Focal Theta Amp.', 'Focal HiBeta Index', 'Focal HiBeta Amp.', 'Focal Beta Index', 'Focal Beta Amp.', 'Frontal Delta',
                    'Frontal Theta', 'Frontal Gamma', 'Front Gamma Asym', 'Diffuse Delta', 'Diffuse Theta', 'Diffuse Hibeta', 'Diffuse Beta', 'Diffuse Gamma',
                    'Diffuse 60Hz', 'Fractal Dimension', 'PDR Moment 1', 'PDR Moment 2', 'PDR Moment 3', 'Beta Moment 1', 'Beta Moment 2', 'Beta Moment 3',
                    'Theta Moment 1', 'Theta Moment 2', 'Theta Moment 3', 'Delta Moment 1', 'Delta Moment 2', 'Delta Moment 3']
    range_strings = ["0.85-1.0","0.7-1.0","> 0.8","> 10","> 0.2","> 1.0","> 1.0","< 0.9","< 0.7","0.9 - 1.1","range","range12"]

    mymetrics[10], report_strings = process.detect_artifact.detect_pdr_sym(alpha_artifact, channel_labels_pre, report_strings)
    mymetrics[11], report_strings = process.detect_artifact.detect_pdr_sync(alpha_artifact, channel_labels_pre, report_strings)
    mymetrics[12], report_strings = process.detect_artifact.detect_pdr_reg(alpha_artifact, channel_labels_pre, report_strings)
    mymetrics[13], report_strings = process.detect_artifact.detect_pdr_enough(alpha_artifact, channel_labels_pre, report_strings)
    mymetrics[14], report_strings = process.detect_artifact.detect_pdr_sinusoidal(alpha_artifact, beta_artifact, channel_labels_pre, report_strings)
    mymetrics[15], report_strings = process.detect_artifact.detect_pdr_max_post(alpha_artifact, channel_labels_pre, report_strings)
    mymetrics[16] = process.detect_artifact.detect_pdr_freq_width(mysigs, channel_labels_pre, numpages)
    mymetrics[17] = process.detect_artifact.detect_pdr_amp(alpha_artifact, channel_labels_pre, numpages)
    mymetrics[18] = process.detect_artifact.detect_pdr_art_width(alpha_artifact, channel_labels_pre, numpages)
    mymetrics[19], report_strings = process.detect_artifact.detect_beta_ftob(beta_artifact, channel_labels_pre, report_strings)
    mymetrics[20], report_strings = process.detect_artifact.detect_phen_frontasym(alpha_artifact, channel_labels_pre, report_strings)
    mymetrics[21], report_strings = process.detect_artifact.detect_phen_xstempalpha(alpha_artifact, channel_labels_pre, report_strings)
    mymetrics[22], report_strings = process.detect_artifact.detect_phen_fastalpha(loalpha_artifact, alpha_artifact, hialpha_artifact, channel_labels_pre, report_strings)
    mymetrics[23], report_strings = process.detect_artifact.detect_phen_spinbeta(beta_artifact, channel_labels_pre, report_strings)

    mymetrics[24], mymetrics[25], report_strings = process.detect_artifact.detect_focal_delta(delta_artifact, channel_labels_pre, report_strings, sites_rsi)
    mymetrics[26], mymetrics[27], report_strings = process.detect_artifact.detect_focal_theta(theta_artifact, channel_labels_pre, report_strings, sites_rsi)
    mymetrics[28], mymetrics[29], report_strings = process.detect_artifact.detect_focal_hibeta(hibeta_artifact, channel_labels_pre, report_strings, sites_rsi)
    mymetrics[30], mymetrics[31], report_strings = process.detect_artifact.detect_focal_hibeta(beta_artifact, channel_labels_pre, report_strings, sites_rsi) #FOCAL BETA
    mymetrics[32], report_strings = process.detect_artifact.detect_frontal_delta(delta_artifact, channel_labels_pre, report_strings)
    mymetrics[33], report_strings = process.detect_artifact.detect_phen_xsfrontslow(theta_artifact, channel_labels_pre, report_strings) #FRONTAL THETA
    mymetrics[34], report_strings = process.detect_artifact.detect_frontal_delta(gamma_artifact, channel_labels_pre, report_strings) #FRONTAL GAMMA
    mymetrics[35], report_strings = process.detect_artifact.detect_phen_frontasym(gamma_artifact, channel_labels_pre, report_strings) #FRONTAL GAMMA ASYM
    
    mymetrics[36], report_strings = process.detect_artifact.detect_diffuse_delta(delta_artifact, channel_labels_pre, report_strings)
    mymetrics[37], report_strings = process.detect_artifact.detect_diffuse_theta(theta_artifact, channel_labels_pre, report_strings)
    mymetrics[38], report_strings = process.detect_artifact.detect_diffuse_hibeta(hibeta_artifact, channel_labels_pre, report_strings)
    mymetrics[39], report_strings = process.detect_artifact.detect_diffuse_hibeta(beta_artifact, channel_labels_pre, report_strings) #DIFFUSE BETA
    mymetrics[40], report_strings = process.detect_artifact.detect_diffuse_delta(gamma_artifact, channel_labels_pre, report_strings)
    mymetrics[41], report_strings = process.detect_artifact.detect_diffuse_delta(f60hz_artifact, channel_labels_pre, report_strings)
    mymetrics[42] = process.detect_artifact.detect_fractal_dimension(mysigs, channel_labels_pre, numsamples)
    
    mymetrics[43], mymetrics[44], mymetrics[45] = process.detect_artifact.detect_drowsiness(alpha_artifact, channel_labels_pre)
    mymetrics[46], mymetrics[47], mymetrics[48] = process.detect_artifact.detect_moments(beta_artifact, channel_labels_pre)
    mymetrics[49], mymetrics[50], mymetrics[51] = process.detect_artifact.detect_moments(theta_artifact, channel_labels_pre)
    mymetrics[52], mymetrics[53], mymetrics[54] = process.detect_artifact.detect_moments(delta_artifact, channel_labels_pre)
    #mymetrics[26], report_strings = process.detect_artifact.detect_phen_spinbeta(alpha_artifact, channel_labels_short, report_strings)

#  FINAL PAGE OF DETAIL OF ONE CHANNEL--------------------------------------------------------------------------------------------------------
    print('METRICS: ', mymetrics)
#   find channels to focus on
    channel_index = channel_labels_short.index('FP1')
    print("channel index for Fp1:   " + str(channel_index))
    channel_index1 = channel_labels_short.index('O1')
    print("channel index for O1:    " + str(channel_index1))

#  PICK A PARTICULAR CHANNEL TO DO FURTHER ANALYSIS ON

    current_channel = channel_index
#    stdmeas = np.std(myfilteredsigs[current_channel])
    first_row = myfilteredsigs[current_channel]
    first_seg = first_row[:length]
    stdmeas = np.std(first_row[:length])
    has_artifact = process.detect_artifact.detect_artifact(first_seg)
    saw_artifact = np.max(has_artifact[1:length])
#    print("artifact shape:")
#    print(has_artifact.shape)

#  CREATE MARKERS FROM THE  FLAGS AND WRITE THEM TO A FILE

    has_markers = fs.flag_to_marker(has_artifact, 25)
    print (has_markers)
    if selstring[11] == 1:
      markerfname = outputdir1 + ".mrk.txt"
      fs.write_markers_to_file(has_markers, markerfname)

    print(first_row[:4])

#    fig, ax1 = plt.subplots(figsize=(12, 9))
    plt.figure(figsize=(12,15))
    plt.ylim(-500, 500)
    plotlabel = edf_file + "  " + channel_labels_short[current_channel] + "   " + str(stdmeas) + "      artifact not found"
    if(saw_artifact):
        plotlabel = edf_file + "  " + channel_labels_short[current_channel] + "    " + str(stdmeas) + "      artifact found"
    plt.title(plotlabel)
    
    markertext = fs.array_to_text(has_markers)
 #   add_text_to_plot(markertext)
    plt.annotate(markertext, (0.01, 0.99), xycoords='axes fraction', ha='left', va='top', fontsize=12)

    plt.plot(first_row[:length])

    x = np.arange(0, length, 1)
    y = np.zeros(length)
  
    for z in range (0,length-1):
     y[z] = 20 if has_artifact[z] else 1

#    plt.step(x, y, where='post')
    plt.plot(y)
    plotfname = outputdir1 + ".png"
    plt.savefig(plotfname)

    if selstring[7] == 1:
      pdf.savefig(plt.gcf())

    plt.close()
#    plt.show()
    if selstring[7] == 1:
      pdf.close()
    if selstring[11] == 1:  
      fs.data_to_text_file(outputdir1, data, n)

#  WRITE METRICS TO EXCEL FILE FOR LATER COMPILATION INTO DATABASES
    
    outfile=''
    excel_file=''
    if selstring[9] == 1:
      fs.data_to_excel_file(outputdir1, data, n)
      outfile = fs.metrics_to_excel_file(outputdir1, mymetrics, plot_num, montage, database_name)
      if montage == 6:
         excel_file = fs.comps_to_excel_file(database_name, comp_array)
      print('Outfile is ', outfile)
      #fs.histogram_to_excel_file(outfile)  
#    report_strings = ["Sinusoidal", "Maximal posteriorly", "Symmetrical", "Well regulated (characteristic waxing and waning)", "Increases with eyes closed"]
#  CREATE PDF FILE OF REPORT INFORMATION
    if selstring[8] == 1:
      create_report_pdf(outputdir1, short_name, channel_labels_short, name_strings, range_strings, report_strings, mymetrics, montage, excel_file_path, n, numpages, myvisualsigs, channel_labels_pre) #electrodenames
   
#  HELPER FUNCTIONS

#  THIS IS THE END OF THE PROCESSING SEQUENCE WHICH NOW WILL RETURN A VALUE
    return(pageno, outfile, excel_file)
