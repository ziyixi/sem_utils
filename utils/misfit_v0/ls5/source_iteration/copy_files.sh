#!/bin/bash

# copy files from previous iter_dir

source_dir=${1:?[arg]need previous iter_dir}

source_dir=$(readlink -f $source_dir)

find $source_dir -maxdepth 1 -type l | xargs -I@ cp -a @ .

ln -s $(readlink -f $source_dir/CMTSOLUTION_updated) CMTSOLUTION_initial
ln -s $(readlink -f $source_dir/mesh) mesh
cp $source_dir/*.txt .
cp $source_dir/*.py .