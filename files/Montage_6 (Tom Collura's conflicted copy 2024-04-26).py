# Montage Function List
import datetime
import pyedflib
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.widgets
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from scipy.signal import find_peaks
from files.create_report_pdf import save_gui_screenshot
from files.dummy_gui import dummy_gui, dummy_brain
from files.file_svc import setup_electrode_names
from files.Component_selector import ComponentViewer
from process.detect_artifact import find_suspect_ica_components, detect_peak
from process.detect_artifact import reason_to_string
import tkinter as tk
from PIL import Image as img
from tkinter import *
import os
import csv
import math
from fpdf import FPDF



def montage_6(outname, selstring, myfilteredsigs, data, numsamples, ica, ica_components, recon_pyedf_file, clean1_pyedf_file, clean2_pyedf_file, img_cascade_file, n, outputdir1, electrode_names, electrode_names_orig, length, myvisualsigs, icabutton, ica_mixing, short_name, channel_labels_short, numcomps, edf_file, selected_channel_list, icatext, icatextobj, icatextl):
      electrode_names, pdf_filename = setup_electrode_names(n, outputdir1, electrode_names, electrode_names_orig, 4)
# CREATES THE COMPONENT SELECTOR----------------------------------------------------------------------------------------------------------------------------------------------
      orig_selected_channel_list, selected_channel_reasons, max_sites, num_above_half, sites_rsi = find_suspect_ica_components(ica_mixing, channel_labels_short, n)
      del selected_channel_reasons, max_sites, num_above_half, sites_rsi
      
      def show_loading_message():
            loading_label = tk.Label(root, text="Loading... Please wait.", font= 'Helvetica 30')
            loading_label.place(x=root.winfo_reqwidth() // 2, y=root.winfo_reqheight() // 2)
            root.update()
            root.after(2000, loading_label.destroy)
      
      root = tk.Tk()

# Get the dimensions of the screen
      screen_width = root.winfo_screenwidth()
      screen_height = root.winfo_screenheight()

# Set the window dimensions to fill the screen
      root.geometry(f"{screen_width}x{screen_height}+0+0")

      root.title('ICA Component Selector')
      frame = tk.Frame(root)
 
      frame.pack(side="left", fill="both", expand=True)

      fig = Figure(figsize=(5,4), dpi=100)
      ax = fig.add_subplot(1,2,2)

      canvas_ica = FigureCanvasTkAgg(fig, master=frame)
      canvas_ica.draw()
      canvas_ica.get_tk_widget().pack(side="top", fill="both", expand=True)

#      fig, ax = plt.subplots(figsize=(8, 8))
      y_min = -1000
      y_max = 1000
      y_increment = (y_max - y_min) / (n+1)
      ax.set_ylim(y_min, y_max)
      ax.set_xlabel("Samples")
      ax.set_yticklabels([])
#      button_frame = tk.Frame(root)
#      button_frame.pack()

# THIS SECTION DRAWS ICA COMPONENTS ACROSS THE TOP OF THE PAGE-----------------------------------------------------------------------------------------------------------------------
      bar_offset = 150
      square_offset = 50
      bar_mult = 5
      time_range = np.arange(0, length, 1)


#  PLOT THE COMPONENTS FOR VIEWING AND SELECTING
      yticksarray = []
      for i in range(n):
#        print(start, stop)
        sigtoshow = 4 * myfilteredsigs[i, :length]
        y_position = y_max - (i+1) * y_increment
        sigtoshow = sigtoshow + y_position
        ax.plot(time_range, sigtoshow, color="Black", linewidth=0.5)
        ax.text(-300, y_position, electrode_names[i][4:])
        ax.text(length+150, y_position, electrode_names[i][4:])
#        ax.text(length+150, y_position, channel_labels_short[i])
        yticksarray.append(y_position)
      ax.set_yticks(yticksarray)
#      ax.tick_params(axis='y', which='both', length=0)

#  DRAW THE BUTTONS ON THE SELECTOR PANEL TO PICK COMPONENTS--------------------------------------------------------------------------------------------------------------------------
      icabutton_frame = tk.Frame(root)
      icabutton_frame.pack(side="top", pady=(10, 0))
      for i in range(n):
          icabuttonstring = "Component: " + str(i+1)
          button = tk.Button(icabutton_frame, text=icabuttonstring, command=lambda idx=i+1: [show_loading_message(), ComponentViewer(root, update_gui, length, numsamples, ica_mixing, idx, selected_channel_list, icabutton, selected_channel_reasons, channel_labels_short, icatext, myfilteredsigs, n, y_increment)]) #icabutton_callback(idx, n, selected_channel_list, icabutton, icatext, icatextobj, icatextl))
#          button = tk.Button(frame, text=icabuttonstring, command=lambda idx=i+1: icabutton_callback(idx,n))
          button.pack(side=TOP, fill=X)
          icabutton[i] = button

      i = i + 1
      button1 = tk.Button(icabutton_frame, text='Done', command= root.destroy)        #lambda idx=i+1: icabutton_callback(idx, n, selected_channel_list, icabutton, icatext, icatextobj, icatextl))
#      button = tk.Button(icabutton_frame, text='Done', command=lambda idx=i+1: icabutton_callback(idx, n))
#      button = tk.Button(frame, text='Done', command=lambda idx=i: icabutton_callback(idx, n))
      icabutton[i] = button
      button1.pack(side=TOP, fill=X)

#      print("icabutton shape:  ", np.shape(icabutton), "   ", len(icabutton))
      
#  CREATE AND SHOW MIXING MATRIX IN A SEPARATE WINDOW----------------------------------------------------------------------------------------------------------------------------
      cmap = plt.cm.bwr 
#      figm = Figure(figsize=(5,4), dpi=100)
      axm = fig.add_subplot(1,2,1)
      im = axm.imshow((ica_mixing), cmap=cmap, interpolation='nearest')
      now = datetime.datetime.now()
      datetime_string = now.strftime('%Y-%m-%d %H:%M:%S')
#  TRUNCATE FILE PATH TO SHOW NAME ONLY IN FUTURE USE "Studies" for BrainAvatar
      tlabel = "BMrICA: " + short_name + " " + datetime_string
      axm.text(0, -2, tlabel, fontsize=10)
      axm.set_yticks(np.arange(n))

#  SHORTEN ELECTRODE NAMES - MAKE THIS A FUNCTION AND SAVE SHORT LABELS TO PASS TO FUNCTIONS----------------------------------------------------------------------
#  WHERE IS THIS USED    WE HAVE CHANNEL_LABELS_SHORT AS WELL
      newnames = []
      for s in electrode_names_orig:
        if s.startswith('EEG'):
          start = s.find('EEG') + 4
          end = s.find('-LE')
          if start >= end:
            newnames.append(s)
          elif end == -1:
            newnames.append(s[start:])
          else:
            newnames.append(s[start:end])
        else:
          end = s.find('-LE')
          if end > 0:
            newnames.append(s[:end])
          else:
            newnames.append(s)

      print("NEWNAMES:  ", newnames)

      axm.set_yticklabels(channel_labels_short)

#      xticks = [(i-1) for i in range(1,n)]
#      axm.set_xticks(xticks)

#  USE NUMBER OF CHANNELS NOT JUST 21 HARDCODED
      xticks = [i-1 for i in range(1,n)]
      axm.set_xticks(xticks)
      string_list = [str(i) for i in range(1,n)]
      axm.set_xticklabels(string_list)

#  ADD A TEXT AREA WHERE THE FINAL SELECTIONS WILL BE WRITTEN FOR PRINTING-----------------------------------------------------------------------------
      icatext = axm.text(0,-1,"Selections: (use buttons)")
      icatextobj = fig.findobj(lambda x: isinstance(x, plt.Text) and x.get_text() == "Selections: (use buttons)")
      print("icatextobj:  ", icatextobj)

#  ADD A LIVE TEXT BOX TO SHOW THE SELECTIONS
      icatext = tk.Text(root, height=20, width=15, font=("Helvetica", 14))
      icatext.pack()
      icatext.insert(1.0, "ICA SELECTED:\n")

#  HERE IS WHERE WE FIND THE LIKELY ARTIFACT COMPONENTS----------------------------------------------------------------------------------------------------
      selected_channel_list, selected_channel_reasons, max_sites, num_above_half, sites_rsi = find_suspect_ica_components(ica_mixing, channel_labels_short, n)
      #orig_selected_channel_list = selected_channel_list
      counter = 0
      for channel in selected_channel_list:
        icatext.insert(icatext.index('end'), '\n' + str(channel) + " " 
          + reason_to_string(selected_channel_reasons[counter], channel_labels_short))
 
        icabutton[channel-1].config(relief='sunken')
        print("PLOT :  ", str(channel), "  ", str(selected_channel_reasons[counter]))
        axm.plot(channel-1, selected_channel_reasons[counter], 'rX', markersize=10, linewidth=2)
        ax.text(length+310, y_position+(y_increment*n)-y_increment*channel, 
          reason_to_string(selected_channel_reasons[counter], channel_labels_short))
        counter += 1

      array_str = ", ".join(str(i) for i in selected_channel_list)
      string1 = "Machine Selected: " + array_str

      icatextobj[0].set_text(string1)

      icaeditfilename = outputdir1 + ".ica.png"
      print("icafile:  ", icaeditfilename)

      plt.show()
#      root.after(5000, root.destroy)
      
      def update_gui(selected_channel_list, selected_channel_reasons):
          counter = 0
          icatext.delete('1.0', tk.END)
          for channel in selected_channel_list:
             icatext.insert(icatext.index('end'), '\n' + str(channel) + " " 
             + reason_to_string(selected_channel_reasons[counter], channel_labels_short))
 
             icabutton[channel-1].config(relief='sunken')
             print("PLOT :  ", str(channel), "  ", str(selected_channel_reasons[counter]))
             if channel not in orig_selected_channel_list:
                  axm.plot(channel-1, selected_channel_reasons[counter], 'bX', markersize=10, linewidth=2)
             ax.text(length+310, y_position+(y_increment*n)-y_increment*channel, 
                reason_to_string(selected_channel_reasons[counter], channel_labels_short))
             counter += 1

          array_str = ", ".join(str(i) for i in selected_channel_list)
          string1 = "Machine Selected: " + array_str

          icatextobj[0].set_text(string1)

          icaeditfilename = outputdir1 + ".ica.png"
          print("icafile:  ", icaeditfilename)

          plt.show()
      
          root.update()
          root.update_idletasks()
      
      if selstring[9]==1:
          root.destroy()
      root.mainloop()
     
# HERE IS WHER THE IMAGE CASCADE IS CREATED-----------------------------------------------------------------------------------------------------------------------------------
      fig.savefig(icaeditfilename, dpi=100)
# Creation of machine and user selected rejection status      
      kr_machine = np.empty(n, dtype=object)
      kr_user = np.empty(n, dtype=object)
      for i in range(n):
          kr_machine[i] = "Accept"
          kr_user[i] = "Accept"
      for num in orig_selected_channel_list:
          kr_machine[num-1] = "Reject"
      for num in selected_channel_list:
          kr_user[num-1] = "Reject"
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------      
      if selstring[12] == 1:  # or if selstring[9] == 1
          print('BLAHHHHHHHHHHHHHH')
          screenshots = []
          source_regions = []
          fft_peaks = []
          percs = []
          screenshots.append(icaeditfilename)
          pdf = FPDF()
          for idx in range(1, n+1):
            CV, source_point, location_matrix, max_value, max_index, reshaped_list, voxel_csd, peak, perc = dummy_gui(tlabel, length, numsamples, ica_mixing, idx, selected_channel_list, selected_channel_reasons, channel_labels_short, myfilteredsigs, n)
            CV.update()
            fft_peaks.append(peak)
            percs.append(perc)
            
            if selstring[12] == 1:
                  screenshot = save_gui_screenshot(CV)  #if image cascade is selected
                  screenshot_filename = os.path.join(outname, f"screenshot_{idx}.png")
                  screenshot.save(screenshot_filename)
                  screenshots.append(screenshot_filename)
            
            CV.destroy()
            screenshot_filename_brain = os.path.join(outname, f"brain_view_{idx}.png")
            source_region = dummy_brain(source_point, location_matrix, max_value, max_index, reshaped_list, voxel_csd, screenshot_filename_brain, selstring) #Pass selstring?
            source_regions.append(source_region)
            screenshots.append(screenshot_filename_brain)
          #CREATION OF ARRAY FOR TABLE-------------------------------------------------------------------------------------------------
          source_regions = [region.replace("'", "").replace("[", "").replace("]", "") for region in source_regions]
          lobes = [item.split()[0] for item in source_regions]
          #regions = [' '.join(item.split(' Lobe ')[1].split(' ')[0:-3]) for item in source_regions]
          regions = [' '.join(item.split(' Lobe ')[1].split(' ')[0:-3]) if ' Lobe ' in item else ' '.join(item.split(' Sub-lobar ')[1].split(' ')[0:-3]) if ' Sub-lobar ' in item else '' for item in source_regions]
          areas = [item.split()[-1] for item in source_regions]
          components = list(range(1, n+1))
          data_array = [components, percs, max_sites, num_above_half, kr_machine, kr_user, lobes, regions, areas, fft_peaks]
          print(data_array)
          #---------------------------------------------------------------------------------------------------------------------------
          if selstring[12] == 1:
            for screenshot in screenshots:
              image = img.open(screenshot)
              img_w, img_h = image.size
              image.close()
              aspect_ratio = img_w/img_h
              if aspect_ratio > (297/210):
                  page_width = 297
                  page_height = page_width/aspect_ratio
              else:
                  page_height = 210
                  page_width = page_height*aspect_ratio
              #x=(page_width)/2
              if page_height < 210:
                  y= 0 + np.abs((210-page_height)/2)
                  x=0
              else:
                  y=0
                  x= 0+np.abs((297-page_width)/2)
              pdf.add_page(orientation="L")
              pdf.image(screenshot, x=x, y=y, w=page_width, h=page_height)
              if screenshot == screenshots[0]:
                  pdf.add_page(orientation="L")
                  pdf.set_font("Arial", size=10)
                  headers =["Comp. #", "%", "Max Site", "RSI", "Machine", "User", "Lobe", "Region", 'Area', "FFT Peak"]
                  # Convert numpy arrays to Python lists
                  data_array = [list(col) if isinstance(col, np.ndarray) else col for col in data_array]

                  # Determine the number of columns and rows
                  num_columns = len(data_array)
                  num_rows = len(data_array[0])  # Assumes every column has the same number of rows

                  # Calculate column widths based on the maximum width between header and data
                  column_widths = [max(pdf.get_string_width(headers[col_idx]), max(pdf.get_string_width(str(item)) for item in col_data)) + 3 for col_idx, col_data in enumerate(data_array)]
                  # Print the headers with adjusted column widths
                  for col_idx in range(num_columns):
                        pdf.cell(column_widths[col_idx], 8, headers[col_idx], border=1)

                  pdf.ln()

                  # Fill rows with data
                  for row_idx in range(num_rows):
                        for col_idx in range(num_columns):
                              pdf.cell(column_widths[col_idx], 8, str(data_array[col_idx][row_idx]), border=1)
                        pdf.ln()           

          #TABLE CREATION
            pdf.output(img_cascade_file)  
            for screenshot in screenshots[1:]:
              os.remove(screenshot)
              #image = img.open(screenshot)
              #img_w, img_h = image.size
              #page_width = 297
              #page_height = img_h * (297/img_w)
              #x=(page_width - img_w)/2
              #y=(page_height - img_h)/2
              #pdf.add_page(orientation="L")
              #pdf.image(screenshot, x=x, y=y, w=page_width, h=page_height)
              #os.remove(screenshot)
# HERE IS WHERE WE GET THE COMPONENT METRICS--------------------------------------------------------------------------------------------------------     
      comp_array=[]
      if selstring[9]==1:
            locs1=[]
            locs2=[]
            locs3=[]
            percs_=[]
            peaks_=[]
            depths = []
            rythms = []
            rythms_ai = []
            coords = []
            widths = []
            lengths = []
            amounts = []
            diffs = []
            std_devs = []
            for idx in range(1, 20):
                  loc_1, loc_2, loc_3, rms_perc, peak, depth, source_coords, half_width, sig_peak, amount, diff, std_dev = comp_metrics(channel_labels_short, ica_mixing, idx, numsamples, length, myfilteredsigs)
                  locs = loc_1.split()
                  locs1.append(locs[0])
                  locs2.append(loc_2)
                  locs3.append(loc_3[-2:])
                  percs_.append(round(rms_perc, 4))
                  peaks_.append(peak)
                  depths.append(round(depth, 4))
                  coords.append(source_coords)
                  widths.append(half_width)
                  lengths.append(sig_peak)
                  amounts.append(amount)
                  diffs.append(diff)
                  std_devs.append(std_dev)
                  print(max_sites)
                  if 12 <= peak <= 16 and max_sites[idx-1] in ['C3', 'C4', 'CZ']:
                        rythms.append('SMR')
                  elif 6 <= peak <= 13 and max_sites[idx-1] in ['O1', 'O2', 'P3', 'P4', 'PZ']:
                        rythms.append('PDR')
                  elif 7 <= peak <= 12 and max_sites[idx-1] in ['T3', 'T4', 'T5', 'T6']:
                        rythms.append('Temporal Alpha')
                  elif 4 <= peak <= 7 and max_sites[idx-1] in ['FZ']:
                        rythms.append('Frontal Midline Theta') #Associated with ADHD
                  elif 4 <= peak <= 7 and max_sites[idx-1] in ['T3', 'T4', 'T5', 'T6']:
                        rythms.append('Temporal Theta') #Associated with Epilepsy
                  elif 4 <= peak <= 7 and max_sites[idx-1] in ['FP1', 'FP2', 'F3', 'F4']:
                        rythms.append('Frontal Theta') #Cognitive processing, stress, frontal lobe dysfunction
                  elif 7 <= peak <= 11 and max_sites[idx-1] in ['C3', 'C4', 'CZ']:
                        rythms.append('Mu')
                  elif 0.5 <= peak <= 4 and max_sites[idx-1] in ['FP1', 'FP2']:
                        rythms.append('Blink')
                  elif 0.5 <= peak <= 2 and max_sites[idx-1] in ['F3', 'F4']:
                        rythms.append('Triphasic')
                  elif 0.5 <= peak <= 4 and max_sites[idx-1] in ['F7', 'F8']:
                        rythms.append('Lateral')
                  elif 0 <= peak <= 2 and max_sites[idx-1] in ['T3', 'T4']:
                        rythms.append('EKG')
                  elif 0.5 <= peak <= 4:
                        rythms.append('Delta')
                  elif 6 <= peak <= 13:
                        rythms.append('Alpha')
                  else:
                        rythms.append('Other')

                  #OTHER RYTHM CLASSIFICATION---------------------------------------------------------------------------
                  if 12 <= peak <= 16 and locs3[idx-1] in ['1', '2', '3', '4', '5', '6', '7']:
                        rythms_ai.append('SMR')
                  elif 6 <= peak <= 13 and locs3[idx-1] in ['17', '18', '19', '7']:
                        rythms_ai.append('PDR')
                  elif 7 <= peak <= 12 and locs3[idx-1] in ['20', '21', '22']:
                        rythms_ai.append('Temporal Alpha')
                  elif 4 <= peak <= 7 and locs3[idx-1] in ['8', '6', '9', '10', '11']:
                        rythms_ai.append('Frontal Midline Theta') #Associated with ADHD
                  elif 4 <= peak <= 7 and locs3[idx-1] in ['20', '21', '22', '38']:
                        rythms_ai.append('Temporal Theta') #Associated with Epilepsy
                  elif 4 <= peak <= 7 and locs3[idx-1] in ['5', '6', '8', '9', '10', '11', '44', '45', '46']:
                        rythms_ai.append('Frontal Theta') #Cognitive processing, stress, frontal lobe dysfunction
                  elif 7 <= peak <= 11 and locs3[idx-1] in ['1', '2', '3', '4']:
                        rythms_ai.append('Mu')
                  elif 0.5 <= peak <= 4 and locs3[idx-1] in ['9', '10', '11']:
                        rythms_ai.append('Blink')
                  #elif 0.5 <= peak <= 2 and locs3[idx-1] in ['F3', 'F4']:
                  #      rythms_ai.append('Triphasic')
                  elif 0.5 <= peak <= 4 and locs3[idx-1] in ['9', '10', '11', '44', '45', '46']:
                        rythms_ai.append('Lateral')
                  elif 0 <= peak <= 2 and locs3[idx-1] in ['28', '20', '37', '36', '38']:
                        rythms_ai.append('EKG')
                  elif 0.5 <= peak <= 4:
                        rythms_ai.append('Delta')
                  elif 6 <= peak <= 13:
                        rythms_ai.append('Alpha')
                  else:
                        rythms_ai.append('Other')
                  #if .5 <= peak <= 4:
                  #    if max_sites[idx-1] in ['FP1', 'FP2']:
                  #        rythms.append('Blink')
                  #    elif max_sites[idx-1] in ['F7', 'F8']:
                  #        rythms.append('Lateral Eye')
                  #    else:
                  #        rythms.append('Delta')
                  #if peak >= 6:
                  #    if 12 <= peak <= 16:
                  #        if max_sites[idx-1] in ['C3', 'C4', 'CZ']:
                  #            rythms.append('SMR')
                  #    elif peak <= 13:
                  #        if max_sites[idx-1] in ['O1', 'O2', 'P3', 'P4', 'PZ']:
                  #            rythms.append('PDR')
                  #        else:
                  #            rythms.append('Alpha')
                  #else:
                  #    rythms.append('Other')
                  #if 6 <= peak <= 13:
                  #    if max_sites[idx-1] in ['O1', 'O2', 'P3', 'P4', 'PZ']:
                  #      rythms.append('PDR')
                  #    else:
                  #      rythms.append('Alpha Rythm')
                  #elif 0.5 <= peak <= 4:
                  #    if max_sites[idx-1] in ['FP1', 'FP2']:
                  #        rythms.append('Blink')
                  #    elif max_sites[idx-1] in ['F7', 'F8']:
                  #        rythms.append('Lateral Eye')
                  #    else:
                  #        rythms.append('Delta')
                  #else:
                  #    rythms.append('Other')
            comp_array = [max_sites[:19], num_above_half[:19], percs_[:19], peaks_[:19], depths[:19], locs1[:19], locs2[:19], locs3[:19], rythms[:19], coords[:19], rythms_ai[:19], widths[:19], lengths[:19], kr_machine[:19], amounts[:19], diffs[:19], std_devs[:19]]
            print('COMPP ARRAY: ', comp_array)
#  MAINLOOP OF ICA PICKER HAS RETURNED

      print("list returned:  ", selected_channel_list)
      print("reasons returned:  ", selected_channel_reasons)


#  HERE IS A GOOD TIME TO SAVE AN IMAGE OF THE COMPONENTS AND SELECTIONS TO A FILE
      #fig.savefig(icaeditfilename, dpi=100)

#  OPPORTUNITY HERE TO RECONSTRUCT FROM MATRIX WITHOUT ZEROING ANY COMPONENTS-----------------------------------------------------------------------
      ####
#  U MEANS UNCLEANED WHICH MEANS RECONSTRUCTED WITHOUT ANY CLEANING
      restored_signalsu = ica.inverse_transform(ica_components)
      restored_signalsut = restored_signalsu.T
#  restored_signalsut is the recon without removing any components      
      RED = "\033[91m"
      GREEN = "\033[92m"
      YELLOW = "\033[93m"
      RESET = "\033[0m"
# RECON STD
      stdorig = np.std(myvisualsigs)
      rmsorig = np.sqrt(np.mean(np.square(myvisualsigs)))
      stdrecon = np.std(restored_signalsut)
      rmsrecon = np.sqrt(np.mean(np.square(restored_signalsut)))
      stddiffreconorig = np.std(myvisualsigs - restored_signalsut)
      #print('STD ORIGINAL: ', stdorig, 'STD RECON:', stdrecon, 'STD DIFF RECON ORIG:', stddiffreconorig)
      print(f"STD RAW: {YELLOW}{stdorig}{RESET}, STD RECON: {RED}{stdrecon}{RESET}, STD DIFFERENCE RECON ORIGINAL: {RED}{stddiffreconorig}{RESET}, RMS RAW: {YELLOW}{rmsorig}{RESET}, RMS RECON: {GREEN}{rmsrecon}{RESET}")
      #reconstd= abs(np.std(restored_signalsut) - np.std(data))
      
      #print("RECON STANDARD DEVIATION: ", reconstd)
     
#  HERE WE CAN HAVE TWO LEVELS OF CLEANING
#  LEVEL ONE ONLY REMOVES COMPONENTS MAXIMUM AT FP1 FP2 F7 F8 A2
#  LEVEL TWO REMOVES THE OTHER COMPONENTS AS WELL
#  BASED ON selected_channel_reasons, zero out only Fp1/2/ etc components first
#  THEN RECONSTRUCT,  e.g. restored_signals1 and restored_signals2

# CLEANING LEVEL 1 ---------------------------------------------------------------------------------------------------------------------------      
      print('CHANNEL LABELS SHORT', channel_labels_short)
      for compno in selected_channel_list:
            index = selected_channel_list.index(compno)
            numval = selected_channel_reasons[index]
            if channel_labels_short[numval] in ['FP1', 'FP2']:
                  compint = compno - 1
                  print("CLEANING LEVEL 1 --- removing component:", compint)
                  ica_components[:, compint] = 0
            else:
                compint = compno -1 
                print("Reserved For Level 2 :", compint) 
      
#  NOW RECONSTRUCT LEVEL 1-------------------------------------------------------------------------------------------------------------------------
       
      restored_signals1 = ica.inverse_transform(ica_components)
      restored_signals1t = restored_signals1.T
      stddiffclean1orig = np.std(myvisualsigs - restored_signals1t)
      stdclean1 = np.std(restored_signals1t)
      rmsclean1 = np.sqrt(np.mean(np.square(restored_signals1t)))
      #print('STD ORIGINAL: ', stdorig, 'STD CLEAN1:', stdclean1, 'STD DIFF CLEAN ORIG:', stddiffclean1orig)
      print(f"STD RAW: {YELLOW}{stdorig}{RESET}, STD Clean1: {GREEN}{stdclean1}{RESET}, STD DIFFERENCE ClEAN1 ORIGINAL: {GREEN}{stddiffclean1orig}{RESET}, RMS CLEAN1: {YELLOW}{rmsclean1}{RESET}")
      percent = ((stddiffclean1orig)/(np.std(myvisualsigs))*100)
      print(f"Percentage: {YELLOW}{percent}{RESET}")

      for i in range(numcomps):
         myvisualsigs[i] = restored_signals1t[i]
      print("myvisualsignals shape after Level 1:", myvisualsigs.shape)
      myvisualsigsc = myvisualsigs

      stdclean1 = np.std(restored_signals1t)
      pyedf_file = pyedflib.EdfReader(edf_file)
      print("pyedflib EDF file opened third time. File type: ", pyedf_file.getSignalHeaders()[0]['label'])
      
#      stdorig = np.std(myvisualsigs)
#      stdrecon = np.std(restored_signalsut)
      #stddiffclean1orig = np.std(myvisualsigs - restored_signals1t)
      #print('STD ORIGINAL: ', stdorig, 'STD CLEAN1:', stdrecon, 'STD DIFF CLEAN ORIG:', stddiffclean1orig)

      clean1_pyedf_headers = [pyedf_file.getSignalHeader(i) for i in range(pyedf_file.signals_in_file)]
      clean1_pyedf_header = pyedf_file.getHeader()
      clean1_pyedf_file = pyedflib.EdfWriter(clean1_pyedf_file, n_channels=n, file_type=pyedflib.FILETYPE_EDF)
      clean1_pyedf_file.setSignalHeaders(clean1_pyedf_headers)
      clean1_pyedf_file.setHeader(clean1_pyedf_header)
      clean1_pyedf_file.writeSamples(myvisualsigs)
      pyedf_file.close()
      clean1_pyedf_file.close()
      print('STD CLEAN1: ', stdclean1)

      
      #reconstd= abs(np.std(restored_signalsut) - np.std(data))
      #print("RECON STANDARD DEVIATION: ", reconstd)
      #clean1std = abs(stdclean1 - np.std(data))
      #print("CLEAN STANDARD DEVIATION: ", clean1std)
      
#  BELOW IS LEVEL 2 BECAUSE IT SETS ANY ON SELECTED CHANNEL_LIST TO ZERO----------------------------------------------------------------------------
#  GOT SELECTIONS FROM POPUP BOX - NOW SET THEM TO ZEROS
      for compno in selected_channel_list:
            compint = int(compno) - 1
            print("CLEANING LEVEL 2---removing component:  ", compint)
            ica_components[:, compint] = 0

#  RECONSTRUCT SIGNALS FROM ICA COMPONENTS (LEVEL 2) ----------------------------------------------------------------------------------------------------------
      restored_signals2 = ica.inverse_transform(ica_components)
      restored_signals2t = restored_signals2.T

      for i in range(numcomps):
         myvisualsigs[i] = restored_signals2t[i]
      print("myvisualsignals shape after Level 2", myvisualsigs.shape)

#  RELABEL SINCE WE ARE GOING BACK TO LINKED EARS----------------------------------------------------------------------------------------------------------
      print("relabeling back to linked ears")
      electrode_names, pdf_filename = setup_electrode_names(n, outputdir1, electrode_names, electrode_names_orig, 6)

# GO AHEAD AND SAVE THE NEW ICA CLEANED DATA INTO A NEW EDF FILE RIGHT NOW
# Open the EDF file
      pyedf_file = pyedflib.EdfReader(edf_file)
      print("pyedflib EDF file opened second time. File type: ", pyedf_file.getSignalHeaders()[0]['label'])
#  GET READY TO  HAVE AN OUTPUT EDF FILE WITH THE SAME HEADERS
      stdclean2 = np.std(myvisualsigs)
      clean_pyedf_signals = [pyedf_file.readSignal(i)for i in range(pyedf_file.signals_in_file)]
      clean_pyedf_annotations = pyedf_file.readAnnotations()
      clean2_pyedf_headers = [pyedf_file.getSignalHeader(i) for i in range(pyedf_file.signals_in_file)]
      clean2_pyedf_header = pyedf_file.getHeader()
      clean2_pyedf_file = pyedflib.EdfWriter(clean2_pyedf_file, n_channels=n, file_type=pyedflib.FILETYPE_EDF)
      clean2_pyedf_file.setSignalHeaders(clean2_pyedf_headers)
      clean2_pyedf_file.setHeader(clean2_pyedf_header)
      clean2_pyedf_file.writeSamples(myvisualsigs)
      pyedf_file.close()
      clean2_pyedf_file.close()
      print('STD CLEAN2: ', stdclean2)
#  NOW WRITE OUT  UNCLEAN FILE WITH NO COMPONENTS REMOVED
      for i in range(numcomps):
         myvisualsigs[i] = restored_signalsut[i]
      print("myvisualsignals shape", myvisualsigs.shape)


      pyedf_file = pyedflib.EdfReader(edf_file)
      print("pyedflib EDF file opened third time. File type: ", pyedf_file.getSignalHeaders()[0]['label'])
#  GET READY TO  HAVE AN OUTPUT EDF FILE WITH THE SAME HEADERS

      recon_pyedf_signals = [pyedf_file.readSignal(i)for i in range(pyedf_file.signals_in_file)]
      recon_pyedf_annotations = pyedf_file.readAnnotations()
      recon_pyedf_headers = [pyedf_file.getSignalHeader(i) for i in range(pyedf_file.signals_in_file)]
      recon_pyedf_header = pyedf_file.getHeader()
      recon_pyedf_file = pyedflib.EdfWriter(recon_pyedf_file, n_channels=n, file_type=pyedflib.FILETYPE_EDF)
      recon_pyedf_file.setSignalHeaders(recon_pyedf_headers)
      recon_pyedf_file.setHeader(recon_pyedf_header)
      recon_pyedf_file.writeSamples(myvisualsigs)
      pyedf_file.close()
      recon_pyedf_file.close()
      return(electrode_names, pdf_filename, fig, ax, channel_labels_short, n, myvisualsigsc, time_range, comp_array, stdorig, stddiffreconorig, stddiffclean1orig, percent, sites_rsi)

#  ICA BUTTON CALLBACK FOR SELECTING ICA COMPONENTS-----------------------------------------------------------------------------------------------------------------------
def icabutton_callback(button_num, n, selected_channel_list, icabutton, icatext, icatextobj, icatextl):
    #global selected_channel_list
    #global icabutton
    #global icatext
    #global icatextobj
    #global icatextl

    mybutton = icabutton[button_num-1]
#    print(mybutton)

#    selected_channel = int(event.widget.cget('text')) - 1
    print("button pressed:  ", button_num, ", N equals:  ", n)

#    print("selected channel:  ", button_num)
#    print('Selected channels:  ', selected_channel_list)
    
       
      
    #if button_num == n+1:
    #    print('Selected channels:  ', selected_channel_list)
    #    print('closing selector panel')
#        destroy()
#        plt.close()
    
    if button_num in selected_channel_list:
            selected_channel_list.remove(button_num)
            print('Selected channels:  ', selected_channel_list)
            icabutton[button_num-1].config(relief='raised')
#            button.configure(relief=SUNKEN)
#            event.widget.config(relief=tk.SUNKEN)
    else:
            selected_channel_list.append(button_num)
            print('Selected channels:  ', selected_channel_list)
            icabutton[button_num-1].config(relief='sunken')
            
#            button.configure(relief=RAISED)
#            event.widget.config(relief=tk.RAISED)
    print("adding selects")
    icatext.delete("1.0", tk.END)
#    j=2
   
#  SHOW SELECTED COMPONENTS - NEED TO SHOW REASONS HERE
    selected_channel_list.sort()
    mylist = []
    icatext.insert(tk.END, "ICA SELECTED: \n")
    for selchan in selected_channel_list:
      icatext.insert(tk.END, selchan)     #, + "MAX AT:", channel_labels_short[selected_channel_reasons[selchan]]
      icatext.insert(tk.END, "\n")
      mylist.append(selchan)

    print("mylist:  ", mylist)
    array_str = ", ".join(str(i) for i in mylist)
    string1 = "Operator Selected:  "
    string2 = string1 + array_str

    icatextobj[0].set_text(string2)

#    for i in range(20):
#      if i in selected_channel_list:
#        icatext.insert(tk.INSERT, str(i))
#        j = j+1

    print("exiting button callback")

def comp_metrics(channel_labels_short, ica_mixing, idx, numsamples, length, myvisualsigs):#myfilteredsigs
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
    print('VECTOR TO BE MULTIPLIED: ', vector)
    print('VECTOR SHAPE: ', vector.shape)
    #GET MATRIX OUT OF CSV FILE------------------------------------------------------------------------------------------------------------------------------------------------
    with open(file_path) as file:
        reader = csv.reader(file)
        matrix_data = [row[2:21] for row in reader]

    matrix = np.array(matrix_data, dtype=float)
    print('MATRIX SHAPE: ', matrix.shape)
    #print(matrix)
    mult_result = vector_matrix_multiplication(matrix, vector[:19])
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
    print('DEPTH: ', depth)
    #----------------------------------------------------------------------------------------------------------------------------------------------
    loc_1 = source_point[3]
    loc_2 = source_point[4]
    loc_3 = source_point[5]
    #RMS-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
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
    #FFT----------------------------------------------------------------------------------------
    kernel=np.array([1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16])

    kernel1 = np.array([1/16, 1/8, 3/16, 1/2, 3/16, 1/8, 1/16])
    sig_s = np.zeros(2560)
    amp_s = np.zeros(2560)
    amp_sc = np.zeros(2560)
    window_s = np.hamming(2560)
    numpages = numsamples//length - 1
    epoch_vals= []
    for i in range(numpages):
        epoch_range = np.arange(2560*(i-1), 2560*i, 1)
        sig_s = myvisualsigs[idx-1, epoch_range]
        fft_s = np.fft.fft(sig_s)
        amp_s = np.abs(fft_s)
        #amp_sc = np.convolve(amp_s, kernel, mode='same')
        amp_sc = np.convolve(amp_s, kernel1, mode='same')
        epoch_vals.append(amp_sc)
          #freq_s = np.fft.fftfreq(len(sig_s), d=1/256)

    avg_amp_sc = sum(epoch_vals) / len(epoch_vals)
    retcon = detect_peak(avg_amp_sc[:650])
    half_peak = max(avg_amp_sc[:650])/2
    tolerance = 200
    indexes = [i for i, value in enumerate(avg_amp_sc[:650]) if abs(value-half_peak) <= tolerance]
    print('Indexes: ', indexes)
    print(retcon)
    peak = retcon/10
    closest_left = None
    closest_right = None
    if indexes:
      #closest_left = 0
      #closest_right = 0
      min_distance_l = float('inf')  # Initialize with positive infinity
      min_distance_r = float('inf')
      for index in indexes:
        distance = abs(index - retcon)

        if index < retcon:
            if distance < min_distance_l:
                min_distance_l = distance
                closest_left = index
        elif index > retcon:
            if distance < min_distance_r:
                min_distance_r = distance
                closest_right = index
    if closest_left is None:
        closest_left = 0
    if closest_right is None:
        closest_right = 0
    half_width = (closest_right-closest_left)/10
#----------------------------------------------------------------------------------------------------------------------------------------------
    i_fft = np.fft.ifft(avg_amp_sc)
    i_fft[0:6] = 0
    i_fft[len(i_fft)-4:] = 0
    template = i_fft[2300:2470]
    peaks, _ = find_peaks(abs(i_fft[:1280]))
    #peaks = [peak + 1280 for peak in peaks]
    print('peals:', peaks)
    peak_heights = i_fft[peaks]
    print('peals:', peak_heights)
    sig_peak = None
    for i in range(0, len(peak_heights)-1):
        if abs(peak_heights[i]) < 0.02 * abs(peak_heights[0]):
            sig_peak = (peaks[i]/256) * 1000
            break
    if sig_peak is None:
            sig_peak=0

#--------------------------------------------------------------------------------------------------------------------------------------------------
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
    bursts = []
    for j in range(0, len(threshold)):
      red_points = []
      for i in range(len(threshold[0])-1):
        thresh = threshold[j]
        if thresh[i] != 0 and all(thresh[i - k] == 0 for k in range(1, 35)):
            red_points.append(i)
      print('RED: ', red_points)
      bursts.append(red_points)
    amounts = []
    for red_points in bursts:
        amounts.append(len(red_points))
    amount = sum(amounts) / len(amounts)

    average_differences = []
    for_stdev = []
    for red_points in bursts:
        differences = []
        for i in range(0, len(red_points)):
            if i == 0:
                difference = red_points[i]/256
            else:
                difference = (red_points[i]/256) - (red_points[i-1]/256)
            differences.append(difference)
            for_stdev.append(difference)
        print('DIFFS: ', differences)
        if len(differences) != 0:
            average_diff = sum(differences) / len(differences)
            average_differences.append(average_diff)
    
    if len(average_differences) != 0:
      diff = round(sum(average_differences)/len(average_differences), 3)
    else:
      diff = 0
    
    std_dev = np.std(for_stdev)
    std_dev = round(std_dev, 4)
    return loc_1, loc_2, loc_3, rms_perc, peak, depth, source_coords, half_width, sig_peak, amount, diff, std_dev