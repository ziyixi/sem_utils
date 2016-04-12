#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Process misfit
"""
import sys
from misfit import Misfit

# read command line args
misfit_file = "misfit/misfit.pkl"
figure_dir = "misfit"

plot_param = {
  'time':[-50,200], 'rayp':10., 'azbin':30, 'window_id':'F.p,P',
  'SNR':None, 'CC0':None, 'CCmax':None, 'dist':None }

#------
print "\n====== initialize\n"
misfit = Misfit()

print "\n====== load data\n"
misfit.load(filename=misfit_file)

print "\n====== plot seismograms\n"
misfit.plot_seismogram(
    savefig=True,
    out_dir=figure_dir,
    plot_param=plot_param)