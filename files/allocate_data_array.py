#clean_eeg_project
#2/11/2023
#allocate 2 seconds of 20channel eeg 256 samples/second

def allocate_data_array(rows, columns):

    datarray = [[0.0 for j in range(columns)] for i in  range(rows)]    
    return datarray


def process_data_array(datarray):
    datarray[0][0] = 1.0
    datarray[2][3] = 3.14


#current_data = allocate_data_array(20, 512)
#process_data_array(current_data)







