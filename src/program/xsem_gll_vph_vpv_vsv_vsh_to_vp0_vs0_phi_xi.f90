subroutine selfdoc()
  print '(a)', "NAME"
  print '(a)', ""
  print '(a)', "  xsem_gll_vph_vpv_vsv_vsh_to_vp0_vs0_phi_xi"
  print '(a)', "    - convert parameterization from (vph,vpv,vsv,vsh) to (vp0,vs0,phi,xi)"
  print '(a)', ""
  print '(a)', "SYNOPSIS"
  print '(a)', ""
  print '(a)', "  xsem_gll_vph_vpv_vsv_vsh_to_vp0_vs0_phi_xi \"
  print '(a)', "    <nproc> <mesh_dir> <model_dir> <out_dir>"
  print '(a)', ""
  print '(a)', "DESCRIPTION"
  print '(a)', ""
  print '(a)', ""
  print '(a)', "PARAMETERS"
  print '(a)', ""
  print '(a)', "  (int)    nproc:  number of mesh slices"
  print '(a)', "  (string) mesh_dir:  directory containing proc000***_reg1_solver_data.bin"
  print '(a)', "  (string) model_dir:  directory holds proc*_reg1_[vph,vpv,vsv,vsh].bin"
  print '(a)', "  (string) out_dir:  output directory for proc*_reg1_[vp0,vs0,phi,xi].bin"
  print '(a)', ""
  print '(a)', "NOTE"
  print '(a)', ""
  print '(a)', "  1. can be run in parallel"
  print '(a)', "  2. vp0, vs0: voigt averaged isotropic P and S velocities"
  print '(a)', "    For weak anisotropy (Panning & Romanowicz, 2006) "
  print '(a)', "     vp0^2 = 4/5*vph^2 + 1/5*vpv^2, vs0^2 = 1/3*vsh^2 + 2/3*vsv^2"
  print '(a)', "     , and phi = (vph^2 - vpv^2)/vp0^2, xi = (vsh^2 - vsv^2)/vs0^2"
end subroutine


program xsem_gll_vph_vpv_vsv_vsh_to_vp0_vs0_phi_xi

  use sem_constants
  use sem_io
  use sem_mesh
  use sem_utils
  use sem_parallel

  implicit none

  !===== declare variables

  ! command line args
  integer, parameter :: nargs = 4
  character(len=MAX_STRING_LEN) :: args(nargs)
  integer :: nproc
  character(len=MAX_STRING_LEN) :: mesh_dir
  character(len=MAX_STRING_LEN) :: model_dir
  character(len=MAX_STRING_LEN) :: out_dir

  ! local variables
  integer, parameter :: iregion = IREGION_CRUST_MANTLE ! crust_mantle
  integer :: i, iproc, ier
  ! mpi
  integer :: myrank, nrank
  ! mesh
  type(sem_mesh_data) :: mesh_data
  integer :: ispec, nspec
  ! model
  real(dp), dimension(:,:,:,:), allocatable :: vph,vpv,vsh,vsv
  real(dp), dimension(:,:,:,:), allocatable :: vp0,vs0,phi,xi

  !===== start MPI
  call init_mpi()
  call world_size(nrank)
  call world_rank(myrank)

  !===== read command line arguments
  if (command_argument_count() /= nargs) then
    if (myrank == 0) then
      call selfdoc()
      print *, "[ERROR] check your inputs."
      call abort_mpi()
    endif
  endif

  call synchronize_all()

  do i = 1, nargs
    call get_command_argument(i, args(i))
  enddo
  read(args(1),*) nproc
  read(args(2),'(a)') mesh_dir 
  read(args(3),'(a)') model_dir 
  read(args(4),'(a)') out_dir

  call synchronize_all()

  !====== get mesh geometry
  if (myrank == 0) then
    call sem_mesh_read(mesh_dir, myrank, iregion, mesh_data)
    nspec = mesh_data%nspec
  endif
  call bcast_all_singlei(nspec)
  call synchronize_all()

  ! allocate arrays 
  allocate(vph(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(vpv(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(vsv(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(vsh(NGLLX,NGLLY,NGLLZ,nspec))

  allocate(vp0(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(vs0(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(phi(NGLLX,NGLLY,NGLLZ,nspec))
  allocate(xi(NGLLX,NGLLY,NGLLZ,nspec))

  !====== calculate thomsen parameters
  do iproc = myrank, (nproc-1), nrank
  
    print *, "iproc = ", iproc

    ! read mesh
    call sem_mesh_read(mesh_dir, iproc, iregion, mesh_data)

    ! read models
    call sem_io_read_gll_file_1(model_dir, iproc, iregion, 'vph', vph)
    call sem_io_read_gll_file_1(model_dir, iproc, iregion, 'vpv', vpv)
    call sem_io_read_gll_file_1(model_dir, iproc, iregion, 'vsv', vsv)
    call sem_io_read_gll_file_1(model_dir, iproc, iregion, 'vsh', vsh)

    ! voigt averaged isotropic velocities 
    vp0 = sqrt((4*vph**2 + vpv**2)/5)
    vs0 = sqrt((2*vsv**2 + vsh**2)/3)
    ! P and S anisotropy
    phi = (vph**2 - vpv**2)/vp0**2
    xi = (vsh**2 - vsv**2)/vs0**2

    ! enforce isotropy for element with ispec_is_tiso = .false.
    do ispec = 1, nspec
      if (.not. mesh_data%ispec_is_tiso(ispec)) then
        phi(:,:,:,ispec) = 0.0
        xi(:,:,:,ispec) = 0.0
      endif
    enddo

    ! write models
    call sem_io_write_gll_file_1(out_dir, iproc, iregion, 'vp0', vp0)
    call sem_io_write_gll_file_1(out_dir, iproc, iregion, 'vs0', vs0)
    call sem_io_write_gll_file_1(out_dir, iproc, iregion, 'phi', phi)
    call sem_io_write_gll_file_1(out_dir, iproc, iregion, 'xi', xi)

  enddo

  !====== Finalize
  call synchronize_all()
  call finalize_mpi()

end program
