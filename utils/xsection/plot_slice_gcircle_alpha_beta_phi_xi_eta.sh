#!/bin/bash

# plot xsections for model relative difference
sem_utils=~/seiscode/sem_utils

model_dir=${1:?[arg]need model_dir (for *.nc)}
slice_list=${2:?[arg]need slice_list}
title=${3:?[arg]need title}
model_names=${4:?[arg]need model names (e.g. xi,beta,alpha)}
out_dir=${5:?[arg]need out_dir}

awk 'NF&&$1!~/#/' $slice_list |\
while read lat0 lon0 azimuth theta0 theta1 ntheta r0 r1 nr flag_ellipticity nc_tag 
do
  echo
  echo "#====== $nc_tag: $lat0 $lon0 $azimuth $theta0 $theta1 $ntheta $r0 $r1 $nr $flag_ellipticity"
  echo

  out_fig=$out_dir/${nc_tag}.pdf

  $sem_utils/utils/xsection/plot_slice_gcircle_alpha_beta_phi_xi_eta.py \
    $model_dir/${nc_tag}.nc "$title ($nc_tag)" $model_names $out_fig
done