#!/bin/bash

# copy date to jsg
wkdir=$(pwd)

jsg_host="jsg15:/home/u1/kt23545/NEChina/"

iter_dir=$(echo $(readlink -f $wkdir) | sed "s/.*\/\([^\/]*\/[^\/]*$\)/\1/")
#iter_dir="stage01.structure/iter01"

event_list=${1:?[arg]need event_list}

echo ==============
echo rsync to $jsg_host/$iter_dir
echo ==============
#echo -n "Is this directory OK? (ctrl+c if not)"
#read dummy

#====== <event_id>/
cat<<EOF > $wkdir/rsync_exclude.list
output_kernel
output_hess
output_perturb
DATABASES_MPI
misfit.pkl
adj_hess
adj_kernel
SEM
OUTPUT_FILES
source_mask
kernel_precond
kernel_smooth_precond
vtk
EOF

awk -F"|" 'NF&&$1!~/#/{print $9}' $event_list |\
while read event_id
do
  echo "====== $event_id"
  event_dir=$wkdir/$event_id
  rsync -auvz $event_dir ${jsg_host}/${iter_dir} --exclude-from $wkdir/rsync_exclude.list
done

#====== kernel
for folder in misfit model_searched wcc_sum_step_size xsection
do
  echo "====== $folder"
  rsync -auvz $folder ${jsg_host}/${iter_dir} --exclude-from $wkdir/rsync_exclude.list
done

#====== shell scripts
rsync -auvz *.sh *.py *.txt *.pdf ${jsg_host}/${iter_dir}