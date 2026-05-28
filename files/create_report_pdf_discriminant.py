# 3-page Brain Panel report with the Collura et al. (2026) discriminant
# functions inserted at the bottom of page 2.
#
# This is a sibling of files/create_report_pdf.py.  Pages 1 and 3 are
# rendered identically; page 2 keeps the existing "Findings" list (red
# / green sentences derived from out-of-bounds rows) and adds a new
# "Likelihood of Findings" block beneath, showing the six weighted-count
# discriminant scores (Clinical Abnormality, Drowsiness, Artifact,
# Paroxysmal/Epileptiform, PDR Frequency Abnormality, EEG Quality
# Concern) with risk-band labels.
#
# Output filename mirrors create_report_pdf.py but with a .disc segment
# inserted before .rep.pdf -- e.g. <edfname>.icale.disc.rep.pdf for
# montage 6 -- so the original report is never overwritten.
#
# Entry point selstring[13] = 1 (see edftotextbynameplotproc.py).

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from process.detect_artifact import detect_peak
import matplotlib.pyplot as plt
from PIL import Image
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import numpy as np
import datetime
import os
import pandas as pd

from files.create_report_pdf import allocate_data_5x19
from process import discriminant


def create_report_pdf_discriminant(name, short_name, channel_labels_short,
                                   name_strings, range_strings, report_strings,
                                   metrics, montage, excel_file_path, n,
                                   numpages, myvisualsigs, electrode_names):
    suffix_map = {0: ".le", 1: ".avg", 2: ".lap", 3: ".lngb",
                  4: ".ica", 5: ".pca", 6: ".icale"}
    fname = name + suffix_map.get(montage, "") + ".disc.rep.pdf"

    print("PDF:  ", fname)
    pdf_file = canvas.Canvas(fname, pagesize=letter)
    width, height = letter

    style_sheet = getSampleStyleSheet()
    normal_style = style_sheet['Normal']

    # ============================================================
    # PAGE 1 -- metrics table + color bars (identical to create_report_pdf)
    # ============================================================
    pdf_file.setFont("Helvetica", 14)
    pdf_file.drawString(15, 770, "BrainML (Machine Learning) Brain Panel Report (c) 2026")

    pdf_file.setFont("Helvetica", 10)
    pdf_file.drawString(385, 775, 'Database Used: ' + str(os.path.basename(excel_file_path)))

    df = pd.read_excel(excel_file_path, sheet_name='Sheet1')
    num_files = df.shape[1] - 2
    pdf_file.drawString(385, 763, 'Number of files: ' + str(num_files))

    normal_style.fontSize = 9
    paragraph = Paragraph("This report provides quantitative estimation of how well this EEG meets the expectations of a visual quality review by a clinical neurophysiologist", normal_style)
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

    # ----- Findings-sentence pools (verbatim from create_report_pdf.py) -----
    high_sentences = [
        'The power in the raw EEG is exhibited to be high in comparison to other individuals. this may be artifact, but is not a concern',
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

    low_sentences = [
        'The power in the raw EEG is exhibited to be low in comparison to other individuals',
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
        'Alpha speed reflects the speed of background processing, slow alpha is normal in children, in adults may be a concern (developmental delay, cognitive decline)',
        'Alpha peak reflects the speed of background processing, slow alpha is normal in children, in adults may be a concern (development delay, cognitive decline)',
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

    # ----- Build the metrics table and color bars (identical layout) -----
    datat = allocate_data_5x19()
    datat[0] = ["Parameter", "Value", "Typ", "Z-Score", "Range"]
    df = pd.read_excel(excel_file_path, skiprows=1)
    metrics_avg = df.iloc[:, 0].tolist()
    metrics_std = df.iloc[:, 1].tolist()
    bar_y = 719
    lows = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 27, 28, 29, 30, 32, 33, 35, 36, 37, 39, 40, 41, 42, 43, 44, 45, 46, 47]
    highs = [0, 1, 5, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47]
    sentence_lf, sentence_hf, low_indexes, high_indexes = [], [], [], []
    z_scores_all = []  # 48-vector for the discriminant analysis

    sym_word = sync_word = reg_word = post_word = ''
    theta_word = beta_word = ''

    for i in range(48):
        thismetric = '{:.2f}'.format(metrics[8+i])
        z_score = (float(thismetric) - float(metrics_avg[i+7])) / float(metrics_std[i+7])
        z_scores_all.append(z_score)
        z_range = str(round(metrics_avg[i+7]-(2*metrics_std[i+7]), 2)) + '-' + str(round(metrics_avg[i+7]+(2*metrics_std[i+7]), 2))
        datat[i+1] = [name_strings[i], thismetric, round(metrics_avg[i+7], 2), round(z_score, 2), z_range]

        bar_height = 8
        yellow_width, green_width = 200, 100
        yellow_x, green_x = 355, 405
        if i in [28, 35]:
            yellow_width, green_width = 250, 150
        elif i in [12, 13, 18, 20, 22, 24, 25, 26, 31, 38]:
            yellow_width, green_width = 250, 150
            yellow_x, green_x = 305, 355
        elif i in [2, 3, 4, 6, 7, 11]:
            green_width = 200
        elif i in [16, 17, 19, 21, 23, 34]:
            green_width = 200
            green_x = 305

        if z_score < -2:
            sentence_lf.append(i)
            low_indexes.append(i)
        if z_score > 2:
            sentence_hf.append(i)
            high_indexes.append(i)

        if i == 2:
            sym_word = 'symmetric' if z_score > -1 else ('asymmetric' if z_score < -2 else 'fairly symmetric')
        if i == 3:
            sync_word = 'synchronous' if z_score > -1 else ('asynchronous' if z_score < -2 else 'fairly synchronous')
        if i == 4:
            reg_word = 'well' if z_score > -1 else ('poorly' if z_score < -2 else 'fairly well')
        if i == 7:
            post_word = 'most prominently' if z_score > -1 else ('however, not prominently' if z_score < -2 else 'semi-prominently')
        if i == 26:
            theta_word = 'only moderately' if z_score < -2 else ('most prominently' if z_score > 1 else '')
        if i == 32:
            beta_word = 'minimally' if z_score < -2 else ('heavily' if z_score > 2 else '')

        pdf_file.setFillColor(colors.Color(1, 0, 0))
        pdf_file.rect(305, bar_y, 300, bar_height, fill=1, stroke=1)
        pdf_file.setFillColor(colors.Color(255, 255, 0))
        pdf_file.rect(yellow_x, bar_y, yellow_width, bar_height, fill=1, stroke=1)
        pdf_file.setFillColor(colors.Color(0, 255, 0))
        pdf_file.rect(green_x, bar_y, green_width, bar_height, fill=1, stroke=1)

        pdf_file.line(455, bar_y, 455, bar_y+bar_height)
        pdf_file.line(405, bar_y, 405, bar_y+bar_height)
        pdf_file.line(505, bar_y, 505, bar_y+bar_height)
        pdf_file.line(555, bar_y, 555, bar_y+bar_height)
        pdf_file.line(355, bar_y, 355, bar_y+bar_height)
        pdf_file.line(275, 722-(bar_height+7)*i, 305, 722-(bar_height+7)*i)

        z_clip = max(-3, min(3, z_score))
        pdf_file.setFillColor(colors.Color(0, 0, 0))
        pdf_file.circle(x_cen=455+z_clip*50, y_cen=bar_y+4, r=3, stroke=1, fill=1)

        pdf_file.setFont("Helvetica", 9)
        bar_y -= bar_height + 7

    low_pdf_sentences = [low_sentences[i] for i in sentence_lf]
    high_pdf_sentences = [high_sentences[i] for i in sentence_hf]

    tablet = Table(datat[:][:])
    tablet_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), .5),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR',  (0, 1), (-1, -1), colors.black),
        ('ALIGN',      (0, 1), (-1, -1), 'CENTER'),
        ('FONTNAME',   (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',   (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), .05),
        ('GRID',       (0, 0), (-1, -1), 1, colors.black)]

    for i in low_indexes:
        bg = colors.red if i in lows else colors.green
        tablet_style.extend([
            ('BACKGROUND', (0, i+1), (-1, i+1), bg),
            ('TEXTCOLOR',  (0, i+1), (-1, i+1), colors.white)])
    for i in high_indexes:
        bg = colors.red if i in highs else colors.green
        tablet_style.extend([
            ('BACKGROUND', (0, i+1), (-1, i+1), bg),
            ('TEXTCOLOR',  (0, i+1), (-1, i+1), colors.white)])
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
    pdf_file.line(0, 567, 288, 567)
    pdf_file.line(0, 476, 288, 476)
    pdf_file.line(0, 296, 288, 296)
    pdf_file.line(0, 191, 288, 191)
    pdf_file.line(0, 10, 288, 10)
    pdf_file.line(0, 702, 288, 702)

    pdf_file.showPage()

    # ============================================================
    # PAGE 2 -- Findings list + NEW Likelihood-of-Findings block
    # ============================================================
    sentence_y = 730
    pdf_file.setFont("Helvetica", 13)
    pdf_file.drawString(15, 770, "BrainML (Machine Learning) Brain Panel Summary (c) 2026")

    pdf_file.setFont("Helvetica", 10)
    pdf_file.drawString(385, 775, 'Database Used: ' + str(os.path.basename(excel_file_path)))
    pdf_file.drawString(385, 763, 'Number of files: ' + str(num_files))
    pdf_file.drawString(385, 750, 'Name: ' + short_name)

    pdf_file.setFont('Helvetica', 9)
    pdf_file.setFillColorRGB(0, 0, 0)
    for line in [
        "NOTE:  This analysis and report are considered experimental, for research and educational use only.",
        "No further warranties or claims are made.  Not intended for the diagnosis or treatment of any disease or disorder.",
        "The following statements are machine-generated and are not intended to reflect human clinical judgment.",
        "They are based on a statistical analysis of metrics derived from the 19-channel surface EEG.",
        "The end-user takes full responsibility for the interpretation of the results herein.",
        "The statements indicate possible areas for attention, but are not to be used on their own."]:
        pdf_file.drawString(30, sentence_y, text=line)
        sentence_y -= 15
    sentence_y -= 30

    pdf_file.setFont('Helvetica', 8)
    pdf_file.setFillColorRGB(0, 0, 0)
    pdf_file.drawString(12, sentence_y, text="Findings:")
    sentence_y -= 15

    # Layout budget for the Findings block:
    #   findings_top    = sentence_y after "Findings:" header (~y=595)
    #   findings_bottom = strict floor; last finding baseline must be >= this
    # The discriminant block divider sits at y=345 with the title 15pt below;
    # leave a 5pt visual gap above the divider so the lowest finding does
    # not touch it.
    findings_top = sentence_y
    findings_bottom = 350
    findings_avail = findings_top - findings_bottom

    all_findings = (
        [(low_sentences.index(s), s, "low") for s in low_pdf_sentences] +
        [(high_sentences.index(s), s, "high") for s in high_pdf_sentences]
    )

    # Choose font size and line spacing so the full list fits in the budget.
    # 8 / 15 is the default for short lists; shrink incrementally; truncate
    # with a note if still too many to fit at minimum spacing.
    n_find = len(all_findings)
    if n_find == 0 or n_find * 15 <= findings_avail:
        font_size, line_h = 8, 15
    elif n_find * 12 <= findings_avail:
        font_size, line_h = 8, 12
    elif n_find * 10 <= findings_avail:
        font_size, line_h = 7, 10
    else:
        font_size, line_h = 7, 9

    max_displayable = int(findings_avail // line_h)
    truncated = max(0, n_find - max_displayable)
    displayed = all_findings[: max_displayable if truncated else n_find]

    for ind, sentence, kind in displayed:
        flag_set = lows if kind == "low" else highs
        pdf_file.setFont("Helvetica", font_size)
        if ind in flag_set:
            pdf_file.setFillColorRGB(1, 0, 0)
        else:
            pdf_file.setFillColorRGB(0, .5, 0)
        pdf_file.drawString(12, sentence_y, text=sentence)
        sentence_y -= line_h

    if truncated:
        pdf_file.setFont("Helvetica-Oblique", 7)
        pdf_file.setFillColorRGB(0.35, 0.35, 0.35)
        pdf_file.drawString(
            12, sentence_y,
            text=f"... plus {truncated} additional finding(s) (truncated for layout — see page 1 metrics table for complete OOB list)."
        )

    # ----- NEW: Likelihood-of-Findings discriminant block -----
    _draw_discriminant_block(pdf_file, z_scores_all)

    # Footer disclaimers (identical to create_report_pdf)
    sentence_y = 130
    pdf_file.setFont('Helvetica', 9)
    pdf_file.setFillColorRGB(0, 0, 0)
    for line in [
        "Stress Therapy Solutions, Inc. and BrainMaster Technologies, Inc. are not responsible for the use of the information herein.",
        "It is recommended that users acquire certification in EEG and/or QEEG to ensure quality of recording and interpretation.",
        "Not intended for use for clinical diagnosis, or for forensic or insurance purposes.",
        "To order online Brain Panels and clinician reviews, visit https://stresstherapysolutions.com/eeg-screening-review/",
        "email: info@stresstherapysolutions.com  phone: 1-800-447-8052   Intl: 216-766-5707"]:
        sentence_y -= 15
        pdf_file.drawString(30, sentence_y, text=line)

    pdf_file.setFillColorRGB(0, 0, 0)
    pdf_file.showPage()

    # ============================================================
    # PAGE 3 -- background-rhythm template + FFT plot + raw waves
    # ============================================================
    template = ("The background rhythm in the eyes closed wakeful state consists of "
                "{}, {}, {} regulated {}-{} uV activity in the {}-{} Hz alpha frequency "
                "range seen {} over the posterior and central head regions. {}-{} uV "
                "activity in the 5-7 Hz theta range is seen {} in the frontal and "
                "central regions. {}-{} uV activity in the 15-25 Hz beta range is seen "
                "{} in the frontal and central regions.")

    sentence_y = 655

    fig, ax = plt.subplots(figsize=(12, 15))
    ax.axis('off')
    kernel1 = np.array([1/16, 1/8, 3/16, 1/2, 3/16, 1/8, 1/16])
    sig_s = np.zeros(2560)
    start, stop, y_min = 20, 2580, -1000
    alpha_vals, alpha_nums, theta_nums, beta_nums = [], [], [], []

    numpages_i = int(np.floor(numpages))
    for j in range(n):
        epoch_vals, phases, powers, ffts = [], [], [], []
        for k in range(numpages_i):
            epoch_range = np.arange(2560*(k-1), 2560*k, 1)
            sig_s = myvisualsigs[j, epoch_range]
            fft_s = np.fft.fft(sig_s)
            ffts.append(fft_s)
            phase = np.imag(fft_s)
            amp_s = np.abs(fft_s)
            amp_sc = np.convolve(amp_s, kernel1, mode='same')
            power_s = np.abs(amp_sc ** 2)
            epoch_vals.append(amp_sc)
            phases.append(phase)
            powers.append(power_s)
            freq_s = np.fft.fftfreq(len(sig_s), d=1/256)
        avg_amp_sc = sum(epoch_vals) / len(epoch_vals)

        line, = ax.plot(start+40*freq_s[:len(freq_s)//4], y_min+100+avg_amp_sc[:len(avg_amp_sc)//4]/5, linewidth=0.5)
        line_color = line.get_color()

        peak_index  = detect_peak(avg_amp_sc[7*10:14*10])
        peak_indexl = detect_peak(avg_amp_sc[7*10:11*10])
        peak_indexh = detect_peak(avg_amp_sc[9*10:14*10])

        tstring1 = f"{electrode_names[j]}:"

        if tstring1 in ['P3:', 'P4:', 'O1:', 'O2:']:
            alpha_nums.append(np.sqrt(max(avg_amp_sc[70:140]))/2)
        elif tstring1 in ['F3:', 'F4:', 'C3:', 'C4:']:
            theta_nums.append(np.sqrt(max(avg_amp_sc[40:70]))/2)
        beta_nums.append(np.sqrt(max(avg_amp_sc[150:250]))/2)

        label_top, label_bottom = 0.94, 0.55
        label_spacing = (label_top - label_bottom) / max(n - 1, 1)
        label_y = label_top - label_spacing * j
        ax.text(0.60, label_y, tstring1, fontsize=14, color=line_color, transform=ax.transAxes)

        marker_y_low, marker_y_mid, marker_y_high = 0.85, 0.90, 0.95
        marker_half_h = 0.018
        marker_trans = ax.get_xaxis_transform()
        ax.text(0.01, marker_y_low,  "Alpha1:", fontsize=12, transform=ax.transAxes)
        ax.text(0.01, marker_y_mid,  "Alpha:",  fontsize=12, transform=ax.transAxes)
        ax.text(0.01, marker_y_high, "Alpha2:", fontsize=12, transform=ax.transAxes)

        if peak_index != 0:
            value = (7*10+peak_index)/10
            ax.text(0.80, label_y, f"{value:.1f}", fontsize=14, color=line_color, transform=ax.transAxes)
            x_peak = start+7*40+4*peak_index
            ax.plot([x_peak, x_peak], [marker_y_mid - marker_half_h, marker_y_mid + marker_half_h], color="Black", linewidth=1.5, transform=marker_trans)
        if peak_indexl != 0:
            valuel = (7*10+peak_indexl)/10
            ax.text(0.72, label_y, f"{valuel:.1f}", fontsize=14, color=line_color, transform=ax.transAxes)
            x_peakl = start+7*40+4*peak_indexl
            ax.plot([x_peakl, x_peakl], [marker_y_low - marker_half_h, marker_y_low + marker_half_h], color="Black", linewidth=1.5, transform=marker_trans)
            if tstring1 in ['P3:', 'P4:', 'O1:', 'O2:']:
                alpha_vals.append(valuel)
        if peak_indexh != 0:
            valueh = (10*10+peak_indexh)/10
            ax.text(0.88, label_y, f"{valueh:.1f}", fontsize=14, color=line_color, transform=ax.transAxes)
            x_peakh = start+10*40+4*peak_indexh
            ax.plot([x_peakh, x_peakh], [marker_y_high - marker_half_h, marker_y_high + marker_half_h], color="Black", linewidth=1.5, transform=marker_trans)
            if tstring1 in ['P3:', 'P4:', 'O1:', 'O2:']:
                alpha_vals.append(valueh)

    ax.plot([start, stop], [y_min+80, y_min+80], color="Black", linewidth=1.0)
    ax.plot([start, start], [y_min+80, y_min+100], color="Black", linewidth=1.0)
    for i in range(7):
        ax.plot([start+400*i, start+400*i], [y_min+80, y_min+50], color="Black", linewidth=1.0)
        ax.text(start+400*i, y_min+5, str(i*10))

    image_path = name + 'plot.png'
    FigureCanvas(fig).print_png(image_path)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 15))
    ax.axis('off')
    y_max = 1000
    y_min = -1000
    y_increment = (y_max - y_min) / (n+20)
    for i in range(n):
        sigtoshow = myvisualsigs[i, 5280:7840] + (y_max - (i+1) * y_increment)
        ax.plot(np.arange(0, 2560, 1), sigtoshow, color="Black", linewidth=0.5)
        ax.text(start-400, y_max - (i+1) * y_increment, f"{electrode_names[i]}:")

    img_path = name + 'waves.png'
    FigureCanvas(fig).print_png(img_path)
    plt.close(fig)

    image = Image.open(img_path)
    width_i, height_i = image.size
    cropped_image = image.crop((0, int(height_i*15/100), width_i, height_i-int(height_i*15/100)))
    cropped_img_path = name + 'crop.png'
    cropped_image.save(cropped_img_path)

    if alpha_nums and alpha_vals:
        filled_sentence = template.format(
            sym_word or 'symmetric',
            sync_word or 'synchronous',
            reg_word or 'well',
            round(min(alpha_nums), 1), round(max(alpha_nums), 1),
            min(alpha_vals), max(alpha_vals),
            post_word or 'most prominently',
            round(min(theta_nums) if theta_nums else 0, 1),
            round(max(theta_nums) if theta_nums else 0, 1),
            theta_word,
            round(min(beta_nums), 1), round(max(beta_nums), 1),
            beta_word)
    else:
        filled_sentence = "Background rhythm summary unavailable (no detected alpha peaks)."

    normal_style.fontSize = 11
    paragraph = Paragraph(filled_sentence, normal_style)
    paragraph.wrapOn(pdf_file, 500, 100)
    paragraph.drawOn(pdf_file, 75, sentence_y-27)

    paragraph = Paragraph('Name: ' + short_name, normal_style)
    paragraph.wrapOn(pdf_file, 400, 100)
    paragraph.drawOn(pdf_file, 25, 738)
    paragraph = Paragraph('Date: ' + formatted_datetime, normal_style)
    paragraph.wrapOn(pdf_file, 400, 100)
    paragraph.drawOn(pdf_file, 25, 728)

    pdf_file.drawImage(image_path, 30, height - 730, width=525, height=380)
    pdf_file.drawImage(cropped_img_path, 50, height - 405, width=490, height=230)

    new_img = os.path.join(os.getcwd(), 'STSLogo.png')
    pdf_file.drawImage(new_img, width/2-115, 700, width=230, height=70)

    pdf_file.setFont("Helvetica-Bold", 16)
    pdf_file.drawString(100, 696, "BrainML (Machine Learning) EEG Quality Review")

    pdf_file.setFont("Helvetica", 9)
    pdf_file.drawString(75, 75, "NOTE: This report is machine generated and experimental.  No clinical claims are made.")
    pdf_file.drawString(75, 60, "Inspection of the raw EEG by a board-certified neurologist/clinical neurophysiologist is recommended.")
    pdf_file.drawString(75, 45, "Stress Therapy Solutions can help you find a provider of EEG quality inspection services.")
    pdf_file.drawString(75, 30, "Find us at www.stresstherapysolutions.com   and   www.stseegscreening.com")
    pdf_file.drawString(75, 15, "email: info@stresstherapysolutions.com  phone: 1-800-447-8052   Intl: 216-766-5707")

    pdf_file.showPage()
    pdf_file.save()
    os.remove(image_path)
    os.remove(img_path)
    os.remove(cropped_img_path)


def _draw_discriminant_block(pdf_file, z_scores_all):
    """
    Render the Likelihood-of-Findings block on the lower half of page 2.
    Layout: title at y=325, OOB-counts line, table from y=295 down.
    Anchored above the footer (which starts at y=115).
    """
    counts = discriminant.compute_oob_counts(z_scores_all)
    rows = discriminant.compute_scores(counts)

    # Section divider — sits 5pt below the findings_bottom floor (y=350)
    # to guarantee no visual collision with the lowest finding sentence.
    pdf_file.setStrokeColorRGB(0, 0, 0)
    pdf_file.setLineWidth(0.8)
    pdf_file.line(12, 345, 600, 345)

    pdf_file.setFont('Helvetica-Bold', 11)
    pdf_file.setFillColorRGB(0, 0, 0)
    pdf_file.drawString(12, 328, "Likelihood of Findings  (Collura et al., 2026 — Optimal Detection Algorithms)")

    pdf_file.setFont('Helvetica', 8)
    counts_line = ("OOB row counts:  "
                   f"Std/Global={counts['std_global']}  "
                   f"PDR={counts['pdr']}  "
                   f"Focal={counts['focal']}  "
                   f"Diffuse={counts['diffuse']}  "
                   f"State Shift={counts['state_shift']}  "
                   f"Phenotypes={counts['phenotypes']}  "
                   f"Total={counts['total']}    "
                   "(OOB = |z| >= 2)")
    pdf_file.drawString(12, 314, counts_line)
    pdf_file.drawString(
        12, 302,
        "Risk bands (Very Low | Low | Moderate | High) scale per category, "
        "proportional to each detector's maximum score.  Per-row bands shown in table.")

    # Table: name | formula | score | bands | likelihood | sens | spec | acc
    header = ["Category", "Detection algorithm", "Score",
              "Bands (VL | L | M | H)", "Likelihood", "Sens", "Spec", "Acc"]
    data = [header]
    for r in rows:
        data.append([
            r["name"],
            r["formula"],
            str(r["score"]),
            r["bands_label"],
            r["label"],
            f"{r['sens']}%",
            f"{r['spec']}%",
            f"{r['acc']}%",
        ])

    col_widths = [95, 145, 30, 75, 80, 30, 30, 30]
    tbl = Table(data, colWidths=col_widths)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 7.5),
        ('FONTNAME',   (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',   (0, 1), (-1, -1), 7.5),
        ('ALIGN',      (2, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',       (0, 0), (-1, -1), 0.5, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
    ]
    # color-code the Likelihood cell per row (col index 4 now that
    # Bands sits in col 3)
    for i, r in enumerate(rows, start=1):
        cr, cg, cb = r["color"]
        style.append(('TEXTCOLOR', (4, i), (4, i),
                      colors.Color(cr, cg, cb)))
        style.append(('FONTNAME', (4, i), (4, i), 'Helvetica-Bold'))
    tbl.setStyle(TableStyle(style))

    # Place the table one line-spacing below the "Risk bands:" text so the
    # grey header row doesn't visually touch the line above it.  Use the
    # actual wrapped height (not an estimate) for the footnote position.
    table_x = 12
    table_y_top = 278
    _table_w, table_h = tbl.wrapOn(pdf_file, sum(col_widths), 200)
    tbl.drawOn(pdf_file, table_x, table_y_top - table_h)

    # Explanatory footnote
    pdf_file.setFont('Helvetica-Oblique', 7)
    pdf_file.setFillColorRGB(0.3, 0.3, 0.3)
    pdf_file.drawString(
        12, table_y_top - table_h - 12,
        "Score = weighted sum of out-of-bounds row counts per Brain Panel group.  "
        "Sens/Spec/Acc reported on the 100-EDF clinical validation cohort.")

    # APA-formatted citation, wrapped to page width via a Paragraph object.
    cite_style = ParagraphStyle(
        "discriminant_cite",
        fontName="Helvetica",
        fontSize=7,
        textColor=colors.Color(0.3, 0.3, 0.3),
        leading=8.5,
    )
    cite_text = (
        "Reference: Collura, T., Rosace, A., Turner, R., Ims, D., &amp; Brubakee, B. (2026). "
        "Using machine learning to enhance the EEG screening review by pre-screening "
        "the EEG. <i>Artificial Intelligence and Applications</i>. Bon View Press. "
        "https://doi.org/10.47852/bonviewAIA62026679"
    )
    cite_para = Paragraph(cite_text, cite_style)
    cite_w, cite_h = cite_para.wrap(580, 60)
    cite_para.drawOn(pdf_file, 12, table_y_top - table_h - 22 - cite_h)

    pdf_file.setFillColorRGB(0, 0, 0)
