from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors, utils
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Table, TableStyle, Spacer, Image, SimpleDocTemplate, PageBreak
from process.detect_artifact import detect_peak
import tkinter as tk
import matplotlib.pyplot as plt
#from files.dummy_gui import dummy_gui
from PIL import ImageGrab
from PIL import Image
import io
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.backends.backend_pdf import FigureCanvasPdf
from matplotlib.patches import Rectangle
from matplotlib.figure import Figure
import numpy as np
import datetime
import os
import pandas as pd

def create_report_pdf(name, short_name, channel_labels_short, name_strings, range_strings, report_strings, metrics, montage, excel_file_path, n, numpages, myvisualsigs, electrode_names):

    # Create a new PDF file
    if montage == 0:
       fname = name + ".le.rep.pdf"
    elif montage == 1:
       fname = name + ".avg.rep.pdf"
    elif montage == 2:
       fname = name + ".lap.rep.pdf"
    elif montage == 3:
       fname = name + ".lngb.rep.pdf"
    elif montage == 4:
       fname = name + ".ica.rep.pdf"
    elif montage == 5:
       fname = name + ".pca.rep.pdf"
    elif montage == 6:
       fname = name + ".icale.rep.pdf"
    else:
       fname = name + ".rep.pdf"

    print("PDF:  ", fname)
    pdf_file = canvas.Canvas(fname, pagesize=letter)
    width, height = letter

    # Set up some styles for the text and tables
    style_sheet = getSampleStyleSheet()
    normal_style = style_sheet['Normal']
    #print(style_sheet)
    #bold_style = style_sheet['Bold']

    # Add some text to the PDF file
    pdf_file.setFont("Helvetica", 14)
    # pdf_file.drawString(15, 770, "BrainMaster EEG Pre-QEEG Auto Scan Report (c) 2023")
    pdf_file.drawString(15, 770, "BrainML (Machine Learning) Brain Panel Report (c) 2025")

    pdf_file.setFont("Helvetica", 10)
    pdf_text = 'Database Used: ' + str(os.path.basename(excel_file_path))
    pdf_file.drawString(385, 775, pdf_text)

    df = pd.read_excel(excel_file_path, sheet_name='Sheet1')
    num_files = df.shape[1] - 2
    pdf_text1 =  'Number of files: '+str(num_files)
    pdf_file.drawString(385, 763, pdf_text1)

    # Add a paragraph of text to the PDF file
    normal_style.fontSize = 9
    paragraph = Paragraph("This report provides quantitative estimation of how well this EEG meets the expectations of a visual quality review by a clinical neurophysiologist", normal_style)
#    paragraph += Paragraph("It is based on calculations using signal processing methods to extract metrics related to the abundance and timing of recognized rhythms and patterns", normal_style)
    paragraph.wrapOn(pdf_file, 600, 100)
    paragraph.drawOn(pdf_file, 15, 750)
    short_name = short_name.split('/')[-1] if '/' in short_name else short_name.split('\\')[-1]
    paragraph = Paragraph('Name: ' + short_name, normal_style)
    paragraph.wrapOn(pdf_file, 400, 100)
    paragraph.drawOn(pdf_file, 305, 730)
    current_datetime = datetime.datetime.now()
    formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    paragraph = Paragraph('Date: ' + formatted_datetime, normal_style)
    paragraph.wrapOn(pdf_file, 400, 100)
    paragraph.drawOn(pdf_file, 475, 730)

#   HERE IS WHERE WE UNPACK THE REPORT STRINGS AND PUT THEM ON THE PAGE
    """
    for i in range(len(report_strings)):
       paragraph= Paragraph(report_strings[i])
       paragraph.wrapOn(pdf_file, 400, 100)
       paragraph.drawOn(pdf_file, 130, 580 - 11 * i)
    """
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#   CREATE A TABLE THAT USES THE NAMES OF THE TESTS AND THE RESULTS AS THE ENTRIES
    #metricstring=', '.join(['{:.2f}'.format(num) for num in metrics])
    #print(metricstring)
    #datat = allocate_data_4x12()
    #datat[0] = ["Parameter", "Range", "Info", "Result"]
    #for i in range (0,10):
    #    thismetric = '{:.2f}'.format(metrics[10+i])
    #    datat[i+1] = [name_strings[i], range_strings[i], thismetric, report_strings[i+1]]        


    #tablet = Table(datat[:][:])
    #tablet.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    #                       ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    #                       ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    #                       ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #                       ('FONTSIZE', (0, 0), (-1, 0), 10),
    #                       ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    #                       ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    #                       ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
    #                       ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
    #                       ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    #                       ('FONTSIZE', (0, 1), (-1, -1), 10),
    #                       ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    #                       ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    #tablet.wrapOn(pdf_file, 400, 100)
    #tablet.drawOn(pdf_file, 100, 200)

    #pdf_file.showPage()
    high_sentences =  ['The power in the raw EEG is exhibited to be high in comparison to other individuals. this may be artifact, but is not a concern',
                      'The power in the filtered EEG is exhibited to be high in comparison to other individuals. this may be artifact but is not a concern',
                      'PDR symmetry reflects the left right balance of the brain activity, extreme symmetry is not a concern',
                      'PDR synchrony reflects the precise timing of the left right brain activity, high synchrony is not a concern, may an asset',
                      'PDR regulation reflects the momentary variations in the left right brain activity, well regulated EEG is not a concern, may be an asset',
                      'PDR magnitude reflects the size of brain activity, a high value may be a concern (chronic anxiety coping, possibly meditation, may be an asset )',
                      'PDR sinusoidal reflects the spectral purity of brain activity, a high value is not a concern, may be an asset',
                      'PDR max posterior reflects the front back balance of relaxed brain activity, a high value is not a concern, may be an asset',
                      'PDR FFT Width is high, a high value suggests extreme variability or lack of PDR bursting or frequency instability',
                      'PDR maximum amplitude is high, may suggest hyper-relaxation or underfocused tendencies, may be meditation, may be an asset',
                      'PDR burst width is wide, this may reflect hyper-relaxation or poor regulation',
                      'Beta max front reflects the front back balance of active brain activity, a high value may be a concern (excess frontal beta, anxiety)',
                      'Frontal alpha asymmetry reflects the emotional balance while at rest, a high value may be a concern (negative affect)',
                      'Excess temporal alpha reflects possible atypical alpha activity, a high value may be a concern (affect, language)',
                      'Alpha speed reflects the speed of background processing, fast alpha may be a concern (anxiety)',
                      'Alpha peak reflects the speed of background processing, fast alpha may be a concern (anxiety)',
                      'Midline Beta reflects conscious processing, a high value may indicate spindling excess beta',
                      'Focal delta index reflects localized the slow activity is, a high value may be a concern (sleep, TBI, stroke, injury)',
                      'Focal delta amplitude reflects the amout of focal slow activity, a high value may be a concern (sleep, TBI, stroke, injury)',
                      'Focal theta index reflects localized dysfunction, a high value may be a concern (sleep, TBI, stroke, injury)',
                      'Focal theta amplitude reflects localized dysfunction, a high value may be a concern (sleep, TBI, stroke, injury)',
                      'Focal hibeta index reflects the local dysfunction (overactivity), a high value may be a concern (headaches, cognitive issues)',
                      'Focal hibeta amplitude reflects the local dysfunction (overactivity), a high value may be a concern (headaches, cognitive issues)',
                      'Focal beta index reflects the local dysfunction (overactivity), a high value may be a concern (headaches, cognitive issues)',
                      'Focal beta amplitude reflects the local dysfunction (overactivity), a high value may be a concern (headaches, cognitive issues)',
                      'Frontal delta reflects the frontal dysfunction (attention, mood, executive), a high value may be a concern (frontal underactivation)',
                      'Frontal theta reflects the frontal dysfunction (attention, mood, executive), a high value may be a concern (frontal underactivation)',
                      'Frontal gamma reflects the activation of exectutive and attention networks, a high value may reflect overactivation',
                      'Frontal gamma asymmetry reflects the regulation, a high value may suggest extreme approach/positive affect/risk-taking',
                      'Diffuse delta reflects generalized slow waves (metabolic/injury), excess may be a concern (encephalopathy, TBI, toxicity)',
                      'Diffuse theta reflects generalized slow waves (attention, excecutive), excess may be a concern (toxicity, encephalopathy, TBI)',
                      'Diffuse hibeta reflects generalized overactivity (busy brain), a high value may be a concern (anxiety, headaches, allergy, drug effect)',
                      'Diffuse beta reflects the generalized overactivity (cognitive, externalized), a high value may be a concern (anxiety, agitation)',
                      'Diffuse gamma reflects the activation of general networks, a high value may reflect overactivation',
                      '60hz artifact reflects the environmental interference a high value reflects a high level if interference',
                      'Fractal dimension reflects the complexity of brain activity, a high value may suggest more complex cortical processing',
                      'PDR moment 1 reflects the amount of resting brain activity, a high value may be a concern (chronic anxiety)',
                      'PDR moment 2 reflects the time course of the PDR, a high value may suggest hyper-relaxation or underfocused tendencies',
                      'PDR moment 3 reflects the PDR shift throughout the EEG, a high value may indicate drowsiness',
                      'Beta moment 1 reflects the amount of resting fast activity, a high value may indicate over-alertness or vigilance',
                      'Beta moment 2 reflects the time course of fast activity, a high value may be a concern (anxiety)',
                      'Beta moment 3 reflects the beta shift throughout the EEG,a high value may suggest instability of alertness',
                      'Theta moment 1 reflects the amount of theta, a high value may be a concern (inattention, unfocused)',
                      'Theta moment 2 reflects the time course of theta, a high value may be a concern (inattention, unfocused)',
                      'Theta moment 3 reflects the theta shift throughout the EEG, a high value may indicate lack of attentional stability',
                      'Delta moment 1 reflects slow activity, may be sleep related, a high value suggests possible dysfunction or sleep concerns',
                      'Delta moment 2 reflects the time course of slow activity, a high value suggests possible dysfunction or sleep concerns',
                      'Delta moment 3 reflects the delta shift throughout the EEG, a high value may suggest drowsiness or sleep concerns']
    
    low_sentences =  ['The power in the raw EEG is exhibited to be low in comparison to other individuals',
                     'The power in the filtered EEG is exhibited to be low in comparison to other individuals',
                     'PDR symmetry reflects the left right balance of the brain activity, poor symmetry can be a concern',
                     'PDR synchrony reflects the precise timing of the left right brain activity, low synchrony may be a concern',
                     'PDR regulation reflects the momentary variations in the left right brain activity, poorly regulated EEG may be a concern',
                     'PDR magnitude reflects the size of brain activity, a low magnitude may be a concern (chronic pain/hypervigilance)',
                     'PDR sinusoidal reflects the spectral purity of brain activity, a low value may be a concern (excess beta)',
                     'PDR max posterior reflects the front back balance of relaxed brain activity, a low value may be a concern (frontal alpha)',
                     'A low PDR FFT width suggests hyper-synchronous or persistent alpha',
                     'PDR max amplitude is low, a low value may reflect under-relaxation or hyper-activation',
                     'PDR burst width is low, a low value may reflect poorly regulated alpha',
                     'Beta max front reflects the front back balance of active brain activity, a low value may be a concern (posterior beta, anxiety)',
                     'Frontal alpha asymmetry reflects the emotional balance while at rest, a low value may be a concern (extreme positive affect, risk-taking)',
                     'Excess temporal alpha reflects possible atypical alpha activity, a low value may suggest overactive temporal areas (memory, auditory)',
                     'Alpha speed reflects the speed of background processing, slow alpha may be a concern (anxiety)',
                     'Alpha peak reflects the speed of background processing, slow alpha may be a concern (anxiety)',
                     'Midline Beta reflects conscious processing, a low value may indicate underactivity',
                     'Focal delta index reflects how localized the slow activity is, a low value may be a concern (sleep, TBI, stroke, injury)',
                     'Focal delta amplitude reflects the amount of local slow activity, a low value may be a concern (overactivation)',
                     'Focal theta index reflects how localized the maximum is, a low value is not be a concern, may be an asset',
                     'Focal theta amplitude reflects localized dysfunction, a low value is not a concern',
                     'Focal hibeta index reflects the local dysfunction (may be EMG), a low value is not a concern',
                     'Focal hibeta amplitude reflects the local dysfunction (may be EMG), a low value is not a concern, may be an asset',
                     'Focal beta index reflects the local dysfunction (overactivity), a low value is not a concern, may be an asset',
                     'Focal beta amplitude reflects the local dysfunction (overactivity), a low value is not a concern, may be an asset',
                     'Frontal delta reflects the frontal dysfunction (attention, mood, executive), a low value may be a concern (frontal overactivation)',
                     'Frontal theta reflects the frontal dysfunction (attention, mood, executive), a low value may be a concern (frontal overactivation)',
                     'Frontal gamma reflects the activation of executive and attention networks, a low may reflect frontal underactivation (disengagement)',
                     'Frontal gamma asymmetry reflects the mood regualtion, a low value may suggest avoidance/negative affect',
                     'Diffuse delta reflects generalized slow waves (metabolic/injury), a low value may be a concern (overactive, reactivity)',
                     'Diffuse theta reflects generalized slow waves (attention, executive), a low value may be a concern (overactive)',
                     'Diffuse hibeta reflects generalized overactivity (busy brain), a low value is not a concern, may be an asset',
                     'Diffuse beta reflects generalized overactivity (cognitive, externalized), a low value may be a concern (processing deficit)',
                     'Diffuse gamma reflects the activation of general networks, a low value may reflect underactivation',
                     '60hz artifact reflects the enviornmental interference a low value is desirable',
                     'Fractal dimension reflects the complexity of brain activity, a low value may suggest reduced cortical processing',
                     'PDR moment 1 reflects the size of brain activity, a low magnitude may be a concern (chronic pain/hypervigilance)',
                     'PDR moment 2 reflects the time course of the PDR, a low value may reflect under-relaxarion or hyper-activation',
                     'PDR moment 3 reflects the PDR shift throughout the EEG, a low value may reflect under-relaxarion or hyper-activation',
                     'Beta moment 1 reflects the amount of resting fast activity, a low value may suggest under-activation',
                     'Beta moment 2 reflects the time course of resting fast activity, a low value may suggest under-activation',
                     'Beta moment 3 reflects the beta shift throughout the EEG, a low value may suggest a rigid activation state',
                     'Theta moment 1 reflects the amount of theta, a low value may be a concern (overfocused, overactivated)',
                     'Theta moment 2 reflects the time course of theta, a low value  may be a concern (overfocused, overactivated) ',
                     'Theta moment 3 reflects the theta shift throughout the EEG, a low value may suggest a rigid state of alertness (high or low)',
                     'Delta moment 1 reflects slow activity, may be sleep related, a low value suggests possible overactivation',
                     'Delta moment 2 reflects the time course of slow activity, may be sleep related, a low value suggests possible overactivation',
                     'Delta moment 3 reflects the delta shift throughout the EEG, a low value suggests continuous slow activity, which may be a concern']
#===================================================================================================================================================================================
    #   CREATE A TABLE THAT USES THE NAMES OF THE TESTS AND THE RESULTS AS THE ENTRIES
    metricstring=', '.join(['{:.2f}'.format(num) for num in metrics])
    print(metricstring)
    #datat = allocate_data_4x12()
    datat = allocate_data_5x19()
    datat[0] = ["Parameter", "Value", "Typ", "Z-Score", "Range"]
    df = pd.read_excel(excel_file_path, skiprows=1)
    metrics_avg = df.iloc[:, 0].tolist()
    metrics_std = df.iloc[:, 1].tolist()
    bar_y = 719
    lows = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 27, 28, 29, 30, 32, 33, 35, 36, 37, 39, 40, 41, 42, 43, 44, 45, 46, 47]
    highs = [0, 1, 5, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47]
    low_flags = []
    high_flags = []
    sentence_lf = []
    sentence_hf = []
    low_indexes = []
    high_indexes = []
    for i in range (0, 48):
        thismetric = '{:.2f}'.format(metrics[8+i])
        z_score = (float(thismetric) - float(metrics_avg[i+7]))/float(metrics_std[i+7])
        z_range = str(round(metrics_avg[i+7]-(2*metrics_std[i+7]), 2)) + '-' + str(round(metrics_avg[i+7]+(2*metrics_std[i+7]), 2))
        datat[i+1] = [name_strings[i], thismetric, round(metrics_avg[i+7], 2), round(z_score, 2), z_range]
#CREATION OF THE 'GRADED' COLOR BARS--------------------------------------------------------------------
        bar_height = 8
        yellow_width = 200
        green_width = 100
        yellow_x = 355
        green_x = 405
        #THIS IS WHERE WE DEFINE THE 'GRADED' COLOR  BARS---------------------------------------------------------------------
        if i in [28, 35]: #RYGGGY
            yellow_width = 250
            green_width = 150
        elif i in [12, 13, 18, 20, 22, 24, 25, 26, 31, 38]: #YGGGYR
            yellow_width = 250
            green_width = 150
            yellow_x = 305
            green_x = 355
        elif i in [2, 3, 4, 6, 7, 11]: #RYGGGG
            green_width = 200
        elif i in [16, 17, 19, 21, 23, 34]: #GGGGYR
            green_width = 200
            green_x = 305
             
        #THIS IS WHERE WE FLAG THE RED METRICS--------------------------------------------------------------------------------------------------------------------------
        if i in lows:
            if z_score < -2:
                low_flags.append(lows.index(i))
        if i in highs:
            if z_score > 2:
                high_flags.append(highs.index(i))

        if z_score < -2:
                sentence_lf.append(i)
                low_indexes.append(i)
        if z_score > 2:
                sentence_hf.append(i)
                high_indexes.append(i)
        
        #THIS IS WHERE WE GET THE FILLER WORDS FOR THE TEMPLATE SENTENCE------------------------------------------------------------------------------------------------------------
        if i == 2:
            if z_score > -1:
                sym_word = 'symmetric'
            elif z_score < -2:
                sym_word = 'asymmetric'
            else:
                sym_word = 'fairly symmetric'
        if i == 3:
            if z_score > -1:
                sync_word = 'synchronous'
            elif z_score < -2:
                sync_word = 'asynchronous'
            else:
                sync_word = 'fairly synchronous'
        if i == 4:
            if z_score > -1:
                reg_word = 'well'
            elif z_score < -2:
                reg_word = 'poorly'
            else:
                reg_word = 'fairly well'
        if i == 7:
            if z_score > -1:
                post_word = 'most prominently'
            elif z_score < -2:
                post_word = 'however, not prominently'
            else:
                post_word = 'semi-prominently'
        if i == 26:
            if z_score < -2:
                theta_word = 'only moderately'
            elif z_score > 1:
                theta_word = 'most prominently'
            else:
                theta_word = ''
        if i == 32:
            if z_score <-2:
                beta_word = 'minimally'
            elif z_score > 2:
                beta_word = 'heavily'
            else:
                beta_word = ''

        red = colors.Color(1, 0, 0)
        pdf_file.setFillColor(red)
        pdf_file.rect(305, bar_y, 300, bar_height, fill=1, stroke=1)
        
        yellow = colors.Color(255, 255, 0)
        pdf_file.setFillColor(yellow)
        pdf_file.rect(yellow_x, bar_y, yellow_width, bar_height, fill=1, stroke=1)
        
        green = colors.Color(0, 255, 0)
        pdf_file.setFillColor(green)
        pdf_file.rect(green_x, bar_y, green_width, bar_height, fill=1, stroke=1)
        
        #AVERAGE LINE========================================================
        pdf_file.line(x1=455,x2=455, y1=bar_y, y2=bar_y+bar_height)
        pdf_file.line(x1=405,x2=405, y1=bar_y, y2=bar_y+bar_height)
        pdf_file.line(x1=505,x2=505, y1=bar_y, y2=bar_y+bar_height)
        pdf_file.line(x1=555,x2=555, y1=bar_y, y2=bar_y+bar_height)
        pdf_file.line(x1=355,x2=355, y1=bar_y, y2=bar_y+bar_height)
        pdf_file.line(x1=275,x2=305, y1=722-(bar_height+7)*i, y2=722-(bar_height+7)*i)
        
        #ZSCORE PLOTTING--------------------------------------------------------
        if z_score > 3:
            z_score = 3
        if z_score < -3:
            z_score = -3
        
        add_x = z_score*50
        black = colors.Color(0, 0, 0)
        pdf_file.setFillColor(black)
        pdf_file.circle(x_cen=455+add_x, y_cen=bar_y+4, r=3, stroke=1, fill=1)

        pdf_file.setFont("Helvetica", 9)
        #text = 'Std Dev.='+str(round(float(metrics_std[i+9]), 2))
        #pdf_file.drawString(305, bar_y+10, text=text)
        
        bar_y -= bar_height + 7

    low_pdf_sentences = [] 
    high_pdf_sentences = []   
    for i in sentence_lf:
        low_pdf_sentences.append(low_sentences[i])
    for i in sentence_hf:
        high_pdf_sentences.append(high_sentences[i])

    #sentence_y = 110
    #for sentence in pdf_sentences:
    #    pdf_file.setFont('Helvetica', 10)
    #    pdf_file.drawString(12, sentence_y, text=sentence)
    #    sentence_y -= 12

    tablet = Table(datat[:][:])
    #tablet.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    #                       ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    #                       ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    #                       ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #                       ('FONTSIZE', (0, 0), (-1, 0), 10),
    #                       ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    #                       ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    #                       ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
    #                       ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
    #                       ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    #                       ('FONTSIZE', (0, 1), (-1, -1), 10),
    #                       ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    #                       ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    
    tablet_style =[
                           ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                           ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                           ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                           ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                           ('FONTSIZE', (0, 0), (-1, 0), 8),
                           ('BOTTOMPADDING', (0, 0), (-1, 0), .5),
                           ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                           ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                           ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                           ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                           ('FONTSIZE', (0, 1), (-1, -1), 8),
                           ('BOTTOMPADDING', (0, 1), (-1, -1), .05),
                           ('GRID', (0, 0), (-1, -1), 1, colors.black)]
    
    # Add conditions to change background color for rows in low_flags and high_flags---------------------------------------------------------------------------------------------------------------
    for i in low_indexes:
        if i in lows:
            tablet_style.extend([
            ('BACKGROUND', (0, i + 1), (-1, i + 1), colors.red),  # Red background for low_flags
            ('TEXTCOLOR', (0, i + 1), (-1, i + 1), colors.white)  # White text for better visibility
            ])
        else:
            tablet_style.extend([
            ('BACKGROUND', (0, i + 1), (-1, i + 1), colors.green),  # Red background for low_flags
            ('TEXTCOLOR', (0, i + 1), (-1, i + 1), colors.white)  # White text for better visibility
            ])


    for i in high_indexes:
        if i in highs: 
            tablet_style.extend([
            ('BACKGROUND', (0, i + 1), (-1, i + 1), colors.red),  # Red background for low_flags
            ('TEXTCOLOR', (0, i + 1), (-1, i + 1), colors.white)  # White text for better visibility
            ])
        else:
            tablet_style.extend([
            ('BACKGROUND', (0, i + 1), (-1, i + 1), colors.green),  # Red background for low_flags
            ('TEXTCOLOR', (0, i + 1), (-1, i + 1), colors.white)  # White text for better visibility
            ])

    # Applying the updated TableStyle---------------------------------------------------------------------------------------------------------------------------------------------------------------
    tablet.setStyle(TableStyle(tablet_style))
    
    pdf_file.rotate(90)
    pdf_file.setFont('Helvetica', 13)
    pdf_file.drawString(612, -17, 'PDR')
    pdf_file.drawString(489, -17, 'Phenotypes')
    pdf_file.drawString(345, -17, 'Focal / Frontal')
    pdf_file.drawString(222, -17, 'Diffuse')
    pdf_file.drawString(70, -17, 'State Shift')
    pdf_file.rotate(-90)

    tablet.wrapOn(pdf_file, 400, 100)
    tablet.drawOn(pdf_file, 25, 10)

    pdf_file.setLineWidth(2)
    pdf_file.line(x1=0, x2=288, y1=567, y2=567)
    pdf_file.line(x1=0, x2=288, y1=476, y2=476)
    pdf_file.line(x1=0, x2=288, y1=296, y2=296)
    pdf_file.line(x1=0, x2=288, y1=191, y2=191)
    pdf_file.line(x1=0, x2=288, y1=10, y2=10)
    pdf_file.line(x1=0, x2=288, y1=702, y2=702)

    pdf_file.showPage()

    descriptions = ['Left right balance of the brain activity',
                    'Precise timing of the left right brain activity',
                    'Momentary variations in the left right brain activity',
                    'Size of the brain activity',
                    'Spectral purity of the brain activity',
                    'Front back balance of the relaxed brain activity',
                    'Width of the PDR power spectrum',
                    'Maximum amplitude of the PDR',
                    'Width of the PDR burst',
                    'Front back balance of the active brain activity',
                    'Emotional balance at rest',
                    'Possible atypical alpha activity',
                    'Speed of the background processing',
                    'Conscious processing',
                    'Localized dysfunction (metabolic/injury)',
                    'Degree of local dysfunction',
                    'Localized dysfunction',
                    'Localized dysfunction',
                    'Local dysfunction (overactivity)',
                    'Local dysfunction (overactivity)',
                    'Local dysfunction (overactivity)',
                    'Local dysfunction (overactivity)',
                    'Frontal dysfunction (attention, mood, executive)',
                    'Frontal dysfunction (attention, mood, executive)',
                    'Activation of executive and attention networks',
                    'Mood regulation',
                    'Generalized slow waves (metabolic/injury)',
                    'Generalized slow waves (attention, executive)',
                    'Generalized overactivity (busy brain)',
                    'Generalized overactivity (cognitive, externalized)',
                    'Activation of general networks',
                    'Enviornmental interference',
                    'Complexity of the brain activity',
                    'Sum of the PDR',
                    'Average of the PDR',
                    'Variance of the PDR',
                    'Sum of the beta rhythm',
                    'Average of the beta rhythm',
                    'Variance of the beta rhythm',
                    'Sum of the theta rhythm',
                    'Average of the theta rhythm',
                    'Variance of the theta rhythm',
                    'Sum of the delta rhythm',
                    'Average of the delta rhythm',
                    'Variance of the delta rhythm']
    
    formulas = ['The ratio of O1 and O2',
                'The ratio of the synchronized bursts and the individual bursts',
                'The sum of the entropy of O1 and O2',
                'The average magnitude of O1 and O2',
                'The relative amount of the second harmonics',
                'The ratio between Fz and Pz',
                '<<<FFT Width>>>',
                '<<<Max Amp>>>',
                '<<<Burst Width>>>']

    # Save and close the PDF file, ----------------------------------------------------------------------------------------------------------------------------------------------------------
#    sentence_y = 675
    sentence_y = 730

# Add some text to the PDF file
    pdf_file.setFont("Helvetica", 13)
    # pdf_file.drawString(15, 770, "BrainMaster EEG Pre-QEEG Auto Scan Report (c) 2023")
    pdf_file.drawString(15, 770, "BrainML (Machine Learning) Brain Panel Summary (c) 2025")

    pdf_file.setFont("Helvetica", 10)
    pdf_text = 'Database Used: ' + str(os.path.basename(excel_file_path))
    pdf_file.drawString(385, 775, pdf_text)

    df = pd.read_excel(excel_file_path, sheet_name='Sheet1')
    num_files = df.shape[1] - 2
    pdf_text1 =  'Number of files: '+str(num_files)
    pdf_file.drawString(385, 763, pdf_text1)
    pdf_text2 =  'Name: '+ short_name
    pdf_file.drawString(385, 750, pdf_text2)


    pdf_file.setFont('Helvetica', 9)
    pdf_file.setFillColorRGB(0, 0, 0)
    pdf_file.drawString(30, sentence_y, text="NOTE:  This analysis and report are considered experimental, for research and educational use only.")
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="No further warranties or claims are made.  Not intended for the diagnosis or treatment of any disease or disorder.")
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="The following statements are machine-generated and are not intended to reflect human clinical judgment.")
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="They are based on a statistical analysis of metrics derived from the 19-channel surface EEG.")
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="The end-user takes full responsibility for the interpretation of the results herein.")
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="The statements indicate possible areas for attention, but are not to be used on their own.")

    sentence_y -= 30

    for sentence in low_pdf_sentences:
        ind = low_sentences.index(sentence)
        if ind in lows:
            pdf_file.setFont('Helvetica', 10)
            pdf_file.setFillColorRGB(1, 0, 0)
            pdf_file.drawString(12, sentence_y, text=sentence)
            sentence_y -= 15
        else:
            pdf_file.setFont('Helvetica', 10)
            pdf_file.setFillColorRGB(0, .5, 0)
            pdf_file.drawString(12, sentence_y, text=sentence)
            sentence_y -= 15    

    for sentence in high_pdf_sentences:
        ind = high_sentences.index(sentence)
        if ind in highs:
            pdf_file.setFont('Helvetica', 10)
            pdf_file.setFillColorRGB(1, 0, 0)
            pdf_file.drawString(12, sentence_y, text=sentence)
            sentence_y -= 15
        else:
            pdf_file.setFont('Helvetica', 10)
            pdf_file.setFillColorRGB(0, .5, 0)
            pdf_file.drawString(12, sentence_y, text=sentence)
            sentence_y -= 15    
    

    sentence_y = 130
    pdf_file.setFont('Helvetica', 9)
    pdf_file.setFillColorRGB(0, 0, 0)
 
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="Stress Therapy Solutions, Inc. and BrainMaster Technologies, Inc. are not responsible for the use of the information herein.")
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="It is recommended that users acquire certification in EEG and/or QEEG to ensure quality of recording and interpretation.")
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="Not intended for use for clinical diagnosis, or for forensic or insurance purposes.")
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="To order online Brain Panels and clinician reviews, visit https://stresstherapysolutions.com/eeg-screening-review/")
    sentence_y -= 15
    pdf_file.drawString(30, sentence_y, text="email: info@stresstherapysolutions.com  phone: 1-800-447-8052   Intl: 216-766-5707")

    pdf_file.setFillColorRGB(0, 0, 0)
    pdf_file.showPage()
    #----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    template = "The background rhythm in the eyes closed wakeful state consists of {}, {}, {} regulated {}-{} uV activity in the {}-{} Hz alpha frequency range seen {} over the posterior and central head regions. {}-{} uV activity in the 5-7 Hz theta range is seen {} in the frontal and central regions. {}-{} uV activity in the 15-25 Hz beta range is seen {} in the frontal and central regions."

    #filled_sentence = template.format(sym_word, sync_word, reg_word, 'XX', 'XX', post_word)
    #paragraph = Paragraph(filled_sentence, normal_style)
    #paragraph.wrapOn(pdf_file, 350, 100)
    #paragraph.drawOn(pdf_file, 15, 725)

    sentence_y = 655
    #for sentence in pdf_sentences:
    #    pdf_file.setFont('Helvetica', 9)
    #    pdf_file.setFillColorRGB(1, 0, 0)
    #    pdf_file.drawString(12, sentence_y, text=sentence)
    #    sentence_y -= 12
    #pdf_file.setFillColorRGB(0, 0, 0)
    print('Y-val', sentence_y)
    #FFT PLOTTING----------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    #'''
    fig, ax = plt.subplots(figsize=(12, 15))
    ax.axis('off')
    #kernel=np.array([1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16])
    #kernel1 = np.array([1/32, 1/16, 1/16, 1/16, 1/4, 1/16, 1/16, 1/16, 1/32])
    kernel1 = np.array([1/16, 1/8, 3/16, 1/2, 3/16, 1/8, 1/16])
    #kernel1=np.array([1/16, 1/16, 1/8, 1/2, 1/8, 1/16, 1/16])
    sig_s = np.zeros(2560)
    amp_s = np.zeros(2560)
    amp_sc = np.zeros(2560)
    window_s = np.hamming(2560)
    
    start = 20
    stop = 2580
    y_min = -1000
    #epoch_vals= []
    #phases = []
    #powers = []
    #ffts = []
    #cyc_ffts = []
    alpha_vals = []
    alpha_nums = []
    theta_nums = []
    beta_nums = []
    for j in range(n):
        epoch_vals= []
        phases = []
        powers = []
        ffts = []
        numpages = np.floor(numpages)
        #print('numpages: ', numpages)
        for k in range(int(numpages)):
            #print('WORKS-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=')
            epoch_range = np.arange(2560*(k-1), 2560*k, 1)
            sig_s =myvisualsigs[j, epoch_range] #* window_s
            fft_s = np.fft.fft(sig_s)
            #print('SHAPE: ', fft_s.shape )
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
            #print('Length is: ', len(power_s))
            powers.append(power_s)
            #FFT OF POWER SPECTRUM
            #cyc_fft = np.fft.fft(amp_sc)
            #cyc_s = np.abs(cyc_fft)
            #cyc_sc = np.convolve(cyc_s, kernel, mode='same')
            #cyc_sc = np.convolve(cyc_sc, kernel1, mode='same')
            #cyc_ffts.append(cyc_sc)
            freq_s = np.fft.fftfreq(len(sig_s), d=1/256)
        phases = phases*100
        avg_amp_sc = sum(epoch_vals) / len(epoch_vals)

        ax.plot(start+40*freq_s[:len(freq_s)//4], y_min+100+avg_amp_sc[:len(avg_amp_sc)//4]/5, linewidth=0.5)

#  FIND THE PEAKS

        peak_index=detect_peak(avg_amp_sc[7*10:14*10])
        peak_indexl=detect_peak(avg_amp_sc[7*10:10*10])
        #print('low peak:', peak_indexl)
        peak_indexh=detect_peak(avg_amp_sc[10*10:14*10])
        #print('Hi Peak:', peak_indexh)
        peak_indexo=detect_peak(avg_amp_sc[4*10:40*10])
#        print("peaks:  ", (7*10+peak_index)/10, (6*10+peak_indexl)/10, (10*10+peak_indexh)/10, (4*10+peak_indexo)/10)
#        tstring = "{:.1f}".format(7*40+peak_index)

#  MONTAGE LAND
          
        tstring1 = f"{electrode_names[j]}:"
        
#        else:
#          tstring = f"{channel_labels_short[i]}:"

#  GET MICROVOLTS VALUES FOR DIFFERENT WAVE-------------------------------------------------------------------------------------------------------------------------------------

        if tstring1 in ['P3:', 'P4:', 'O1:', 'O2:']:
            val = max(avg_amp_sc[70:140])
            alpha_nums.append(np.sqrt(val)/2)
        elif tstring1 in ['F3:', 'F4:', 'C3:', 'C4:']:
            val = max(avg_amp_sc[40:70])
            theta_nums.append(np.sqrt(val)/2)
        val = max(avg_amp_sc[150:250])
        beta_nums.append(np.sqrt(val)/2)

        upper_lim = ax.get_ylim()[1]
        
        ax.text(start+1750, y_min + 900 - 30 * j, tstring1, fontsize=17)   #-1000, + 500

        tstring = "Alpha1:"
        ax.text(start-10, y_min + 930, tstring)  
        tstring = "Alpha:"
        ax.text(start-10, y_min + 950, tstring)
        tstring = "Alpha2:"
        ax.text(start-10, y_min + 970, tstring)

        if peak_index != 0:
            value=(7*10+peak_index)/10
            tstringv = f"{value:.1f}"
            ax.text(start+2150, y_min + 900 - 30 * j, tstringv, fontsize=17)
            ax.plot([start+7*40+4*peak_index, start+7*40+4*peak_index], [y_min+950, y_min+965], color = "Black", linewidth=1.0)
        else:
            value = 0
        #print('Val: ', value)
        if peak_indexl != 0:
            valuel=(7*10+peak_indexl)/10
            tstringl = f"{valuel:.1f}"
            ax.text(start+1950, y_min + 900 - 30 * j, tstringl, fontsize=17)
            ax.plot([start+7*40+4*peak_indexl, start+7*40+4*peak_indexl], [y_min+930, y_min+945], color = "Black", linewidth=1.0)
        else:
            valuel = 0
        #print('low Peak: ', valuel)
        if peak_indexh != 0:
            valueh=(10*10+peak_indexh)/10
            tstringh = f"{valueh:.1f}"
            ax.text(start+2350, y_min + 900 - 30 * j, tstringh, fontsize=17)
            ax.plot([start+10*40+4*peak_indexh, start+10*40+4*peak_indexh], [y_min+970, y_min+985], color = "Black", linewidth=1.0)
        else:
            valueh = 0
        #print('hi peak: ', valueh)
    
        if tstring1 in ['P3:', 'P4:', 'O1:', 'O2:']:
            try:
                alpha_vals.append(float(tstringl))
            except:
                print('NO VAL')
            try:
                alpha_vals.append(float(tstringh))
            except:
                print('NO VAL')

    print('ALPHA VALS', alpha_vals)
    print('Alpha Nums:', alpha_nums)
    print('Theta Nums:', theta_nums)
    print('Beta Nums:', beta_nums)
    ax.plot([start,stop], [y_min+80, y_min+80], color = "Black", linewidth=1.0)
    ax.plot([start, start], [y_min+80, y_min+100], color = "Black", linewidth=1.0)
    for i in range(7):
      ax.plot([start+400*i, start+400*i], [y_min+80, y_min+50], color = "Black", linewidth=1.0)
      ax.text(start+400*i, y_min+5, str(i*10))
    
    image_path = name + 'plot.png'
    canvas_img = FigureCanvas(fig)
    canvas_img.print_png(image_path)

    plt.close(fig)
    
    fig, ax = plt.subplots(figsize=(12, 15))
    ax.axis('off')
    y_max = 1000
    y_min = -1000
    y_increment = (y_max - y_min) / (n+20)
    for i in range(n):
        sigtoshow = myvisualsigs[i, 5280:7840]
        y_position = y_max - (i+1) * y_increment
        sigtoshow = sigtoshow + y_position
  #    if selstring[7] == 1:
        time_range = np.arange(0, 2560, 1)
        ax.plot(time_range, sigtoshow, color="Black", linewidth=0.5)
        tstring = f"{electrode_names[i]}:"

        ax.text(start-400, y_position, tstring)   
    
    img_path = name + 'waves.png'
    canvas_img1 = FigureCanvas(fig)
    canvas_img1.print_png(img_path)

    plt.close(fig)

    image = Image.open(img_path)
    width_i, height_i = image.size
    cropped_image = image.crop((0, int(height_i*15/100), width_i, height_i-int(height_i*15/100)))
    cropped_img_path = name + 'crop.png'
    cropped_image.save(cropped_img_path)

    #pdf_file.rect(50, height-700, 550, 400, fill=0, stroke=1)
    filled_sentence = template.format(sym_word, sync_word, reg_word, round(min(alpha_nums), 1), round(max(alpha_nums), 1), min(alpha_vals), max(alpha_vals), post_word, round(min(theta_nums), 1), round(max(theta_nums), 1), theta_word, round(min(beta_nums), 1), round(max(beta_nums), 1), beta_word)
    normal_style.fontSize = 11
    paragraph = Paragraph(filled_sentence, normal_style)
    paragraph.wrapOn(pdf_file, 500, 100)
    #print('length', len(pdf_sentences))
    print('y-val:', sentence_y)
    paragraph.drawOn(pdf_file, 75, sentence_y-27)

    normal_style.fontSize = 11
    #short_name = short_name.split('/')[-1] if '/' in short_name else short_name.split('\\')[-1]
    paragraph = Paragraph('Name: ' + short_name, normal_style)
    paragraph.wrapOn(pdf_file, 400, 100)
    paragraph.drawOn(pdf_file, 25, 738)
    #current_datetime = datetime.datetime.now()
    #formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    paragraph = Paragraph('Date: ' + formatted_datetime, normal_style)
    paragraph.wrapOn(pdf_file, 400, 100)
    paragraph.drawOn(pdf_file, 25, 728)
    
    pdf_file.drawImage(image_path, 30, height - 730, width=525, height=380) #550, 400
    pdf_file.drawImage(cropped_img_path, 50, height - 405, width=490, height=230)
        
    new_img = os.path.join(os.getcwd(), 'STSLogo.png')
    pdf_file.drawImage(new_img, width/2-115, 700, width=230, height=70)

    pdf_file.setFont("Helvetica-Bold", 16)
#    pdf_file.drawString(200, 696, "BrainML (Machine Learning) EEG Quality Review")
    pdf_file.drawString(100, 696, "BrainML (Machine Learning) EEG Quality Review")
    
    pdf_file.setFont("Helvetica", 9)
    pdf_file.drawString(75, 75, "NOTE: This report is machine generated and experimental.  No clinical claims are made.")
    pdf_file.drawString(75, 60, "Inspection of the raw EEG by a board-certified neurologist/clinical neurophysiologist is recommended.")
    pdf_file.drawString(75, 45, "Stress Therapy Solutions can help you find a provider of EEG quality inspection services.")
    pdf_file.drawString(75, 30, "Find us at www.stresstherapysolutions.com   and   www.stseegscreening.com")
    pdf_file.drawString(75, 15, "email: info@stresstherapysolutions.com  phone: 1-800-447-8052   Intl: 216-766-5707")

    #'''
    pdf_file.showPage()
#   HERE IS WHERE WE UNPACK THE PHENOTYPE SCORES
    #paragraph = Paragraph("Phenotype Scores:")
    #paragraph.wrapOn(pdf_file, 400, 100)
    #paragraph.drawOn(pdf_file, 100, 450)

    #phenotype_strings = create_phenotype_strings()
    #for i in range(len(phenotype_strings)):
    #   paragraph= Paragraph(phenotype_strings[i])
    #   paragraph.wrapOn(pdf_file, 400, 100)
    #   paragraph.drawOn(pdf_file, 130, 400 - 10 * i)

#    metricstring=', '.join([str(num) for num in metrics])

    #paragraph = Paragraph(metricstring)
    #paragraph.wrapOn(pdf_file, 400, 100)
    #paragraph.drawOn(pdf_file, 100, 200)#


    #pdf_file.showPage()

    #paragraph = Paragraph("The following table shows values per sensor location")
    #paragraph.wrapOn(pdf_file, 400, 100)
    #paragraph.drawOn(pdf_file, 100, 700)

    # Add a table to the PDF file
#    data=np.empty((5,3), dtype=str)

    #data = allocate_data_3x19()

    #data[0] = ["Site", "Total", "Entropy"]

    #for i in range(0, 19):
    #  data[i+1] = [channel_labels_short[i], str(10*i), "3.4"]

    #table = Table(data[:][:])
    #table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    #                       ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    #                       ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
    #                       ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    #                       ('FONTSIZE', (0, 0), (-1, 0), 14),
    #                       ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    #                       ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    #                       ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
    #                       ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
    #                       ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
    #                       ('FONTSIZE', (0, 1), (-1, -1), 12),
    #                       ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    #                       ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
    #table.wrapOn(pdf_file, 400, 100)
    #table.drawOn(pdf_file, 100, 200)

    
    pdf_file.save()
    os.remove(image_path)
    os.remove(img_path)
    os.remove(cropped_img_path)

def allocate_data_3x19():
    data = [[ "1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["10", "11", "12"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"],
            ["13", "14", "15"]]
    return data

def allocate_data_4x12():
    data = [[ "1", "2", "3", "9"],
            ["4", "5", "6", "9"],
            ["7", "8", "9", "9"],
            ["10", "11", "12", "9"],
            ["13", "14", "15", "9"],
            ["13", "14", "15", "9"],
            ["13", "14", "15", "9"],
            ["13", "14", "15", "9"],
            ["13", "14", "15", "9"],
            ["13", "14", "15", "9"],
            ["13", "14", "15", "9"],
            ["13", "14", "15", "9"]]
    return data

def allocate_data_5x19():
    data = [[ "1", "2", "3", "9", "9"],
            ["4", "5", "6", "9", "9"],
            ["7", "8", "9", "9", "9"],
            ["10", "11", "12", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"],
            ["13", "14", "15", "9", "9"]]
    return data


def create_report_strings():
    local_strings = ["PDR Analysis:"]
    return local_strings

def create_phenotype_strings():
    local_strings = ["Low-voltage Fast",
        "Epileptiform", 
        "Diffuse slow activity", 
        "Focal Abnormalities", 
        "Mixed Fast and Slow", 
        "Excess Frontal Slow", 
        "Frontal asymmetries", 
        "Excess temporal lobe alpha", 
        "Faster alpha variants", 
        "Spindling excessive beta", 
        "Persistent EO alpha"]
    return local_strings

def create_rating_strings():
    local_strings = ["yes", "no", "questionable"]
    return local_strings

def create_pheno_rating_strings():
    local_strings = ["not likely", "possible", "likely", "very likely"]
    return local_strings

def create_report_comments():
    local_strings = ["The background consists of", 
        "well regulated",
        "poorly regulated",
        "is more readily seen"]
    return local_strings

def create_technical_comments():
    local_strings = ["The total power in the unfiltered EEG in all channels is:",
        "The total power in the filtered EEG in all channels is:"]

def create_metric_strings():
    local_strings = ["Total time",
        "Total artifacted time",
        "Total unfiltered power",
        "Total filtered power",
        "Maximum Value",
        "Test/Retest Reliability:",
        "Split Half Reliability"]

def save_gui_screenshot(window):
    window.update_idletasks()
    x = window.winfo_rootx()
    y = window.winfo_rooty()
    width = window.winfo_width()
    height = window.winfo_height()

    screenshot = ImageGrab.grab(bbox=(x, y, x+width, y+height))
    screenshot = screenshot.crop((0, 0, width-20, height-54))
    return screenshot

#def create_pdf(outname, length, numsamples, ica_mixing, channel_labels_short, myvisualsigs, n, img_cascade_file, selected_channel_list, selected_channel_reasons):
    #print('MAKING IMAGE CASCADE')
    
    # ... pass your other required parameters ...

    #screenshots = []

    #for idx in range(1, n + 1):
        # Create the GUI using dummy_gui
        #CV = dummy_gui(length, numsamples, ica_mixing, idx, selected_channel_list, selected_channel_reasons, channel_labels_short, myvisualsigs, n)

       
        #CV.update_idletasks()
        # Capture screenshot
        #screenshot = save_gui_screenshot(CV)
        #print(f"Screenshot {idx} dimensions: {screenshot.size}")
        #screenshot_filename = os.path.join(outname, f"screenshot_{idx}.png")
        #screenshot.save(screenshot_filename)
        #screenshots.append(screenshot_filename)
    
        #CV.destroy()

    # Create PDF
    #doc = SimpleDocTemplate(img_cascade_file, pagesize=letter)
    #story = []

    #for screenshot in screenshots:
        #img = Image(screenshot, width=497)
        #story.append(img)
        #story.append(PageBreak())

    #doc.build(story)
    #for screenshot in screenshots:
        #os.remove(screenshot)

   