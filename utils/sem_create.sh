#!/bin/bash

# create build directory

source_dir=~/research/waveform_tomography/codes/specfem3d_globe_user_changes
build_dir=specfem3d_globe

# prepare build_dir
rm -rf $build_dir
mkdir $build_dir

cd $build_dir

ln -s ${source_dir}/src ./
ln -s ${source_dir}/config* ./
ln -s ${source_dir}/flags.guess ./
ln -s ${source_dir}/install-sh ./
ln -s ${source_dir}/Makefile.in ./

# copy setup directory
cp -L -r ${source_dir}/setup ./ 

# prepare DATA
mkdir DATA
cd DATA
ln -sf $source_dir/DATA/* ./