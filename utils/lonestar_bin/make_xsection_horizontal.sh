#!/bin/bash

# interpolate SEM gll models to create horizontal cross-sections

#====== command line args
control_file=${1:?must provide control_file}
evid=${2:?must provide evid}
xsection_list=${3:?must provide xsection_list}
mpi_exec=${4:-}
model_names=${5:-vsv,vsh,vpv,vph,rho,eta}

xsection_list=$(readlink -f $xsection_list)

# source parameters in control_file
source ${control_file}

#====== interpolate SEM gll models
event_dir=${iter_dir}/$evid

cd $event_dir
if [ ! -d xsection ]
then
    mkdir xsection
fi

# create job script
cat<<EOF
#!/bin/bash
#$ -V                              # Inherit the submission environment 
#$ -cwd                            # Start job in submission directory
#$ -N xsection                     # Job Name
#$ -j y                            # combine stderr & stdout into stdout  
#$ -o xsection.o                   # Name of the output file (eg. myMPI.oJobID)
#$ -pe 12way 12                    # Requests 12 cores/node, 24 cores total: 12way 24
#$ -q normal                       # Queue name
#$ -l h_rt=01:30:00                # Run time (hh:mm:ss) - 1.5 hours
#$ -M kai.tao@utexas.edu           # email 
#$ -m bea                          # email info: begin/end/abort
#$ -hold_jid -1                    # dependent job id

EOF

grep -v "^#" $xsection_list |\
while read lat0 lat1 nlat lon0 lon1 nlon depth fname
do
    out_file=${fname}.nc

cat<<EOF
echo
echo "#====== depth= $depth [\$(date)]"
echo
${mpi_exec} \
    $sem_utils/bin/xsem_slice_sphere \
    $nproc $mesh_dir/DATABASES_MPI $event_dir/DATABASES_MPI $model_names \
    $lat0 $lat1 $nlat \
    $lon0 $lon1 $nlon \
    $depth \
    $event_dir/xsection/$out_file

EOF

done