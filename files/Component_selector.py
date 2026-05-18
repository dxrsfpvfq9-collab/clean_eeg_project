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
from scipy.signal import find_peaks
import matplotlib.patches as patches
from matplotlib.colors import Normalize
from process.Source_Localization import source_localization
import matplotlib.colors as mcolors
import math
import csv
import os


#from Montage_List import icabutton_callback
#from ttkthemes import ThemedTk

# BEGINNING OF COMPONENT VIEWER -----------------------------------------------------------------------------------------------------------------------------------------------------------------
def ComponentViewer(root, update_gui, length, numsamples, ica_mixing, idx, selected_channel_list, icabutton, selected_channel_reasons, channel_labels_short, icatext, myvisualsigs, n, y_increment):
    global flyover_enabled
    flyover_enabled = True
    # FUNCTIONS------------------------------------------------------------------------------------------------------------------------------------------------------
    def lock_flyover(event):
        global flyover_enabled, y_epoch
        flyover_enabled = not flyover_enabled
        if flyover_enabled:
            fft_lab.config(text="Flyover Disabled", font='Helvetica 15', fg="red", bg="white")
            print('FLYOVER DISABLED')
        else:
            fft_lab.config(text="Flyover Enabled", font='Helvetica 15', fg="green", bg="white")
            print('FLYOVER ENABLED')
        if event.inaxes == ax_ribbon or ax_waterfall:
            y_epoch = np.floor(event.ydata)
            y_epoch = int(y_epoch)
    
    def on_fft_move(event):
        global flyover_enabled, y_epoch
        if not flyover_enabled:
            if event.inaxes == ax_fft:
                x_coord = event.xdata
                line1_y = np.interp(x_coord, np.arange(len(avg_amp_sc)), avg_amp_sc)
                line2_y = np.interp(x_coord, np.arange(len(epoch_vals[y_epoch-1])), epoch_vals[y_epoch-1])
                point1.set_offsets([(x_coord, line1_y)])
                point2.set_offsets([(x_coord, line2_y)])
                vline.set_xdata(x_coord)
                coord_text.set_text(f'X: {(x_coord/10):.2f}\nAverage FFT: {line1_y:.2f}\nEpoch FFT: {line2_y:.2f}')
                canvas_fft.draw_idle()
            
            if event.inaxes == ax_ifft:
                x_coord = event.xdata
                line1_y = np.interp(x_coord, np.arange(len(i_fft)), i_fft)
                line2_y = np.interp(x_coord, np.arange(len(ifft_epochs[y_epoch])), ifft_epochs[y_epoch])
                point1_i.set_offsets([(x_coord, line1_y)])
                point2_i.set_offsets([(x_coord, line2_y)])
                vline_i.set_xdata(x_coord)
                coord_text_i.set_text(f'X: {(x_coord/256):.2f} Average iFFT: {line1_y:.2f}\nEpoch iFFT: {line2_y:.2f}')
                canvas_ifft.draw_idle()
            '''
            if event.inaxes == ax_ceps:
                x_coord = event.xdata
                line1_y = np.interp(x_coord, np.arange(len(avg_ceps)), avg_ceps)
                line2_y = np.interp(x_coord, np.arange(len(ifft_epochs[y_epoch-1])), ifft_epochs[y_epoch-1])
                point1_c.set_offsets([(x_coord, line1_y)])
                point2_c.set_offsets([(x_coord, line2_y)])
                vline_c.set_xdata(x_coord)
                coord_text_c.set_text(f'X: {(x_coord/10):.2f} Average Ceps: {line1_y:.2f}\nEpoch Ceps: {line2_y:.2f}')
                canvas_ceps.draw_idle()
            '''    
    def on_ribbon_select(event):
        global flyover_enabled
        if flyover_enabled:
            if event.inaxes == ax_ribbon or ax_waterfall:
                y = np.floor(event.ydata)
                y = int(y)
                text.set_text(f'Y = {y:.2f}')
                fig_ribbon.canvas.draw_idle()
                print('y = ', y)
                start_stop = start_stops[y-1]
                start = start_stop[0]
                stop = start_stop[1]
                print('Start, Stop = ', start, stop)
                epoch_lab.config(text='Epoch: ' + str(y), font='Helvetica 15', bg='white')
                int_lab.config(text='Interval: ' + str(int(start/256)) + '-' + str(int(stop/256)), font='Helvetica 12', bg='white')
                for line in ax_ifft.lines:
                    if line.get_color() == 'blue':
                        line.remove()
                for line in ax_fft.lines:
                    if line.get_color() == 'blue':
                        line.remove()
                    if line.get_color() == 'orange':
                        line.remove()
                ax_temp.clear()               
                #for line in ax_ceps.lines:
                #    if line.get_color() == 'blue':
                #        line.remove()
                #for line in ax_wavelet.lines:
                #    if line.get_color() == 'blue':
                #        line.remove()
                #for line in ax_pul.lines:
                #    if line.get_color() == 'blue':
                #        line.remove()
                #for line in ax_re.lines:
                #    if line.get_color() == 'blue':
                #        line.remove()
                y_max_e = np.max(epoch_vals[y-1])
                if y_max_e > y_max:
                    ax_fft.set_ylim(0, y_max_e +50)
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
                ax_wave.set_xlim(start, stop)
                ax_temp.set_xlim(0, 2560)
                #epoch_cep = np.roll(epoch_ceps[y-1], len(avg_ceps)//2 - max_lev)
                #ax_ceps.plot(epoch_ceps[y-1], linewidth=1.1, color='blue')
                #ax_re.plot(new_waves[y-1], linewidth=1, color='blue')
                ax_temp.plot(epoch_correlations[y-1], linewidth=1, color='blue')
                ax_temp.plot(threshold[y-1], linewidth=1, color='red')
                #y_lim = ax_temp.get_ylim
                for i in range(len(threshold[y-1])-1):
                    thresh = threshold[y-1]
                    if thresh[i] != 0 and all(thresh[i - j] == 0 for j in range(1, 35)):
                        ax_temp.scatter(i, y_lim[0], color='red', s=20)
                ax_fft.plot(epoch_vals[y-1], linewidth=2, color='blue')
                #ax_pul.plot(time_axis2, pulses[y-1], linewidth=.9, color='blue')
                #ax_ifft.plot(ifft_epochs[y], linewidth=.5, color='blue')
                #ax_wavelet.plot(time_axis, norm_wavelets[y-1], linewidth=.5, color='blue')
                #ax_fft.plot(phases[y-1], linewidth=2, color='orange')
                #if max(norm_wavelets[y-1]) > max(avg_wavelet):
                #    max_w = max(norm_wavelets[y-1])
                #else:
                #    max_w = max(avg_wavelet)
                #if min(norm_wavelets[y-1]) < min(avg_wavelet):
                #    min_w = min(norm_wavelets[y-1])
                #else:
                #    min_w = min(avg_wavelet)
                
                if max(ifft_epochs[y-1]) > max(i_fft):
                    max_s = max(ifft_epochs[y-1])
                else:
                    max_s = max(i_fft)
                if min(ifft_epochs[y-1]) < min(i_fft):
                    min_s = min(ifft_epochs[y-1])
                else:
                    min_s = min(i_fft)
                #ax_ifft.set_ylim(min_s -2, max_s+2)
                #ax_wavelet.set_ylim(min_w-(max_w-min_w)/6, max_w +(max_w-min_w)/6)
                canvas_wave.draw()
                canvas_fft.draw()
                canvas_ifft.draw()
                canvas_temp.draw()
                #canvas_ceps.draw()
                #canvas_wavelet.draw()
                #canvas_pul.draw()
                #canvas_re.draw()

    def error_gui():
        if len(selected_channel_list) != len(selected_channel_reasons):
            EG = Toplevel()
            EG.title('ERROR!!!')
            style.configure("White.TLabel", background="white")
            EG.geometry("500x300")
            center_window(EG)
            EG.configure(bg='white')
            EGT = Label(EG, text="Please Select A Reason For Removal", style= 'White.TLabel', font=('Helvetica', 20, 'bold'))
            EGT.place(x=5, y=50)

            Error_button = Button(EG, text= "Okay", style="GRAY.TButton", command = EG.destroy)
            Error_button.place(x=180, y=150)
        else:
            update_gui(selected_channel_list, selected_channel_reasons)
            CV.destroy()
            
    
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
                icabutton[idx-1].config(relief='sunken')
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
                icabutton[idx-1].config(relief='raised')
                print("Selected Channel Reasons", selected_channel_reasons)

                #selected_channel_list.sort()
                #icatext.insert(tk.END, "MAX AT: \n")
                #for selchan in selected_channel_list:
                #    icatext.insert(tk.END, selchan, "MAX AT:", channel_labels_short[selected_channel_reasons[selchan]])
                #    icatext.insert(tk.END, "\n")

    def on_listbox_select(event):
        selection = listbox.curselection()
        selection = selection[0]
        selected_reason = listbox.get(selection)
        if selection == 20:
            remove_keep('keep')
        else:    
            reason_lab.config(text='Reason: ' + selected_reason, font='Helvetica 15')
            lab.config(text="Current: Remove", font='Helvetica 15', fg="red", bg="white")
            if len(selected_channel_list) == len(selected_channel_reasons):
                if idx not in selected_channel_list:
                    selected_channel_list.append(idx)
                    selected_channel_reasons.append(selection)
                elif idx in selected_channel_list:
                    selected_channel_reasons[selected_channel_list.index(idx)] = selection
            elif len(selected_channel_list) != len(selected_channel_reasons):
                selected_channel_reasons.append(selection)
        print("reason", selected_channel_reasons)
        print('list', selected_channel_list)

#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    numpages = numsamples//length - 1
    print('Length: ', length)
    start_stops = [(int(j * length), int( (j+1) * length)) for j in np.arange(0, numpages, 1)]
    print('Start Stops: ', start_stops)

    stdmeasv = np.std(myvisualsigs[:])
    myvisualsigs = myvisualsigs * 10.0 / stdmeasv
    # CREATES A NEW WINDOW
    CV = Toplevel(root)
    sw = CV.winfo_screenwidth()
    sh = CV.winfo_screenheight()
    style = ttk.Style()
    CV.title("Component Viewer")
    
    
    sw = CV.winfo_screenwidth()
    sh = CV.winfo_screenheight()
    CV.geometry(f"{sw}x{sh}")
    CV.configure(bg='white')
    WTitle = Label(CV, text=("Component:", idx), font=('Helvetica', 50, 'bold'))
    WTitle.place(x=440, y=20)

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
    #rms_lab = tk.Label(CV, text=str(round(rms_perc, 0))+'%', font=('Helvetica', 14, 'bold'), bg='white')
    #rms_lab.place(x=290, y=500)
    print('RMS Total:', rms_tot)
    print('RMS COMP', rms_comp)
    #---------------------------------------------------------------------------------------------------------------------------------------------------
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

    Cbtn = Button(CV, text= "Close", style="GRAY.TButton", command = error_gui)
    Cbtn.place(x = 640, y = 880, height=75, width=150)

    catagory_box = tk.Canvas(CV, width=200, height=990, bg="#a2a2a2")
    catagory_box.place(x=5, y=0)

    #---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def vector_matrix_multiplication(matrix, vector):
        # Verify dimensions
        print('matrix shape: ', matrix.shape)
        print('vector shape:', vector.shape)
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
    
    

    #vector = ordered_ica_mixing[:, idx-1]
    #print('VECTOR TO BE MULTIPLIED: ', vector)
    #print('VECTOR SHAPE: ', vector.shape)
    #GET MATRIX OUT OF CSV FILE------------------------------------------------------------------------------------------------------------------------------------------------
    with open(file_path) as file:
        reader = csv.reader(file)
        matrix_data = [row[2:21] for row in reader]

    matrix = np.array(matrix_data, dtype=float)
    print('MATRIX SHAPE: ', matrix.shape)
    #print(matrix)
    vector = ordered_ica_mixing[:, idx-1]
    vector = vector[:19]
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
    voxel_coords = location_matrix[:, :3]
    voxel_coordinates = [(int(x), int(y), int(z)) for x, y, z in voxel_coords]
    
    
    
    source_coords = source_point[:3]
    source_coords = np.array(source_coords)
    source_coords = tuple(map(int, source_coords))
    print("SOURCE COORDS: ", source_coords)
    #FIND THE DEPTH-----------------------------------------------------------------------------------------------------------------------------------------------------------
    def det_surface_voxel(voxel_coordinates):
      voxel_array = np.array(voxel_coordinates)
      # Find the highest Z value for each XY pillar
      surface_points = []
      unique_xy = np.unique(voxel_array[:, :2], axis=0)
    
      for x, y in unique_xy:
        # Extract all Z values for the current XY pillar
        z_values = voxel_array[(voxel_array[:, 0] == x) & (voxel_array[:, 1] == y), 2]
        
        # Find the maximum Z value for this pillar
        max_z = np.max(z_values)
        
        # Add the surface point for this XY pillar to the result
        surface_points.append((x, y, max_z))

      return surface_points
    

    surface_points = det_surface_voxel(voxel_coordinates)
    print('LENGTH IS: ', len(surface_points))
    source_coords = np.array(source_coords)
    surface_points = np.array(surface_points)
    distances = np.linalg.norm(surface_points - source_coords, axis=1)
    nearest_point_index = np.argmin(distances)
    depth = distances[nearest_point_index]
    nearest_vox = surface_points[nearest_point_index]
    nearest_vox = tuple(map(int, nearest_vox))
    print('NEAREST VOXEL IS: ', nearest_vox)
    print('DEPTH: ', depth)
    
    source_point = location_matrix[max_index, :]
    print('SOURCE POINT: ', source_point) 
    loc_1 = source_point[3]
    loc_2 = source_point[4]
    loc_3 = source_point[5]
    #-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    Bbtn = Button(CV, text= "Brain Viewer", style="GRAY.TButton", command = lambda: source_localization(source_point, location_matrix, max_value, max_index, reshaped_list, voxel_csd, depth, nearest_vox, source_coords, ordered_ica_mixing, matrix))
    Bbtn.place(x = 245, y = 20, height=90, width=170)
    #---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    
    cat_list = ['MAX AT: Fp1', 'MAX AT: Fp2', 'MAX AT: F7', 'MAX AT: F3', 'MAX AT: Fz', 'MAX AT: F4', 'MAX AT: F8', 'MAX AT: T3', 'MAX AT: C3', 'MAX AT: Cz', 'MAX AT: C4', 'MAX AT: T4', 'MAX AT: T5', 'MAX AT: P3', 'MAX AT: Pz', 'MAX AT: P4', 'MAX AT: T6', 'MAX AT: O1', 'MAX AT: O2', 'MAX AT: A2', 'User Override']
    #EOG-Blink, 'EOG-Roll
    if int(source_point[0]) < 0:
        hemi = 'Left Hemisphere'
    elif int(source_point[0]) >0:
        hemi = 'Right Hemisphere'
    else:
        hemi = 'Midline'
    region = tk.Label(CV, text= loc_1 + "\n" + loc_2 + "\n" + loc_3 + "\n" + hemi, font='Helvetica 13', bg='white')
    region.place(x = 259, y = 110)


    font_size = 14
    listbox_font = font.Font(size=font_size, family='Helvetica')

    listbox = Listbox(CV, font=listbox_font, justify="center")
    for cat_list in cat_list:
        listbox.insert(tk.END, cat_list)
    listbox.place(x=40, y = 60, height=800, width=125)
    listbox.bind("<<ListboxSelect>>", lambda event: on_listbox_select(event))    

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
    fig_ribbon.canvas.mpl_connect('motion_notify_event', on_ribbon_select)
    fig_ribbon.canvas.mpl_connect('button_press_event', lock_flyover)
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
    eeg_data = ica_mixing[ :19, idx-1]
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

    print(zi.shape)

     
    fig = Figure(figsize=(3.7, 3.7), frameon=False)
    ax = fig.add_subplot(111)
    fig.subplots_adjust(right=1.01, left=.02)
    # ADD CIRCLE----------------------------------------
    ax.contourf(xi, yi, zi, levels=30, cmap='jet')
    ellipse = patches.Ellipse((0, 0),width=1.64, height=1.02, facecolor='none', edgecolor='black', fill=False, linewidth=3.5)
    ax.add_patch(ellipse)
    
    ax.scatter(locations[:, 0], locations[:, 1], c=eeg_data, cmap='jet', edgecolors='k')
    
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
    
    vmax = np.max(np.abs(eeg_data))/1000
    vmin = -vmax
    norm = Normalize(vmin=vmin, vmax=vmax)
    sm = ScalarMappable(cmap='jet', norm=norm)
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
    for i in range(int(numpages)):
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
    canvas_fft.mpl_connect('motion_notify_event', on_fft_move)
    canvas_fft.get_tk_widget().place(x=1027, y=736)
    
#FFT WATERFALL---------------------------------------------------------------------------------------------------------------------------------------------------------------
    fig_waterfall = Figure(figsize=(8.3, 2.75), dpi=100, linewidth=50)
    ax_waterfall = fig_waterfall.add_subplot(1,1,1)
    fig_waterfall.subplots_adjust(left=.06)
    fig_waterfall.canvas.mpl_connect('motion_notify_event', on_ribbon_select)
    fig_waterfall.canvas.mpl_connect('button_press_event', lock_flyover)
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
    '''
    i_fft = np.fft.ifft(avg_amp_sc)
    print('length: ', len(i_fft))
    i_fft = np.real(i_fft)
    print('IFFT: ', i_fft)
    print('lenght: ', len(i_fft))
    '''
    ifft_epochs = []
    for epoch in epoch_vals: #for fft in ffts:
        i_fft_e = np.fft.ifft(epoch)
        #print('length: ', len(i_fft_e))
        #i_fft_e = np.real(i_fft_e)
        #print('IFFT: ', i_fft_e)
        #print('lenght: ', len(i_fft_e))
        #i_fft_e[0:3] = 0
        ifft_epochs.append(i_fft_e)

    i_fft = sum(ifft_epochs) / len(ifft_epochs)
    #i_fft = np.fft.ifft(avg_amp_sc)
    i_fft[0:6] = 0
    i_fft[len(i_fft)-4:] = 0
    peaks, _ = find_peaks(i_fft[:1280])
    #peaks = [peak + 1280 for peak in peaks]
    print('peals:', peaks)
    peak_heights = i_fft[peaks]
    print('peals:', peak_heights)
    for i in range(0, len(peak_heights)-1):
        if abs(peak_heights[i]) < 0.05 * abs(peak_heights[0]):
            sig_peak = peaks[i]
            break
    print('SIG PEAK: ', sig_peak)
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
    vline_i = ax_ifft.axvline(0, color='black', linestyle='--')
    #POINTS OF INTERSECTION
    point1_i = ax_ifft.scatter([], [], color='red', zorder=5)
    point2_i = ax_ifft.scatter([], [], color='blue', zorder=5)
    #TEXT ANNOTATIOn
    coord_text_i = ax_ifft.text(0.64, 0.34, '', transform=ax_fft.transAxes, va='top')
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
    canvas_ifft.mpl_connect('motion_notify_event', on_fft_move)
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
#CEPSTRUM----------------------------------------------------------------------------------------------------------------------------------------------------------------------
    fig_ceps = Figure(figsize=(4, 1), dpi=100)
    ax_ceps = fig_ceps.add_subplot(111)
    #fig_ceps.subplots_adjust(left=0.073)
    #ax_ceps.set_facecolor('none')
    #ax_ceps.spines['left'].set_visible(False)
    epoch_ceps = []
    for fft in ffts:
        #epoch = epoch[:640]
        log_epoch = np.log(fft)
        ceps = np.fft.ifft(log_epoch)
        #print('Ceps: ', ceps)
        ceps[:1] = 0
        ceps[-1:] = 0
        epoch_ceps.append(ceps)
    
    # Calculate the average cepstrum by dividing the sum by the number of epochs
    avg_ceps = sum(epoch_ceps) / len(epoch_ceps)
    print('LENGTH OF AVG CEPS: ', len(avg_ceps))
    #print(avg_ceps[:640])
    # Calculate the quefrency axis properly centered at 0
    quefrency_axis = np.arange(-len(avg_ceps) // 2, len(avg_ceps) // 2)

    # Find the index of the maximum value and shift the cepstrum accordingly
    max_lev = np.argmax(np.real(avg_ceps))
    
    avg_ceps = np.roll(avg_ceps, len(avg_ceps)//2 - max_lev)
    #print(avg_ceps[1280:1920])
    for i in range(0, len(epoch_ceps)):
        epoch_ceps[i] = np.roll(epoch_ceps[i], len(avg_ceps)//2 - max_lev)
    
    #vline_c = ax_ceps.axvline(0, color='black', linestyle='--')
    #POINTS OF INTERSECTION
    #point1_c = ax_ceps.scatter([], [], color='red', zorder=5)
    #point2_c = ax_ceps.scatter([], [], color='blue', zorder=5)
    #TEXT ANNOTATIOn
    #coord_text_c = ax_ceps.text(0.04, 0.25, '', transform=ax_fft.transAxes, va='top')
    # Plot the average cepstrum with quefrency values
    ax_ceps.plot(avg_ceps, linewidth=1.1, color='red')
    ax_ceps.plot((epoch_ceps[0]), linewidth=1.1, color='blue')

    #ax_ceps.set_ylim(-.5, 2.1)

    ax_ceps.set_xlim(1214, 1354) #1214, 1354
    canvas_ceps = FigureCanvasTkAgg(fig_ceps, master=CV)
    canvas_ceps.draw()
    canvas_ceps.mpl_connect('motion_notify_event', on_fft_move)
    canvas_ceps.get_tk_widget().place(x=215, y=397)
    ceps_lab = tk.Label(CV, text='Cepstrum', font=('Helvetica', 14), bg='white')
    ceps_lab.place(x = 380, y = 381)
    '''
#EXCITATION (WAVELET)_--------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------
    inner_start = len(avg_ceps) // 2 - 15
    inner_end = len(avg_ceps) // 2 + 17
    wavelets = []
    norm_wavelets = []
    pulses = []
    norm_pulses = []
    for ceps in epoch_ceps:
        middle_part = ceps[inner_start:inner_end]
        edges_part = list(ceps[:inner_start]) + list(ceps[inner_end:])
        fft_middle = np.fft.fft(middle_part)
        exp_fft_middle = np.exp(fft_middle)
        ifft_exp_fft_middle = np.fft.ifft(exp_fft_middle)
        
        normalized_wavelet = ifft_exp_fft_middle / np.max(np.abs(ifft_exp_fft_middle))
        
        norm_wavelets.append(normalized_wavelet)
        wavelets.append(ifft_exp_fft_middle)

        fft_edge = np.fft.fft(edges_part)
        exp_fft_edge = np.exp(fft_edge)
        ifft_exp_fft_edge = np.fft.ifft(exp_fft_edge)

        normalized_pulse = ifft_exp_fft_edge / np.max(np.abs(ifft_exp_fft_edge))
        norm_pulses.append(normalized_pulse)
        pulses.append(ifft_exp_fft_edge)

    avg_wavelet = sum(norm_wavelets) / len(norm_wavelets)
    #middle_part = avg_ceps[inner_start:inner_end]
    #edges_part = np.hstack((avg_ceps[:inner_start], avg_ceps[inner_end:]))
    # Perform operations on the middle part
    #print(avg_ceps[inner_start:inner_end])
    time_axis = quefrency_axis[inner_start:inner_end]
    #fft_middle = np.fft.fft(middle_part)
    #exp_fft_middle = np.exp(fft_middle)
    #ifft_exp_fft_middle = np.fft.ifft(exp_fft_middle)
    #print('LENGTH IS: ', len(ifft_exp_fft_middle))
    #print(ifft_exp_fft_middle)
    fig_wavelet = Figure(figsize=(3, 1), dpi=100)
    ax_wavelet = fig_wavelet.add_subplot(111)
    ax_wavelet.plot(time_axis, np.real(avg_wavelet), linewidth=.5, color='red', label='Deconvolved Pulse Trains')
    ax_wavelet.plot(time_axis, np.real(norm_wavelets[0]), linewidth=.5, color='blue', label='Deconvolved Pulse Trains')
    canvas_wavelet = FigureCanvasTkAgg(fig_wavelet, master=CV)
    canvas_wavelet.draw()
    canvas_wavelet.get_tk_widget().place(x=600, y=300)
#--------------------------------------------------------------------------------------------------------------------------------------------
    
    fig_pul = Figure(figsize=(9, 1), dpi=100)
    ax_pul = fig_pul.add_subplot(111)
    print(len(edges_part))
    avg_pulse = sum(pulses) / len(pulses)
    time_axis2 = list(quefrency_axis[:inner_start]) + list(quefrency_axis[inner_end:])
    #ax_pul.plot(quefrency_axis, avg_ceps, linewidth=1.1, color='blue')
    ax_pul.plot(time_axis2, avg_pulse, linewidth=.5, color='red', label='Deconvolved Wavelet')
    ax_pul.plot(time_axis2, pulses[0], linewidth=.5, color='blue')
    #ax_pul.plot(time_axis2, pulses[0], linewidth=1.1, color='blue')
    ax_pul.set_xlim(-1280, 1280)
    ax_pul.set_ylim(-.3, .3)
    canvas_pul = FigureCanvasTkAgg(fig_pul, master=CV)
    canvas_pul.draw()
    canvas_pul.get_tk_widget().place(x=200, y=400)
    '''
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

    #CV.mainloop()
#RECONSTRUCTION-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    '''
    fig_re = Figure(figsize=(9, 1), dpi=100)
    ax_re = fig_re.add_subplot(111)
    new_waves = []
    for i in range(len(wavelets)):
        new_wave = np.convolve(wavelets[i], pulses[i], mode='same')
        new_waves.append(new_wave)

    ax_re.plot(new_waves[0], linewidth=1, color='blue')
    ax_re.set_xlim(-0, 2560)
    canvas_re = FigureCanvasTkAgg(fig_re, master=CV)
    canvas_re.draw()
    canvas_re.get_tk_widget().place(x=200, y=100)
    '''
    CV.mainloop()
# OUT OF ComponentViewer FUNCTION ----------------------------------------------------------------------------------------------------------------------------------------------

def center_window(window):
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

