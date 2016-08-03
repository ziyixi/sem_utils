#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Plot .nc files generated by xsem_slice_sphere
"""
import sys
import numpy as np

from netCDF4 import Dataset

import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap

#------ user inputs
model_dir = sys.argv[1]
nc_tag = sys.argv[2]
title = sys.argv[3]
out_dir = sys.argv[4]

#title = "iter00"
model_names = ['vph', 'vpv', 'vsv', 'vsh']

#-- plot controls
# map plot
map_lat_center = 38.5
map_lon_center = 118.0
map_lat_min= 15
map_lat_max= 55
map_lon_min= 90
map_lon_max= 160
map_parallels = np.arange(0.,81,10.)
map_meridians = np.arange(0.,351,10.)

# model colormap
cmap = plt.cm.get_cmap("jet_r")
cmap.set_under("white")
cmap.set_over("white")

# model plot region
width = 0.8
height = 0.9

#------ read nc files 
fh = Dataset("{:s}/{:s}.nc".format(model_dir, nc_tag), mode='r')

lats = fh.variables['latitude'][:]
lons = fh.variables['longitude'][:]

model = {}
for tag in model_names:
  model[tag] = fh.variables[tag][:]

#------ plot map and xsection surface trace and marker
fig = plt.figure(figsize=(8.5,11))

# add title
ax = fig.add_axes([0.5, 0.07+height, 0.1, 0.1])
ax.axis('off')
ax.text(0, 0, title, 
    horizontalalignment='center',
    verticalalignment='top',
    fontsize=16)

lons2, lats2 = np.meshgrid(lons, lats, indexing='ij')
nrow = len(model_names)
subplot_height = height/nrow
for irow in range(nrow):
  origin_x = 0.1
  origin_y = 0.05+irow*subplot_height
  ax = fig.add_axes([origin_x, origin_y, width, 0.8*subplot_height])
  
  model_tag = model_names[irow]

  m = Basemap(ax=ax, projection='tmerc', resolution='l',
      llcrnrlat=map_lat_min, llcrnrlon=map_lon_min, 
      urcrnrlat=map_lat_max, urcrnrlon=map_lon_max,
      lat_0=map_lat_center, lon_0=map_lon_center)
  m.drawcoastlines(linewidth=0.2)
  m.drawcountries(linewidth=0.2)
  m.drawparallels(map_parallels, linewidth=0.1, labels=[1,0,0,1], fontsize=8)
  m.drawmeridians(map_meridians, linewidth=0.1, labels=[1,0,0,1], fontsize=8)
  
  # contourf model
  xx, yy = m(lons2, lats2)
  vmean = np.mean(model[model_tag])
  dlnv = (np.transpose(model[model_tag])/vmean - 1.0)*100.0
  #dlnvamp = np.max(abs(dlnv))
  dlnvamp = 15.0
  levels = np.linspace(-1.0*dlnvamp, dlnvamp, 21)
  cs = m.contourf(xx, yy, dlnv, cmap=cmap, levels=levels) 

  # colorbar for contourfill
  cb = m.colorbar(cs,location='right',pad="5%", format="%.1f")
  cb.set_label('% mean')
  ax.set_title("{:s} ({:.2f} km/s)".format(model_tag, vmean))

#------ save figure
#plt.show()
plt.savefig("{:s}/{:s}.pdf".format(out_dir, nc_tag), format='pdf')