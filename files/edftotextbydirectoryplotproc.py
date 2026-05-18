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
global sel_LE
global sel_AV
global sel_LA
global sel_DB
global sel_ICAs
global sel_PCA
global sel_ICALE
global sel_PLTS
global sel_REP
global sel_XLF
global sel_SPLIT
global globaldirname
global added_dirname
global database_name
global excel_file_path

def edf_to_text_by_directory_plot_proc(dirname):
    global selstring2
    global filestring
    global added_dirname
    global added_paths
    global database_name
    global excel_file_path
    #print("cleaning old files")
    #if os.path.exists('./out_file.xlsx'):
    #  os.remove('./out_file.xlsx')  
    #if os.path.exists('./out_file.le.xlsx'):
    #  os.remove('./out_file.le.xlsx')  
    #if os.path.exists('./out_file.avg.xlsx'):
    #  os.remove('./out_file.avg.xlsx')  
    #if os.path.exists('./out_file.lap.xlsx'):
    #  os.remove('./out_file.lap.xlsx')  
    #if os.path.exists('./out_file.lngb.xlsx'):
    #  os.remove('./out_file.lngb.xlsx')  
    #if os.path.exists('./out_file.ica.xlsx'):
    #  os.remove('./out_file.ica.xlsx')  
    #if os.path.exists('./out_file.pca.xlsx'):
    #  os.remove('./out_file.pca.xlsx')  
    #if os.path.exists('./out_file.icale.xlsx'):
    #  os.remove('./out_file.icale.xlsx')  
 
    #GETS ALL DIRECTORIES IN PROJECT FOLDER THAT INCLUDE EDF FILES--------------------------------------------------------------------------------------------------------------------------------
    print("getting directory:", dirname)
    contents = os.listdir(dirname)
    for item in contents:
        print(item)
    filtered_directories = [os.path.join(dirname, item) for item in os.listdir(dirname) if os.path.isdir(os.path.join(dirname, item)) and any(file.endswith(".edf") for file in os.listdir(os.path.join(dirname, item)))]
    filtered_directories = [os.path.basename(directory) for directory in filtered_directories]
    print(filtered_directories)
    print ("got directory")
    #GETS ALL FILES IN DIRECTORIES THAT END WITH .EDF---------------------------------------------------------------------------------------------------------------------------------------
    edf_files = [file for file in contents if file.endswith(".edf")]
    selstring2 = np.zeros(len(edf_files)) #Initialize File Selstring
    for file in edf_files:
        print(file)
    print ("got edf files")
    plot_number = 1
    excel_file_path = ''
    added_dirname = []
    added_paths = []
    #OPENS THE PROCESS SELECTOR WINDOW-------------------------------------------------------------------------------------------------------------------------------------------------------
    process_selector(dirname, edf_files, filtered_directories)
    print (selstring)
    print('USER INPUTTED NAME: ', database_name)
    print('FILE CHOSEN: ', excel_file_path)
    
    def new_databasename(base_name, endname): #GETS NAME FOR DATABASE
      counter = 1
      new_name = base_name
      while os.path.exists('./' + new_name + endname):
        new_name = f"{base_name}{counter}"
        counter += 1
      return new_name
    
    print("cleaning old files") 
    if os.path.exists('./' + database_name +'.out_file.xlsx'):
      endname = '.out_file.xlsx'
      database_name = new_databasename(database_name, endname)  
    if os.path.exists('./' + database_name +'.out_file.le.xlsx'):
      endname = '.out_file.le.xlsx'
      database_name = new_databasename(database_name, endname)  
    if os.path.exists('./' + database_name +'.out_file.avg.xlsx'):
      endname = '.out_file.avg.xlsx'
      database_name = new_databasename(database_name, endname)  
    if os.path.exists('./' + database_name +'.out_file.lap.xlsx'):
      endname = '.out_file.lap.xlsx'
      database_name = new_databasename(database_name, endname)  
    if os.path.exists('./' + database_name +'.out_file.lngb.xlsx'):
      endname = '.out_file.lngb.xlsx'
      database_name = new_databasename(database_name, endname)  
    if os.path.exists('./' + database_name +'.out_file.ica.xlsx'):
      endname = '.out_file.ica.xlsx'
      database_name = new_databasename(database_name, endname)  
    if os.path.exists('./' + database_name +'.out_file.pca.xlsx'):
      endname = '.out_file.pca.xlsx'
      database_name = new_databasename(database_name, endname)  
    if os.path.exists('./' + database_name +'.out_file.icale.xlsx'):
      endname = '.out_file.icale.xlsx'
      database_name = new_databasename(database_name, endname) 

    if isinstance(globaldirname, list): #IF BATCH MODE IS SELECTED--------------------------------------------------------------------------------------------------------------------------------
      for dirname in globaldirname:
        print("Out of selector:   " + dirname)
        print("getting directory:", dirname)
        contents = os.listdir(dirname)
        for item in contents:
          print(item)
        print ("got directory")
        edf_files = [file for file in contents if file.endswith(".edf")]
    
        for file in edf_files:
          print(file)
        print ("got edf files")
### Print edf_files, and compare against selstring2 to determine if selected_files is working properly
        selected_files = []
        print("Selstring2 ",selstring2)
        print("range will be:  ", len(edf_files))
        for i in range (len(edf_files)):
          if selstring2[i] == 1:
            selected_files.append(edf_files[i])
  #### At this point, selected_files contains a list of the .edf files that will be processed
        print("Files to be processed: ",selected_files)

#  NEUTRALIZE SELSTRING FOR DEBUGGING GUI
#    selstring = np.zeros(16)

        outname = dirname+"/Review"
  
        if not os.path.exists(outname):
          os.mkdir(outname)
          print("Had to create output dir:   ", outname)
    
        for file in selected_files:
          dirtouse = dirname+"/"+file
          dirtouse1 = dirtouse[:-4]
          outputdir = dirname+"/Review/"+file
          outputdir1 = outputdir[:-4]

          print("Processing file:  " + dirtouse + "   outputdir:  " + outputdir)

#  USE OF MONTAGE CODES IS AS FOLLOWS
# 0 LINKED EARS
# 1 AVERAGE
# 2 LAPLACIAN
# 3 LONGITUDINAL BIPOLAR DOUBLE BANANA
# 4 ICA
# 5 PCA
# 6 USE ICA TO SELECT AND RECOMPOSE, THEN MAKE LE REPORT

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
          print("File process ", dirtouse1, "return:  ", str(freturn))
          plot_number += 1

    else: #IF BATCH MODE IS NOT SELECTED-------------------------------------------------------------------------------------------------------------------------------
      print("Out of selector:   " + globaldirname)
      print("getting directory:", globaldirname)
      contents = os.listdir(globaldirname)
      for item in contents:
        print(item)
      print ("got directory")
      edf_files = [file for file in contents if file.endswith(".edf")]
    
      for file in edf_files:
        print(file)
      print ("got edf files")
### Print edf_files, and compare against selstring2 to determine if selected_files is working properly
      selected_files = []
      print("Selstring2 ",selstring2)
      print("range will be:  ", len(edf_files))
      for i in range (len(edf_files)):
       if selstring2[i] == 1:
          selected_files.append(edf_files[i])
  #### At this point, selected_files contains a list of the .edf files that will be processed
      print("Files to be processed: ",selected_files)

#  NEUTRALIZE SELSTRING FOR DEBUGGING GUI
#    selstring = np.zeros(16)

      outname = globaldirname+"/Review"
  
      if not os.path.exists(outname):
        os.mkdir(outname)
        print("Had to create output dir:   ", outname)
    
      for file in selected_files:
        dirtouse = globaldirname+"/"+file
        dirtouse1 = dirtouse[:-4]
        outputdir = globaldirname+"/Review/"+file
        outputdir1 = outputdir[:-4]

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
        plot_number += 1
    
    if selstring[9] == 1:
       files.file_svc.histogram_to_excel_file(outfile)
       if selstring[6] == 1:
        files.file_svc.histograms_to_comps_file(excel_file)

def set_variable(num):
    global sel_LE
    global sel_AV
    global sel_LA
    global sel_DB
    global sel_ICA
    global sel_PCA
    global sel_ICALE
    global sel_PLTS
    global sel_REP
    global sel_XLF
    global sel_SHORT
    global selstring
    global sel_TEXT
    global sel_IMG
    global sel_DROP
    global sel_SPLIT

    selstring = np.zeros(16)
    if sel_LE.get():
      selstring[0] = 1
    if sel_AV.get():
      selstring[1] = 1
    if sel_LA.get():
      selstring[2] = 1
    if sel_DB.get():
      selstring[3] = 1
    if sel_ICA.get():
      selstring[4] = 1
    if sel_PCA.get():
      selstring[5] = 1
    if sel_ICALE.get():
      selstring[6] = 1
    if sel_PLTS.get():
      selstring[7] = 1
    if sel_REP.get():
      selstring[8] = 1
    if sel_XLF.get():
      selstring[9] = 1
    if sel_SHORT.get():
      selstring[10] = 1
    if sel_TEXT.get():
       selstring[11] = 1
    if sel_IMG.get():
       selstring[12] = 1
    #if sel_SPLIT.get():
    #   selstring[13] = 1
    #if sel_DROP.get():
    #   selstring[13] = 1
    
    if num == 1:
       sel_REP.set(0)
       selstring[8] = 0
    elif num ==2:
       sel_XLF.set(0)
       selstring[9] = 0
    print("selstring:  ", selstring)

def set_filename_variable():
   global filestring
   global selstring2
   if filestring == ():
     for i in range(0, len(selstring2)):
         selstring2[i] = 1

#  PROCESS_SELECTOR CREATES THE POPUP DIALOG TO SELECT THE DIRECTORY AND FUNCTIONS DESIRED

def process_selector(dirname, edf_files, filtered_directories):
    global sel_LE
    global sel_AV
    global sel_LA
    global sel_DB
    global sel_ICA
    global sel_PCA
    global sel_ICALE
    global sel_PLTS
    global sel_REP
    global sel_XLF
    global sel_SHORT
    global sel_TEXT
    global sel_IMG
    global sel_DROP
    #global sel_SPLIT
    global globaldirname
    globaldirname = dirname

    root = tk.Tk()
    def getSelectedFiles():
        global filestring
        global database_name
        database_name = user_input_entry.get()
        print('DATABASE NAME:', database_name)
        filestring = listbox.curselection()
        if selstring[8]==1 and excel_file_path=='':
           messagebox.showerror("Error", "Please Select a Database to use")
        elif selstring[9]==1 and database_name == '':
           messagebox.showerror("Error", "Please Input a Database Name")
        else:
          print("Filestring ",filestring)
          set_filename_variable()
          root.destroy()
    
    def on_item_selected(event):
        print('ON ITEM SELECTED FUNCTION')
        global selected_item
        selected_item = [listbox.get(index) for index in listbox.curselection()]
        for i in range(len(selstring2)):
           selstring2[i] = 0
        for index in listbox.curselection():
          selstring2[index] = 1
        print('Selected File String: ', selstring2)

    def browse_excel_file():
      global excel_file_path
      excel_file_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx;*.xls")])
      file_name = os.path.basename(excel_file_path)
      if excel_file_path:
        excel_file_label.config(text="Selected Excel File: " + file_name)
      else:
        excel_file_label.config(text="No Excel File Selected")


#  CREATE THE POPUP BOX TO SELECT WHAT PROCESSING TO DO---------------------------------------------------------------------------------------------------------
    titlestring = "BrainAvatar Analysis CleanEEG EDF File Reader / Processor "
    root.title(titlestring)

    def toggle_checkbox(event=None):
      if batch_button_var.get():
        dir_listbox.configure(selectmode=tk.MULTIPLE)
        print('multiple select')
      else:
        dir_listbox.configure(selectmode=tk.SINGLE)
        print('single select')
      dir_listbox.selection_clear(0, tk.END)  

    
#    frame = tk.Frame(root, padding=20)
    left_frame = tk.Frame(root, width=100, height=200, padx=10, pady=10,
        highlightthickness=1, borderwidth=2, relief=tk.RIDGE)
    left_frame_title = tk.Label(left_frame, text="SELECT DIRECTORY TO PROCESS")
    left_frame_title.pack(side="top", pady=10)
    left_frame.pack(side="left")
    
    button_frame = tk.Frame(left_frame)
    button_frame.pack(side="bottom")
    directory_label = tk.Label(left_frame, text="ALL FILES IN DIRECTORY WILL BE PROCESSED")
    directory_label.pack(pady=5)
    directory_entry = tk.Entry(left_frame, width=100)
    directory_entry.pack(pady=5)
    directory_entry.insert(0, dirname)
# CREATE THE NEW LIST BOX THAT WILL CONTAIN THE FOLDERS------------------------------------------------------------------------------------------------------
    batch_button_var = tk.BooleanVar()
    batch_button = tk.Checkbutton(button_frame, text='BATCH PROCESSING MODE', variable=batch_button_var, command=toggle_checkbox)
    batch_button.pack(side='left', padx= 10)
  
    dir_listbox = tk.Listbox(left_frame, width=50, height=20, selectmode=tk.SINGLE)
    dir_listbox.pack(side='left', fill="both", expand=True)
    for directory in filtered_directories:
      dir_listbox.insert(tk.END, directory)
# CREATE THE SCROLLBAR FOR THE NEW LIST BOX
    scrollbar = tk.Scrollbar(left_frame)
    scrollbar.pack(side="left", fill="y")

# CONFIGURE THE SCROLLBAR TO WORK WITH THE NEW LIST BOX
    dir_listbox.config(yscrollcommand=scrollbar.set)
    #scrollbar.config(command=dir_listbox.yview)
#  CREATE THE LIST BOX THAT WILL CONTAIN ALL THE EDF FILE NAMES
    listbox = tk.Listbox(left_frame, width=50, height=20, selectmode=tk.MULTIPLE)
# CREATE THE SCROLLBAR FOR THE EXISTING LIST BOX
    scrollbar2 = tk.Scrollbar(left_frame)
    scrollbar2.pack(side="left", fill="y")

# CONFIGURE THE SCROLLBAR TO WORK WITH THE EXISTING LIST BOX
    listbox.config(yscrollcommand=scrollbar2.set)
    #scrollbar2.config(command=listbox.yview)
#    listbox.configure(bg="#FFFFFF", fg="black", font=("Arial", 10))
    listbox.pack(side='left', fill="both", expand=True)
    for name in edf_files:
        listbox.insert(tk.END, name)
    listbox.bind("<<ListboxSelect>>", lambda event: on_item_selected(event))

    def fill_listbox(event, directory_entry):
      global selstring2
      global globaldirname
      print('FILL LISTBOX FUNCTION')
      if batch_button_var.get():  # Check the state of the checkbutton
        selected_indices = dir_listbox.curselection()
        selected_directories = [dir_listbox.get(index) for index in selected_indices]
        selected_paths = []
        current_dir = os.getcwd()
        #print('Selected Directories:', selected_directories)
        for selection in selected_directories:
           if selection in added_dirname:
              selected_paths.append(added_paths[added_dirname.index(selection)])
           else:
              selected_paths.append(os.path.join(current_dir, selection))
        
        globaldirname = selected_paths
        print('SELECTED DIRECTORIES:', selected_paths)
        directory_entry.delete(0, tk.END)
        for dir in selected_paths:
           directory_entry.insert(tk.END, dir + '\n')
        files_edf = []
        for selected_directory in selected_paths:
            files_dir = os.listdir(selected_directory)
            for file in files_dir:
                if file.lower().endswith('.edf'):
                    files_edf.append(file)
        selstring2 = np.zeros(len(files_edf))
        print('Selstring 2: ', selstring2)
        listbox.delete(0, tk.END)
        for name in files_edf:
            listbox.insert(tk.END, name)
      else:
        if dir_listbox.curselection():
            selected_directory = dir_listbox.get(dir_listbox.curselection())
            print('Selected Directory:', selected_directory)
            current_dir = os.getcwd()
            if selected_directory in added_dirname:
               selected_directory = added_paths[added_dirname.index(selected_directory)]
            else:
               selected_directory = os.path.join(current_dir, selected_directory)
            directory_entry.delete(0, tk.END)
            directory_entry.insert(0, selected_directory)
            globaldirname = selected_directory
            files_edf = []
            files_dir = os.listdir(selected_directory)
            for file in files_dir:
                if file.lower().endswith('.edf'):
                    files_edf.append(file)
            
            selstring2 = np.zeros(len(files_edf))
            listbox.delete(0, tk.END)
            for name in files_edf:
                listbox.insert(tk.END, name)

    
    dir_listbox.bind("<<ListboxSelect>>", lambda event: fill_listbox(event, directory_entry))
#   CREATE THE BROWSE BUTTON TO GET TO A DIRECTORY BROWSER
    browse_button = tk.Button(button_frame, text="BROWSE FOR DIRECTORY", command=lambda: browse_directory(directory_entry, directory_label, listbox, dir_listbox))
    browse_button.pack(pady=10)
#  CREATE THE RIGHT FRAME TO CONTAIN THE BUTTONS
    right_frame = tk.Frame(root, width=150, height=100, padx=10, pady=10,
        highlightthickness=1, borderwidth=2, relief=tk.RIDGE)
    right_frame_title = tk.Label(right_frame, text = "SELECT PROCESSING OPTIONS")
    right_frame_title.pack(side="top", pady=10)
    right_frame.pack(side="right")

    sel_LE = tk.IntVar()
    check_button1 = tk.Checkbutton(right_frame, text="LINKED EARS (not cleaned)", variable=sel_LE, command=lambda: set_variable(0))
#    check_button1.configure(bg="#4CAF50", fg="white",font=("Arial", 12), padx=20, pady=10, bd=0)
    check_button1.pack(side="top", anchor="w")

    sel_AV = tk.IntVar()
    check_button2 = tk.Checkbutton(right_frame, text="AVERAGE REFERENCE (not cleaned)", variable=sel_AV, command=lambda: set_variable(0))
    check_button2.pack(side="top", anchor="w")

    sel_LA = tk.IntVar()
    check_button3 = tk.Checkbutton(right_frame, text="LAPLACIAN (not cleaned)", variable=sel_LA, command=lambda: set_variable(0))
    check_button3.pack(side="top", anchor="w")

    sel_DB = tk.IntVar()
    check_button4 = tk.Checkbutton(right_frame, text="DOUBLE BANANA (not cleaned)", variable=sel_DB, command=lambda: set_variable(0))
    check_button4.pack(side="top", anchor="w")

    sel_ICA = tk.IntVar()
    check_button5 = tk.Checkbutton(right_frame, text="INDEPENDENT COMPONENTS ANALYSIS (ICA using FastICA)", variable=sel_ICA, command=lambda: set_variable(0))
    check_button5.pack(side="top", anchor="w")

    sel_PCA = tk.IntVar()
    check_button6 = tk.Checkbutton(right_frame, text="PRINCIPAL COMPONENTS ANALYSIS (PCA)", variable=sel_PCA, command=lambda: set_variable(0))
    check_button6.pack(side="top", anchor="w")

    sel_ICALE = tk.IntVar()
    check_button7 = tk.Checkbutton(right_frame, text="LINKED EARS (ICA CLEANED WITH NEW EDF FILE)", variable=sel_ICALE, command=lambda: set_variable(0))
    check_button7.pack(side="top", anchor="w")

    sel_PLTS = tk.IntVar()
    check_button8 = tk.Checkbutton(right_frame, text="PLOTS OF EVERY PAGE", variable=sel_PLTS, command=lambda: set_variable(0))
    check_button8.pack(side="top", anchor="w")

    dropdown_frame = tk.Frame(right_frame)
    dropdown_frame.pack(side="top", anchor='w')
    
    sel_REP = tk.IntVar()
    check_button9 = tk.Checkbutton(dropdown_frame, text="SUMMARY REPORT (PDR, ETC)", variable=sel_REP, command=lambda: set_variable(2))
    check_button9.pack(side="left", anchor="w")
    
    excel_button = tk.Button(dropdown_frame, text="Browse Database", command=browse_excel_file)
    excel_button.pack(side="left")

    excel_file_label = tk.Label(dropdown_frame, text="No Database Selected")
    excel_file_label.pack(side="left")

    user_input_frame = tk.Frame(right_frame)
    user_input_frame.pack(side="top", anchor="w")
    
    sel_XLF = tk.IntVar()
    check_button10 = tk.Checkbutton(user_input_frame, text="CREATE DATABASE", variable=sel_XLF, command=lambda: set_variable(1))
    check_button10.pack(side="left")
 
    # Add a label for user input
    user_input_label = tk.Label(user_input_frame, text="| Database name:")
    user_input_label.pack(side="left")

    # Add an entry for user input
    user_input_entry = tk.Entry(user_input_frame)
    user_input_entry.pack(side="left")

    sel_SHORT = tk.IntVar()
    check_button11 = tk.Checkbutton(right_frame, text="SHORT (2 PAGES) PLOT REPORT", variable=sel_SHORT, command=lambda: set_variable(0))
    check_button11.pack(side="top", anchor="w")

    sel_TEXT = tk.IntVar()
    check_button12 = tk.Checkbutton(right_frame, text="TEXT FILE DATA", variable=sel_TEXT, command=lambda: set_variable(0))
    check_button12.pack(side="top", anchor="w")

    sel_IMG = tk.IntVar()
    check_button13 = tk.Checkbutton(right_frame, text="IMAGE CASCADE", variable=sel_IMG, command=lambda: set_variable(0))
    check_button13.pack(side="top", anchor="w")

    #sel_SPLIT = tk.IntVar()
    #check_button14 = tk.Checkbutton(right_frame, text="SPLIT HALF TEST", variable=sel_SPLIT, command=lambda: set_variable(0))
    #check_button14.pack(side="top", anchor="w")

    #dropdown_frame = tk.Frame(right_frame)
    #dropdown_frame.pack(side="top", anchor='w')
    
    #sel_DROP = tk.IntVar()
    #check_button14 = tk.Checkbutton(dropdown_frame, text="USE DATABASE", variable=sel_DROP, command=lambda: set_variable(2))
    #check_button14.pack(side="left")

    #excel_button = tk.Button(dropdown_frame, text="Browse Excel File", command=browse_excel_file)
    #excel_button.pack(side="left")

    #excel_file_label = tk.Label(dropdown_frame, text="No Database Selected")
    #excel_file_label.pack(side="left")

    exit_button = tk.Button(right_frame, text="PROCESS FILES", command=getSelectedFiles) 
    
    exit_button.pack(pady=(10,0))

    right_frame.pack(side="right")
    
    root.mainloop()

#  BROWSE AND GET A DIRECTORY TO PROCESS - THIS WILL BE A COMPLETE PATH
def browse_directory(dir_entry, dir_label, listbox, dir_listbox):
    global globaldirname
    global selstring2
    global added_dirname
    global added_paths
#    initialdir = os.getcwd()

    initialdir = globaldirname
    
    print("CWD:  " + initialdir + "   dirname:  " + globaldirname)
    newdirectory = filedialog.askdirectory(initialdir=initialdir)
    if newdirectory:
      added_paths.append(newdirectory)
      
      newdirectory = os.path.abspath(newdirectory)
      added_dirname.append(os.path.basename(newdirectory))
      print(added_dirname, added_paths)
      folder_name = os.path.basename(newdirectory)
      dir_entry.delete(0, tk.END)
      dir_entry.insert(0, newdirectory)
#      dir_label.configure(text=newdirectory)
      print("New directory:   " + newdirectory)
      globaldirname = newdirectory
      listbox.delete(0, tk.END)
      files = [f for f in os.listdir(newdirectory) if f.endswith('.edf')]
      selstring2 = np.zeros(len(files)) #Initialize file Selstring based on new Directory
      dir_listbox.insert(tk.END, folder_name)
      for file in files:
        listbox.insert(tk.END, file)
