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

#====== utility functions
def round_to_1(x):
  """round a number to one significant figure
  """
  return np.round(x, -int(np.floor(np.log10(np.abs(x)))))

# round to n significant figure
round_to_n = lambda x, n: np.round(x, -int(np.floor(np.log10(x))) + (n - 1)) 

#------ user inputs
nc_file = sys.argv[1]
title = sys.argv[2]
model_tags = sys.argv[3]
out_fig = sys.argv[4]

model_names = model_tags.split(',')
#model_names = ['xi', 'beta', 'alpha']

#-- plot controls
# map plot
map_lat_center = 38.5
map_lon_center = 118.0
map_lat_min= 10
map_lat_max= 55
map_lon_min= 90
map_lon_max= 160
map_parallels = np.arange(0.,81,10.)
map_meridians = np.arange(0.,351,10.)

# model colormap
# model plot region
width = 0.8
height = 0.9

#------ read nc files 
fh = Dataset(nc_file, mode='r')

lats = fh.variables['latitude'][:]
lons = fh.variables['longitude'][:]

slice_depth = fh.variables['depth'][:]

model = {}
#for tag in model_names:
for tag in ['vp0', 'vs0', 'alpha', 'beta', 'phi', 'xi', 'eta']:
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

  m = Basemap(ax=ax, projection='tmerc',
      resolution='l', area_thresh=30000,
      llcrnrlat=map_lat_min, llcrnrlon=map_lon_min, 
      urcrnrlat=map_lat_max, urcrnrlon=map_lon_max,
      lat_0=map_lat_center, lon_0=map_lon_center)
  m.drawcoastlines(linewidth=0.2)
  m.drawcountries(linewidth=0.2)
  m.drawparallels(map_parallels, linewidth=0.1, labels=[1,0,0,0], fontsize=12)
  m.drawmeridians(map_meridians, linewidth=0.1, labels=[0,0,0,1], fontsize=12)
  
  # contourf model
  xx, yy = m(lons2, lats2)

  if model_tag in ['alpha', 'beta']:
    zz = np.transpose(model[model_tag])
    zz = zz * 100 # use percentage

    #levels = np.concatenate((np.arange(-6,0,1), np.arange(1,6.1,1)))
    #cs = m.contour(xx, yy, zz, levels=levels, colors=('k',), linewidths=(0.1,))
    #plt.clabel(cs, fmt='%1.0f', colors='k', fontsize=3)

    levels = np.concatenate((np.arange(-6,0,0.5), np.arange(0.5,6.1,0.5)))
    cmap = plt.cm.get_cmap("jet_r")
    cs = m.contourf(xx, yy, zz, cmap=cmap, levels=levels, extend="both")
    cs.cmap.set_over('black')
    cs.cmap.set_under('purple')

    # colorbar for contourfill
    cb = m.colorbar(cs,location='right',ticks=np.arange(-6,6.1,1), pad="5%")
    cb.ax.set_title('(%)', fontsize=10)
    #cb.set_label('%')
    ax.set_title("{:s}".format(model_tag))

  elif model_tag in ['eta']:
    zz = np.transpose(model[model_tag])
    cmap = plt.cm.get_cmap("jet")

    levels = np.arange(0.9, 1.101, 0.01)
    cs = m.contourf(xx, yy, zz, cmap=cmap, levels=levels, extend="both")
    cs.cmap.set_over('purple')
    cs.cmap.set_under('black')

    # colorbar for contourfill
    levels = np.arange(0.9,1.101,0.05)
    cb = m.colorbar(cs,location='right',ticks=levels,pad="5%", format="%.2f")
    #cb.set_label('% mean')
    ax.set_title("{:s}".format(model_tag))

  elif model_tag in ['phi', 'xi']:
    zz = np.transpose(model[model_tag])
    zz = zz*100.0
    levels = np.arange(-10, 10.01, 1)
    cmap = plt.cm.get_cmap("jet")
    cs = m.contourf(xx, yy, zz, cmap=cmap, levels=levels, extend="both")
    cs.cmap.set_over('purple')
    cs.cmap.set_under('black')

    # colorbar for contourfill
    levels = np.arange(-10, 10.01, 2)
    cb = m.colorbar(cs,location='right',pad="5%", format="%.2f", ticks=levels)
    cb.ax.set_title('(%)', fontsize=10)
    ax.set_title("{:s}".format(model_tag))

  elif model_tag in ['kappa']:
    vp = (1.0 + model['alpha'])*model['vp0']
    vs = (1.0 + model['beta'])*model['vs0']
    kappa0 = model['vp0']/model['vs0']
    zz = np.transpose(vp/vs/kappa0 - 1.0)
    zz = zz*100.0

    levels = np.linspace(-5, 5, 100)
    cmap = plt.cm.get_cmap("jet")
    cs = m.contourf(xx, yy, zz, cmap=cmap, levels=levels, extend="both")
    cs.cmap.set_over('purple')
    cs.cmap.set_under('black')

    # colorbar for contourfill
    levels = np.arange(-5, 5.01, 1)
    cb = m.colorbar(cs,location='right',pad="5%", format="%.2f", ticks=levels)
    cb.ax.set_title('(%%) x %.3f'%(np.mean(kappa0)), fontsize=10)
    ax.set_title("{:s}".format(model_tag))

  else:
    raise Exception("unrecognized model {:s}".format(model_tag))

  #-- plot fault lines
  #fault_line_file = 'fault_lines.txt'
  #fault_lines = []
  #with open(fault_line_file, 'r') as f:
  #  lon = []
  #  lat = []
  #  for l in f.readlines():
  #    if not l.startswith('>'):
  #      x = l.split()
  #      lon.append(float(x[0]))
  #      lat.append(float(x[1]))
  #    else:
  #      fault_lines.append([lon, lat])
  #      lon = []
  #      lat = []
  #for l in fault_lines:
  #  x, y = m(l[0], l[1])
  #  ax.plot(x, y, 'k-', lw=0.05)

  #-- plot geological blocks 
  block_line_file = 'zhangpz_block.txt'
  block_lines = []
  with open(block_line_file, 'r') as f:
    lon = []
    lat = []
    for l in f.readlines():
      if not l.startswith('>'):
        x = l.split()
        lon.append(float(x[0]))
        lat.append(float(x[1]))
      else:
        block_lines.append([lon, lat])
        lon = []
        lat = []
  for l in block_lines:
    x, y = m(l[0], l[1])
    ax.plot(x, y, lw=0.2, color='gray')

  #-- plot plate_boundary
  pb_line_file = 'zhangpz_pb.txt'
  pb_lines = []
  with open(pb_line_file, 'r') as f:
    lon = []
    lat = []
    for l in f.readlines():
      if not l.startswith('>'):
        x = l.split()
        lon.append(float(x[0]))
        lat.append(float(x[1]))
      else:
        pb_lines.append([lon, lat])
        lon = []
        lat = []
  for l in pb_lines:
    x, y = m(l[0], l[1])
    ax.plot(x, y, lw=1.0, color='red')

  #--- plot seismicity
  catalog_file = 'isc_d50km.txt'
  with open(catalog_file, 'r') as f:
    lines = [ l.split('|') for l in f.readlines() if not l.startswith('#') ] 
    eq_lats = np.array([float(x[2]) for x in lines])
    eq_lons = np.array([float(x[3]) for x in lines])
    eq_deps = np.array([float(x[4]) for x in lines]) # km

  eq_indx = np.abs(eq_deps - slice_depth) <= 10.0
  x, y = m(eq_lons[eq_indx], eq_lats[eq_indx])
  if slice_depth < 200:
    markersize = 0.5
  elif slice_depth < 500:
    markersize = 1
  else:
    markersize = 2

  ax.plot(x, y, 'w.', markersize=markersize)

  #--- plot Holocene volcanoes
  volcano_file= 'volcanoes.list'
  with open(volcano_file, 'r') as f:
    lines = [ l.split('|') for l in f.readlines() if not l.startswith('#') ] 
    volcano_lats = np.array([float(x[4]) for x in lines])
    volcano_lons = np.array([float(x[5]) for x in lines])

  x, y = m(volcano_lons, volcano_lats)
  ax.plot(x, y, '^', markeredgecolor='red', markerfacecolor='none', markersize=5, markeredgewidth=1)

#------ save figure
#plt.show()
plt.savefig(out_fig, format='pdf')