#clean_eeg_project
#2/11/2023

# module6.py
# first thing you run
# will read in a directory of edf files and convert them to text files with plots

import os
import files.allocate_data_array
import files.edftotextbydirectoryplotproc
import importlib

# Color codes
RED = "\033[31m"
BLUE = "\033[34m"
RESET = "\033[0m"

# Reload modules
importlib.reload(files.allocate_data_array)
importlib.reload(files.edftotextbydirectoryplotproc)

# Allocate data array and process data
current_data = files.allocate_data_array.allocate_data_array(20, 512)
files.allocate_data_array.process_data_array(current_data)

# Process data in subdirectory "data"
initialdir = os.getcwd()
files.edftotextbydirectoryplotproc.edf_to_text_by_directory_plot_proc(initialdir)

# Print messages
print(RED + "Data array allocated." + RESET)
print(current_data[0][0])
print(RED + "Data array processed." + RESET)
print(BLUE + "Calling processor with: " + initialdir + RESET)
