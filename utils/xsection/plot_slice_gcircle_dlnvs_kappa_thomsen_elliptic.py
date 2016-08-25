#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Plot .nc files generated by xsem_slice_gcircle
Need both inverted and reference model
"""
import sys
import numpy as np

from netCDF4 import Dataset
import pyproj

import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap

#------ user inputs
model_dir = sys.argv[1] # dir of reference model nc file
nc_tag = sys.argv[2] # to find nc file <model_dir>/<nc_tag>.nc

# xsection geometry
xsection_lat0 = float(sys.argv[3])
xsection_lon0 = float(sys.argv[4])
xsection_azimuth = float(sys.argv[5])
title = sys.argv[6]
out_dir = sys.argv[7]

#model_names = ['eps', 'gamma', 'kappa', 'dlnvs']
model_names = ['gamma', 'kappa', 'dlnvs']
#model_names = ['kappa', 'dlnvs']

# earth parameters 
R_earth_meter = 6371000.0
R_earth_km = 6371.0

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
#cmap = plt.cm.get_cmap("jet_r")
#cmap.set_under("white")
#cmap.set_over("white")

# model plot region
width = 0.8
height = 0.6

#------ utility functions
def rotation_matrix(v_axis, theta):
  """ rotation matrix: rotate through a given axis by an angle of theta
      (right-hand rule)
  """
  sint = np.sin(theta)
  cost = np.cos(theta)
  one_minus_cost = 1.0 - cost

  # normalize v_axis to unit vector
  v = v_axis / sum(v_axis**2)**0.5

  # rotation matrix
  R = np.zeros((3,3))
  R[0,0] = cost + one_minus_cost * v_axis[0]**2
  R[1,1] = cost + one_minus_cost * v_axis[1]**2
  R[2,2] = cost + one_minus_cost * v_axis[2]**2

  R[0,1] = one_minus_cost*v_axis[0]*v_axis[1] - sint * v_axis[2]
  R[1,0] = one_minus_cost*v_axis[0]*v_axis[1] + sint * v_axis[2]

  R[0,2] = one_minus_cost*v_axis[0]*v_axis[2] + sint * v_axis[1]
  R[2,0] = one_minus_cost*v_axis[0]*v_axis[2] - sint * v_axis[1]

  R[1,2] = one_minus_cost*v_axis[1]*v_axis[2] - sint * v_axis[0]
  R[2,1] = one_minus_cost*v_axis[1]*v_axis[2] + sint * v_axis[0]

  return R

#------ read nc files 
fh = Dataset("{:s}/{:s}.nc".format(model_dir, nc_tag), mode='r')

radius = fh.variables['radius'][:]
theta = np.deg2rad(fh.variables['theta'][:])

model = {}
for tag in model_names:
  model[tag] = fh.variables[tag][:]

#------ plot map and xsection surface trace and marker
fig = plt.figure(figsize=(8.5,11))

ax = fig.add_axes([0.2, 0.75, 0.6, 0.2])
m = Basemap(ax=ax, projection='tmerc', resolution='l',
    llcrnrlat=map_lat_min, llcrnrlon=map_lon_min, 
    urcrnrlat=map_lat_max, urcrnrlon=map_lon_max,
    lat_0=map_lat_center, lon_0=map_lon_center)
m.drawcoastlines(linewidth=0.2)
m.drawcountries(linewidth=0.2)
m.drawparallels(map_parallels, linewidth=0.1, labels=[1,0,0,1], fontsize=8)
m.drawmeridians(map_meridians, linewidth=0.1, labels=[1,0,0,1], fontsize=8)

# initialize pyproj objects
geod = pyproj.Geod(ellps='WGS84')
ecef = pyproj.Proj(proj='geocent', ellps='WGS84', datum='WGS84')
lla = pyproj.Proj(proj='latlong', ellps='WGS84', datum='WGS84')

# unit direction vector v0 at origin point of the great circle
x, y, z = pyproj.transform(lla, ecef, xsection_lon0, xsection_lat0, 0.0)
v0 = np.array([x, y, z])
v0 = v0 / np.sqrt(np.sum(v0**2))

# unit direction vector v1 along the shooting azimuth of the great circle
vnorth = np.array( [ - np.sin(np.deg2rad(xsection_lat0)) * np.cos(np.deg2rad(xsection_lon0)),
                     - np.sin(np.deg2rad(xsection_lat0)) * np.sin(np.deg2rad(xsection_lon0)),
                       np.cos(np.deg2rad(xsection_lat0)) ])
veast = np.array([ - np.sin(np.deg2rad(xsection_lon0)), np.cos(np.deg2rad(xsection_lon0)), 0.0 ])

v1 = np.cos(np.deg2rad(xsection_azimuth)) * vnorth + np.sin(np.deg2rad(xsection_azimuth)) * veast

# rotation axis = v0 cross-product v1
v_axis = np.cross(v0, v1)

# xsection surface trace
xsection_lons = np.zeros(theta.shape)
xsection_lats = np.zeros(theta.shape)
for i in range(len(theta)):
  rotmat = rotation_matrix(v_axis, theta[i])
  vr = np.dot(rotmat, v0)*R_earth_meter
  xsection_lons[i], xsection_lats[i], alt = pyproj.transform(ecef, lla, vr[0], vr[1], vr[2])

x, y = m(xsection_lons, xsection_lats)
ax.plot(x, y, 'k-', lw=0.5)
xlim = ax.get_xlim()
length = xlim[1]-xlim[0]
ax.arrow(x[-1], y[-1], x[-1]-x[-2], y[-1]-y[-2], head_width=0.03*length, head_length=0.03*length, fc='k', ec='k')

# xsection surface marker 
nmarker = 5
xsection_lons = np.zeros(nmarker)
xsection_lats = np.zeros(nmarker)
marker_theta = np.linspace(theta[0], theta[-1], nmarker)
for i in range(nmarker):
  rotmat = rotation_matrix(v_axis, marker_theta[i])
  vr = np.dot(rotmat, v0)*R_earth_meter
  xsection_lons[i], xsection_lats[i], alt = pyproj.transform(ecef, lla, vr[0], vr[1], vr[2])
x, y = m(xsection_lons, xsection_lats)
ax.plot(x, y, 'ro', markersize=4, )

# title
ax.set_title(title)

#------ plot models
theta_mid = (theta[-1]+theta[0])/2.0
theta = theta - theta_mid

rr, tt = np.meshgrid(radius, theta, indexing='ij')
xx = np.sin(tt) * rr
yy = np.cos(tt) * rr

nrow = len(model_names)
subplot_height = height/nrow
for irow in range(nrow):
  ax = fig.add_axes([0.1,0.1+irow*subplot_height,width,subplot_height], aspect='equal')
  ax.axis('off')
  
  tag = model_names[irow]
 
  # colorbar axis
  cax = fig.add_axes([0.12+width, 0.1+irow*subplot_height, 0.01, 0.8*subplot_height])

  # contourfill relative difference 
  if tag == 'dlnvs':
    cmap = plt.cm.get_cmap("jet_r")

    zz = model[tag]*100
    cs = ax.contour(xx, yy, zz, levels=np.arange(-6,6.1,1), colors=('k',), linewidths=(0.1,))
    plt.clabel(cs, fmt='%2.1f', colors='k', fontsize=5)

    cs = ax.contourf(xx, yy, zz, cmap=cmap, levels=np.arange(-6,6.1,0.5), extend="both")
    cs.cmap.set_over('black')
    cs.cmap.set_under('purple')
    cb = plt.colorbar(cs, cax=cax, orientation="vertical")
    #cb.set_label('%', fontsize=10)
    cb.ax.set_title('(%)', fontsize=10)
  if tag == 'kappa':
    cmap = plt.cm.get_cmap("jet")
    zz = model[tag]
    cs = ax.contourf(xx, yy, zz, cmap=cmap, levels=np.arange(1.65,1.96,0.01), extend="both")
    cs.cmap.set_over('purple')
    cs.cmap.set_under('black')
    cb = plt.colorbar(cs, cax=cax, orientation="vertical")
    #cb.set_label('vp/vs', fontsize=10)
  if tag in ['eps','gamma']:
    cmap = plt.cm.get_cmap("jet")
    zz = model[tag]*100
    cs = ax.contourf(xx, yy, zz, cmap=cmap, levels=np.arange(0,6,0.5), extend="both")
    cs.cmap.set_over('purple')
    cs.cmap.set_under('black')
    cb = plt.colorbar(cs, cax=cax, orientation="vertical")
    cb.ax.set_title("(%)", fontsize=10)

  ## colorbar for contourfill
  #if irow == 0:
  #  cax = fig.add_axes([0.3, 0.07, 0.4, 0.01])
  #  cb = plt.colorbar(cs, cax=cax, orientation="horizontal")
  #  cb.ax.tick_params(labelsize=8)
  #  cb.set_label('% REF', fontsize=10)
  #  #l, b, w, h = ax.get_position().bounds
  #  #ll, bb, ww, hh = CB.ax.get_position().bounds
  #  #cb.ax.set_position([ll, b + 0.1*h, ww, h*0.8])
 
  # mark certain depths 
  for depth in [220, 410, 670]:
    x = np.sin(theta) * (R_earth_km - depth)
    y = np.cos(theta) * (R_earth_km - depth)
    ax.plot(x, y, 'k', lw=0.5)
    ax.text(x[-1],y[-1], str(depth), horizontalalignment='left', verticalalignment='top', fontsize=8)

  # surface marker
  marker_theta = np.linspace(theta[0], theta[-1], nmarker)
  x = np.sin(marker_theta) * radius[-1]
  y = np.cos(marker_theta) * radius[-1]
  ax.plot(x, y, 'ko', markersize=4, clip_on=False)
  x1 = np.sin(theta[-1]) * radius[-1]
  x2 = np.sin(theta[-2]) * radius[-1]
  y1 = np.cos(theta[-1]) * radius[-1]
  y2 = np.cos(theta[-2]) * radius[-1]
  xlim = ax.get_xlim()
  length = xlim[1]-xlim[0]
  ax.arrow(x1, y1, x1-x2, y1-y2, head_width=0.02*length, head_length=0.02*length, fc='k', ec='k', clip_on=False)

  # text model tag
  xlim = ax.get_xlim()
  ylim = ax.get_ylim()
  ax.text(xlim[0], ylim[1], tag, 
      horizontalalignment='left',
      verticalalignment='top', 
      fontsize=14)
  
#------ save figure
#plt.show()
plt.savefig("{:s}/{:s}.pdf".format(out_dir, nc_tag), format='pdf')