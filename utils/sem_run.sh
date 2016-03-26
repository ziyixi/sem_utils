#!/bin/bash

# setup mesh folders, generate the batch script to run SEM meshfem3D

#====== command line args
run_dir=${1:?[arg]need run_dir(for all output)}
par_dir=${2:?[arg]need par_dir(for Par_file,STATIONS,CMTSOLUTION)}
mesh_dir=${3:?[arg]need mesh_dir(for DATABASES/*)}

if [ -d "$run_dir" ]
then
    echo "[WARN] run_dir($run_dir) exists, delete!"
    rm -rf $run_dir
fi
mkdir $run_dir

if [ ! -d "$par_dir" ]
then
    echo "[ERROR] par_dir($par_dir) does NOT exist!"
    exit 1
elif [ ! -f "$par_dir/Par_file" ]
then
    echo "[ERROR] $par_dir/Par_file does NOT exist!"
    exit 1
elif [ ! -f "$par_dir/CMTSOLUTION" ]
then
    echo "[ERROR] $par_dir/CMTSOLUTION does NOT exist!"
    exit 1
elif [ ! -f "$par_dir/STATIONS" ]
then
    echo "[ERROR] $par_dir/STATIONS does NOT exist!"
    exit 1
fi

if [ ! -d "$mesh_dir" ]
then
    echo "[ERROR] mesh_dir($mesh_dir) does NOT exit!"
    exit 1
fi

run_dir=$(readlink -f $run_dir)
par_dir=$(readlink -f $par_dir)
mesh_dir=$(readlink -f $mesh_dir)

#====== setup run_dir
cd $run_dir
mkdir DATA DATABASES_MPI OUTPUT_FILES

# link data files: topography, bathymetry, etc.
cd $run_dir/DATA
#ln -sf $mesh_dir/DATA/* ./

rm -rf Par_file STATIONS CMTSOLUTION
cp -L $par_dir/Par_file .
cp -L $par_dir/CMTSOLUTION .
cp -L $par_dir/STATIONS .

#sed -i "/^[\s]*SAVE_MESH_FILES/s/=.*/= .false./" Par_file
#sed -i "/^[\s]*MODEL/s/=.*/= GLL/" Par_file

# backup Par_file into OUTPUT_FILES/
cp -L Par_file CMTSOLUTION STATIONS $run_dir/OUTPUT_FILES/

# link mesh database
cd $run_dir/DATABASES_MPI
ln -s $mesh_dir/DATABASES_MPI/*_solver_data.bin .
ln -s $mesh_dir/DATABASES_MPI/*_solver_data_mpi.bin .
ln -s $mesh_dir/DATABASES_MPI/*_boundary.bin .
ln -s $mesh_dir/DATABASES_MPI/*_stacey.bin .

# OUTPUT_FILES
cp $mesh_dir/OUTPUT_FILES/addressing.txt $run_dir/OUTPUT_FILES

#END
