#!/bin/bash

# create model gradient from all event kernels
#   - make kernel preconditioner (e.g. mask)
#   - sum event kernels (cijkl, rho)
#   - reduce cijkl_kernel to (lamda,mu)_kernel
#   - get dkernel

#====== command line args
control_file=${1:?must provide control_file}
event_list=${2:?must provide event_id list}
mpi_exec=${3:-}

# check inputs
if [ ! -f "$control_file" ]
then
    echo "[ERROR] invalid control_file: ", $control_file
fi
control_file=$(readlink -f $control_file)

if [ ! -f "$event_list" ]
then
    echo "[ERROR] invalid event_list: ", $event_list
fi
event_list=$(readlink -f $event_list)

# load parameters from control_file
source ${control_file}

echo
echo "Start updating gradient [$(date)]."
echo

#====== event kernel preconditioner
echo
echo "#====== make event kernel mask [$(date)]"
echo

for event_id in $(grep -v ^# $event_list)
do
    echo "#-- $event_id"
    event_dir=$iter_dir/$event_id

    # create source_xyz.list
    src_vtk=$event_dir/OUTPUT_forward/source.vtk
    sed -n '/^POINTS/{n;p;}' $src_vtk > $event_dir/source_xyz.list
    echo "# source_xyz: "
    cat $event_dir/source_xyz.list

    # create mask gll
    cd ${event_dir}
    ${mpi_exec} \
        $sem_utils/bin/xsem_make_source_depth_mask \
        ${nproc}\
        ${mesh_dir}/DATABASES_MPI \
        ${event_dir}/source_xyz.list \
        ${source_gaussa} \
        ${depth_pass} \
        ${depth_gaussa} \
        ${event_dir}/DATABASES_MPI
done

#====== model gradient
echo
echo "#====== get model gradient [$(date)]"
echo

#-- make event_kernel.list
mkdir -p $kernel_dir/DATABASES_MPI

awk '$1!~/^#/{printf "%s/%s/DATABASES_MPI\n", iter_dir, $1}' \
    iter_dir="${iter_dir}" $event_list > ${kernel_dir}/event_kernel.list

echo "#-- event_kernel list:"
cat ${kernel_dir}/event_kernel.list

#-- sum up all event cijkl_kernel (use each event mask)
echo "#-- sum up all event cijkl_kernel [$(date)]"

${mpi_exec} $sem_utils/bin/xsem_sum_event_kernels_cijkl \
    ${nproc} \
    ${mesh_dir}/DATABASES_MPI \
    ${kernel_dir}/event_kernel.list \
    ${use_mask} \
    ${nroot_stack} \
    ${kernel_dir}/DATABASES_MPI

#-- sum up all event rho_kernel (use each event mask)
echo "#-- sum up all event rho_kernel [$(date)]"

${mpi_exec} $sem_utils/bin/xsem_sum_event_kernels_1 \
    ${nproc} \
    ${mesh_dir}/DATABASES_MPI \
    ${kernel_dir}/event_kernel.list \
    "rho_kernel" \
    ${use_mask} \
    ${nroot_stack} \
    ${kernel_dir}/DATABASES_MPI

#-- reduce cijkl kernel to (lamda,mu)_kernel
echo "#-- reduce cijkl kernel to (lamda,mu)_kernel [$(date)]"

${mpi_exec} $sem_utils/bin/xsem_reduce_kernel_cijkl_to_lamda_mu \
    ${nproc} \
    ${mesh_dir}/DATABASES_MPI \
    ${kernel_dir}/DATABASES_MPI \
    ${kernel_dir}/DATABASES_MPI

#-- get dkernel
if [ "$iter_minus_one" -ge "$iter0" ]
then
    for tag in lamda mu rho
    do
        echo "#-- get ${tag}_dkernel [$(date)]"
        ${mpi_exec} $sem_utils/bin/xsem_math \
            ${nproc} \
            ${mesh_dir}/DATABASES_MPI \
            ${kernel_dir}/DATABASES_MPI ${tag}_kernel \
            ${prev_kernel_dir}/DATABASES_MPI ${tag}_kernel \
            "sub" \
            ${kernel_dir}/DATABASES_MPI ${tag}_dkernel
    done
fi

##-- kernel thresholding (lamda,mu,rho)_kernel
#echo "#-- kernel thresholding [$(date)]"
#cd ${iter_dir}/model_update
#for ker_name in lamda_kernel mu_kernel rho_kernel
#do
#    ${mpi_exec} $sem_utils/bin/xsem_pdf \
#        $nproc $mesh_dir/DATABASES_MPI DATABASES_MPI $ker_name  \
#        1000 1 ${ker_name}_abs_pdf.txt
#
#    zc=$(awk '$1!~/#/{a+=$3; if(a>cutoff){print $2; exit}}' \
#        cutoff=$threshold_corner ${ker_name}_abs_pdf.txt)
#
#    echo "### ${ker_name}: corner amplitude is $zc"
#
#    ${mpi_exec} $sem_utils/bin/xsem_thresholding \
#        $nproc $mesh_dir/DATABASES_MPI DATABASES_MPI $ker_name  \
#        $zc $threshold_rmax DATABASES_MPI ${ker_name}_precond
#done

echo
echo "The kernel update is finished [$(date)]."
echo

#END