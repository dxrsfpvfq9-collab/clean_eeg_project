#tfcfilters.py
#clean_eeg_project
# 2-16-2023

import numpy as np
from scipy import signal
from scipy import stats
from scipy.signal import butter, lfilter, filtfilt


class filts:
    def filist(self, forder):
        self.forder = forder
        self.b, self.a, self.bh, self.ah = self.setup(1.0, 55.0)
        self.bv, self.av, self.bhv, self.ahv = self.setup(1.5, 45.0)
        self.bld, self.ald, self.bhld, self.ahld = self.setup(0.1, 2.0)
        self.bd, self.ad, self.bhd, self.ahd = self.setup(0.5, 4.0)
        self.bt, self.at, self.bht, self.aht = self.setup(4.0, 8.0)
        self.bla, self.ala, self.bhla, self.ahla = self.setup(8.0, 10.0)
        self.bal, self.aal, self.bhal, self.ahal = self.setup(8.0, 12.0)
        self.bha, self.aha, self.bhha, self.ahha = self.setup(10.0, 13.0)
        self.blb, self.alb, self.bhlb, self.ahlb = self.setup(12.0, 15.0)
        self.bb, self.ab, self.bhb, self.ahb = self.setup(15.0, 20.0)
        self.bhbb, self.ahbb, self.bhhb, self.ahhb = self.setup(20.0, 30.0)
        self.bg, self.ag, self.bhg, self.ahg = self.setup(38.0, 42.0)
        self.bhbg, self.ahbg, self.bhhg, self.ahhg = self.setup(42.0, 50.0)
        self.b60, self.a60, self.bh60, self.ah60 = self.setup(55.0, 65.0)
        self.b61, self.a61, self.bh61, self.ah61 = self.setup(65.0, 70.0)
    def setup(self, LoF, HiF):
        return tfcfilterssetup(LoF, HiF, self.forder)

def tfcfilterall(b, a, bh, ah, thesignal, numsamples):
    thefilteredsignal = np.zeros(numsamples)
    thefilteredsignal = filtfilt(bh, ah, thesignal)
    thefilteredsignal = lfilter(b, a, thefilteredsignal)
    sigmean = np.mean(thefilteredsignal)
    thefilteredsignal = thefilteredsignal - sigmean
    mean, median, st_dev = get_statistics(thefilteredsignal)
#    print("stats", " : ", str(mean), " ", str(median), " ", str(st_dev))
    return thefilteredsignal
    

def tfcfilterssetup(lowcut, highcut, order):

    fs = 256
    cutoff = highcut
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
#    order = 6
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
#    print("LP Filter: " + str(order) + " " + str(cutoff) + " " + str(normal_cutoff))
 
    cutoff = lowcut
    normal_cutoff = cutoff / nyq
#    order = 4
    bh, ah = butter(order, normal_cutoff, btype='high', analog=False)
    print("HP Filter: " + str(lowcut) + "   LP Filter: " + str(highcut))

    return b, a, bh, ah

def get_statistics(numbers):
    """
    Compute the mean, median, and standard deviation of a list of numbers.
    """
    mean = sum(numbers) / len(numbers)
    median = sorted(numbers)[len(numbers)//2]
    variance = sum((x - mean)**2 for x in numbers) / len(numbers)
    std_dev = variance**0.5
    return mean, median, std_dev

def tfcentropy(thesignal):

# Calculate the probability distribution of the EEG data
    hist, _ = np.histogram(thesignal, bins=10, density=True)
    prob_dist = hist / sum(hist)

# Calculate the entropy of the EEG data
    entropy = -sum(p * np.log2(p) for p in prob_dist if p != 0)

# Print the entropy value
#    print("Entropy:", entropy)

    return entropy
