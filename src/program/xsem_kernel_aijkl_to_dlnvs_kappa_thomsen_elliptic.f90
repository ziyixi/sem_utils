subroutine selfdoc()

  print '(a)', "NAME"
  print '(a)', ""
  print '(a)', "  xsem_kernel_aijkl_to_dlnvs_kappa_thomsen_elliptic"
  print '(a)', "    - reduce aijkl kernel to VTI kernel (dlnvsv, kappa, eps, gamma)"
  print '(a)', ""
  print '(a)', "SYNOPSIS"
  print '(a)', ""
  print '(a)', "  xsem_kernel_aijkl_to_dlnvs_kappa_thomsen_elliptic \"
  print '(a)', "    <nproc> <mesh_dir> <model_dir> <kernel_dir> <out_dir>"
  print '(a)', ""
  print '(a)', "DESCRIPTION"
  print '(a)', ""
  print '(a)', "  aijkl kernels are indexed from 1 to 21 as defined in "
  print '(a)', "  specfem3d_globe/src/specfem3D/compute_kernels.f90:compute_strain_product()"
  print '(a)', ""
  print '(a)', "PARAMETERS"
  print '(a)', ""
  print '(a)', "  (int) nproc:  number of mesh slices"
  print '(a)', "  (string) mesh_dir:  directory holds proc*_reg1_solver_data.bin"
  print '(a)', "  (string) model_dir:  directory holds the model files to do the simulation, proc*_reg1_[vsv_ref,dlnvs,kappa,eps,gamma].bin"
  print '(a)', "  (string) kernel_dir:  directory holds the aijkl_kernel files"
  print '(a)', "                        proc******_reg1_aijkl_kernel.bin"
  print '(a)', "  (string) out_dir:  output directory for [dlnvs,kappa,eps,gamma]_kernel"
  print '(a)', ""
  print '(a)', "NOTE"
  print '(a)', ""
  print '(a)', "  1. can be run in parallel"
  print '(a)', "  2. aijkl = cijkl/rho"
  print '(a)', "  3. thomsen's anisotropic parameters: eps = (C66-C44)/C44/2, gamma = (C11-C33)/C33/2"
  print '(a)', "  4. elliptical condition: delta = eps "
  print '(a)', "  5. vsv = vsv_ref * exp(dlnvs) "

end subroutine


!///////////////////////////////////////////////////////////////////////////////
program xsem_kernel_aijkl_to_dlnvs_kappa_thomsen_elliptic

  use sem_constants
  use sem_io
  use sem_mesh
  use sem_utils
  use sem_parallel

  implicit none

  !===== declare variables
  ! command line args
  integer, parameter :: nargs = 5
  character(len=MAX_STRING_LEN) :: args(nargs)
  integer :: nproc
  character(len=MAX_STRING_LEN) :: mesh_dir
  character(len=MAX_STRING_LEN) :: model_dir
  character(len=MAX_STRING_LEN) :: kernel_dir
  character(len=MAX_STRING_LEN) :: out_dir

  ! local variables
  integer, parameter :: iregion = IREGION_CRUST_MANTLE ! crust_mantle
  integer :: i, iproc

  ! mpi
  integer :: myrank, nrank

  ! mesh
  type(sem_mesh_data) :: mesh_data
  integer :: nspec, ispec

  ! model gll
  real(dp), dimension(:,:,:,:), allocatable :: vsv_ref, vsv2, dlnvs, kappa, kappa2, eps, gamma

  ! kernel gll 
  real(dp), allocatable :: aijkl_kernel(:,:,:,:,:)
  real(dp), dimension(:,:,:,:), allocatable :: dlnvs_kernel, kappa_kernel
  real(dp), dimension(:,:,:,:), allocatable :: eps_kernel, gamma_kernel

  !===== start MPI
  call init_mpi()
  call world_size(nrank)
  call world_rank(myrank)

  !===== read command line arguments
  if (command_argument_count() /= nargs) then
    if (myrank == 0) then
      call selfdoc()
      print *, "[ERROR] xsem_kernel_aijkl_to_vti: check your inputs."
      call abort_mpi()
    endif 
  endif
  call synchronize_all()

  do i = 1, nargs
    call get_command_argument(i, args(i))
  enddo
  read(args(1), *) nproc
  read(args(2), '(a)') mesh_dir
  read(args(3), '(a)') model_dir
  read(args(4), '(a)') kernel_dir
  read(args(5), '(a)') out_dir 

  !====== loop model slices 

  ! get mesh geometry
  if (myrank == 0) then
    call sem_mesh_read(mesh_dir, myrank, iregion, mesh_data)
    nspec = mesh_data%nspec
  endif
  call bcast_all_singlei(nspec)

  call synchronize_all()

  ! initialize gll arrays 
  allocate(vsv_ref(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(dlnvs(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(vsv2(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(kappa(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(kappa2(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(eps(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(gamma(NGLLX,NGLLY,NGLLZ,nspec))

  allocate(aijkl_kernel(21,NGLLX,NGLLY,NGLLZ,nspec))

  allocate(dlnvs_kernel(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(kappa_kernel(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(eps_kernel(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(gamma_kernel(NGLLX,NGLLY,NGLLZ,nspec))

  ! reduce aijkl kernels
  do iproc = myrank, (nproc-1), nrank

    print *, '# iproc=', iproc

    ! read mesh
    call sem_mesh_read(mesh_dir, iproc, iregion, mesh_data)

    ! read aijkl_kernel
    call sem_io_read_cijkl_kernel(kernel_dir, iproc, iregion, 'aijkl_kernel', aijkl_kernel)

    ! read reference model
    call sem_io_read_gll_file_1(model_dir, iproc, iregion, 'vsv_ref', vsv_ref)
    ! read model
    call sem_io_read_gll_file_1(model_dir, iproc, iregion, 'dlnvs', dlnvs)
    call sem_io_read_gll_file_1(model_dir, iproc, iregion, 'kappa', kappa)
    call sem_io_read_gll_file_1(model_dir, iproc, iregion, 'eps', eps)
    call sem_io_read_gll_file_1(model_dir, iproc, iregion, 'gamma', gamma)

    kappa2 = kappa**2
    vsv2 = vsv_ref**2 * exp(2.0*dlnvs)

    ! enforce isotropy for element with ispec_is_tiso = .false.
    do ispec = 1, nspec
      if (.not. mesh_data%ispec_is_tiso(ispec)) then
        eps(:,:,:,ispec) = 0.0
        gamma(:,:,:,ispec) = 0.0
      endif
    enddo

    ! reduce kernels
    dlnvs_kernel = ( aijkl_kernel(1,:,:,:,:)*(1.0+2.0*eps)*kappa2                       &
                   + aijkl_kernel(7,:,:,:,:)*(1.0+2.0*eps)*kappa2                       &
                   + aijkl_kernel(12,:,:,:,:)*kappa2                                    &
                   + aijkl_kernel(2,:,:,:,:)*((1.0+2.0*eps)*kappa2-2.0*(1.0+2.0*gamma)) &
                   + aijkl_kernel(3,:,:,:,:)*((1.0+eps)*kappa2-2.0)                     &
                   + aijkl_kernel(8,:,:,:,:)*((1.0+eps)*kappa2-2.0)                     &
                   + aijkl_kernel(16,:,:,:,:)                                           &
                   + aijkl_kernel(19,:,:,:,:)                                           &
                   + aijkl_kernel(21,:,:,:,:)*(1.0+2.0*gamma) )*2.0*vsv2

    kappa_kernel = ( aijkl_kernel(1,:,:,:,:)*(1.0+2.0*eps)                  &
                   + aijkl_kernel(7,:,:,:,:)*(1.0+2.0*eps)                  &
                   + aijkl_kernel(12,:,:,:,:)                               &
                   + aijkl_kernel(2,:,:,:,:)*(1.0+2.0*eps)                  &
                   + aijkl_kernel(3,:,:,:,:)*(1.0+eps)                      &
                   + aijkl_kernel(8,:,:,:,:)*(1.0+eps) )*2.0*kappa*vsv2                  

    eps_kernel = ( aijkl_kernel(1,:,:,:,:)*2.0            &
                 + aijkl_kernel(7,:,:,:,:)*2.0            &
                 + aijkl_kernel(2,:,:,:,:)*2.0            &
                 + aijkl_kernel(3,:,:,:,:)                &
                 + aijkl_kernel(8,:,:,:,:) )*kappa2*vsv2

    gamma_kernel = ( aijkl_kernel(21,:,:,:,:)*2.0         &
                   - aijkl_kernel(2,:,:,:,:)*4.0 )*vsv2

    ! enforce isotropy for element with ispec_is_tiso = .false.
    do ispec = 1, nspec
      if (.not. mesh_data%ispec_is_tiso(ispec)) then
        eps_kernel(:,:,:,ispec) = 0.0
        gamma_kernel(:,:,:,ispec) = 0.0
      endif
    enddo

    print *, "aijkl_kernel: min/max=", minval(aijkl_kernel), maxval(aijkl_kernel)
    print *, "dlnvs_kernel: min/max=", minval(dlnvs_kernel), maxval(dlnvs_kernel)
    print *, "kappa_kernel: min/max=", minval(kappa_kernel), maxval(kappa_kernel)
    print *, "eps_kernel: min/max=", minval(eps_kernel), maxval(eps_kernel)
    print *, "gamma_kernel: min/max=", minval(gamma_kernel), maxval(gamma_kernel)

    ! write out kernel files
    call sem_io_write_gll_file_1(out_dir, iproc, iregion, 'dlnvs_kernel', dlnvs_kernel)
    call sem_io_write_gll_file_1(out_dir, iproc, iregion, 'kappa_kernel', kappa_kernel)
    call sem_io_write_gll_file_1(out_dir, iproc, iregion, 'eps_kernel', eps_kernel)
    call sem_io_write_gll_file_1(out_dir, iproc, iregion, 'gamma_kernel', gamma_kernel)

  enddo ! iproc

  !====== exit MPI
  call synchronize_all()
  call finalize_mpi()

end program
