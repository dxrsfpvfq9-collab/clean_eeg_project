#DUMMY GUI
from tkinter import *
from tkinter.ttk import *
import tkinter.font as font
import tkinter.ttk as ttk
import tkinter as tk
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from scipy.interpolate import griddata
import matplotlib.patches as patches
from matplotlib.colors import Normalize
from PIL import Image as img
#from mayavi import mlab
import matplotlib.colors as mcolors
import math
import csv
import os
os.environ['ETS_TOOLKIT'] = 'wx'

#import imp
#try:
#    imp.find_module('PySide') # test if PySide if available
#except ImportError:
#    os.environ['QT_API'] = 'pyqt5' # signal to pyface that PyQt4 should be used

#from pyface.qt import QtGui, QtCore
import pyvista as pv
from process.detect_artifact import detect_peak

#from Montage_List import icabutton_callback
#from ttkthemes import ThemedTk

# BEGINNING OF COMPONENT VIEWER -----------------------------------------------------------------------------------------------------------------------------------------------------------------

# --- Point Process Spectrum helpers -------------------------------------------
# Module level on purpose: as closures inside the component-view function these
# captured its locals and formed reference cycles, so freeing them needed the
# cyclic collector. The image cascade creates and destroys one tk.Tk() root per
# component, and a collection pass landing in the middle of a Tk call is a
# hazard worth removing. They are pure numpy -- no Tk, no pyplot, no globals.

def pp_spectrum(train, live_frac, nlive_b, nbins, binf, ksmooth):
    """Normalized, smoothed point-process spectrum. 1.0 = chance level.

    `train` is a full-rate impulse train; it is summed into `binf`-sample bins
    before the transform. The rate is subtracted only in proportion to how much
    of each bin was actually observable (live_frac), so the per-epoch dead zone
    contributes exactly zero instead of a deterministic -rate square wave -- an
    error that otherwise puts a 0.1 Hz comb straight through the display band.
    """
    tb = train[:nbins * binf].reshape(nbins, binf).sum(axis=1)
    n_ev = tb.sum()
    spec = np.abs(np.fft.rfft(tb - live_frac * (n_ev / nlive_b))) ** 2
    spec = spec / (n_ev * (1.0 - n_ev / nlive_b))
    # Daniell smoothing: the raw periodogram is chi-square with 2 dof (~100%
    # scatter, unreadable). A ksmooth-bin box cuts that to 1/sqrt(ksmooth) and
    # leaves the 1.0 baseline unbiased.
    if ksmooth > 1:
        spec = np.convolve(spec, np.ones(ksmooth) / ksmooth, mode='same')
    return spec


def pp_surrogate(n_ev, refractory, live_idx, total, rng):
    """A random train with the SAME event count and the SAME refractory.

    Poisson is the wrong null here: the detector enforces a refractory, which by
    itself suppresses low frequencies and humps the spectrum near 1/refractory,
    so a Poisson reference reads that bias as rhythm. Positions are drawn
    uniformly over the live samples with the minimum gap folded in, which is
    uniform over all admissible layouts. Returns None if the count cannot fit.
    """
    span = len(live_idx) - (n_ev - 1) * refractory
    if span < n_ev:
        return None
    pos = np.sort(rng.choice(span, size=n_ev, replace=False))
    pos = pos + np.arange(n_ev) * refractory
    sur = np.zeros(total)
    sur[live_idx[pos]] = 1.0
    return sur

def dummy_gui(tlabel, length, numsamples, ica_mixing, idx, selected_channel_list, selected_channel_reasons, channel_labels_short, myvisualsigs, n, disp_idx=None):
    # FUNCTIONS------------------------------------------------------------------------------------------------------------------------------------------------------
    def remove_keep(button):
        if button == "remove":
            print('remove f')
            lab.config(text="Current: Remove", font='Helvetica 15', fg="red", bg="white")
            if idx in selected_channel_list:
                if len(selected_channel_list) == len(selected_channel_reasons):
                    idxval = selected_channel_list.index(idx)
                    reason_val = selected_channel_reasons[idxval]
                    reason_lab.config(text='Reason: ' + channel_labels_short[reason_val], font='Helvetica 15')
                #elif len(selected_channel_list) != len(selected_channel_reasons):
                #    selected_item = [listbox.get(index) for index in listbox.curselection()]
                #    reason_lab.config(text='Reason: ' + selected_item, font='Helvetica 15')
            if idx not in selected_channel_list:
                selected_channel_list.append(idx)
                print('Selected channels:  ', selected_channel_list)
                #icabutton[idx-1].config(relief='sunken')
                #grabbed_value = None
                #for value in channel_labels_short:
                #    if value not in exclude_values:
                #        grabbed_value = value
                #        break
                #index = channel_labels_short.index(grabbed_value)
                #selected_channel_reasons.append(index)
                print("Selected Channel Reasons", selected_channel_reasons)
                #selected_channel_list.sort()
                #icatext.insert(tk.END, "MAX AT: \n")
                #for selchan in selected_channel_list:
                #    icatext.insert(tk.END, selchan, "MAX AT:", channel_labels_short[selected_channel_reasons[selchan]])
                #    icatext.insert(tk.END, "\n")
                    
        elif button == "keep":
            print('keep f')
            lab.config(text="Current: Keep", font='Helvetica 15', fg="green", bg="white")
            reason_lab.config(text='Reason: User Override', font='Helvetica 15')
            if idx in selected_channel_list:
                idxval = selected_channel_list.index(idx)
                if len(selected_channel_list) == len(selected_channel_reasons):
                    reason_val = selected_channel_reasons[idxval]
                    selected_channel_reasons.remove(reason_val)
                selected_channel_list.remove(idx)
                print('Selected channels:  ', selected_channel_list)
                #icabutton[idx-1].config(relief='raised')
                print("Selected Channel Reasons", selected_channel_reasons)

                #selected_channel_list.sort()
                #icatext.insert(tk.END, "MAX AT: \n")
                #for selchan in selected_channel_list:
                #    icatext.insert(tk.END, selchan, "MAX AT:", channel_labels_short[selected_channel_reasons[selchan]])
                #    icatext.insert(tk.END, "\n")
#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    numpages = numsamples//length - 1
    print('Length: ', length)
    start_stops = [(int(j * length), int( (j+1) * length)) for j in np.arange(0, numpages, 1)]
    print('Start Stops: ', start_stops)

    stdmeasv = np.std(myvisualsigs[:])
    myvisualsigs = myvisualsigs * 10.0 / stdmeasv
    # CREATES A NEW WINDOW
    CV = tk.Tk()
    sw = CV.winfo_screenwidth()
    sh = CV.winfo_screenheight()
    style = ttk.Style()
    CV.title("Component Viewer")
    
    
    sw = CV.winfo_screenwidth()
    sh = CV.winfo_screenheight()
    CV.geometry(f"{sw}x{sh}")
    CV.configure(bg='white')
    # idx indexes the FastICA arrays; disp_idx is its magnitude rank, which
    # is what the reader sees. Falls back to idx so other callers are safe.
    WTitle = tk.Label(CV, text=("Component:", idx if disp_idx is None else disp_idx), font=('Helvetica', 50, 'bold'), bg='white')
    WTitle.place(x=440, y=20)


    tlab = tk.Label(CV, text=tlabel, font='Helvetica 13', bg='white')
    tlab.place(x=250, y=5)

    lab = tk.Label(CV, text="Current: #TBD", font='Helvetica 15')
    lab.place(x = 810, y = 885)

    fft_lab = tk.Label(CV, text="Flyover Disabled", font='Helvetica 15', fg='red', bg='white')
    #fft_lab.place(x=1630, y=1000)

    epoch_lab = tk.Label(CV, text='Epoch: 1 ', font='Helveica 15', bg='white')
    epoch_lab.place(x = 940, y = 30)

    int_lab = tk.Label(CV, text='Interval: 0-10', font='Helvetica 12', bg='white')
    int_lab.place(x = 940, y = 55)
    #RMS Calculation-----------------------------------------------------------------------------------------------------------------------------------------------------------------
    mix_list = []
    for item in ica_mixing:
        for num in item:
            mix_list.append(num)
    #print('List: ', mix_list)
    mix_list = np.array(mix_list)
    #rms_tot = np.sqrt(np.mean(np.square(mix_list)))
    comp =ica_mixing[:, idx-1]
    #rms_comp = np.sqrt(np.mean(np.square(comp)))
    rms_tot = np.sum(np.square(ica_mixing))
    rms_comp = np.sum(np.square(comp))
    rms_perc = (rms_comp/rms_tot)*100

    reason_lab = tk.Label(CV, text='Reason: ', font='Helvetica 15', bg='white')
    reason_lab.place(x =810, y = 910)

    style.configure("RED.TButton", foreground="black", background="red", padding=[10, 10, 10, 10], font='Helvetica 15')
    style.configure("GREEN.TButton", foreground="black", background="green", padding=[10, 10, 10, 10], font='Helvetica 15')
    style.configure("GRAY.TButton", foreground="black", background="black", padding=[10, 10, 10, 10], font='Helvetica 15')

    # HERE IS THE REMOVE, KEEP, AND CLOSE BUTTONS-------------------------
    Rbtn = Button(CV, text = "Remove", style="RED.TButton", command = lambda: (remove_keep("remove")))#, icabutton_callback()))
    Rbtn.place(x = 260, y = 880, height=75, width=150)
    Rbtn.lower()
    
   
    Kbtn = Button(CV, text = "Keep", style="GREEN.TButton", command = lambda: remove_keep("keep"))
    Kbtn.place(x = 450, y = 880, height=75, width=150)
    Kbtn.lower()

    Cbtn = Button(CV, text= "Close", style="GRAY.TButton")
    Cbtn.place(x = 640, y = 880, height=75, width=150)
    
    catagory_box = tk.Canvas(CV, width=200, height=990, bg="#a2a2a2")
    catagory_box.place(x=5, y=0)

    #---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def vector_matrix_multiplication(matrix, vector):
        # Verify dimensions
        if matrix.shape[1] != len(vector):
            vector = vector[:-1]
        # Initialize the output vector
        mult_result = np.zeros(matrix.shape[0])
        # Perform matrix-vector multiplication
        for i in range(matrix.shape[0]):
            mult_result[i] = np.dot(matrix[i], vector)
    
        return mult_result

    
    #GET TMATRIX FILE----------------------------------------------------------------------------------------------------------------------------------------------------------
    print('IN SOURCE LOCALIZATION FUNCTION')
    cwd = os.getcwd()
    file_path = os.path.join(cwd, '19chan.sLoreta.none.csv')
    #REORDER ICA MIXING TO DISCOVERY ORDER-------------------------------------------------------------------------------------------------------------------------------------
    disc_order = ['FP1', 'F3', 'C3', 'P3', 'O1', 'F7', 'T3', 'T5', 'FZ', 'FP2', 'F4', 'C4', 'P4', 'O2', 'F8', 'T4', 'T6', 'CZ', 'PZ', 'A2', 'AX1', 'AX2']
    if channel_labels_short != disc_order:
        string_index_map = {string: index for index, string in enumerate(channel_labels_short)}
    #print('ICA Before Sorting: ', icamixing)
        channel_labels_disc_sorted = sorted(channel_labels_short, key=lambda x: disc_order.index(x))
        print('CHANNEL LABELS', channel_labels_disc_sorted) 
        reordered_ica_mixing = []
    
        for string in channel_labels_disc_sorted:
            index = string_index_map[string]
            reordered_ica_mixing.append(ica_mixing[index])

        ordered_ica_mixing = np.array(reordered_ica_mixing)
    #print('ICA After Sorting: ', icamixing)
    #GET INDIVIDUAL COMPONENT OUT OF ICA MIXNG----------------------------------------------------------------------------------------------------------------------------------
    vector = ordered_ica_mixing[:, idx-1]
    vector = vector[:19]
    print('VECTOR TO BE MULTIPLIED: ', vector)
    print('VECTOR SHAPE: ', vector.shape)
    #GET MATRIX OUT OF CSV FILE------------------------------------------------------------------------------------------------------------------------------------------------
    with open(file_path) as file:
        reader = csv.reader(file)
        matrix_data = [row[2:21] for row in reader]

    matrix = np.array(matrix_data, dtype=float)
    print('MATRIX SHAPE: ', matrix.shape)
    #print(matrix)
    mult_result = vector_matrix_multiplication(matrix, vector)
    print('DOT PRODUCT RESULT SHAPE: ', mult_result.shape)
    #print(mult_result)
    reshaped_list = np.reshape(mult_result, (6239, 3))
    print("RESHAPED LIST: ", reshaped_list)
    #CREATE CSD BASED OFF DOT PRODUCT RESULT---------------------------------------------------------------------------------------------------------------------------------------
    voxel_csd = []
    for i in range(0, len(mult_result), 3):
        xyz = mult_result[i:i+3]
        sum_of_squares = sum(k**2 for k in xyz)
        new_val = math.sqrt(sum_of_squares)
        voxel_csd.append(new_val)
    print('CSD SHAPE: ', len(voxel_csd))
    #FIND THE MAX----------------------------------------------------------------------------------------------------------------------------------------------------------------
    max_value = max(voxel_csd)
    max_index = voxel_csd.index(max_value)
    print("Maximum value:", max_value)
    print("Index of maximum value:", max_index)
    #GET LOCATION OF SOURCE VOXEL-----------------------------------------------------------------------------------------------------------------------------------------------
    location_file_path = os.path.join('MNI-BAs-6239-voxels.csv')
    with open(location_file_path, 'r') as file:
        location_data = csv.reader(file)
        location_matrix = np.array(list(location_data), dtype=str)
    #print(location_matrix)
    print('LOCATION MATRIX SHAPE: ',location_matrix.shape)
   
    #ACQUIRE SOURCE POINT--------------------------------------------------------------------------------------------------------------------------------------------------------
    source_point = location_matrix[max_index, :]
    print('SOURCE POINT: ', source_point) 
    
    
    
    loc_1 = source_point[3]
    loc_2 = source_point[4]
    loc_3 = source_point[5]
    #-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    Bbtn = Button(CV, text= "Brain Viewer", style="GRAY.TButton")
    Bbtn.place(x = 245, y = 25, height=90, width=170)
    #---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    
    cat_list = ['MAX AT: Fp1', 'MAX AT: Fp2', 'MAX AT: F7', 'MAX AT: F3', 'MAX AT: Fz', 'MAX AT: F4', 'MAX AT: F8', 'MAX AT: T3', 'MAX AT: C3', 'MAX AT: Cz', 'MAX AT: C4', 'MAX AT: T4', 'MAX AT: T5', 'MAX AT: P3', 'MAX AT: Pz', 'MAX AT: P4', 'MAX AT: T6', 'MAX AT: O1', 'MAX AT: O2', 'MAX AT: A2', 'User Override']
    #EOG-Blink, 'EOG-Roll
    if int(source_point[0]) < 0:
        hemi = 'Left Hemisphere'
    elif int(source_point[0]) >0:
        hemi = 'Right Hemisphere'
    else:
        hemi = "Midline"
    
    region = tk.Label(CV, text= loc_1 + "\n" + loc_2 + "\n" + loc_3 + "\n" + hemi, font='Helvetica 13', bg='white')
    region.place(x = 259, y = 115)


    font_size = 14
    listbox_font = font.Font(size=font_size, family='Helvetica')

    listbox = Listbox(CV, font=listbox_font, justify="center")
    for cat_list in cat_list:
        listbox.insert(tk.END, cat_list)
    listbox.place(x=40, y = 60, height=800, width=125)
        

    # CREATES THE CATAGORIES AND OTHER COMPONENTS LABEL ON THE LEFT OF SCREEN
    CTitle = Label(CV, text="Catagories", font=('Helvetica', 15, 'underline', 'bold'), background="#a2a2a2")
    CTitle.place(x=50, y=20)
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    if idx in selected_channel_list:
        remove_keep("remove")
        print('remove')
    elif idx not in selected_channel_list:
        remove_keep("keep")
        print('keep')
        
    print('# of Trials: ', numpages) 
    # CREATES THE PLOTS TO VIEW FOR EACH COMPONENT ----------------------------------------------------------------------------------------------------------------------------------------------
    fig_wave = Figure(figsize=(8.11, 1.05), dpi=100)
    ax_wave = fig_wave.add_subplot(111)
    fig_wave.subplots_adjust(left=.04)
    x = np.arange(0, numsamples, 512)
    ax_wave.set_xticks(x, x)
    ax_wave.set_xticklabels([])
    sigtoshow = myvisualsigs[idx-1, :]
    time_range = np.arange(0, numsamples, 1)
    ax_wave.set_xlim(0, 2560)
    ax_wave.plot(time_range, sigtoshow, color="Black", linewidth=0.5)
    y_bound = ax_wave.get_ylim()
    print('Ybound: ', y_bound)
    time_range = np.arange(0, numsamples, 10)
    sigtoshow = myvisualsigs[(idx-1), time_range]
    for j in range(len(time_range) - 1):
                ax_wave.plot(time_range[j:j+2], [y_bound[0], y_bound[0]], color=plt.cm.jet((20+sigtoshow[j])/40), linewidth= 7)
    canvas_wave = FigureCanvasTkAgg(fig_wave, master=CV)
    canvas_wave.draw()
    canvas_wave.get_tk_widget().place(x=1061, y=0)
    # Bath Water Graph ----------------------------------------------------------------------------------------------------------------------------
    fig_ribbon = Figure(figsize=(8.3, 2.75), dpi=100, linewidth=50)
    ax_ribbon = fig_ribbon.add_subplot(1,1,1)
    fig_ribbon.subplots_adjust(left=.06)
    text = ax_ribbon.text(0.1, 0.9, '', ha='left', va='top', backgroundcolor='white')
    ax_ribbon.set_ylim(0, numpages + 1)
    ax_ribbon.set_xlim(0, 2560)
    ax_ribbon.set_xticks([0, 512, 1024, 1523, 2048, 2560])
    ax_ribbon.set_xticklabels([0, 2, 4, 6, 8, 10])
    ax_ribbon.set_xlabel('Seconds')
    ax_ribbon.set_ylabel('Trials')
    time_range = np.arange(0, 2560, 10)
    signalsin = myvisualsigs
    print("SHAPE: ", myvisualsigs.shape)
    yvalues = np.zeros(4)
    y_position = 1
    #y_position -= y_increment
    for i in range(numpages):
    #    data_range = np.arange(2560*(i-1), 2560*i, 10)
        y_position = i + 1
        yvalues[0:4] = y_position
        data_range = np.arange(2560*(i), 2560*(i+1), 10)
        sigtoshow = signalsin[(idx-1), data_range]
        for j in range(len(time_range) - 1):
            ax_ribbon.plot(time_range[j:j+2], yvalues[0:2], color=plt.cm.jet((20+sigtoshow[j])/40), linewidth= (146/numpages)-.6)
    #()
    canvas = FigureCanvasTkAgg(fig_ribbon, master=CV)
    canvas.get_tk_widget().place(x=1043, y=218)
    ax_ribbon.set_title('Bath Water Graph', pad=1)
    fig_ribbon.subplots_adjust(bottom=0.15)
    sm = ScalarMappable(cmap='jet_r')
    sm.set_clim(vmin=-np.max(np.abs(sigtoshow)), vmax=np.max(np.abs(sigtoshow)))
    colorbar = Figure(figsize=(0.2, 2.5), dpi=100)
    colorbar.subplots_adjust(left=0, right=1, bottom=0, top=1)
    colorbar_ax = colorbar.add_subplot(111)
    colorbar_ax.axis('off')
    color_range = np.arange(256)
    colorbar_ax.imshow(color_range.reshape(-1, 1), aspect='auto', cmap='jet_r')

    colorbar_img = FigureCanvasTkAgg(colorbar, master=CV)
    colorbar_img.get_tk_widget().place(x=1830, y=232)

    #CHANGING INTERVAL OF WAVE------------------------------------------------------------------------------------------------------------------------------------------------------
    #fig_ribbon.canvas.mpl_connect('button_press_event', on_ribbon_select)
    #COMPONENT WAVE-------------------------------------------------------------------------------------------------------------------------------------------------------------------
    #fig_wave = Figure(figsize=(9, 1.6), dpi=100)
    #ax_wave = fig_wave.add_subplot(111)
    #x = np.arange(0, numsamples, 512)
    #ax_wave.set_xticks(x, x)
    #ax_wave.set_xticklabels([])
    #sigtoshow = myvisualsigs[idx-1, :]
    #time_range = np.arange(0, numsamples, 1)
    #ax_wave.set_xlim(0, 2560)
    #ax_wave.plot(time_range, sigtoshow, color="Black", linewidth=0.5)
    #y_bound = ax_wave.get_ylim()
    #time_range = np.arange(0, numsamples, 10)
    #sigtoshow = myvisualsigs[(idx-1), time_range]
    #for j in range(len(time_range) - 1):
    #            ax_wave.plot(time_range[j:j+2], [y_bound[0], y_bound[0]], color=plt.cm.jet((20+sigtoshow[j])/40), linewidth= 7)
    #canvas_wave = FigureCanvasTkAgg(fig_wave, master=CV)
    #canvas_wave.draw()
    #canvas_wave.get_tk_widget().place(x=980, y=0)
    # HEAD MAP------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    eeg_data = ica_mixing[ :19, idx-1] / 1000.0   # un-scale the x1000 mixing
    locations = np.array([[-0.25, 0.51], #FP1
                      [0.25, 0.51], #FP2
                      [-0.71, 0.3], #F7
                      [-0.32, 0.25], #F3
                      [0, 0.25], #Fz
                      [0.32, 0.25], #F4
                      [0.71, 0.3], #F8
                      [-0.85, 0], #T3
                      [-0.41, 0], #C3
                      [0, 0], #Cz
                      [0.41, 0], #C4
                      [0.85, 0], #T4
                      [-0.71, -0.3], #T5
                      [-0.32, -0.25], #P3
                      [0, -0.25], #Pz
                      [0.32, -0.25], #P4
                      [0.71, -0.3], #T6
                      [-0.25, -0.51], #O1
                      [0.25, -0.51]]) #O2

    print(locations.shape)


    xi = np.linspace(-.82, .82, 100)
    yi = np.linspace(-.51, .51, 100)
    xi, yi = np.meshgrid(xi, yi)
    zi = griddata((locations[:,0], locations[:,1]), eeg_data, (xi, yi), method='cubic')
    # Cubic interpolation OVERSHOOTS beyond the electrode value range, painting
    # spurious red/blue at the head periphery that matches no channel and makes
    # the contour disagree with the mixing-matrix bar graph. Clamp to the true
    # data range, and drive contour/scatter/colorbar from ONE symmetric-around-0
    # normalization so sign is preserved (all-negative component -> all blue,
    # matching the Blues_r bars; positives -> red).
    hm_amax = float(np.nanmax(np.abs(eeg_data)))
    if not hm_amax > 0:
        hm_amax = 1.0
    zi = np.clip(zi, -hm_amax, hm_amax)
    hm_norm = Normalize(vmin=-hm_amax, vmax=hm_amax)

    print(zi.shape)

     
    fig = Figure(figsize=(3.7, 3.7), frameon=False)
    ax = fig.add_subplot(111)
    fig.subplots_adjust(right=1.01, left=.02)
    # ADD CIRCLE----------------------------------------
    ax.contourf(xi, yi, zi, levels=np.linspace(-hm_amax, hm_amax, 31), cmap='jet', norm=hm_norm)
    ellipse = patches.Ellipse((0, 0),width=1.64, height=1.02, facecolor='none', edgecolor='black', fill=False, linewidth=3.5)
    ax.add_patch(ellipse)

    ax.scatter(locations[:, 0], locations[:, 1], c=eeg_data, cmap='jet', norm=hm_norm, edgecolors='k')
    
    #ax.scatter(locations[:, 0], locations[:, 1], c=eeg_data[:, 0], cmap='jet', edgecolors='k')
    ax.set_xlim(-.82, .82)
    ax.set_ylim(-.51, .51)
    ax.set_title('Head Contour Map')
    zoom_factor = 1.2
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    x_center = 0.5 * (x_min + x_max)
    y_center = 0.5 * (y_min + y_max)
    x_new_min = x_center - (zoom_factor * (x_center - x_min))
    x_new_max = x_center + (zoom_factor * (x_max - x_center))
    y_new_min = y_center - (zoom_factor * (y_center - y_min))
    y_new_max = y_center + (zoom_factor * (y_max - y_center))
    ax.set_xlim(x_new_min, x_new_max)
    ax.set_ylim(y_new_min, y_new_max)

    ax.axis("off")
    
    sm = ScalarMappable(cmap='jet', norm=hm_norm)
    fig.colorbar(sm, ax=ax, orientation='vertical')

    canvas = FigureCanvasTkAgg(fig, master=CV)
    canvas.draw()
    canvas.get_tk_widget().place(x=605, y=151)

    # ADD FFT -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    
    fig_fft = Figure(figsize=(8.5, 2.7), dpi=100)
    ax_fft = fig_fft.add_subplot(111)      
    fig_fft.subplots_adjust(left=.08)
    #kernel=np.array([1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16])
    #kernel1 = np.array([1/32, 1/16, 1/16, 1/16, 1/4, 1/16, 1/16, 1/16, 1/32])
    kernel1 = np.array([1/16, 1/8, 3/16, 1/2, 3/16, 1/8, 1/16])
    #kernel1=np.array([1/16, 1/16, 1/8, 1/2, 1/8, 1/16, 1/16])
    sig_s = np.zeros(2560)
    amp_s = np.zeros(2560)
    amp_sc = np.zeros(2560)
    window_s = np.hamming(2560)
    
    epoch_vals= []
    phases = []
    powers = []
    ffts = []
    #cyc_ffts = []
    for i in range(numpages):
        epoch_range = np.arange(2560*(i-1), 2560*i, 1)
        sig_s =myvisualsigs[idx-1, epoch_range] #* window_s
        fft_s = np.fft.fft(sig_s)
        #fft_s[651:] = 0 + 0j
        ffts.append(fft_s)
        phase = np.imag(fft_s)
        amp_s = np.abs(fft_s)
        #power_s = amp_s ** 2
        #amp_sc = np.convolve(amp_s, kernel, mode='same')
        amp_sc = np.convolve(amp_s, kernel1, mode='same')
        power_s = amp_sc ** 2
        epoch_vals.append(amp_sc)
        phases.append(phase)
        power_s = np.abs(power_s)
        print('Length is: ', len(power_s))
        powers.append(power_s)
        #FFT OF POWER SPECTRUM
        #cyc_fft = np.fft.fft(amp_sc)
        #cyc_s = np.abs(cyc_fft)
        #cyc_sc = np.convolve(cyc_s, kernel, mode='same')
        #cyc_sc = np.convolve(cyc_sc, kernel1, mode='same')
        #cyc_ffts.append(cyc_sc)
          #freq_s = np.fft.fftfreq(len(sig_s), d=1/256)
    phases = phases*100
    avg_amp_sc = sum(epoch_vals) / len(epoch_vals)
    avg_unsmooth = sum(ffts) / len(ffts)
    avg_power = sum(powers) / len(powers)
    print(avg_power[1920:])
    #i_fft = np.fft.ifft(avg_amp_sc)
    #print('length: ', len(i_fft))
    #i_fft = np.real(i_fft)
    #print('IFFT: ', i_fft)
    #print('lenght: ', len(i_fft))
    avg_phase = sum(phases) / len(phases)
    #avg_cyc = sum(cyc_ffts) / len(cyc_ffts)
    #print("FFT OF FFT?", avg_cyc)
    #x_min = np.amin()
    #x_max = np.max()
    y_min = np.amin(avg_amp_sc)
    y_max = np.max(avg_amp_sc)
    y_max_e = np.max(epoch_vals[0]) 
    ax_fft.set_xticklabels([0, 10, 20, 30, 40, 50, 60])
    if y_max_e > y_max:
        ax_fft.set_ylim(0, y_max_e + 50)
        if y_max_e > 1500:
            ax_fft.set_yticks(range(int(y_min), int(y_max_e) + 80, 200))
            if y_max_e > 3000:
                ax_fft.set_yticks(range(int(y_min), int(y_max_e) + 80, 300))
                if y_max_e > 5000:
                    ax_fft.set_yticks(range(int(y_min), int(y_max_e) + 80, 500))
        elif y_max_e:
            ax_fft.set_yticks(range(int(y_min), int(y_max_e) + 80, 100))
    elif y_max_e < y_max:
        ax_fft.set_ylim(0, y_max+50)
        if y_max > 1500:
            ax_fft.set_yticks(range(int(y_min), int(y_max) + 80, 200))
            if y_max > 3000:
                ax_fft.set_yticks(range(int(y_min), int(y_max) + 80, 300))
                if y_max_e > 5000:
                    ax_fft.set_yticks(range(int(y_min), int(y_max_e) + 80, 500))
        elif y_max:
            ax_fft.set_yticks(range(int(y_min), int(y_max) + 80, 100))
    
    ax_fft.set_title('Fast Fourier Transform')
    #VERT LINE FOR INTERSECTION
    vline = ax_fft.axvline(0, color='black', linestyle='--')
    #POINTS OF INTERSECTION
    point1 = ax_fft.scatter([], [], color='red', zorder=5)
    point2 = ax_fft.scatter([], [], color='blue', zorder=5)
    #TEXT ANNOTATIOn
    coord_text = ax_fft.text(0.788, 0.7, '', transform=ax_fft.transAxes, va='top')
    ax_fft.plot(avg_amp_sc, linewidth=2, color='red', label='Average FFT')
    #ax_fft.plot(avg_power, linewidth=2, color='green', label='Average Power')
    #ax_fft.plot(avg_cyc, linewidth=2, color='yellow', label='FFT of PS')
    ax_fft.plot(epoch_vals[0], linewidth=2, color='blue', label='Epoch FFT')
    #ax_fft.plot(powers[0], linewidth=2, color='orange', label='Epoch Power')
    print('imag EPOCH 0: ', np.imag(epoch_vals[0]))
    print('AVG PHASE: ', avg_phase)
    print('Phase 0: ', phases[0])
    ax_fft.set_xlim(0, 640)
    ax_fft.legend()
    #ax_fft.set_ylim(y_min, y_max+50)
    ax_fft.set_xticks(range(0, 650, 100))
    canvas_fft = FigureCanvasTkAgg(fig_fft, master=CV)
    canvas_fft.draw()
    canvas_fft.get_tk_widget().place(x=1027, y=736)
    retcon = detect_peak(avg_amp_sc[:650])
    peak = retcon/10
#FFT WATERFALL---------------------------------------------------------------------------------------------------------------------------------------------------------------
    fig_waterfall = Figure(figsize=(8.3, 2.75), dpi=100, linewidth=50)
    ax_waterfall = fig_waterfall.add_subplot(1,1,1)
    fig_waterfall.subplots_adjust(left=.06)
    ax_waterfall.set_ylim(0, numpages + 1)
    ax_waterfall.set_xlim(0, 650)
    #ax_waterfall.set_xlabel('Frequency')
    ax_waterfall.set_ylabel('Trials')
    time_range = np.arange(0, 650, 2)
    fig_waterfall.subplots_adjust(bottom=0.15)#, top=.92)
    ax_waterfall.set_xticklabels([0, 10, 20, 30, 40, 50, 60])
    yvalues = np.zeros(4)
    y_position = 1
    max_val = np.log(np.max(powers))
    min_val = -1
    cmap = plt.get_cmap('jet')
    norm = plt.Normalize(vmin=min_val, vmax=max_val)
    for i in range(numpages):
        y_position = i + 1
        yvalues[0:4] = y_position
        epoch = powers[i]
        data_range = np.arange(0, 650, 2)
        sigs = epoch[data_range]
        #print('EPOCH: ', sigs)
        #print('Length: ', len(epoch))
        for j in range(len(time_range)-1):
            ax_waterfall.plot(time_range[j:j+2], yvalues[0:2], color=cmap(norm(np.log(sigs[j]))), linewidth= (146/numpages)-.6)
    canvas = FigureCanvasTkAgg(fig_waterfall, master=CV)
    canvas.get_tk_widget().place(x=1043, y=472)
    ax_waterfall.set_title('Log FFT Waterfall', pad=1)
#IFFT--------------------------------------------------------------------------------------------------------------------------------------------------------------------
    ifft_epochs = []
    for fft in ffts:
        i_fft_e = np.fft.ifft(fft)
        #print('length: ', len(i_fft_e))
        #i_fft_e = np.real(i_fft_e)
        #print('IFFT: ', i_fft_e)
        #print('lenght: ', len(i_fft_e))
        #i_fft_e[0:3] = 0
        ifft_epochs.append(i_fft_e)

    i_fft = np.fft.ifft(avg_amp_sc)
    i_fft[0:6] = 0
    i_fft[len(i_fft)-4:] = 0
    template = i_fft[2300:2470] #95:275
    i_fft = np.roll(i_fft, len(i_fft)//2 - np.argmax(np.real(i_fft)))
    #template = i_fft[1110:1410]
    print('LENGTH: ', len(i_fft))
    fig_ifft = Figure(figsize=(4, 1), dpi=100) #4.1
    ax_ifft = fig_ifft.add_subplot(111)
    #fig_ifft.subplots_adjust(left=.25)
    x = np.arange(0, 2560, 512)
    ax_ifft.set_xticks(x, x)
    #ax_ifft.set_xlim(0, 190)
    ax_ifft.set_xticklabels([])
    #i_fft[0:3] = 0
    ax_ifft.plot(i_fft, color="red", linewidth=1.3)
    #ax_ifft.plot(ifft_epochs[1], color='blue', linewidth=.5)
    #y_bound = ax_ifft.get_ylim()
    max_ = max(i_fft[0:6])
    min_ = min(i_fft)
    ax_ifft.set_xlim(640, 2560-640)
    #ax_ifft.set_ylim(-5, 50)
    canvas_ifft = FigureCanvasTkAgg(fig_ifft, master=CV)
    canvas_ifft.draw()
    canvas_ifft.get_tk_widget().place(x=215, y=220) #647
    ifft_lab = tk.Label(CV, text='Signature', font=('Helvetica', 14), bg='white')
    ifft_lab.place(x = 380, y = 203)
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------=
    #template = i_fft[50:200]
    fig_temp = Figure(figsize=(9,1.2), dpi=100)
    ax_temp = fig_temp.add_subplot(111)
    fig_temp.subplots_adjust(bottom=.05)
    #ax_temp.plot(template, linewidth=1, color='blue')
    epoch_correlations = []
    threshold = []
    for i in range(numpages):
        epoch_range = np.arange(2560*(i-1), 2560*i, 1)
        sig_s =myvisualsigs[idx-1, epoch_range]
        window = len(template)
        correlation = []
        for i in range(len(sig_s) - window+1):
            segment = sig_s[i:i + window]
            corr = np.correlate(segment, template, mode='valid')
            correlation.append(corr[0])
        #correlation = np.abs(correlation)
        correlation1 = np.where(np.abs(correlation) < .65*max(correlation), 0, correlation)
        epoch_correlations.append(correlation)
        threshold.append(correlation1)

    ax_temp.plot(epoch_correlations[0], linewidth=1, color='blue')
    ax_temp.plot(threshold[0], linewidth=1, color='red' )
    y_lim = ax_temp.get_ylim()
    print('y_lim: ', y_lim)
    for i in range(len(threshold[0])-1):
        thresh = threshold[0]
        if thresh[i] != 0 and all(thresh[i - j] == 0 for j in range(1, 35)):
            ax_temp.scatter(i, y_lim[0], color='red', s=20)
    ax_temp.set_xlim(0, 2560)
    canvas_temp = FigureCanvasTkAgg(fig_temp, master=CV)
    canvas_temp.draw()
    canvas_temp.get_tk_widget().place(x=980, y=110)
#POINT PROCESS SPECTRUM--------------------------------------------------------------------------------------------------------------------------------------------------
    # Replaces the former Cepstrum panel.
    #
    # The template-correlation strip above detects "signature events": samples
    # where the thresholded correlation rises after a quiet gap -- the red dots
    # drawn along the bottom of that strip. Taken as a time series over the
    # whole recording those event times form a POINT PROCESS, and its FFT says
    # whether the signature RECURS rhythmically or arrives at random.
    #
    # NOTE this is the rhythm of the RECURRENCE, not the component's own
    # carrier frequency: a 10 Hz alpha component can throw its signature every
    # ~820 ms, i.e. a ~1.2 Hz point-process rhythm riding on a 10 Hz waveform.
    # The reported interval is the mean inter-event interval +/- 1 SD.
    PP_FS = 256.0           # sample rate of the correlation series
    PP_REFRACTORY = 35      # samples; same refractory as the red-dot rule
    PP_EPOCH = 2560         # samples per epoch (10 s)
    PP_FMAX = 8.0           # Hz; 256/35 = 7.3 Hz is the hard detection ceiling
    PP_SMOOTH_HZ = 0.05     # Daniell smoothing width
    PP_FMIN_PEAK = 0.2      # Hz; ignore below this when reporting the peak
    PP_NSUR = 200           # surrogate trains used to calibrate "rhythmic"
    PP_ALPHA = 0.01         # false-positive rate for the WHOLE study, not per
                            # component: with n components a per-component 1%
                            # would fire on ~n% of studies.
    PP_SEED = 0             # pinned: the verdict must reproduce run to run
    PP_BIN = 4              # decimate before the FFT; < PP_REFRACTORY

    pp_total = numpages * PP_EPOCH
    event_train = np.zeros(pp_total)
    pp_live = np.zeros(pp_total, dtype=bool)
    pp_events_by_page = []
    for pp_page in range(numpages):
        pp_thr = threshold[pp_page]
        # The correlation is 2560-len(template)+1 samples, so the tail of each
        # epoch is a DEAD ZONE where no event could have been detected. Track it
        # -- subtracting a rate there would manufacture a 0.1 Hz comb.
        pp_live[pp_page * PP_EPOCH: pp_page * PP_EPOCH + len(pp_thr)] = True
        # An event is a nonzero sample whose previous nonzero sample was at
        # least PP_REFRACTORY back. Same test the strip uses for its red dots
        # ("nonzero now, previous 34 all zero") but without the negative-index
        # wraparound the strip version has at the epoch start.
        pp_hits = []
        pp_last_nz = -PP_REFRACTORY
        for pp_i in np.flatnonzero(pp_thr):
            if pp_i - pp_last_nz >= PP_REFRACTORY:
                pp_hits.append(int(pp_i))
                event_train[pp_page * PP_EPOCH + pp_i] = 1.0
            pp_last_nz = pp_i
        pp_events_by_page.append(pp_hits)
    pp_n_events = int(event_train.sum())
    pp_nlive = int(pp_live.sum())
    pp_live_idx = np.flatnonzero(pp_live)

    # Inter-event intervals, pooled WITHIN epochs only: a gap spanning an epoch
    # boundary would be padded by that epoch's dead zone and read too long.
    pp_gaps = [np.diff(h) for h in pp_events_by_page if len(h) > 1]
    pp_iei_ms = (np.concatenate(pp_gaps) / PP_FS * 1000.0) if pp_gaps else np.array([])

    fig_pps = Figure(figsize=(4, 1), dpi=100)
    ax_pps = fig_pps.add_subplot(111)
    fig_pps.subplots_adjust(left=0.10, right=0.99, bottom=0.28, top=0.96)

    # Decimate before transforming. Record length is unchanged, so the 0-8 Hz
    # band keeps its full resolution; only 32-128 Hz, which is never drawn, is
    # dropped. PP_REFRACTORY > PP_BIN guarantees one event per bin at most.
    pp_nb = pp_total // PP_BIN
    pp_live_frac = pp_live[:pp_nb * PP_BIN].reshape(pp_nb, PP_BIN).mean(axis=1)
    pp_nlive_b = pp_live_frac.sum()
    pp_freqs = np.fft.rfftfreq(pp_nb, d=PP_BIN / PP_FS)
    pp_band = pp_freqs <= PP_FMAX
    pp_search = pp_band & (pp_freqs >= PP_FMIN_PEAK)
    pp_k = max(1, int(round(PP_SMOOTH_HZ / (pp_freqs[1] - pp_freqs[0]))))

    if pp_n_events >= 2 and pp_nlive_b > pp_n_events:
        pp_spec = pp_spectrum(event_train, pp_live_frac, pp_nlive_b,
                              pp_nb, PP_BIN, pp_k)
        ax_pps.plot(pp_freqs[pp_band], pp_spec[pp_band], linewidth=1.1, color='red')
        ax_pps.axhline(1.0, color='black', linestyle='--', linewidth=0.8)
        pp_top = float(np.max(pp_spec[pp_band]))
        pp_pk = int(np.argmax(np.where(pp_search, pp_spec, -np.inf)))

        # RHYTHMIC or random: is the tallest peak bigger than the tallest peak a
        # refractory-matched RANDOM train of the same size produces? PP_PCT of
        # surrogates fall below the threshold, so the false-positive rate is
        # (100 - PP_PCT) percent. Seeded, so the verdict reproduces run to run.
        pp_rng = np.random.default_rng(PP_SEED)
        pp_null = []
        for _ in range(PP_NSUR):
            pp_sur = pp_surrogate(pp_n_events, PP_REFRACTORY, pp_live_idx,
                                  pp_total, pp_rng)
            if pp_sur is None:
                break
            pp_ns = pp_spectrum(pp_sur, pp_live_frac, pp_nlive_b,
                                pp_nb, PP_BIN, pp_k)
            pp_null.append(float(np.max(np.where(pp_search, pp_ns, -np.inf))))
        if len(pp_null) > 2:
            # The threshold must be the alpha/n quantile of the surrogate max,
            # which sits beyond what PP_NSUR draws can resolve directly. The
            # maximum over many bins is asymptotically Gumbel, so fit one by
            # moments and read the quantile off it. Checked against 2000 true
            # surrogates: the fit from 200 is mildly conservative.
            pp_ms = np.array(pp_null)
            pp_sd = float(pp_ms.std(ddof=1))
            if pp_sd > 0:
                pp_beta = pp_sd * math.sqrt(6.0) / math.pi
                pp_mu = float(pp_ms.mean()) - pp_beta * 0.5772156649
                pp_q = 1.0 - PP_ALPHA / float(max(1, n))
                pp_thresh = pp_mu - pp_beta * math.log(-math.log(pp_q))
            else:
                pp_thresh = float(pp_ms.max())
            pp_is_rhythmic = pp_spec[pp_pk] > pp_thresh
            pp_verdict = 'RHYTHMIC' if pp_is_rhythmic else 'random'
            pp_vcolor = 'red' if pp_is_rhythmic else 'gray'
        else:
            pp_verdict, pp_vcolor = '', 'gray'

        pp_box = dict(facecolor='white', edgecolor='none', alpha=0.75, pad=0.8)
        if pp_verdict:
            ax_pps.text(0.015, 0.96, pp_verdict, transform=ax_pps.transAxes,
                        ha='left', va='top', fontsize=8, fontweight='bold',
                        color=pp_vcolor, bbox=pp_box)
        if pp_iei_ms.size:
            # The RECURRENCE interval. NOT the component's own carrier period --
            # a 10 Hz component recurring every 820 ms reads "every 820 ms" here
            # and "10 Hz" in the FFT panel.
            ax_pps.text(0.015, 0.52,
                        'every %.0f +/- %.0f ms' % (pp_iei_ms.mean(), pp_iei_ms.std()),
                        transform=ax_pps.transAxes, ha='left', va='top',
                        fontsize=6.5, color='black', bbox=pp_box)
        ax_pps.text(0.985, 0.96,
                    'n=%d   peak %.2f Hz  x%.1f'
                    % (pp_n_events, pp_freqs[pp_pk], pp_spec[pp_pk]),
                    transform=ax_pps.transAxes, ha='right', va='top',
                    fontsize=6, color='black', bbox=pp_box)
        ax_pps.set_ylim(0, max(2.0, 1.15 * pp_top))
    else:
        ax_pps.text(0.5, 0.5, 'too few signature events (n=%d)' % pp_n_events,
                    transform=ax_pps.transAxes, ha='center', va='center',
                    fontsize=7, color='gray')
        ax_pps.set_ylim(0, 2.0)

    ax_pps.set_xlim(0, PP_FMAX)
    ax_pps.set_xticks([0, 2, 4, 6, 8])
    ax_pps.set_xlabel('Recurrence rate (Hz)', fontsize=6, labelpad=0)
    ax_pps.tick_params(labelsize=6, pad=1)
    canvas_pps = FigureCanvasTkAgg(fig_pps, master=CV)
    canvas_pps.draw()
    canvas_pps.get_tk_widget().place(x=215, y=397)
    pps_lab = tk.Label(CV, text='Periodicity', font=('Helvetica', 14), bg='white')
    pps_lab.place(x = 373, y = 370)   # centred on the 215..615 panel;
                                      # clear of the figure top at y=397
# COMPONENT AMPLITUDE GRAPH----------------------------------------------------------------------------------------------------------------------------------------------------
    fig = Figure(figsize=(8, 3), dpi=100)
    ax = fig.add_subplot(111)   
    #fig.subplots_adjust(left=.09, right=1)
    bar_heights = (ica_mixing[:, idx-1])
    x_values = np.arange(n)
    
    # Check if all values are positive or all values are negative
    all_positive = all(value >= 0 for value in bar_heights)
    all_negative = all(value < 0 for value in bar_heights)
    
    if all_positive:
        cmap = 'Reds'  # Colormap for all positive values
    elif all_negative:
        cmap = 'Blues_r'  # Colormap for all negative values
    else:
        cmap = 'bwr'  # Colormap for mixed positive and negative values

    norm = mcolors.Normalize(vmin=np.min(bar_heights), vmax=np.max(bar_heights))

    ax.bar(x_values, bar_heights, color=plt.cm.get_cmap(cmap)(norm(bar_heights)), edgecolor='black')
    ax.set_xticks(range(len(channel_labels_short)))
    ax.set_xticklabels(channel_labels_short)
    
    ax.set_title('Individual Component Mixing Matrix')
    canvas = FigureCanvasTkAgg(fig, master=CV)
    canvas.draw()
    canvas.get_tk_widget().place(x=210, y=560)
    
    rms_lab = tk.Label(CV, text=str(round(rms_perc, 0))+'%', font=('Helvetica', 20, 'bold'), bg='white')
    rms_lab.place(x=365, y=550)

    fft_lab = tk.Label(CV, text="Flyover Disabled", font='Helvetica 14', fg='red', bg='white')
    fft_lab.place(x=1640, y=880)

    
    
    
    return CV, source_point, location_matrix, max_value, max_index, reshaped_list, voxel_csd, peak, round(rms_perc, 1)
    
# OUT OF ComponentViewer FUNCTION ----------------------------------------------------------------------------------------------------------------------------------------------

def dummy_brain(source_point, location_matrix, max_value, max_index, reshaped_list, voxel_csd, sceenshot_filename, selstring):
    # Convert voxel coordinates to numeric values--------------------------------------------------------------------------------------------------------------------------------
    voxel_coordinates = np.array(location_matrix[:, 0:3], dtype=float)
    #print(voxel_coordinates)
    
    #ACQUIRE SOURCE POINT--------------------------------------------------------------------------------------------------------------------------------------------------------
   
    voxel_coords = source_point[:3]
    # Convert the coordinates to float
    voxel_coords = [float(coord) for coord in voxel_coords]
    
    print('SOURCE POINT COORDS', voxel_coords)
    reshape_val = reshaped_list[max_index, :]
    print('CORRESPONDING ELECTRICAL SIGNAL: ', reshape_val)
    # Calculate the dipole orientation as the normalized electric field vector
    dipole_orientation = reshape_val / np.linalg.norm(reshape_val)
    print('DIPOLE ORIENTATION: ', dipole_orientation)
    print('AMPLITUDE: ', max_value)
    new_amp = max_value * 1e-9
    print('NEW AMPLITUDE: ', new_amp)

    colormap = 'jet'  # You can choose any other colormap as per your preference
    voxel_csd = np.array(voxel_csd)
    csd_min, csd_max = voxel_csd.min(), voxel_csd.max()
    csd_normalized = (voxel_csd - csd_min) / (csd_max - csd_min)  # Normalize CSD values between 0 and 1
    opacity = 1
    
    
    # Create the points and their associated opacity values
    points = voxel_coordinates
    opacity_values = opacity * csd_normalized

    # Create a PyVista dataset for the points
    point_cloud = pv.PolyData(points)
    point_cloud['opacity'] = opacity_values

    # Plot the points with variable opacity using PyVista==============================================================================================================================
    #app = QApplication(sys.argv)
    #window = QMainWindow()
    #widget = QWidget()
    #layout = QHBoxLayout(widget)

    # Create a pyvistaqt.BackgroundPlotter for each view
    pl = pv.Plotter(shape=(3, 3), off_screen=True)
    #pl_y = pv.Plotter()
    #pl_z = pv.Plotter()
    coord = np.array(voxel_coords)
    direction_array = np.array(reshape_val)
    ori = direction_array / (max_value / 35)
# Add the same point cloud to all 6 views
    cloud = pv.PolyData(point_cloud)
    pl.subplot(1, 0)
    new_coords = [coord[0], coord[1], 70]
    pl.add_mesh(cloud, scalars='opacity', cmap=colormap, render_points_as_spheres=False, point_size=16)
    pl.add_points(points=coord, point_size=16, color='white', render_points_as_spheres=True)
    pl.add_arrows(cent=np.array([new_coords]), direction=np.array([ori]), color='white')
    pl.add_text(text=('Source Region: ' + '\n' + str(source_point[3:]) + '\n' + 'Dorsal (Superior)'), position='upper_right', color='white', shadow=False, font_size=10)
    pl.add_text(text='L', position='left', font_size=16, color='white')
    pl.add_text(text='R', position='right', font_size=16, color='white')
    pl.view_xy()
    
    pl.subplot(1, 1)
    new_coords = [coord[0], -100, coord[2]]
    pl.add_mesh(cloud, scalars='opacity', cmap=colormap, render_points_as_spheres=False, point_size=16)
    pl.add_points(points=coord, point_size=16, color='white', render_points_as_spheres=True)
    pl.add_arrows(cent=np.array([new_coords]), direction=np.array([ori]), color='white')
    pl.add_text(text=('Source Region: ' + '\n' + str(source_point[3:]) + '\n' + 'Posterior (Caudal)'), position='upper_right', color='white', shadow=False, font_size=10)
    pl.add_text(text='L', position='left', font_size=16, color='white')
    pl.add_text(text='R', position='right', font_size=16, color='white')
    pl.view_xz()
    
    pl.subplot(1, 2)
    new_coords = [65, coord[1], coord[2]]
    pl.add_mesh(cloud, scalars='opacity', cmap=colormap, render_points_as_spheres=False, point_size=16)
    pl.add_points(points=coord, point_size=16, color='white', render_points_as_spheres=True)
    pl.add_arrows(cent=np.array([new_coords]), direction=np.array([ori]), color='white')
    pl.add_text(text=('Source Region: ' + '\n' + str(source_point[3:]) + '\n' + 'Lateral (Right)'), position='upper_right', color='white', shadow=False, font_size=10)
    pl.add_text(text='B', position='left', font_size=16, color='white')
    pl.add_text(text='F', position='right', font_size=16, color='white')
    pl.view_yz()

    pl.subplot(2, 0)
    new_coords = [coord[0], coord[1], -45]
    pl.add_mesh(cloud, scalars='opacity', cmap=colormap, render_points_as_spheres=False, point_size=16)
    pl.add_points(points=coord, point_size=16, color='white', render_points_as_spheres=True)
    pl.add_arrows(cent=np.array([new_coords]), direction=np.array([ori]), color='white')
    pl.add_text(text=('Source Region: ' + '\n' + str(source_point[3:]) + '\n' + 'Ventral (Inferior)'), position='upper_right', color='white', shadow=False, font_size=10)
    pl.add_text(text='L', position='right', font_size=16, color='white')
    pl.add_text(text='R', position='left', font_size=16, color='white')
    pl.view_xy(negative=True)

    pl.subplot(2, 1)
    new_coords = [coord[0], 65, coord[2]]
    pl.add_mesh(cloud, scalars='opacity', cmap=colormap, render_points_as_spheres=False, point_size=16)
    pl.add_points(points=coord, point_size=16, color='white', render_points_as_spheres=True)
    pl.add_arrows(cent=np.array([new_coords]), direction=np.array([ori]), color='white')
    pl.add_text(text=('Source Region: ' + '\n' + str(source_point[3:]) + '\n' + 'Anterior (Rostral)'), position='upper_right', color='white', shadow=False, font_size=10)
    pl.add_text(text='L', position='right', font_size=16, color='white')
    pl.add_text(text='R', position='left', font_size=16, color='white')
    pl.view_xz(negative=True)

    pl.subplot(2, 2)
    new_coords = [-65, coord[1], coord[2]]
    pl.add_mesh(cloud, scalars='opacity', cmap=colormap, render_points_as_spheres=False, point_size=16)
    pl.add_points(points=coord, point_size=16, color='white', render_points_as_spheres=True)
    pl.add_arrows(cent=np.array([new_coords]), direction=np.array([ori]), color='white')
    pl.add_text(text=('Source Region: ' + '\n' + str(source_point[3:]) + '\n' + 'Lateral (Left)'), position='upper_right', color='white', shadow=False, font_size=10)
    pl.add_text(text='F', position='left', font_size=16, color='white')
    pl.add_text(text='B', position='right', font_size=16, color='white')
    pl.view_yz(negative=True)

#   HERE ARE THE THREE SLICE VIEWS
    xs = voxel_coordinates[:, 0]
    ys = voxel_coordinates[:, 1]
    zs = voxel_coordinates[:, 2]
    
    x_slice_points = voxel_coordinates[np.isclose(xs, voxel_coords[0])]
    y_slice_points = voxel_coordinates[np.isclose(ys, voxel_coords[1])]
    z_slice_points = voxel_coordinates[np.isclose(zs, voxel_coords[2])]

    cloudx = pv.PolyData(x_slice_points)
    pl.subplot(0, 2)
    #new_coords = [coord[0], coord[1], 70]
    pl.add_mesh(cloudx, scalars=voxel_csd[np.isclose(xs, voxel_coords[0])], cmap=colormap, render_points_as_spheres=False, point_size=16)
    pl.add_points(points=coord, point_size=16, color='white', render_points_as_spheres=True)
    pl.add_arrows(cent=np.array([coord]), direction=np.array([ori]), color='white')
    pl.add_text(text=('Source Region: ' + '\n' + str(source_point[3:]) + '\n' + 'X Slice'), position='upper_right', color='white', shadow=False, font_size=10)
    pl.add_text(text='B', position='left', font_size=16, color='white')
    pl.add_text(text='F', position='right', font_size=16, color='white')
    pl.view_yz()
    
    cloudy = pv.PolyData(y_slice_points)
    pl.subplot(0, 1)
    #new_coords = [coord[0], coord[1], 70]
    pl.add_mesh(cloudy, scalars=voxel_csd[np.isclose(ys, voxel_coords[1])], cmap=colormap, render_points_as_spheres=False, point_size=16)
    pl.add_points(points=coord, point_size=16, color='white', render_points_as_spheres=True)
    pl.add_arrows(cent=np.array([coord]), direction=np.array([ori]), color='white')
    pl.add_text(text=('Source Region: ' + '\n' + str(source_point[3:]) + '\n' + 'Y Slice'), position='upper_right', color='white', shadow=False, font_size=10)
    pl.add_text(text='L', position='left', font_size=16, color='white')
    pl.add_text(text='R', position='right', font_size=16, color='white')
    pl.view_xz()
    
    cloudz = pv.PolyData(z_slice_points)
    pl.subplot(0, 0)
    #new_coords = [coord[0], coord[1], 70]
    pl.add_mesh(cloudz, scalars=voxel_csd[np.isclose(zs, voxel_coords[2])], cmap=colormap, render_points_as_spheres=False, point_size=16)
    pl.add_points(points=coord, point_size=16, color='white', render_points_as_spheres=True)
    pl.add_arrows(cent=np.array([coord]), direction=np.array([ori]), color='white')
    pl.add_text(text=('Source Region: ' + '\n' + str(source_point[3:]) + '\n' + 'Z SLice'), position='upper_right', color='white', shadow=False, font_size=10)
    pl.add_text(text='L', position='left', font_size=16, color='white')
    pl.add_text(text='R', position='right', font_size=16, color='white')
    pl.view_xy()

# Add the render windows of the plotters to the layout
    #widget.setLayout(layout)
    #window.setCentralWidget(widget)
    #window.showMaximized()
    #pl.show(full_screen=True)
# Set the layout to the main window and show it
    if selstring[12] == 1:
        screenshot = pl.screenshot()
        pl.close()
    #screenshot_array = np.array(screenshot.GetPointData().GetScalars()).reshape(screenshot.GetDimensions()[1], screenshot.GetDimensions()[0], -1)

# Convert to a PIL image
        pil_image = img.fromarray(screenshot)

        pil_image.save(sceenshot_filename)
# Return the screenshot as a QImage
    print('returning')
    return str(source_point[3:])