#  plot_svc

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse
import numpy as np
from process.tfcfilters import tfcentropy
from process.detect_artifact import detect_peak

def draw_a_wax_wane(ax, start, stop, length, y_base, bar_offset, bar_mult, label, colorstring, artifact_flags, time_range, fill_scale=1.0, bar_width_scale=1.0):

#      print("in draw_wax_wane")
      ax.text(start-400, y_base, label, color=colorstring)
      for j in range(0, length-16, 16):
         ybot = y_base - artifact_flags[time_range[j:j+16]]/2 * fill_scale
         ytop = y_base + artifact_flags[time_range[j:j+16]]/2 * fill_scale
         plt.fill_between(time_range[j:j+16], ytop, ybot, where=(ytop >= ybot), color=colorstring)

      total = np.sum(artifact_flags[time_range])/1000
      tstring = "{:.1f}".format(total)
      ax.text(stop, y_base, tstring)
      rectangle = plt.Rectangle((stop+bar_offset, y_base), total*bar_mult/2 * bar_width_scale, 20, color=colorstring)
      ax.add_patch(rectangle)
      localentropy=tfcentropy(artifact_flags[time_range])
      tstring = "{:.1f}".format(localentropy)
      ax.text(stop+6.5*bar_offset, y_base, tstring)
      rectangle = plt.Rectangle((stop+7.5*bar_offset, y_base), localentropy*10*bar_mult, 20, color=colorstring)
      ax.add_patch(rectangle)

def draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, label, colorstring, artifact_flags, time_range, rmsvalue, fill_scale=1.0, bar_width_scale=1.0):

#      print("in draw_wax_wane")
      ax.text(start-400, y_base, label, color=colorstring)
      for j in range(0, length-16, 16):
         ybot = y_base - artifact_flags[time_range[j:j+16]]/20 * fill_scale
         ytop = y_base + artifact_flags[time_range[j:j+16]]/20 * fill_scale
         plt.fill_between(time_range[j:j+16], ytop, ybot, where=(ytop >= ybot), color=colorstring)

      total = np.sum(artifact_flags[time_range])/1000
      tstring = "{:.1f}".format(rmsvalue)
      ax.text(stop, y_base, tstring)
      rectangle = plt.Rectangle((stop+bar_offset, y_base), total*bar_mult/2 * bar_width_scale, 20, color=colorstring)
      ax.add_patch(rectangle)
      localentropy=tfcentropy(artifact_flags[time_range])
      tstring = "{:.1f}".format(localentropy)
      ax.text(stop+6.5*bar_offset, y_base, tstring)
      rectangle = plt.Rectangle((stop+7.5*bar_offset, y_base), localentropy*10*bar_mult, 20, color=colorstring)
      ax.add_patch(rectangle)


def draw_a_ribbon(ax, y_position, colorscale, signalsin, n, length, time_range):
      yvalues = np.zeros(4)
      for i in range(n):
        y_position -= 2
        yvalues[0:4] = y_position
        sigtoshow = signalsin[i, time_range]
        for j in range(0, length-4, 4):
          ax.plot(time_range[j:j+4], yvalues[0:4], color=plt.cm.bwr((20+sigtoshow[j])/40))
#          ax.plot(time_range[j:j+16], yvalues[0:16])

def draw_eeg_waveforms(myvisualsigs, i, ax, start, stop, y_max, y_increment, time_range, montage, electrode_names, channel_labels_short, stdmeas, square_offset, bar_mult, colorlist, lodelta_artifact, delta_artifact, theta_artifact, loalpha_artifact, alpha_artifact, hialpha_artifact, lobeta_artifact, beta_artifact, hibeta_artifact, gamma_artifact, higamma_artifact, f60hz_artifact, f61hz_artifact, band_bar_scale=1.0, power_sq_scale=1.0, entropy_bar_scale=1.0):
      #for i in range(n):
        sigtoshow = myvisualsigs[i, start:stop]
        y_position = y_max - (i+1) * y_increment
        sigtoshow = sigtoshow + y_position
  #    if selstring[7] == 1:
        ax.plot(time_range, sigtoshow, color="Black", linewidth=0.5)

#  MONTAGE LAND
        if montage == 3 or montage == 4 or montage == 5:
             tstring = f"{electrode_names[i][4:]}:"
        elif montage == 2:
             tstring =  f"{channel_labels_short[i]}:"
        else:
             tstring = f"{electrode_names[i]}:"

        ax.text(start-400, y_position, tstring)

#  CALCULATE THE POWER FOR THIS CHANNEL AND SHOW IT
        stand = np.sqrt(np.std(sigtoshow)) * stdmeas / 10.0
        tstring = "{:.1f}".format(stand)
        ax.text(stop+20, y_position, tstring)
        rectangle = plt.Rectangle((stop+3*square_offset+5, y_position), stand*bar_mult*power_sq_scale, square_offset-1, color=colorlist[0])

        ax.add_patch(rectangle)

        bar_mult_powers = 1.5
        lodelt = np.sum(lodelta_artifact[i,time_range]/1000)
        rectangle = plt.Rectangle((stop+6*square_offset, y_position), square_offset, lodelt*bar_mult*band_bar_scale, color=colorlist[1])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+7*square_offset, y_position), square_offset, ((np.sum(delta_artifact[i, time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[2])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+8*square_offset, y_position),square_offset, ((np.sum(theta_artifact[i, time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[3])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+9*square_offset, y_position), square_offset, ((np.sum(loalpha_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[4])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+10*square_offset, y_position), square_offset, ((np.sum(alpha_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[5])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+11*square_offset, y_position), square_offset, ((np.sum(hialpha_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[6])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+12*square_offset, y_position), square_offset, ((np.sum(lobeta_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[7])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+13*square_offset, y_position), square_offset, ((np.sum(beta_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[8])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+14*square_offset, y_position), square_offset, ((np.sum(hibeta_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[9])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+15*square_offset, y_position), square_offset, ((np.sum(gamma_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[10])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+16*square_offset, y_position), square_offset, ((np.sum(higamma_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[11])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+17*square_offset, y_position), square_offset, ((np.sum(f60hz_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[12])
        ax.add_patch(rectangle)
        rectangle = plt.Rectangle((stop+18*square_offset, y_position), square_offset, ((np.sum(f61hz_artifact[i,time_range]))/100)*bar_mult_powers*band_bar_scale, color=colorlist[13])
        ax.add_patch(rectangle)

#  CALCULATE ENTROPY OF THIS CHANNEL FOR THIS PAGE
        entropy = tfcentropy(sigtoshow)
        tstring = "{:.1f}".format(entropy)
        ax.text(stop+20*square_offset, y_position, tstring)
        rectangle = plt.Rectangle((stop+23*square_offset+10, y_position), entropy*10*bar_mult*entropy_bar_scale, square_offset, color="Black")
        ax.add_patch(rectangle)
        return(y_position)
      
def draw_fft_power_spectra(n, ax, myvisualsigs, time_range, selstring, start, stop, y_min, montage, electrode_names, channel_labels_short):
    kernel=np.array([1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16, 1/16])
#      kernel=np.array([1/12, 1/12, 1/12, 1/12, 1/12, 1/12, 1/12, 1/12, 1/12, 1/12, 1/12, 1/12])
    kernel1=np.array([1/16, 1/16, 1/8, 1/2, 1/8, 1/16, 1/16])
    sig_s = np.zeros(2560)
    amp_s = np.zeros(2560)
    amp_sc = np.zeros(2560)
    window_s = np.hamming(2560)
    for i in range(n):
          sig_s = window_s * myvisualsigs[i,time_range]
          fft_s = np.fft.fft(sig_s)
          amp_s = np.abs(fft_s)
          amp_sc = np.convolve(amp_s, kernel, mode='same')
          amp_sc = np.convolve(amp_sc, kernel1, mode='same')
          freq_s = np.fft.fftfreq(len(sig_s), d=1/256)

#        print("Freqs    ", freq_s)
          if selstring[7] == 1:
            ax.plot(start+40*freq_s[:len(freq_s)//4], y_min+100+amp_sc[:len(amp_s)//4]/5, linewidth=0.5)

#  FIND THE PEAKS

          peak_index=detect_peak(amp_sc[7*10:14*10])
          peak_indexl=detect_peak(amp_sc[7*10:11*10])
          peak_indexh=detect_peak(amp_sc[9*10:14*10])
          peak_indexo=detect_peak(amp_sc[4*10:40*10])
#        print("peaks:  ", (7*10+peak_index)/10, (6*10+peak_indexl)/10, (10*10+peak_indexh)/10, (4*10+peak_indexo)/10)
#        tstring = "{:.1f}".format(7*40+peak_index)

#  MONTAGE LAND
          if montage == 3 or montage == 4 or montage == 5:
             tstring = f"{electrode_names[i][4:]}:"
          elif montage == 2:
             tstring =  f"{channel_labels_short[i]}:"
          else:
             tstring = f"{electrode_names[i]}:"

#        else:
#          tstring = f"{channel_labels_short[i]}:"

          ax.text(start+2750, y_min + 450 - 20 * i, tstring)

          tstring = "Alpha1:"
          ax.text(start-10, y_min + 430, tstring)  
          tstring = "Alpha:"
          ax.text(start-10, y_min + 450, tstring)
          tstring = "Alpha2:"
          ax.text(start-10, y_min + 470, tstring)

          # Peak-frequency value columns moved 200 px right (Alpha1: 2950->3150,
          # Alpha: 3150->3350, Alpha2: 3350->3550) so wider channel labels like
          # "ICA C19:" no longer collide with the Alpha1 value column.
          if peak_index != 0:
              value=(7*10+peak_index)/10
              tstring = f"{value:.1f}"
              ax.text(start+3350, y_min + 450 - 20 * i, tstring)
              ax.plot([start+7*40+4*peak_index, start+7*40+4*peak_index], [y_min+450, y_min+465], color = "Black", linewidth=1.0)
          else:
              value = 0

          if peak_indexl != 0:
              valuel=(7*10+peak_indexl)/10
              tstring = f"{valuel:.1f}"
              ax.text(start+3150, y_min + 450 - 20 * i, tstring)
              ax.plot([start+7*40+4*peak_indexl, start+7*40+4*peak_indexl], [y_min+430, y_min+445], color = "Black", linewidth=1.0)
          else:
              valuel = 0

          if peak_indexh != 0:
              valueh=(10*10+peak_indexh)/10
              tstring = f"{valueh:.1f}"
              ax.text(start+3550, y_min + 450 - 20 * i, tstring)
              ax.plot([start+10*40+4*peak_indexh, start+10*40+4*peak_indexh], [y_min+470, y_min+485], color = "Black", linewidth=1.0)
          else:
              valueh = 0

#        tstring = f"{channel_labels_short[i]}: {value:.1f}  {valuel:.1f}  {valueh:.1f}"
#        ax.text(start+1800, y_min + 500 - 20 * i, tstring)
       
    ax.plot([start,stop], [y_min+80, y_min+80], color = "Black", linewidth=1.0)
    ax.plot([start, start], [y_min+80, y_min+100], color = "Black", linewidth=1.0)
    for i in range(7):
      ax.plot([start+400*i, start+400*i], [y_min+80, y_min+50], color = "Black", linewidth=1.0)
      ax.text(start+400*i, y_min+5, str(i*10))
      
def draw_artifact_line(n, stop, start, bar_offset, square_offset, comod, bar_mult, colorlist, y_position, y_increment, ax, length, time_range, lodelta_artifact_tot, lodelta_rms_tot, delta_artifact_tot, delta_rms_tot, theta_artifact_tot, theta_rms_tot, loalpha_artifact_tot, loalpha_rms_tot, alpha_artifact_tot, alpha_rms_tot, hialpha_artifact_tot, hialpha_rms_tot, lobeta_artifact_tot, lobeta_rms_tot, beta_artifact_tot, beta_rms_tot, hibeta_artifact_tot, hibeta_rms_tot, gamma_artifact_tot, gamma_rms_tot, higamma_artifact_tot, higamma_rms_tot, f60hz_artifact_tot, f60hz_rms_tot, y_base, band_fill_scale=1.0, bar_width_scale=1.0):
        for j in  range(1, 13):
          ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[j]*12*bar_mult, comod[j]*5*bar_mult, color=colorlist[j])
          ax.add_artist(ellipse)

# DRAW THE LODELTA LINE 2
        y_base = y_position - 1.0 * y_increment
#      draw_a_wax_wane(ax, start, stop, length, y_base, bar_offset, bar_mult, "LoD:", colorlist[1], lodelta_artifact_tot, time_range)
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "LoD:", colorlist[1], lodelta_artifact_tot, time_range, lodelta_rms_tot/n, band_fill_scale, bar_width_scale)

#  SECOND ROW OF COMODULATIONS
 
        for j in  range(1, 13):
#        rectangle = plt.Rectangle((stop+bar_offset+(j+3)*square_offset, y_base), comod[16+j]*20*bar_mult, 25, color=colorlist[j+1])
#        ax.add_patch(rectangle)
          ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[16+j]*12*bar_mult, comod[16+j]*5*bar_mult, color=colorlist[j])
          ax.add_artist(ellipse)

# DRAW THE DELTA LINE 3
        y_base = y_position - 1.5 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "D:", colorlist[2], delta_artifact_tot, time_range, delta_rms_tot/n, band_fill_scale, bar_width_scale)

#  THIRD ROW OF COHERENCES
        for j in  range(1, 13):
           ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[32+j]*12*bar_mult, comod[32+j]*5*bar_mult, color=colorlist[j])
           ax.add_artist(ellipse)

# DRAW THE THETA LINE 4
        y_base = y_position - 2.0 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "T:", colorlist[3], theta_artifact_tot, time_range, theta_rms_tot/n, band_fill_scale, bar_width_scale)

#  FOURTH ROW OF COHERENCES
        for j in  range(1, 13):
           ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[48+j]*12*bar_mult, comod[48+j]*5*bar_mult, color=colorlist[j])
           ax.add_artist(ellipse)
# DRAW THE ALPHA1 LINE 5
        y_base = y_position - 2.5 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "A1:", colorlist[4], loalpha_artifact_tot, time_range, loalpha_rms_tot/n, band_fill_scale, bar_width_scale)
#  FIFTH ROW OF COHERENCES
        for j in  range(1, 13):
           ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[64+j]*12*bar_mult, comod[64+j]*5*bar_mult, color=colorlist[j])
           ax.add_artist(ellipse)
# DRAW THE ALPHA LINE 6
        y_base = y_position - 3.0 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "A:", colorlist[5], alpha_artifact_tot, time_range, alpha_rms_tot/n, band_fill_scale, bar_width_scale)
#  SIXTH ROW OF COHERENCES
        for j in  range(1, 13):
           ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[80+j]*12*bar_mult, comod[80+j]*5*bar_mult, color=colorlist[j])
           ax.add_artist(ellipse)
# DRAW THE ALPHA2 LINE 7
        y_base = y_position - 3.5 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "A2:", colorlist[6], hialpha_artifact_tot, time_range, hialpha_rms_tot/n, band_fill_scale, bar_width_scale)
#  SEVENTH ROW OF COHERENCES
        for j in  range(1, 13):
           ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[96+j]*12*bar_mult, comod[96+j]*5*bar_mult, color=colorlist[j])
           ax.add_artist(ellipse)
# DRAW THE LOBETA LINE 8
        y_base = y_position - 4.0 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "LoB:", colorlist[7], lobeta_artifact_tot, time_range, lobeta_rms_tot/n, band_fill_scale, bar_width_scale)
#  EIGHTH ROW OF COHERENCES
        for j in  range(1, 13):
           ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[112+j]*12*bar_mult, comod[112+j]*5*bar_mult, color=colorlist[j])
           ax.add_artist(ellipse)
# DRAW THE BETA LINE 9
        y_base = y_position - 4.5 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "B:", colorlist[8], beta_artifact_tot, time_range, beta_rms_tot/n, band_fill_scale, bar_width_scale)
#  NINTH ROW OF COHERENCES
        for j in  range(1, 13):
#        rectangle = plt.Rectangle((stop+bar_offset+(j+10)*square_offset, y_base), comod[128+j]*20*bar_mult, 25, color=colorlist[j+8])
#        ax.add_patch(rectangle)
           ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[128+j]*12*bar_mult, comod[128+j]*5*bar_mult, color=colorlist[j])
           ax.add_artist(ellipse)
# DRAW THE HIBETA LINE 10
        y_base = y_position - 5.0 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "HiB:", colorlist[9], hibeta_artifact_tot, time_range, hibeta_rms_tot/n, band_fill_scale, bar_width_scale)
#  TENTH ROW OF COHERENCES
        for j in  range(1, 13):
           ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[144+j]*12*bar_mult, comod[144+j]*5*bar_mult, color=colorlist[j])
           ax.add_artist(ellipse)
# DRAW THE GAMMA LINE 11
        y_base = y_position - 5.5 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "G:", colorlist[10], gamma_artifact_tot, time_range, gamma_rms_tot/n, band_fill_scale, bar_width_scale)
        for j in  range(1, 13):
           ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[160+j]*12*bar_mult, comod[160+j]*5*bar_mult, color=colorlist[j])
           ax.add_artist(ellipse)
# DRAW THE HIGAMMA LINE 12
        y_base = y_position - 6.0 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "HiG:", colorlist[11], higamma_artifact_tot, time_range, higamma_rms_tot/n, band_fill_scale, bar_width_scale)
        for j in  range(1, 13):
            ellipse = Ellipse((stop+bar_offset+(j+3)*square_offset, y_base), comod[176+j]*12*bar_mult, comod[176+j]*5*bar_mult, color=colorlist[j])
            ax.add_artist(ellipse)
# DRAW THE f60hz LINE 13
        y_base = y_position - 6.5 * y_increment
        draw_a_wax_waner(ax, start, stop, length, y_base, bar_offset, bar_mult, "60Hz:", colorlist[12], f60hz_artifact_tot, time_range, f60hz_rms_tot/n, band_fill_scale, bar_width_scale)