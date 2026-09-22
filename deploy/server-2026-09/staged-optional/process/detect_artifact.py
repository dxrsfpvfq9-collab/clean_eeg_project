import numpy as np
from scipy import signal
from scipy.signal import lfilter, filtfilt
from process.tfcfilters import tfcentropy
import mne


def detect_artifact(insignal, threshold=30):
    # Calculate the absolute value of the signal
    abs_signal = np.abs(insignal)
#    print("abs:  ", abs_signal[:4])
    
    # Apply a median filter to the absolute signal
    median_signal = signal.medfilt(abs_signal, 5)
    
    # Calculate the difference between the absolute signal and the median-filtered signal
    diff_signal = abs_signal - median_signal
    
    # Normalize the difference signal to have zero mean and unit variance
    norm_signal = (diff_signal - np.mean(diff_signal)) / np.std(diff_signal)
    
    # Threshold the normalized difference signal to detect artifact segments
 #   artifact_mask = norm_signal > threshold
    artifact_mask = abs_signal > threshold 
    saw_artifact = np.max(artifact_mask)
#    print("abs: " + str(abs_signal) + "  thr: " + str(threshold) + "  detect:" + str(saw_artifact))
    return artifact_mask

def detect_rms(insignal, threshold=30):
    median_signal = signal.medfilt(insignal, 5)
    rms = np.sqrt(np.mean(np.square(median_signal)))
    #print('RMS: ', rms)
    return rms

def detect_delta(bd, ad, bhd, ahd, thesignal, numsamples, threshold=20):

#    print("sig into delta:  ", thesignal[:4])

    thefilteredsignal = np.zeros(numsamples)
    thefilteredsignal = filtfilt(bhd, ahd, thesignal)
    thefilteredsignal = lfilter(bd, ad, thefilteredsignal)

#    print("filtered:  ", thefilteredsignal[:4])
 
    # Calculate the absolute value of the signal
    abs_signal = np.abs(thefilteredsignal)
#    print("abs:  ", abs_signal[:4])
    
    # Apply a median filter to the absolute signal
    median_signal = signal.medfilt(abs_signal, 5)
    
    # Calculate the difference between the absolute signal and the median-filtered signal
    diff_signal = abs_signal - median_signal
    
    # Normalize the difference signal to have zero mean and unit variance
    norm_signal = (diff_signal - np.mean(diff_signal)) / np.std(diff_signal)
    
    # Threshold the normalized difference signal to detect artifact segments
 #   artifact_mask = norm_signal > threshold
    artifact_mask = abs_signal > threshold 
    saw_artifact = np.max(artifact_mask)
#    print("abs: " + str(abs_signal) + "  thr: " + str(threshold) + "  detect:" + str(saw_artifact))

    return artifact_mask


def detect_theta(b, a, bh, ah, thesignal, numsamples, threshold=20):

#    print("sig into delta:  ", thesignal[:4])

    thefilteredsignal = np.zeros(numsamples)
    thefilteredsignal = filtfilt(bh, ah, thesignal)
    thefilteredsignal = lfilter(b, a, thefilteredsignal)

#    print("filtered:  ", thefilteredsignal[:4])
 
    # Calculate the absolute value of the signal
    abs_signal = np.abs(thefilteredsignal)
#    print("abs:  ", abs_signal[:4])
    
    # Apply a median filter to the absolute signal
    median_signal = signal.medfilt(abs_signal, 5)
    
    # Calculate the difference between the absolute signal and the median-filtered signal
    diff_signal = abs_signal - median_signal
    
    # Normalize the difference signal to have zero mean and unit variance
    norm_signal = (diff_signal - np.mean(diff_signal)) / np.std(diff_signal)
    
    # Threshold the normalized difference signal to detect artifact segments
 #   artifact_mask = norm_signal > threshold
    artifact_mask = abs_signal > threshold 
    saw_artifact = np.max(artifact_mask)
#    print("abs: " + str(abs_signal) + "  thr: " + str(threshold) + "  detect:" + str(saw_artifact))

    return artifact_mask

def detect_band(b, a, bh, ah, thesignal, numsamples, threshold=20):

#    print("sig into delta:  ", thesignal[:4])

    thefilteredsignal = np.zeros(numsamples)
    thefilteredsignal = filtfilt(bh, ah, thesignal)
    thefilteredsignal = lfilter(b, a, thefilteredsignal)

#    print("filtered:  ", thefilteredsignal[:4])
 
    # Calculate the absolute value of the signal
    abs_signal = np.abs(thefilteredsignal)
#    print("abs:  ", abs_signal[:4])
    
    # Apply a median filter to the absolute signal
    median_signal = signal.medfilt(abs_signal, 5)
    
    # Calculate the difference between the absolute signal and the median-filtered signal
    diff_signal = abs_signal - median_signal
    
    # Normalize the difference signal to have zero mean and unit variance
    norm_signal = (diff_signal - np.mean(diff_signal)) / np.std(diff_signal)
    
    # Threshold the normalized difference signal to detect artifact segments
 #   artifact_mask = norm_signal > threshold
#    thresh_use = np.max(abs_signal) / 3
    artifact_mask = abs_signal > threshold 
    saw_artifact = np.max(artifact_mask)
#    print("abs: " + str(abs_signal) + "  thr: " + str(threshold) + "  detect:" + str(saw_artifact))

    return artifact_mask

def detect_band_with_rms(b, a, bh, ah, thesignal, numsamples, threshold=10):

#    print("sig into delta:  ", thesignal[:4])

    thefilteredsignal = np.zeros(numsamples)
    thefilteredsignal = filtfilt(bh, ah, thesignal)
    thefilteredsignal = lfilter(b, a, thefilteredsignal)

#    print("filtered:  ", thefilteredsignal[:4])
 
    # Calculate the absolute value of the signal
    abs_signal = np.abs(thefilteredsignal)
    rms_signal = np.sqrt(np.std(thefilteredsignal))
#    print("abs:  ", abs_signal[:4])
    
    # Apply a median filter to the absolute signal
    median_signal = signal.medfilt(abs_signal, 5)
    
    # Calculate the difference between the absolute signal and the median-filtered signal
    diff_signal = abs_signal - median_signal
    
    # Normalize the difference signal to have zero mean and unit variance
    norm_signal = (diff_signal - np.mean(diff_signal)) / np.std(diff_signal)
    
    # Threshold the normalized difference signal to detect artifact segments
 #   artifact_mask = norm_signal > threshold
#    thresh_use = np.max(abs_signal) / 3
    #artifact_mask = abs_signal > threshold
    artifact_mask = abs(abs_signal - threshold) 
    saw_artifact = np.max(artifact_mask)
#    print("abs: " + str(abs_signal) + "  thr: " + str(threshold) + "  detect:" + str(saw_artifact))

    return artifact_mask, rms_signal

#  DETECT THE PROPER PEAK OF A SIGNAL IN A RANGE
def detect_peak(signal):
    peak_index = np.argmax(signal)
    if peak_index == 0:
        retcode = 0
    elif peak_index == len(signal)-1:
        retcode = 0
    elif signal[peak_index] > signal[peak_index + 1] and signal[peak_index] > signal[peak_index-1]:
        retcode = peak_index
    else:
        retcode = 0
#    print("peak:  ", str(len(signal)), "   ", str(peak_index), "   ", str(signal[peak_index]))
    return retcode

#  DETERMINE IF TWO VALUES ARE WITHIN A CERTAIN PERCENTAGE
def is_within_percent(a, b, p):
    diff = abs(a-b)
    perc = (diff / a) * 100
    return perc <= p


def percent_difference(a,b):
    diff=abs(a-b)
    return 100 * diff / a

def  t_test(mean1, std1, mean2, std2):
    return 1
    
#  DETECT IF THE PDR WAVE IS SINUSOIDAL
#  SHOULD CHECK IF SECOND HARMONIC BURSTS ARE NESTED INSIDE FUNDAMENTAL
def detect_pdr_sinusoidal(art_flags1, art_flags2, channel_labels, report_strings):
    score = 1
#    report_strings.append("Sinusoidal Test") 
    O1_index = channel_labels.index('O1')
    fund = np.sum(art_flags1[O1_index])/1000
    harm = np.sum(art_flags2[O1_index])/1000
    oc = np.sum(np.logical_and(art_flags1[O1_index], art_flags2[O1_index]))/1000
#    score = 100 * harm / fund
    score =  harm / oc
    if score > 0.20:
       localstring = "SinA: " + '{:.2f}'.format(score) + "  > 0.2 nonsinusoidal"
    else:
       localstring = "SinA: " + '{:.2f}'.format(score) + "  < 0.2 sinusoidal"
    report_strings.append(localstring)
    return score, report_strings

#  DETECT IF THE PDR IS MAXIMAL POSTERIORLY
def detect_pdr_max_post(art_flags, channel_labels, report_strings):
    Fz_index = channel_labels.index('FZ')
    Pz_index = channel_labels.index('PZ')
#    print("alpha max posterior test")
    fz = np.sum(art_flags[Fz_index])/1000
#    print (fz)
    pz = np.sum(art_flags[Pz_index])/1000
#    print (pz)
    score = fz / pz
#    print(score)
    if score > 1.0:
        localstring = "PDRMP: " + '{:.2f}'.format(score) + " (maximal posteriorly)"
        report_strings.append(localstring)
    else:
       localstring = "PDRMP: " + '{:.2f}'.format(score) +  " (not maximal posteriorly)"
       report_strings.append(localstring)
    return score, report_strings

# DETERMINE THE SYMMETRY IN ALPHA PDR COUNTS IN THE POSTERIOR REGION
def detect_pdr_sym(art_flags, channel_labels, report_strings):
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
#    print("posterior alpha asymmetry")
    o1 = np.sum(art_flags[O1_index])
#    print (o1)
    o2 = np.sum(art_flags[O2_index])
#    print (o2)
    score = o1/o2
#    print(score)
    if score < 1:
        localstring = "PDSYM: " + '{:.2f}'.format(score) + "  < 1 (lower on left, as expected)"
    else:
        localstring = "PDSYM: " + '{:.2f}'.format(score) + "  >= 1 (lower on right)"
    report_strings.append(localstring)
    return score, report_strings

#  DETERMINE THE SYNCHRONY IN ALPHA PDR, DO THE BURSTS COINCIDE
def detect_pdr_sync(art_flags, channel_labels, report_strings):
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
#    print("posterior alpha synchrony")
    o1 = np.sum(art_flags[O1_index])
#    print (o1)
    o2 = np.sum(art_flags[O2_index])
#    print(o2)
    oc = np.sum(np.logical_and(art_flags[O1_index], art_flags[O2_index]))
#    print(oc)
    score = (2 * oc) / (o1 + o2)
    if score >= 0.7:
        localstring = "PDSYN: " + '{:.2f}'.format(score) + "  > 0.7 (typical)"
    else:
        localstring = "PDSYN: " + '{:.2f}'.format(score) + "  < 0.7 (less than typical)"
    report_strings.append(localstring)
#    print (score)
    return score, report_strings

#  MEASURE IF PDR IS WELL-REGULATED USING ENTROPY OF BURSTING
def detect_pdr_reg(sigs, channel_labels, report_strings):
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
#    print("posterior alpha synchrony")
    o1 = tfcentropy(sigs[O1_index])
    #o1 = tfcentropy(art_flags[O1_index])     old
#    print (o1)
    o2 = tfcentropy(sigs[O2_index])
    #o2 = tfcentropy(art_flags[O2_index])     old
#    print(o2)
    oc = o1 + o2
#    print(oc)
    score = oc
    if score >= 0.8 :
        localstring = "PDREG: " + '{:.2f}'.format(score) + "  > 0.8 (well regulated)"
    else:
        localstring = "PDREG: " + '{:.2f}'.format(score) + "  < 0.8 (not well regulated)"
    report_strings.append(localstring)
    return score, report_strings

# MEASURE IF ENOUGH PDR FOR EYES CONDITION PDR MAGNITUDE
def detect_pdr_enough(art_flags, channel_labels, report_strings):
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
#    print("posterior alpha synchrony")
    o1 = np.sum(art_flags[O1_index])/1000
#    print (o1)
    o2 = np.sum(art_flags[O2_index])/1000
#    print(o2)
    oc = np.sum(np.logical_and(art_flags[O1_index], art_flags[O2_index]))
#    print(oc)
    score = (o1 + o2)/2
    if score > 20:
       localstring = "PDRMag: " + '{:.2f}'.format(score) + "  > 20 (high)"
    elif score >= 10:
        localstring = "PDRMag: " + '{:.2f}'.format(score) + "  > 10 (typical)"
    else:
        localstring = "PDRMag: " + '{:.2f}'.format(score) + "  < 10 (low)"
    report_strings.append(localstring)
 #   print (score)
    return score, report_strings

#  MEASURE FRONT TO BACK BETA RATIO
def detect_beta_ftob(art_flags, channel_labels, report_strings):
    Fz_index = channel_labels.index('FZ')
    Pz_index = channel_labels.index('PZ')
#    print("anterior / posterior beta")
    fz = np.sum(art_flags[Fz_index])/1000
#    print (fz)
    pz = np.sum(art_flags[Pz_index])/1000
#    print(pz)
    score = fz/pz
#    print(score)
    if score >= 1:
        localstring = "BMF: " + '{:.2f}'.format(score) + "  > 1  (as expected)"
    else:
        localstring = "BMF: " + '{:.2f}'.format(score) + "  < 1 (beta not maximum frontally)"
    report_strings.append(localstring)
    return score, report_strings

#  DETECT IF LOW VOLTAGE FAST PHENOTYPE
def detect_phen_lovfast(art_flags, channel_labels, report_strings):
    score = 6
    return score, report_strings

#  DETECT IF EPILEPTIFORM ACTIVITY
def detect_phen_epi(art_flags, channel_labels, report_strings):
    score = 5
    return score, report_strings

#  DETECT IF DIFFUSE SLOW PHENOTYPE
def detect_phen_difslow(art_flags, channel_labels, report_strings):
    score = 12.718
    return score, report_strings

#  DETECT IF FOCAL ABNORMALITY
def detect_phen_focal_ab(art_flags, channel_labels, report_strings):
    score = 3.14
    return score, report_strings

#  DETECT IF MIXED FAST AND SLOW
def detect_phen_mixfslow(art_flags, channel_labels, report_strings):
    score = 1.4142
    return score, report_strings

def detect_frontal_delta(art_flags, channel_labels, report_strings):
    F3_index = channel_labels.index('F3')
    F4_index = channel_labels.index('F4')
    FZ_index = channel_labels.index('FZ')
    F7_index = channel_labels.index('F7')
    F8_index = channel_labels.index('F8')
    f3 = np.sum(art_flags[F3_index])
    f4 = np.sum(art_flags[F4_index])
    fz = np.sum(art_flags[FZ_index])
    f7 = np.sum(art_flags[F7_index])
    f8 = np.sum(art_flags[F8_index])
    score = ((f3 + f4 + fz + f7 + f8)/5)/10000
    return score, report_strings

#  DETECT IF EXCESS FRONTAL SLOW WAVES
def detect_phen_xsfrontslow(art_flags, channel_labels, report_strings):
    F3_index = channel_labels.index('F3')
    F4_index = channel_labels.index('F4')
    FZ_index = channel_labels.index('FZ')
    C3_index = channel_labels.index('C3')
    C4_index = channel_labels.index('C4')
    f3 = np.sum(art_flags[F3_index])
    f4 = np.sum(art_flags[F4_index])
    fz = np.sum(art_flags[FZ_index])
    c3 = np.sum(art_flags[C3_index])
    c4 = np.sum(art_flags[C4_index])
    score = ((f3 + f4 + fz + c3 + c4)/5)/10000
    return score, report_strings
# focaltheta

def detect_diffuse_delta(art_flags, channel_labels, report_strings):
    sums = []
    for i in range(0, 19):
        sum_ = np.sum(art_flags[i])
        sums.append(sum_)
    #print('aksjdhfaksdhfpiusdhf', len(sums))
    score = (sum(sums) / 19) / 10000
    #print(score)
    return score, report_strings

def detect_diffuse_theta(art_flags, channel_labels, report_strings):
    sums = []
    for i in range(0, 19):
        sum_ = np.sum(art_flags[i])
        sums.append(sum_)
    #print('aksjdhfaksdhfpiusdhf', len(sums))
    score = (sum(sums) / 19) / 10000
    #print(score)
    return score, report_strings

def detect_diffuse_hibeta(art_flags, channel_labels, report_strings):
    sums = []
    for i in range(0, 19):
        sum_ = np.sum(art_flags[i])
        sums.append(sum_)
    #print('aksjdhfaksdhfpiusdhf', len(sums))
    score = (sum(sums) / 19) / 10000
    #print(score)
    return score, report_strings

def detect_focal_delta(art_flags, channel_labels, report_strings, num_above_half):
    sums = []
    for i in range(0, 19):
        sum_ = np.sum(art_flags[i])
        sums.append(sum_)
    #print('SUMS: ', sums)
    max_chan_index = sums.index(max(sums))
    #print('Max Chan Index: ', max_chan_index)
    max_site = max(sums)
    #print('MAX VAL: ', max_site, 'SITE: ', channel_labels[max_chan_index])
    rogues = []
    others = []
    for sum in sums:
        if sum >= (max_site*.8):
            rogues.append(sum)
        elif sum < (max_site*.8):
            others.append(sum)
    #print(others)
    #print(rogues)
    score = np.sum(rogues) / ((np.sum(rogues)) + (np.sum(others)))
    score2 = (np.sum(rogues) / len(rogues)) / 10000
    return score, score2, report_strings

def detect_focal_theta(art_flags, channel_labels, report_strings, num_above_half):
    sums = []
    for i in range(0, 19):
        sum_ = np.sum(art_flags[i])
        sums.append(sum_)
    #print('SUMS: ', sums)
    max_chan_index = sums.index(max(sums))
    #print('Max Chan Index: ', max_chan_index)
    max_site = max(sums)
    #print('MAX VAL: ', max_site, 'SITE: ', channel_labels[max_chan_index])
    rogues = []
    others = []
    for sum in sums:
        if sum >= (max_site*.8):
            rogues.append(sum)
        elif sum < (max_site*.8):
            others.append(sum)
    #print(others)
    #print(rogues)
    score = np.sum(rogues) / ((np.sum(rogues)) + (np.sum(others)))
    score2 = (np.sum(rogues) / len(rogues)) / 10000
    #print('SCORE: ', score, score2)
    return score, score2, report_strings

def detect_focal_hibeta(art_flags, channel_labels, report_strings, num_above_half):
    sums = []
    for i in range(0, 19):
        sum_ = np.sum(art_flags[i])
        sums.append(sum_)
    #print('SUMS: ', sums)
    max_chan_index = sums.index(max(sums))
    #print('Max Chan Index: ', max_chan_index)
    max_site = max(sums)
    #print('MAX VAL: ', max_site, 'SITE: ', channel_labels[max_chan_index])
    rogues = []
    others = []
    for sum in sums:
        if sum >= (max_site*.8):
            rogues.append(sum)
        elif sum < (max_site*.8):
            others.append(sum)
    #print(others)
    #print(rogues)
    score = np.sum(rogues) / ((np.sum(rogues)) + (np.sum(others)))
    score2 = (np.sum(rogues) / len(rogues)) / 10000
    return score, score2, report_strings

def detect_pdr_epoch_width(alpha_art, channel_labels):
    P3_index = channel_labels.index('P3')
    P4_index = channel_labels.index('P4')
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
    p3 = alpha_art[P3_index, :]
    p4 = alpha_art[P4_index, :]
    o1 = alpha_art[O1_index, :]
    o2 = alpha_art[O2_index, :]
    art_list = [p3, p4, o1, o2]
    widths = [] 
    half_peaks = []
    for art in art_list:
        peak_indices = []
        max_value = max(art)
        for i in range(1, len(art) - 1):
            if art[i] > art[i-1] and art[i] > art[i+1]:
                peak_indices.append(i)
        if not peak_indices:
            return None
#        print('PEAK INDICES:', peak_indices)
        current_peak_value = max(art[i] for i in peak_indices)
#        print('PEAK VALUE:', current_peak_value)
        max_peak_index = peak_indices.index(art.tolist().index(current_peak_value))
#        print('MAX PEAK INDEX:', max_peak_index)
        peak_index = peak_indices[max_peak_index]
        # Find the first peak to the right of the max where the next peak isn't above half the max
        furthest_right = peak_index
        for peak in peak_indices[max_peak_index:]:
            if art[peak] > max(art) / 2:
                furthest_right = peak
            else:
                break

        # Find the first peak to the left of the max where the next peak isn't above half the max
        furthest_left = peak_index
        for peak in peak_indices[:max_peak_index][::-1]:
            if art[peak] > max(art) / 2:
                furthest_left = peak
            else:
                break
        
        width = furthest_right - furthest_left
        widths.append((width/256)*1000)
        half_peaks.append(max_value)

    ind = half_peaks.index(max(half_peaks)) 
    width = widths[ind]
    #width = 2
    return width    

def detect_pdr_art_width(alpha_art, channel_labels, numpages):
    P3_index = channel_labels.index('P3')
    P4_index = channel_labels.index('P4')
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
    p3 = alpha_art[P3_index, :]
    p4 = alpha_art[P4_index, :]
    o1 = alpha_art[O1_index, :]
    o2 = alpha_art[O2_index, :]
    art_list = [p3, p4, o1, o2]
    avg_widths = []
    avg_half_peaks = []
    for art in art_list:
        widths = []
        half_peaks = []
        numpages = np.floor(numpages)
        for k in range(int(numpages)):
            epoch_range = np.arange(2560*(k-1), 2560*k, 1)
            art_s = art[epoch_range]
            peak_indices = []
            max_value = max(art_s)
            for i in range(1, len(art_s) - 1):
                if art_s[i] > art_s[i-1] and art_s[i] > art_s[i+1]:
                    peak_indices.append(i)
            if not peak_indices:
                return None
        
            current_peak_value = max(art_s[i] for i in peak_indices)
            max_peak_index = peak_indices.index(art_s.tolist().index(current_peak_value))
            peak_index = peak_indices[max_peak_index]
            # Find the first peak to the right of the max where the next peak isn't above half the max
            furthest_right = peak_index
            for peak in peak_indices[max_peak_index:]:
                if art_s[peak] > max(art_s) / 2:
                    furthest_right = peak
                else:
                    break

            # Find the first peak to the left of the max where the next peak isn't above half the max
            furthest_left = peak_index
            for peak in peak_indices[:max_peak_index][::-1]:
                if art_s[peak] > max(art_s) / 2:
                    furthest_left = peak
                else:
                    break
            
            width = furthest_right - furthest_left
            widths.append((width/256)*1000)
            half_peaks.append(max_value)

        avg_width = sum(widths)/len(widths)
        avg_peak = sum(half_peaks)/len(half_peaks)
        avg_widths.append(avg_width)
        avg_half_peaks.append(avg_peak)
    
    ind = avg_half_peaks.index(max(avg_half_peaks))
    width = avg_widths[ind]
    #width = 2
    return width

def detect_pdr_amp(alpha_art, channel_labels, numpages):
    P3_index = channel_labels.index('P3')
    P4_index = channel_labels.index('P4')
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
    p3 = alpha_art[P3_index, :]
    p4 = alpha_art[P4_index, :]
    o1 = alpha_art[O1_index, :]
    o2 = alpha_art[O2_index, :]
    art_list = [p3, p4, o1, o2]
    avg_maxes = []
    for art in art_list:
        maxes = []
        for k in range(int(numpages)):
            epoch_range = np.arange(2560*(k-1), 2560*k, 1)
            art_s = art[epoch_range]
            max_val = max(art_s)
            maxes.append(max_val)
        avg_max = sum(maxes) / len(maxes)
        avg_maxes.append(avg_max)
    score = max(avg_maxes)
    return score

def detect_pdr_amp_epoch(alpha_art, channel_labels):
    P3_index = channel_labels.index('P3')
    P4_index = channel_labels.index('P4')
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
    p3 = alpha_art[P3_index, :]
    p4 = alpha_art[P4_index, :]
    o1 = alpha_art[O1_index, :]
    o2 = alpha_art[O2_index, :]
    art_list = [p3, p4, o1, o2]
    maxes = []
    for art in art_list:
        max_val = max(art)
        maxes.append(max_val)
    score = max(maxes)
    return score

def detect_pdr_freq_epoch(sigs, channel_labels):
    P3_index = channel_labels.index('P3')
    P4_index = channel_labels.index('P4')
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
    p3 = sigs[P3_index, :]
    p4 = sigs[P4_index, :]
    o1 = sigs[O1_index, :]
    o2 = sigs[O2_index, :]
    sig_list = [p3, p4, o1, o2]
    kernel1 = np.array([1/16, 1/8, 3/16, 1/2, 3/16, 1/8, 1/16])
    widths = []
    half_peaks = []
    for sig in sig_list:
        fft_s = np.fft.fft(sig)
        amp_s = np.abs(fft_s)
        amp_sc = np.convolve(amp_s, kernel1, mode='same')
        retcon = detect_peak(amp_sc[70:140])
        half_peak = max(amp_sc[70:140])/2
        half_peaks.append(half_peak)
        tolerance = 80
        indexes = [i for i, value in enumerate(amp_sc[:650]) if abs(value-half_peak) <= tolerance]
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
        widths.append(half_width)

    ind = half_peaks.index(max(half_peaks))
    width = widths[ind]
    return width    
        

def detect_pdr_freq_width(sigs, channel_labels, numpages):
    P3_index = channel_labels.index('P3')
    P4_index = channel_labels.index('P4')
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
    p3 = sigs[P3_index, :]
    p4 = sigs[P4_index, :]
    o1 = sigs[O1_index, :]
    o2 = sigs[O2_index, :]
    sig_list = [p3, p4, o1, o2]
    kernel1 = np.array([1/16, 1/8, 3/16, 1/2, 3/16, 1/8, 1/16])
    widths = []
    half_peaks = []
    for sig in sig_list:
        epoch_vals= []
        powers = []
        ffts = []
        numpages = np.floor(numpages)
        #print('numpages: ', numpages)
        for k in range(int(numpages)):
            #print('WORKS-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=')
            epoch_range = np.arange(2560*(k-1), 2560*k, 1)
            sig_s = sig[epoch_range] #* window_s
            fft_s = np.fft.fft(sig_s)
            ffts.append(fft_s)
            phase = np.imag(fft_s)
            amp_s = np.abs(fft_s)
            amp_sc = np.convolve(amp_s, kernel1, mode='same')
            power_s = amp_sc ** 2
            epoch_vals.append(amp_sc)
            power_s = np.abs(power_s)
            #print('Length is: ', len(power_s))
            powers.append(power_s)
            freq_s = np.fft.fftfreq(len(sig_s), d=1/256)
        #phases = phases*100
        avg_amp_sc = sum(epoch_vals) / len(epoch_vals)
        retcon = detect_peak(avg_amp_sc[70:140])
        half_peak = max(avg_amp_sc[70:140])/2
        half_peaks.append(half_peak)
        tolerance = 80
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
        print('Half Width: ', half_width)
        widths.append(half_width)

    ind = half_peaks.index(max(half_peaks))
    width = widths[ind]
    return width

def detect_fractal_dimension(sigs, channel_labels, numsamples):
    cz_index = channel_labels.index('CZ')
    cz_sigs = sigs[cz_index, :]
    n1 = numsamples
    derivative = np.gradient(cz_sigs)
    n2 = np.sum(np.diff(np.sign(derivative)) != 0)
    score = (np.log10(n1))/(np.log10(n1)+np.log10(n1/(n1+.4*n2)))
    score = score - 1
    score = score*100
    return score

def detect_drowsiness(art_flags, channel_labels):
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
    o1 = art_flags[O1_index]
    o2 = art_flags[O2_index]
    zeroth = ((np.sum(o1) + np.sum(o2))/2)/1000
    first = (np.mean(o1) + np.mean(o2))/2
    second = (np.var(o1) + np.var(o2))/2
    #-------------------------
    # NOTE: int32 dtype is intentional. The EC_191 reference database was
    # built when np.arange defaulted to int32 on Windows (numpy <2.0).
    # x_values**2 overflows at i>=46341, producing wrap-around values that
    # the reference statistics depend on. numpy 2.x defaults arange to
    # int64, which yields mathematically correct but reference-incompatible
    # results. Forcing int32 here reproduces production behavior.
    x_values = np.arange(0, len(o1), 1, dtype=np.int32)
    zeroth = ((np.sum(o1) + np.sum(o2))/2)/1000
    first = (((np.dot(x_values, o1) / sum(o1)) + (np.dot(x_values, o2) / sum(o2)))/2)/1000
    second = (((np.dot(x_values**2, o1) / sum(o1)) + (np.dot(x_values, o2) / sum(o2)))/2)/100000
    return zeroth, first, second

def detect_moments(art_flags, channel_labels):
    CZ_index = channel_labels.index('CZ')
    cz = art_flags[CZ_index]
    zeroth = np.sum(cz)/1000
    first = np.mean(cz)
    second = np.var(cz)
    #------------------------------
    # NOTE: int32 dtype is intentional — see detect_drowsiness above.
    # The EC_191 reference database was built with numpy <2.0's int32
    # arange default. x_values**2 overflows at i>=46341 and the
    # reference statistics depend on the wrap-around values.
    x_values = np.arange(0, len(cz), 1, dtype=np.int32)
    zeroth = sum(cz)/1000
    first = (np.dot(x_values, cz) / sum(cz))/1000
    second = (np.dot(x_values**2, cz) / sum(cz))/100000
    #-------------------------------------
    return zeroth, first, second

#  DETECT FRONTAL ALPHA ASYMMETRY -  COULD MODIFY TO PASS IN CHANNELS AND BANDS
def detect_phen_frontasym(art_flags, channel_labels, report_strings):
#    print("frontal alpha asymmetry")
    F3_index = channel_labels.index('F3')
    F4_index = channel_labels.index('F4')
    f3 = np.sum(art_flags[F3_index])
#    print (f3)
    f4 = np.sum(art_flags[F4_index])
#    print (f4)
    score = f3/f4
#    print(score)
    if score < 0.9:
        localstring = "FAS: " + '{:.2f}'.format(score) + "  < 0 (positive affect)"
    else:
        localstring = "FAS: " + '{:.2f}'.format(score) + "  >= 0 (negative affect)"
    report_strings.append(localstring)
    return score, report_strings

#  DETERMINE EXCESS TEMPORAL ALPHA
def detect_phen_xstempalpha(art_flags, channel_labels, report_strings):
#    print("excess temporal alpha")
    T3_index = channel_labels.index('T3')
    T4_index = channel_labels.index('T4')
    t3 = np.sum(art_flags[T3_index])
#    print (t3)
    t4 = np.sum(art_flags[T4_index])
#    print (t4)
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
    o1 = np.sum(art_flags[O1_index])
#    print (o1)
    o2 = np.sum(art_flags[O2_index])
#    print(o2)
    #print('T3T4:', t3+t4)
    #print('O1O2:', o1+o2)
    score = (t3+t4)/(o1+o2)
    #print('score:', score)
    if score > 0.7:
        localstring = "XSTA: " + '{:.2f}'.format(score) + "  > 0.7 (excess)"
    else:
        localstring = "XSTA: " + '{:.2f}'.format(score) + "  <= 0.7 (not in excess)"
    report_strings.append(localstring)
    return score, report_strings

#  DETECT IF A FAST ALPHA PHENOTYPE USING THE FILTERED BURST COUNTS FOR ALPHA AND ALPHA2
def detect_phen_fastalpha(art_flags1, art_flags2, art_flags3, channel_labels, report_strings, myvisualsigs, numpages):
    O1_index = channel_labels.index('O1')
    O2_index = channel_labels.index('O2')
    P3_index = channel_labels.index('P3')
    P4_index = channel_labels.index('P4')

    o11 = np.sum(art_flags1[O1_index])/1000  #low
    o12 = np.sum(art_flags2[O1_index])/1000  #mid
    o13 = np.sum(art_flags3[O1_index])/1000  #high
    score = o13 / o11
    if score > 1.1:
      localstring = "FASTA: " + '{:.2f}'.format(score)  + ": above 1.1:  Fast Alpha"
    elif score < 0.9:
      localstring = "FASTA: " + '{:.2f}'.format(score)  + ": below 0.9:  Slow Alpha"
    else:
      localstring = "FASTA: " + '{:.2f}'.format(score)  + "within 0.9-1.1: Typical Alpha"
    report_strings.append(localstring)
    
    chans = [O1_index, O2_index, P3_index, P4_index]
    

    kernel1 = np.array([1/16, 1/8, 3/16, 1/2, 3/16, 1/8, 1/16])
    #kernel1=np.array([1/16, 1/16, 1/8, 1/2, 1/8, 1/16, 1/16])
    sig_s = np.zeros(2560)
    amp_s = np.zeros(2560)
    amp_sc = np.zeros(2560)
    window_s = np.hamming(2560)
    
    #epoch_vals= []
    #phases = []
    #powers = []
    #ffts = []
    #cyc_ffts = []
    alpha_vals = []
    alpha_nums = []
    theta_nums = []
    beta_nums = []
    for j in chans:
        epoch_vals= []
        phases = []
        powers = []
        ffts = []
        numpages = np.floor(numpages)
        #print('numpages: ', numpages)
        for k in range(int(numpages)):
            #print('WORKS-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=')
            epoch_range = np.arange(2560*(k-1), 2560*k, 1)
            sig_s = myvisualsigs[j, epoch_range] #* window_s
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

#  FIND THE PEAKS

        peak_index=detect_peak(avg_amp_sc[7*10:14*10])
        peak_indexl=detect_peak(avg_amp_sc[7*10:11*10])
        #print('low peak:', peak_indexl)
        peak_indexh=detect_peak(avg_amp_sc[10*10:14*10])
        #print('Hi Peak:', peak_indexh)
        peak_indexo=detect_peak(avg_amp_sc[4*10:40*10])
#        print("peaks:  ", (7*10+peak_index)/10, (6*10+peak_indexl)/10, (10*10+peak_indexh)/10, (4*10+peak_indexo)/10)
#        tstring = "{:.1f}".format(7*40+peak_index)
        
#        else:
#          tstring = f"{channel_labels_short[i]}:"

#  GET MICROVOLTS VALUES FOR DIFFERENT WAVE-------------------------------------------------------------------------------------------------------------------------------------

       
        #val = max(avg_amp_sc[70:140])
        #alpha_nums.append(np.sqrt(val)/2)
        
        if peak_index != 0:
            value=(7*10+peak_index)/10
            tstringv = f"{value:.1f}"
        else:
            value = 0
        #print('Val: ', value)
        if peak_indexl != 0:
            valuel=(7*10+peak_indexl)/10
            tstringl = f"{valuel:.1f}"
        else:
            valuel = 0
        #print('low Peak: ', valuel)
        if peak_indexh != 0:
            valueh=(10*10+peak_indexh)/10
            tstringh = f"{valueh:.1f}"
        else:
            valueh = 0
        #print('hi peak: ', valueh)
    
        try:
            alpha_vals.append(float(tstringl))
            val = max(avg_amp_sc[70:100])
            alpha_nums.append(np.sqrt(val)/2)
        except:
            print('NO VAL')
        try:
            alpha_vals.append(float(tstringh))
            val = max(avg_amp_sc[100:140])
            alpha_nums.append(np.sqrt(val)/2)
        except:
            print('NO VAL')
    
        
    print('Alphavals--------------------------------', alpha_vals)
    print('AlphaNums--------------------------------', alpha_nums)
    
    if len(alpha_vals) != 0:
        alpha_speed = alpha_vals[alpha_nums.index(max(alpha_nums))]
    else:
        alpha_speed = 0
    print('Alpha Speed -------------: ', alpha_speed)
    
    return score, alpha_speed, report_strings

# DETECT SPINDLING BETA - USE ENTROPY OF BURSTS TO DETERMINE IF SPINDLING
def detect_phen_spinbeta(art_flags, channel_labels, report_strings):
    cz_index = channel_labels.index('CZ')
    fz_index = channel_labels.index('FZ')
    cz = np.sum(art_flags[cz_index])
    fz = np.sum(art_flags[fz_index])
    score = (cz + fz)/1000
    #print('score:', score)
    return score, report_strings

#  DETECT IF ONE SET OF FLAGS IS CAUSING ANOTHER (B ONLY OCCURS WHEN A)
#  WORKS WITH TOT ARRAYS WHICH COUNT HOW MANY CHANNELS PARTICIPATE
def detect_a_causes_b(art_flags1, art_flags2):
    sum1 = np.sum(art_flags1)
    sum2 = np.sum(art_flags2)
#    sum3 = sum(x for x, y in zip(art_flags1, art_flags2) if y > 0)
    sum3 = sum(y for x, y in zip(art_flags1, art_flags2) if x > y)
#    print("sum1 is   ", sum1, "   sum2 is   ", sum2, "   sum3 is  ", sum3)
    if sum2 != 0:
      result = 2 * sum3 / (sum1 + sum2)
    else:
      result = 0
#    print("result is    ", result)
    return result


def detect_all_a_causes_b(comod, time_range, has_artifact_tot, lodelta_artifact_tot, delta_artifact_tot, theta_artifact_tot, loalpha_artifact_tot, alpha_artifact_tot, hialpha_artifact_tot,
                          lobeta_artifact_tot, beta_artifact_tot, hibeta_artifact_tot, gamma_artifact_tot, higamma_artifact_tot, f60hz_artifact_tot, f61hz_artifact_tot):

    comod[0] = detect_a_causes_b(has_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[1] = detect_a_causes_b(has_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[2] = detect_a_causes_b(has_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[3] = detect_a_causes_b(has_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[4] = detect_a_causes_b(has_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[5] = detect_a_causes_b(has_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[6] = detect_a_causes_b(has_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[7] = detect_a_causes_b(has_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[8] = detect_a_causes_b(has_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[9] = detect_a_causes_b(has_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[10] = detect_a_causes_b(has_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[11] = detect_a_causes_b(has_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[12] = detect_a_causes_b(has_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[13] = detect_a_causes_b(has_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[16] = detect_a_causes_b(lodelta_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[17] = detect_a_causes_b(lodelta_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[18] = detect_a_causes_b(lodelta_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[19] = detect_a_causes_b(lodelta_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[20] = detect_a_causes_b(lodelta_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[21] = detect_a_causes_b(lodelta_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[22] = detect_a_causes_b(lodelta_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[23] = detect_a_causes_b(lodelta_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[24] = detect_a_causes_b(lodelta_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[25] = detect_a_causes_b(lodelta_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[26] = detect_a_causes_b(lodelta_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[27] = detect_a_causes_b(lodelta_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[28] = detect_a_causes_b(lodelta_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[29] = detect_a_causes_b(lodelta_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[32] = detect_a_causes_b(delta_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[33] = detect_a_causes_b(delta_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[34] = detect_a_causes_b(delta_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[35] = detect_a_causes_b(delta_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[36] = detect_a_causes_b(delta_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[37] = detect_a_causes_b(delta_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[38] = detect_a_causes_b(delta_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[39] = detect_a_causes_b(delta_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[40] = detect_a_causes_b(delta_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[41] = detect_a_causes_b(delta_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[42] = detect_a_causes_b(delta_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[43] = detect_a_causes_b(delta_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[44] = detect_a_causes_b(delta_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[45] = detect_a_causes_b(delta_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[48] = detect_a_causes_b(theta_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[49] = detect_a_causes_b(theta_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[50] = detect_a_causes_b(theta_artifact_tot[time_range], delta_artifact_tot[time_range])

    comod[51] = detect_a_causes_b(theta_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[52] = detect_a_causes_b(theta_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[53] = detect_a_causes_b(theta_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[54] = detect_a_causes_b(theta_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[55] = detect_a_causes_b(theta_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[56] = detect_a_causes_b(theta_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[57] = detect_a_causes_b(theta_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[58] = detect_a_causes_b(theta_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[59] = detect_a_causes_b(theta_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[60] = detect_a_causes_b(theta_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[61] = detect_a_causes_b(theta_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[64] = detect_a_causes_b(loalpha_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[65] = detect_a_causes_b(loalpha_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[66] = detect_a_causes_b(loalpha_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[67] = detect_a_causes_b(loalpha_artifact_tot[time_range], theta_artifact_tot[time_range])

    comod[68] = detect_a_causes_b(loalpha_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[69] = detect_a_causes_b(loalpha_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[70] = detect_a_causes_b(loalpha_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[71] = detect_a_causes_b(loalpha_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[72] = detect_a_causes_b(loalpha_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[73] = detect_a_causes_b(loalpha_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[74] = detect_a_causes_b(loalpha_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[75] = detect_a_causes_b(loalpha_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[76] = detect_a_causes_b(loalpha_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[77] = detect_a_causes_b(loalpha_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[80] = detect_a_causes_b(alpha_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[81] = detect_a_causes_b(alpha_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[82] = detect_a_causes_b(alpha_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[83] = detect_a_causes_b(alpha_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[84] = detect_a_causes_b(alpha_artifact_tot[time_range], loalpha_artifact_tot[time_range])

    comod[85] = detect_a_causes_b(alpha_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[86] = detect_a_causes_b(alpha_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[87] = detect_a_causes_b(alpha_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[88] = detect_a_causes_b(alpha_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[89] = detect_a_causes_b(alpha_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[90] = detect_a_causes_b(alpha_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[91] = detect_a_causes_b(alpha_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[92] = detect_a_causes_b(alpha_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[93] = detect_a_causes_b(alpha_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[96] = detect_a_causes_b(hialpha_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[97] = detect_a_causes_b(hialpha_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[98] = detect_a_causes_b(hialpha_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[99] = detect_a_causes_b(hialpha_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[100] = detect_a_causes_b(hialpha_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[101] = detect_a_causes_b(hialpha_artifact_tot[time_range], alpha_artifact_tot[time_range])

    comod[102] = detect_a_causes_b(hialpha_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[103] = detect_a_causes_b(hialpha_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[104] = detect_a_causes_b(hialpha_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[105] = detect_a_causes_b(hialpha_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[106] = detect_a_causes_b(hialpha_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[107] = detect_a_causes_b(hialpha_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[108] = detect_a_causes_b(hialpha_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[109] = detect_a_causes_b(hialpha_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[112] = detect_a_causes_b(lobeta_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[113] = detect_a_causes_b(lobeta_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[114] = detect_a_causes_b(lobeta_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[115] = detect_a_causes_b(lobeta_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[116] = detect_a_causes_b(lobeta_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[117] = detect_a_causes_b(lobeta_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[118] = detect_a_causes_b(lobeta_artifact_tot[time_range], hialpha_artifact_tot[time_range])

    comod[119] = detect_a_causes_b(lobeta_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[120] = detect_a_causes_b(lobeta_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[121] = detect_a_causes_b(lobeta_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[122] = detect_a_causes_b(lobeta_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[123] = detect_a_causes_b(lobeta_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[124] = detect_a_causes_b(lobeta_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[125] = detect_a_causes_b(lobeta_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[128] = detect_a_causes_b(beta_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[129] = detect_a_causes_b(beta_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[130] = detect_a_causes_b(beta_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[131] = detect_a_causes_b(beta_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[132] = detect_a_causes_b(beta_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[133] = detect_a_causes_b(beta_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[134] = detect_a_causes_b(beta_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[135] = detect_a_causes_b(beta_artifact_tot[time_range], lobeta_artifact_tot[time_range])

    comod[136] = detect_a_causes_b(beta_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[137] = detect_a_causes_b(beta_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[138] = detect_a_causes_b(beta_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[139] = detect_a_causes_b(beta_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[140] = detect_a_causes_b(beta_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[141] = detect_a_causes_b(beta_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[144] = detect_a_causes_b(hibeta_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[145] = detect_a_causes_b(hibeta_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[146] = detect_a_causes_b(hibeta_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[147] = detect_a_causes_b(hibeta_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[148] = detect_a_causes_b(hibeta_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[149] = detect_a_causes_b(hibeta_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[150] = detect_a_causes_b(hibeta_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[151] = detect_a_causes_b(hibeta_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[152] = detect_a_causes_b(hibeta_artifact_tot[time_range], beta_artifact_tot[time_range])

    comod[153] = detect_a_causes_b(hibeta_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[154] = detect_a_causes_b(hibeta_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[155] = detect_a_causes_b(hibeta_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[156] = detect_a_causes_b(hibeta_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[157] = detect_a_causes_b(hibeta_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[160] = detect_a_causes_b(gamma_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[161] = detect_a_causes_b(gamma_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[162] = detect_a_causes_b(gamma_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[163] = detect_a_causes_b(gamma_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[164] = detect_a_causes_b(gamma_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[165] = detect_a_causes_b(gamma_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[166] = detect_a_causes_b(gamma_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[167] = detect_a_causes_b(gamma_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[168] = detect_a_causes_b(gamma_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[169] = detect_a_causes_b(gamma_artifact_tot[time_range], hibeta_artifact_tot[time_range])

    comod[170] = detect_a_causes_b(gamma_artifact_tot[time_range], gamma_artifact_tot[time_range])
    comod[171] = detect_a_causes_b(gamma_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[172] = detect_a_causes_b(gamma_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[173] = detect_a_causes_b(gamma_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    comod[176] = detect_a_causes_b(gamma_artifact_tot[time_range], has_artifact_tot[time_range])
    comod[177] = detect_a_causes_b(gamma_artifact_tot[time_range], lodelta_artifact_tot[time_range])
    comod[178] = detect_a_causes_b(gamma_artifact_tot[time_range], delta_artifact_tot[time_range])
    comod[179] = detect_a_causes_b(gamma_artifact_tot[time_range], theta_artifact_tot[time_range])
    comod[180] = detect_a_causes_b(gamma_artifact_tot[time_range], loalpha_artifact_tot[time_range])
    comod[181] = detect_a_causes_b(gamma_artifact_tot[time_range], alpha_artifact_tot[time_range])
    comod[182] = detect_a_causes_b(gamma_artifact_tot[time_range], hialpha_artifact_tot[time_range])
    comod[183] = detect_a_causes_b(gamma_artifact_tot[time_range], lobeta_artifact_tot[time_range])
    comod[184] = detect_a_causes_b(gamma_artifact_tot[time_range], beta_artifact_tot[time_range])
    comod[185] = detect_a_causes_b(gamma_artifact_tot[time_range], hibeta_artifact_tot[time_range])
    comod[186] = detect_a_causes_b(gamma_artifact_tot[time_range], gamma_artifact_tot[time_range])

    comod[187] = detect_a_causes_b(higamma_artifact_tot[time_range], higamma_artifact_tot[time_range])
    comod[188] = detect_a_causes_b(higamma_artifact_tot[time_range], f60hz_artifact_tot[time_range])
    comod[189] = detect_a_causes_b(higamma_artifact_tot[time_range], f61hz_artifact_tot[time_range])

    return comod

#   FIND SUSPECT ICA COMPONENTS
    """
    COMPONENT SUSPICIOUSNESS CODES
    1  MAX FP1 ONLY
    2  MAX FP2 ONLY
    3  MAX FP2 AND FP2
    4  MAX F7 ONLY
    5  MAX F8 ONLY
    6  MAX F7 AND F8
    7  MAX T3
    8  MAX T4
    9  MAX T3 AND T4
    10 MAX A2
    """

def find_suspect_ica_components(ica_mixing, channel_labels_short, size):

    print("IN Find Suspect ICA Components")

    selected_channel_list = []
    selected_channel_reasons = []

#    print("ICA MIX:   ", ica_mixing)
#    print("CHANS:  ", channel_labels_short)
#    print("Size:   ", size)

#  FIND THE CHANNEL INDICES BASED ON THE LABELS
    fp1chan = channel_labels_short.index('FP1')
    fp2chan = channel_labels_short.index('FP2')
    f7chan = channel_labels_short.index('F7')
    f8chan = channel_labels_short.index('F8')
    t3chan = channel_labels_short.index('T3')
    t4chan = channel_labels_short.index('T4')

    if 'A2' in channel_labels_short:
      a2chan = channel_labels_short.index('A2')
      print("FOUND REFERENCE A2")
    else:
      a2chan = -1
      print("NO REFERENCE A2")

#    ax1chan = channel_labels_short.index('ax1')
#    ax2chan = channel_labels_short.index('ax2')


    ica_mix_abs = np.abs(ica_mixing)
    max_sites = []
    num_above_half = []
    sites_rsi = []
    for compno in range (size):
      compcolumn = ica_mix_abs[:, compno]
      comprow = ica_mix_abs[compno, :]
      max_val_site = np.max(comprow)
      maxval = np.max(compcolumn)
      maxloc = np.argmax(compcolumn)
 
      num_above_halfsite = np.sum(comprow > max_val_site/2)
      num_above_halfmax = np.sum(compcolumn > maxval/2)
      print("COMP: ", compno+1,   "MAXLOC:  ", maxloc, 
        "  MAXVAL:  ", maxval, "  MAX CHAN IS:  ", channel_labels_short[maxloc],
        "  NUM ABOVE HALF: ", num_above_halfmax)
      max_sites.append(channel_labels_short[maxloc])
      num_above_half.append(num_above_halfmax)
      sites_rsi.append(num_above_halfsite)

#  FIRST LOOK FOR ANYTHING THAT IS IN "ALL CHANNELS"
      if num_above_halfmax > 16:
        print("MAX AT MANY CHANNELS:  ", compno+1)
        selected_channel_list.append(compno+1)
        selected_channel_reasons.append(maxloc)

#  THEN LOOK FOR ANYTHING THAT  IS ONLY "ONE  CHANNEL"
#      elif num_above_halfmax < 2:
#        print("MAX AT ONLY ONE CHANNEL:  ", compno+1)
#        selected_channel_list.append(compno+1)
#        selected_channel_reasons.append(maxloc)

      elif maxloc == fp1chan and num_above_halfmax < 5:
        print("MAX AT FP1 COMPONENT:  ", compno+1)
        selected_channel_list.append(compno+1)
        selected_channel_reasons.append(fp1chan)
      elif maxloc == fp2chan and num_above_halfmax < 5:
        print("MAX AT FP2 COMPONENT:  ", compno+1)
        selected_channel_list.append(compno+1) 
        selected_channel_reasons.append(fp2chan)
      elif maxloc == f7chan and num_above_halfmax < 5:
        print("MAX AT F7 COMPONENT:  ", compno+1)
        selected_channel_list.append(compno+1)
        selected_channel_reasons.append(f7chan)      
      elif maxloc == f8chan and num_above_halfmax < 5:
        print("MAX AT F8 COMPONENT:  ", compno+1)
        selected_channel_list.append(compno+1)
        selected_channel_reasons.append(f8chan)
      elif maxloc == t3chan and num_above_halfmax < 5:
        print("MAX AT T3 COMPONENT:  ", compno+1)
        selected_channel_list.append(compno+1)
        selected_channel_reasons.append(t3chan)      
      elif maxloc == t4chan and num_above_halfmax < 5:
        print("MAX AT T4 COMPONENT:  ", compno+1)
        selected_channel_list.append(compno+1)
        selected_channel_reasons.append(t4chan)

      if a2chan != -1:
#         print("CHECKING REFERENCE A2")
         if maxloc == a2chan:
           print("MAX AT A2 COMPONENT:  ", compno+1)
           selected_channel_list.append(compno+1)
           selected_channel_reasons.append(a2chan)

      largest_indices = np.argsort(compcolumn)
#      print("Sorted indices:  ", largest_indices)
      largest_values = compcolumn[largest_indices]
      print("Largest vals:  ", largest_values[-4:])
      print("Largest indices:  ", largest_indices)
#      print("Largest locations:  ", channel_labels_short[largest_indices])


#    print("fp1 channel is found at:   ", fp1chan)
#    selected_channel_list = [3, 7]
#    selected_channel_reasons = [1, 2]

    return selected_channel_list, selected_channel_reasons, max_sites, num_above_half, sites_rsi

def reason_to_string(reason, channel_labels_short):
    string = "MAX AT:  " + channel_labels_short[reason]
    return string


# Load the EEG signal
#signal = np.loadtxt('path/to/eeg.txt')

# Detect artifact in the signal
#artifact_mask = detect_artifact(signal)

# Replace the artifact segments with NaN values
#signal[artifact_mask] = np.nan
