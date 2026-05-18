#file_svc.py
#file services for cleaneegproject
#2-20-2023

import os
import pyedflib
import openpyxl
from openpyxl import load_workbook
from openpyxl.chart import BarChart, Reference, ScatterChart
from openpyxl.drawing.image import Image
from pyedflib import highlevel
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.widgets
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
import files.file_svc
import process.detect_artifact
import process.tfcfilters
from scipy import signal
from scipy import stats
from scipy.signal import butter, lfilter, filtfilt
from collections import Counter

global electrode_names_orig

#  WRITE EEG DATA TO AN EXCEL FILE
def data_to_excel_file(name, data, n):
    excel_file = name + ".xlsx"
    writer = pd.ExcelWriter(excel_file, engine='xlsxwriter')

#    dfs = {'Sheet1': pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]}),
#           'Sheet2': pd.DataFrame({'C': [7, 8, 9], 'D': [10, 11, 12]})}#

    dfs = {'Sheet1': pd.DataFrame({'A': data[1][:256]}),
           'Sheet2': pd.DataFrame({'B': data[2][:256]})}

    for sheet_name, df in dfs.items():
      df.to_excel(writer, sheet_name=sheet_name, index=False)

    writer.close()



#  WRITE OUT METRICS FOR EACH PAGE IN AN EXCEL FILE

def page_metrics_to_excel_file(name, metrics, pageno, montage, metricnames):
    print("IN PAGE METRICS TO EXCEL FILE PAGE:  ", pageno)
    print("METRICS:  ", metrics)
    if montage == 0:
        excel_file = name + ".mts.xlsx"
    elif montage == 1:
        excel_file = name + ".avg.mts.xlsx"
    elif montage == 2:
        excel_file = name + ".lap.mts.xlsx"
    elif montage == 3:
        excel_file = name + ".lngb.mts.xlsx"
    elif montage == 4:
        excel_file = name + ".ica.mts.xlsx"
    elif montage == 5:
        excel_file = name + ".pca.mts.xlsx"
    elif montage == 6:
        excel_file = name + ".icale.mts.xlsx"
    else:
        excel_file = name + ".mts.xlsx"

   
#  CREATE THE PAGE SUMMARY EXCEL FILE AND POST THE FIRST PAGE OF METRICS
    if pageno == 1:
      if os.path.exists(excel_file):
        os.remove(excel_file)
      writer = pd.ExcelWriter(excel_file, engine='xlsxwriter')
      print("Creating summary file")

#      dfs = {'Sheet1': pd.DataFrame({'P1': metrics}),
#             'Sheet2': pd.DataFrame({'B': 2 * metrics})}
#

      dfs={'Sheet1': pd.DataFrame({'Metric': metricnames})}

      for sheet_name, df in dfs.items():
#        df.insert(0, column='Metric', value=metricnames)
        df.to_excel(writer, sheet_name=sheet_name, index=False)
      print("Summary file created")
      writer.close()
#  APPEND METRICS TO THE PAGE SUMMARY FILE
    
    print("Appending to summary file") 
    dfs = pd.read_excel(excel_file)
    num_rows = len(dfs.index)
    colname = "P" + str(pageno)
    #if colname not in dfs.columns:
    #metrics_padded = np.pad(metrics, (0, num_rows - len(metrics)), mode='constant')
    dfs.insert(loc=len(dfs.columns), column = colname, value=metrics)
    dfs.to_excel(excel_file, index=False)
    
def comps_to_excel_file(name, data_array):
    ''''''
    data_array = [item for sublist in data_array for item in sublist]
    data_array = [str(item) for item in data_array]
    excel_file = name + '.compmets.xlsx'
    names = ['Sites', 'RSI', 'Percentage', 'FFT Peaks', 'Lobes', 'Region', 'Area']
    print('--------------------------------------------------EXCEL FILE IS:', excel_file)
    if not os.path.exists(excel_file):
        writer = pd.ExcelWriter(excel_file, engine='xlsxwriter')
        print("Creating summary file")
    
        #dfs={'Sheet1': pd.DataFrame({'Metric': names})}

        #for sheet_name, df in dfs.items():
#         df.insert(0, column='Metric', value=metricnames)
        #  df.to_excel(writer, sheet_name=sheet_name, index=False)
        #print("Summary file created")
        writer.close()

    print("Appending to summary file") 
    dfs = pd.read_excel(excel_file)
    colname = "P" + str(len(dfs.columns))
    #if colname not in dfs.columns:
    #metrics_padded = np.pad(metrics, (0, num_rows - len(metrics)), mode='constant')
    dfs.insert(loc=len(dfs.columns), column = colname, value=data_array)
    dfs.to_excel(excel_file, index=False)
    return excel_file
    '''
    try:
        # Load the Excel file into a Pandas DataFrame
        xls = pd.ExcelFile(file_path)
    except FileNotFoundError:
        # If the file doesn't exist, create a new DataFrame and Excel file
        df = pd.DataFrame()
        df.to_excel(file_path, sheet_name="component metrics", index=False, engine='openpyxl')
        xls = pd.ExcelFile(file_path)

    # Check if the sheet "component metrics" exists, create it if not
    sheet_name = "component metrics"
    if sheet_name not in xls.sheet_names:
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            writer.book.create_sheet(sheet_name)

    # Load the Excel file again with the sheet now created
    xls = pd.ExcelFile(file_path)
    df = pd.read_excel(xls, sheet_name="component metrics")

    # Create a new column with the provided data
    col_name = f"Column_{df.shape[1] + 1}"
    df.insert(loc=len(df.columns), column=col_name, value=data_array)

    # Write the updated DataFrame back to the Excel file
    with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df.to_excel(writer, sheet_name="component metrics", index=False)
    #'''
    '''
    # Load the Excel workbook
    workbook = openpyxl.load_workbook(file_path)

    # Check if the sheet "component metrics" exists, create it if not
    sheet_name = "Component Metrics"
    if sheet_name not in workbook.sheetnames:
        workbook.create_sheet(sheet_name)

    # Get the "component metrics" sheet
    sheet = workbook[sheet_name]

    # Find the first available column
    #--------------------------------------------------
    #col_num = sheet.max_column + 1
    #-----------------------------------------------
    col_num = sheet.max_column + 1 if sheet.max_column else 1
    #-----------------------------------------------------
    #col_num = 1
    #while sheet.cell(row=1, column=col_num).value is not None:
    #    col_num += 1

    # Add data to the first available column
    for i, item in enumerate(data_array):
        sheet.cell(row=i + 1, column=col_num, value=item)

    # Save the updated workbook
    workbook.save(file_path)
    #'''
def histograms_to_comps_file(file_path):
    df = pd.read_excel(file_path)
    workbook = load_workbook(file_path)
    start_row = 77
    end_row = 95
    start_column = 1
    histogram_sheet = workbook.create_sheet(title="Histograms")

    for comp_row in range(start_row-1, end_row):
        values = df.iloc[comp_row, start_column - 1:].dropna().tolist()
        values = [float(num) for num in values]
        length_val = len(values)
        start = length_val * 0.05
        end = length_val * 0.95
        sorted_vals = np.sort(values)
        values = np.sort(values)
        values = sorted_vals[int(np.floor(start)):int(np.floor(end))]
        print('VALUES: ', values)
        # Calculate the range of values
        min_val = min(value for value in values if value is not None)
        max_val = max(value for value in values if value is not None)

        num_bins = 10
        bins_width = (max_val-min_val)/num_bins
        bins = [min_val + i * bins_width for i in range(num_bins+1)]
        frequencies = [0] * num_bins

        for value in values:
            for i in range(num_bins):
                if i == num_bins - 1:
                    if bins[i] <= value <= bins[i + 1]:
                        frequencies[i] += 1
                        break
                else:
                    if bins[i] <= value < bins[i + 1]:
                        frequencies[i] += 1
                        break

        histogram_sheet.append([f"Metric {comp_row + 1}"] + bins)
        histogram_sheet.append(["Frequency"] + frequencies)

        bar_chart = BarChart()
        bar_chart.title = f"Component {comp_row - 75} Depth"
        bar_chart.y_axis.title = "Frequency"

        bar_chart.width = 8
        bar_chart.height = 5
        # Create references for x (bins) and y (frequencies)
        x_values_ref = Reference(histogram_sheet, min_col=2, min_row=comp_row * 2 + 1, max_row=None, max_col=num_bins + 1)
        y_values_ref = Reference(histogram_sheet, min_col=2, min_row=(comp_row-75)*2, max_row=None, max_col=num_bins + 1)

        # Add data to the bar chart
        bar_chart.add_data(y_values_ref, titles_from_data=False)
        bar_chart.set_categories(x_values_ref)


        # Add the bar chart to the histogram sheet
        histogram_sheet.add_chart(bar_chart, f"A{1+(comp_row - 76) * 10}")

        data = values
        data = np.sort(data)
        mean = np.mean(data)
        std = np.std(data)

        # Calculate the expected quantiles for a Gaussian distribution
        expected_quantiles = stats.norm.ppf(np.linspace(0.01, 0.99, len(data)), loc=mean, scale=std)

        cor_coef = np.corrcoef(expected_quantiles, data)[0,1]

        plt.figure(figsize=(8, 6))
        plt.scatter(expected_quantiles, data, marker='o', s=25, color='blue', label='Data Q-Q Plot')
        plt.plot([min(expected_quantiles), max(expected_quantiles)], [min(expected_quantiles), max(expected_quantiles)], color='red', linestyle='--', label='Ideal Q-Q Line')
        plt.xlabel('Theoretical Quantiles')
        plt.ylabel('Sample Quantiles')
        plt.title(f'Q-Q Plot - {comp_row - 75} --- {cor_coef}')
        plt.legend()
        plt.grid(True)

        # Save the Q-Q plot as an image file (e.g., PNG)
        image_file_path =f'qq_plot_dataset_{comp_row - 76}.png'
        #print(dirpath)
        #print(image_file_path)
        plt.savefig(image_file_path, format='png', dpi=300, bbox_inches='tight')
        plt.close()  # Close the plot to release memory

        # Embed the Q-Q plot as an image in the Excel worksheet
        img = Image(image_file_path)
        img.anchor = f'F{1+(comp_row - 76) * 11}'  # Adjust the cell reference as needed
        img.width = 3*80
        img.height = 3*72
        
        histogram_sheet.add_image(img)

    start_row = 1
    end_row = 19
    possible_strings = ['FP1', 'FP2', 'F7', 'F3', 'FZ', 'F4', 'F8', 'T3', 'C3', 'CZ', 'C4', 'T4', 'T5', 'P3', 'PZ', 'P4', 'T6', 'O1', 'O2']
    histogram_sheet.append([''] + possible_strings)
    for comp_row in range(start_row-1, end_row):
        sites = df.iloc[comp_row, start_column - 1:].tolist()
        counts = [sites.count(string) for string in possible_strings]
        #print('C:', counts)
        histogram_sheet.append([f"Sites {comp_row + 1}"] + counts)

        bar_chart = BarChart()
        bar_chart.title = f"Component {comp_row +1} Sites"
        bar_chart.y_axis.title = "Frequency"

        bar_chart.width = 8
        bar_chart.height = 5

        data = Reference(histogram_sheet, min_col=2, min_row=comp_row + 40, max_row=None, max_col=20)
        labels = Reference(histogram_sheet, min_col=2, min_row=39, max_row=None, max_col=20)
        #print('D:', data)
        bar_chart.add_data(data, titles_from_data=False)
        #bar_chart.set_categories(labels)
        histogram_sheet.add_chart(bar_chart, f"J{1+(comp_row) * 10}")

    start_row = 153
    end_row = 171
    possible_strings = ['SMR', 'PDR', 'Temporal Alpha', 'Frontal Midline Theta', 'Temporal Theta', 'Frontal Theta', 'Mu', 'Blink', 'Lateral', 'Delta', 'Alpha', 'Other']
    for comp_row in range(start_row-1, end_row):
        sites = df.iloc[comp_row, start_column - 1:].tolist()
        counts = [sites.count(string) for string in possible_strings]
        #print('C:', counts)
        histogram_sheet.append([f"Rythm {comp_row + 1}"] + counts)

        bar_chart = BarChart()
        bar_chart.title = f"Component {comp_row - 151} Rythms"
        bar_chart.y_axis.title = "Frequency"

        bar_chart.width = 8
        bar_chart.height = 5

        data = Reference(histogram_sheet, min_col=2, min_row=(comp_row-152) + 59, max_row=None, max_col=13)
        #print('D:', data)
        bar_chart.add_data(data, titles_from_data=False)

        histogram_sheet.add_chart(bar_chart, f"O{1+(comp_row-152) * 10}")
       
    start_row = 134
    end_row = 152
    possible_strings = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '13', '17', '18', '19', '20', '21', '22', '23', '24', '25', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40', '41', '42', '43', '44', '45', '46', '47']
    for comp_row in range(start_row-1, end_row):
        sites = df.iloc[comp_row, start_column - 1:].tolist()
        #counts = [str(sites.count(string)) for string in possible_strings]  
        counts = [0] * len(possible_strings)
    
        for i, string in enumerate(possible_strings):
            for site in sites:
                if str(site).strip() == string:  # Ensure we're comparing strings
                    counts[i] += 1
    
    # Convert counts to strings
        #counts = [str(count) for count in counts]
        print('C:', counts)
        histogram_sheet.append([f"Areas {comp_row + 1}"] + counts)

        bar_chart = BarChart()
        bar_chart.title = f"Component {comp_row - 132} Areas"
        bar_chart.y_axis.title = "Frequency"

        bar_chart.width = 8
        bar_chart.height = 5

        data = Reference(histogram_sheet, min_col=2, min_row=(comp_row-133) + 78, max_row=None, max_col=43)
        print('D:', data)
        bar_chart.add_data(data, titles_from_data=False)

        histogram_sheet.add_chart(bar_chart, f"T{1+(comp_row-133) * 10}")
    
    workbook.save(file_path)

def histogram_to_excel_file(file_path):
    df = pd.read_excel(file_path)
    workbook = load_workbook(file_path)
    worksheet = workbook['Sheet1']
    #dirpath = os.path.dirname(file_path)
    start_row = 5
    end_row = 55
    start_column = 3
    names_list = ['STD Orig', 'Raw-Recon Diff', 'Raw-Clean Diff', 'Percentage Removed', 'STD Raw', 'Global STD', 'PDR Symmetry', 'PDR Synchrony', 'PDR Regulation', 'PDR Magnitude',
                  'PDR Sinusoidal', 'PDR Max Post.', 'PDR FFT Width', 'PDR Amplitude', 'PDR Artifact Width', 'Beta Max Front', 'Front Alpha Asym', 'XS Temp. Alpha', 'Fast Alpha', 'Midline Beta', 'Focal Delta Index', 'Focal Delta Amplitude', 'Focal Theta Index',
                  'Focal Theta Amplitude', 'Focal HiBeta Ind.', 'Focal HiBeta Amp.', 'Focal Beta Ind.', 'Focal Beta Amp.', 'Frontal Delta', 'Frontal Theta', 'Frontal Gamma', 'Front Gamma Asym',
                  'Diffuse Delta', 'Diffuse Theta', 'Diffuse HiBeta', 'Diffuse Beta', 'Diffuse Gamma', '60hz Diffuse', 'Fractal Dimension', 'PDR Moment 1', 'PDR Moment 2', 'PDR Moment 3',
                  'Beta Moment 1', 'Beta Moment 2', 'Beta Moment 3', 'Theta Moment 1', 'Theta Moment 2', 'Theta Moment 3', 'Delta Moment 1', 'Delta Moment 2', 'Delta Moment 3']
    histogram_sheet = workbook.create_sheet(title="Histograms")

    for metric_row in range(start_row-1, end_row):
        values = df.iloc[metric_row, start_column - 1:].dropna().tolist()
        #print("BEFORE", values)
        length_val = len(values)
        start = length_val * 0.05
        end = length_val * 0.95
        print('START', start)
        print('END', end)
        sorted_vals = np.sort(values)
        values = sorted_vals[int(np.floor(start)):int(np.floor(end))]
        #print('AFTER', values)
        statistic, p_val = stats.kstest(values, 'norm')
        #print ("Metric", metric_row-1)
        print("K-S Stat: ", statistic)
        print("P-value: ", p_val)
        # Skip rows with no valid data
        if all(value is None for value in values):
            continue
        '''
        if metric_row == 15 or metric_row == 16: # or metric_row == 12:
            print('in 12')
            for i in range(len(values)):
                values[i] = np.cbrt(values[i])
        if metric_row == 11: # or metric_row == 12:
            for i in range(len(values)):
                values[i] = np.square(values[i])
        '''
        # Calculate the range of values
        min_val = min(value for value in values if value is not None)
        max_val = max(value for value in values if value is not None)

        num_bins = 10
        bins_width = (max_val-min_val)/num_bins
        bins = [min_val + i * bins_width for i in range(num_bins+1)]
        frequencies = [0] * num_bins

        for value in values:
            for i in range(num_bins):
                if i == num_bins - 1:
                    if bins[i] <= value <= bins[i + 1]:
                        frequencies[i] += 1
                        break
                else:
                    if bins[i] <= value < bins[i + 1]:
                        frequencies[i] += 1
                        break

        histogram_sheet.append([f"Metric {metric_row + 1}"] + bins)
        histogram_sheet.append(["Frequency"] + frequencies)

        bar_chart = BarChart()
        bar_chart.title = names_list[metric_row-4]
        bar_chart.y_axis.title = "Frequency"

        bar_chart.width = 8
        bar_chart.height = 5
        # Create references for x (bins) and y (frequencies)
        x_values_ref = Reference(histogram_sheet, min_col=2, min_row=metric_row * 2 + 1, max_row=None, max_col=num_bins + 1)
        y_values_ref = Reference(histogram_sheet, min_col=2, min_row=(metric_row-3)*2, max_row=None, max_col=num_bins + 1)

        # Add data to the bar chart
        bar_chart.add_data(y_values_ref, titles_from_data=False)
        bar_chart.set_categories(x_values_ref)


        # Add the bar chart to the histogram sheet
        histogram_sheet.add_chart(bar_chart, f"A{1+(metric_row - 4) * 10}")
        
        data = values
        data = np.sort(data)
        mean = np.mean(data)
        std = np.std(data)

        # Calculate the expected quantiles for a Gaussian distribution
        expected_quantiles = stats.norm.ppf(np.linspace(0.01, 0.99, len(data)), loc=mean, scale=std)

        cor_coef = np.corrcoef(expected_quantiles, data)[0,1]

        plt.figure(figsize=(8, 6))
        plt.scatter(expected_quantiles, data, marker='o', s=25, color='blue', label='Data Q-Q Plot')
        plt.plot([min(expected_quantiles), max(expected_quantiles)], [min(expected_quantiles), max(expected_quantiles)], color='red', linestyle='--', label='Ideal Q-Q Line')
        plt.xlabel('Theoretical Quantiles')
        plt.ylabel('Sample Quantiles')
        plt.title(f'Q-Q Plot - {names_list[metric_row-4]} --- {cor_coef}')
        plt.legend()
        plt.grid(True)

        # Save the Q-Q plot as an image file (e.g., PNG)
        image_file_path =f'qq_plot_dataset_{names_list[metric_row-4]}.png'
        #print(dirpath)
        #print(image_file_path)
        plt.savefig(image_file_path, format='png', dpi=300, bbox_inches='tight')
        plt.close()  # Close the plot to release memory

        # Embed the Q-Q plot as an image in the Excel worksheet
        img = Image(image_file_path)
        img.anchor = f'F{1+(metric_row - 4) * 11}'  # Adjust the cell reference as needed
        img.width = 3*80
        img.height = 3*72
        
        histogram_sheet.add_image(img)
        
        #os.remove(image_file_path)
        #histogram_sheet.append([metric_row + 1] + frequencies)
        #histogram_sheet.add_chart(chart, f'F{1+(metric_row-10)*10}')
        #print('BINS:', bins)
        #print("FREQUENCIES:", frequencies)
        # Create a bar chart using the histogram data

    # Save the modified workbook
    workbook.save(file_path)   
    #df = pd.read_excel(file_path)
    #workbook = load_workbook(file_path)
    #worksheet = workbook['Sheet1']

    #start_row = 11
    #end_row = 20
    #start_column = 3

    #histogram_sheet = workbook.create_sheet(title="Histograms")
    #chart_row = 2
    #for metric_row in range(start_row-1, end_row):
    #    values = df.iloc[metric_row, start_column - 1:].dropna().tolist()
    
        # Skip rows with no valid data
    #    if all(value is None for value in values):
    #        continue

        # Calculate the range of values
    #    min_val = min(value for value in values if value is not None)
    #    max_val = max(value for value in values if value is not None)

    #    num_bins = 10
    #    bins_width = (max_val-min_val)/num_bins
    #    bins = [min_val + i * bins_width for i in range(num_bins+1)]
    #    frequencies = [0] * num_bins

    #    for value in values:
    #        for i in range(num_bins):
    #            if i == num_bins - 1:
    #                if bins[i] <= value <= bins[i + 1]:
    #                    frequencies[i] += 1
    #                    break
    #            else:
    #                if bins[i] <= value < bins[i + 1]:
    #                    frequencies[i] += 1
    #                    break

        #frequencies, bins = np.histogram(values, bins=10)
        
    #    histogram_sheet.cell(row=chart_row, column=1, value=f"Metric {metric_row + 1}")
    #    for i, freq in enumerate(frequencies):
    #        histogram_sheet.cell(row=chart_row + 1, column=i + 2, value=freq)

        # Create a bar chart
    #    bar_chart = BarChart()
    #    data = Reference(histogram_sheet, min_col=2, min_row=chart_row + 1, max_row=chart_row + 1,
    #                 max_col=len(bins) + 1)
    #    categories = Reference(histogram_sheet, min_col=1, min_row=chart_row+1, max_row=chart_row+1,
    #                       max_col=1)
    #    bar_chart.add_data(data, titles_from_data=True)
    #    bar_chart.set_categories(categories)

        # Append the chart to the histogram sheet
    #    histogram_sheet.add_chart(bar_chart, f"F{chart_row}")

        # Move to the next row for the next chart
    #    chart_row += 14
        
        #histogram_sheet.append([metric_row + 1] + frequencies)
        
    #    print('BINS:', bins)
    #    print("FREQUENCIES:", frequencies)
        # Create a bar chart using the histogram data

    # Save the modified workbook
    #workbook.save(file_path)
    
#  WRITE OUT LISTS OF METRICS TO EXCEL FILE, INCLUDING MAIN DATABASE
def metrics_to_excel_file(name, metrics, plot_num, montage, database_name):

    if montage == 0:
        excel_file = name + ".met.xlsx"
        out_file = "./" + database_name +".out_file.le.xlsx"
        name_file = "./" + database_name +".names_file.le.xlsx"
    elif montage == 1:
        excel_file = name + ".avg.met.xlsx"
        out_file = "./" + database_name +".out_file.avg.xlsx"
        name_file = "./" + database_name +".names_file.avg.xlsx"
    elif montage == 2:
        excel_file = name + ".lap.met.xlsx"
        out_file = "./" + database_name +".out_file.lap.xlsx"
        name_file = "./" + database_name +".names_file.lap.xlsx"
    elif montage == 3:
        excel_file = name + ".lngb.met.xlsx"
        out_file = "./" + database_name +".out_file.lngb.xlsx"
        name_file = "./" + database_name +".names_file.lngb.xlsx"
    elif montage == 4:
        excel_file = name + ".ica.met.xlsx"
        out_file = "./" + database_name +".out_file.ica.xlsx"
        name_file = "./" + database_name +".names_file.ica.xlsx"
    elif montage == 5:
        excel_file = name + ".pca.met.xlsx"
        out_file = "./" + database_name +".out_file.pca.xlsx"
        name_file = "./" + database_name +".names_file.pca.xlsx"
    elif montage == 6:
        excel_file = name + ".icale.met.xlsx"
        out_file = "./" + database_name +".out_file.icale.xlsx"
        name_file = "./" + database_name +".names_file.icale.xlsx"
    else:
        excel_file = name + ".met.xlsx"
        out_file = "./" + database_name +".out_file.xlsx"
        name_file = "./" + database_name +".names_file..xlsx"
    print('OUTFILE: ', out_file)

    writer = pd.ExcelWriter(excel_file, engine='xlsxwriter')

    dfs = {'Sheet1': pd.DataFrame({'A': metrics}),
           'Sheet2': pd.DataFrame({'B': 2 * metrics})}

    for sheet_name, df in dfs.items():
      df.to_excel(writer, sheet_name=sheet_name, index=False)

# APPEND METRICS TO SHARED OUTPUT FILE AND INDIVIDUAL FILE
    if not os.path.isfile(out_file):
        formulas=['=AVG(A2:A5)', '=AVG(B2:B5)', '=AVG(C2:C5)', '=AVG(D2:D5)', '=AVG(E2:E5)', '=AVG(F2:F5)',
                    '=AVG(G2:G5)', '=AVG(H2:H5)', '=AVG(I2:I5)', '=AVG(B2:B5)', '=AVG(B2:B5)', '=AVG(B2:B5)',
                    '=AVG(A2:A5)', '=AVG(B2:B5)', '=AVG(C2:C5)', '=AVG(B2:B5)', '=AVG(B2:B5)', '=AVG(B2:B5)',
                    '=AVG(A2:A5)', '=AVG(B2:B5)', '=AVG(C2:C5)', '=AVG(B2:B5)', '=AVG(B2:B5)', '=AVG(B2:B5)',
                    '=AVG(A2:A5)', '=AVG(B2:B5)', '=AVG(C2:C5)', '=AVG(B2:B5)', '=AVG(B2:B5)', '=AVG(B2:B5)',
                    '=AVG(A2:A5)', '=AVG(B2:B5)', '=AVG(C2:C5)', '=AVG(B2:B5)', '=AVG(B2:B5)', '=AVG(B2:B5)',
                    '=AVG(A2:A5)', '=AVG(B2:B5)', '=AVG(C2:C5)', '=AVG(B2:B5)', '=AVG(B2:B5)', '=AVG(B2:B5)',
                    '=AVG(A2:A5)', '=AVG(B2:B5)', '=AVG(C2:C5)', '=AVG(B2:B5)', '=AVG(B2:B5)', '=AVG(B2:B5)',
                    '=AVG(A2:A5)', '=AVG(B2:B5)', '=AVG(C2:C5)', '=AVG(C2:C5)', '=AVG(C2:C5)', '=AVG(C2:C5)', '=AVG(C2:C5)'] 

        df = pd.DataFrame({'STD DEV': formulas[:]})
#        df[0,'CALC'] = 'AVG(Column1, Column5)'
        df.insert(0, column = 'AVG', value=formulas)
#        df.loc[0, 'CALC'] = formulas
        df.to_excel(out_file, index=False)
 
    if not os.path.isfile(name_file):
        df = pd.DataFrame()
        df.to_excel(name_file, index=False)
 
#  WRITE OUT THE EXCEL FILE WITH  THE METRICS FOR THIS RECORDING
    df = pd.read_excel(out_file)
    num_rows = len(df.index)
    colname = "C" + str(plot_num)
    df.insert(loc=len(df.columns), column = colname, value=metrics)
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    def remove_outliers(row):
        sorted_values = np.sort(row)
        n = len(sorted_values)
        num_excluded = int(0.05*n)
        new_row = sorted_values[num_excluded:-num_excluded]
        return new_row.mean(), new_row.std()
    
    avg_std_vals = df.iloc[:, 2:].apply(remove_outliers, axis = 1)

    avg_column = avg_std_vals.apply(lambda x: x[0])
    std_column = avg_std_vals.apply(lambda x: x[1])
    
    #avg_column = df.iloc[:, 2:].mean(axis=1)
    #std_column = df.iloc[:, 2:].std(axis=1)
    
    df["AVG"] = avg_column
    df["STD DEV"] = std_column
    
    df.to_excel(out_file, index=False)

#  IF YOU WANT TO KNOW HOW MANY NONZEROCOLUMNS WE HAVE
#    nonzero_cols = (df.astype(bool).sum(axis=0) > 0).sum()

#  NICE TO WRITE FORMULAS HERE FOR MEAN AND STANDARD DEVIATIONS

#  WRITE AN EXCEL FILE WITH ALL THE FILE NAMES FOR THIS BATCH
    df = pd.read_excel(name_file)
    num_rows = len(df.index)
    colname = name
#    df.insert(loc=0, column = name, value=name)
#    df.loc[len(df)] = name
    rowname = "R" + str(plot_num)

#  this  worked
    df.loc[plot_num, 0] = name

#    df.append(pd.Series(name, index=0), ignore_index=True)
#    df.insert(loc=num_rows, row = name, value=name)
    df.to_excel(name_file, index=False)

#    df['New Column'] = metrics
#    cols=df.columns.tolist()
#    cols=cols[:-1]+cols[-1:]
#    df = df[cols]
#    df.to_excel('./out_file.xlsx', index=False)

    writer.close()
    return out_file

#  WRITE OUT A TEXT FILE CONTAINING THE EEG DATA
def data_to_text_file(name, data, n):
    text_file = name + ".txt"
    print("writing file")
    # Write the data to a text file
    with open(text_file, 'w') as outfile:
        for i in range(n):
            outfile.write('Channel {}\n'.format(i + 1))
#            for j in range(len(data[i])):
            for j in range(256):
                outfile.write('{} '.format(data[i][j]))
    print("done writing file")

#  CONVERT AN ARRAY OF NUMBERS TO A STRING OF TEXT
def array_to_text(array):
    text = ''
    for row in array:
        text += ' '.join([str(x) for x in row]) + '\n'
    return text

def add_text_to_plot(text):
    fig, ax = plt.subplots()
    ax.text(0.5, 0.5, text, transform=ax.transAxes, ha='center', va='center')
    plt.show()


def write_markers_to_file(markers, filename):
    with open(filename, 'w') as f:
        for marker in markers:
            f.write(str(marker) + '\n')

#  CONVERT AN ARRAY OF FLAGS TO A LIST OF MARKERS OF MINIMUM LENGTH
def flag_to_marker(flags, length):
    markers = []
    start = 0
    count = 0
    for i, flag in enumerate(flags):
        if flag:
            count += 1
        else:
            if count >= length:
                markers.append((start, count))
            start = i + 1
            count = 0
    if count >= length:
        markers.append((start, count))
    return markers


def onselect(xmin, xmax):
    print("Selection from x=%s to x=%s" % (xmin, xmax))

def get_statistics(numbers):
    """
    Compute the mean, median, and standard deviation of a list of numbers.
    """
    mean = sum(numbers) / len(numbers)
    median = sorted(numbers)[len(numbers)//2]
    variance = sum((x - mean)**2 for x in numbers) / len(numbers)
    std_dev = variance**0.5
    return mean, median, std_dev

def setup_electrode_names(n, name, electrode_names, electrode_names_orig, montage):

#   INSERT CORRECT CHANNEL LABELS BASED ON THE MONTAGE USED
#   AVERAGE REFERENCE MONTAGE
  
    if montage == 0 or montage == 6:
        for i in  range(n):
#            print(electrode_names_orig[i])
            electrode_names[i] = electrode_names_orig[i]

    elif montage == 1:
        for i in range(19):
          electrode_names[i] = electrode_names[i].replace('LE', 'AV')

#   LAPLACIAN MONTAGE
    elif montage == 2:
         electrode_names[0] = 'EEG Fp1-LA'
         electrode_names[1] = 'EEG F7-LA'
         electrode_names[2] = 'EEG T3-LA'
         electrode_names[3] = 'EEG T5-LA'
         electrode_names[4] = 'EEG O1-LA'
         electrode_names[5] = 'EEG F3-LA'
         electrode_names[6] = 'EEG C3-LA'
         electrode_names[7] = 'EEG P3-LA'
         electrode_names[8] = 'EEG Fp2-LA'
         electrode_names[9] = 'EEG F8-LA'
         electrode_names[10] = 'EEG T4-LA'
         electrode_names[11] = 'EEG T6-LA'
         electrode_names[12] = 'EEG O2-LA'
         electrode_names[13] = 'EEG F4-LA'
         electrode_names[14] = 'EEG C4-LA'
         electrode_names[15] = 'EEG P4-LA'
         electrode_names[16] = 'EEG Fz-LA'
         electrode_names[17] = 'EEG Cz-LA'
         electrode_names[18] = 'EEG Pz-LA'

#   DOUBLE BANANA TRANSVERSE MONTAGE
    elif montage == 3:
         electrode_names[0] = 'EEG Fp1-F7'
         electrode_names[1] = 'EEG F7-T3'
         electrode_names[2] = 'EEG T3-T5'
         electrode_names[3] = 'EEG T5-O1'
         electrode_names[4] = 'EEG Fp1-F3'
         electrode_names[5] = 'EEG F3-C3'
         electrode_names[6] = 'EEG C3-P3'
         electrode_names[7] = 'EEG P3-O1'
         electrode_names[8] = 'EEG Fp2-F8'
         electrode_names[9] = 'EEG F8-T4'
         electrode_names[10] = 'EEG T4-T6'
         electrode_names[11] = 'EEG T6-O2'
         electrode_names[12] = 'EEG Fp2-F4'
         electrode_names[13] = 'EEG F4-C4'
         electrode_names[14] = 'EEG C4-P4'
         electrode_names[15] = 'EEG P4-O2'
         electrode_names[16] = 'EEG Fz-Cz'
         electrode_names[17] = 'EEG Cz-Pz'
         electrode_names[18] = 'EEG Fz-Pz'

#   ICA INDEPENDENT COMPONENTS ANALYSIS "MONTAGE"
    elif montage == 4:
         for i in range(n):
           electrode_names[i] = 'ICA C' + str(i+1) 
    elif montage == 5:
         for i in range(n):
           electrode_names[i] = 'PCA C' + str(i+1)

    if montage == 0:
        pdf_filename =  name + ".le.plts.pdf"
    elif montage == 1:
        pdf_filename =  name + ".avg.plts.pdf"
    elif montage == 2:
        pdf_filename =  name + ".lap.plts.pdf"
    elif montage == 3:
        pdf_filename =  name + ".lngb.plts.pdf"
    elif montage == 4:
        pdf_filename =  name + ".ica.plts.pdf"
    elif montage == 5:
        pdf_filename =  name + ".pca.plts.pdf"
    elif montage == 6:
        pdf_filename =  name + ".icale.plts.pdf"
    else:
        pdf_filename =  name + ".plts.pdf"

    return electrode_names, pdf_filename



