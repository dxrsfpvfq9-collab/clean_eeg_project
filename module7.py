#clean_eeg_project
#12/19/2024

# module7.py
# called by watchdog
# takes a file  path that points to the edf file to be processed
# processes it without any user intervention
# takes as arguments the file name as a full path, and desired selstring
# calls new function edftotextbycommandplotproc.py that is parallel to edftotextbydirectoryplotproc.py


import os
import files.allocate_data_array
import files.edftotextbycommandplotproc
import importlib
import sys

# Color codes
RED = "\033[31m"
BLUE = "\033[34m"
RESET = "\033[0m"

# Reload modules
importlib.reload(files.allocate_data_array)
importlib.reload(files.edftotextbycommandplotproc)

# Allocate data array and process data
current_data = files.allocate_data_array.allocate_data_array(20, 512)
files.allocate_data_array.process_data_array(current_data)

print("data array allocated")

# Process data in subdirectory "data"
if len(sys.argv) > 1:
    argument = sys.argv[1]
    print(f"You passed the argument: {argument}")
else:
    print("No arguments passed")



#initialdir = os.getcwd()
#initialdir = "c:/users/tcollura/Dropbox/STS EEG Quality Assurance Reviews/tom misc testing/becky december 2024/ATB 11292024 EC post 01.000.02 AGE 55  EC.edf"

print("Got initialdir:", argument)

files.edftotextbycommandplotproc.edf_to_text_by_command_plot_proc(argument)

