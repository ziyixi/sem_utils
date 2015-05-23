subroutine selfdoc()

  print '(a)', "NAME"
  print '(a)', ""
  print '(a)', "  xsem_interp_mesh "
  print '(a)', "    - interpolate GLL model from one SEM mesh onto a new mesh"
  print '(a)', ""
  print '(a)', "SYNOPSIS"
  print '(a)', ""
  print '(a)', "  xsem_interp_mesh \ "
  print '(a)', "    <old_mesh_dir> <nproc_old> <old_model_dir> <model_tags> "
  print '(a)', "    <new_mesh_dir> <nproc_new> <new_model_dir> "
  print '(a)', ""
  print '(a)', "DESCRIPTION"
  print '(a)', ""
  print '(a)', "  interpolate GLL model given on one SEM mesh onto  another SEM mesh"
  print '(a)', "    the GLL interpolation is used, which is the SEM basis function."
  print '(a)', ""
  print '(a)', "PARAMETERS"
  print '(a)', ""
  print '(a)', "  (string) old_mesh_dir: directory holds proc*_reg1_solver_data.bin"
  print '(a)', "  (int) nproc_old: number of slices of the old mesh"
  print '(a)', "  (string) old_model_dir: directory holds proc*_reg1_<model_tag>.bin"
  print '(a)', "  (string) model_tags: comma delimited string, e.g. vsv,vsh,rho "
  print '(a)', "  (string) new_mesh_dir: directory holds proc*_reg1_solver_data.bin"
  print '(a)', "  (int) nproc_new: number of slices of the new mesh"
  print '(a)', "  (string) new_model_dir: directory holds output model files"
  print '(a)', ""
  print '(a)', "NOTES"
  print '(a)', ""
  print '(a)', "  This program must run in parallel, e.g. mpirun -n <nproc> ..."

end subroutine


!///////////////////////////////////////////////////////////////////////////////
program xsem_interp_mesh
  
  use sem_constants
  use sem_io
  use sem_mesh
  use sem_utils
  use sem_parallel

  implicit none

  !===== declare variables

  !-- command line args
  integer, parameter :: nargs = 7
  character(len=MAX_STRING_LEN) :: args(nargs)
  character(len=MAX_STRING_LEN) :: old_mesh_dir, old_model_dir
  integer :: nproc_old
  character(len=MAX_STRING_LEN) :: model_tags

  character(len=MAX_STRING_LEN) :: new_mesh_dir, new_model_dir
  integer :: nproc_new

  !-- region id
  integer, parameter :: iregion = IREGION_CRUST_MANTLE ! crust_mantle

  !-- local variables
  integer :: i, iproc, ier, iglob, ispec

  !-- mpi
  integer :: myrank, nrank

  !-- model names
  integer :: imodel, nmodel
  character(len=MAX_STRING_LEN), allocatable :: model_names(:)

  !-- old mesh slice
  type(sem_mesh_data) :: mesh_old
  integer :: iproc_old, nspec_old
  real(dp), allocatable :: model_gll_old(:,:,:,:,:)

  !-- new mesh slice
  type(sem_mesh_data) :: mesh_new
  integer :: iproc_new, nspec_new
  real(dp), allocatable :: model_gll_new(:,:,:,:,:)

  !-- interpolation points
  real(dp), allocatable :: xyz_new(:,:)
  integer, allocatable :: idoubling_new(:,:,:,:)
  real(sp), parameter :: FILLVALUE_sp = huge(1.0_sp)
  integer :: igll, igllx, iglly, igllz

  !-- sem location
  type(sem_mesh_location), allocatable :: location_1slice(:)
  integer, parameter :: nnearest = 10
  real(dp) :: typical_size, max_search_dist, max_misloc
  real(dp), allocatable :: misloc(:), misloc_final(:)
  integer, allocatable :: stat(:), stat_final(:)
  real(dp), allocatable :: model_interp(:,:)

  !===== start MPI

  call init_mpi()
  call world_size(nrank)
  call world_rank(myrank)

  !===== read command line arguments

  if (command_argument_count() /= nargs) then
    if (myrank == 0) then
      call selfdoc()
      stop "[ERROR] xsem_interp_mesh: check your input arguments."
    endif
  endif
  call synchronize_all()

  do i = 1, nargs
    call get_command_argument(i, args(i), status=ier)
  enddo
  read(args(1), '(a)') old_mesh_dir
  read(args(2), *) nproc_old
  read(args(3), '(a)') old_model_dir
  read(args(4), '(a)') model_tags
  read(args(5), '(a)') new_mesh_dir
  read(args(6), *) nproc_new
  read(args(7), '(a)') new_model_dir

  !===== parse model tags
  call sem_utils_delimit_string(model_tags, ',', model_names, nmodel)

  if (myrank == 0) then
    print '(a)', '# nmodel=', nmodel
    print '(a)', '# model_names=', (trim(model_names(i))//" ", i=1,nmodel)
  endif

  !===== loop each slices of the new mesh

  do iproc_new = myrank, (nproc_new - 1), nrank

    !-- read new mesh slice
    call sem_mesh_read(mesh_new, new_mesh_dir, iproc_new, iregion)

    !-- initialize arrays of xyz points
    nspec_new = mesh_new%nspec
    nglob_new = mesh_new%nglob
    ngll_new = NGLLX * NGLLY * NGLLZ * nspec_new

    if (allocated(xyz_new)) then
      deallocate(xyz_new, idoubling_new)
    endif
    allocate(xyz_new(3, ngll_new), idoubling_new(ngll_new))

    do ispec = 1, nspec_new
      do igllz = 1, NGLLZ
        do iglly = 1, NGLLY
          do igllx = 1, NGLLX
            igll = igllx + &
                   NGLLX * ( (iglly-1) + &
                   NGLLY * ( (igllz-1) + &
                   NGLLZ * ( (ispec-1))))
            iglob = mesh_new%ibool(igllx, iglly, igllz, ispec)
            xyz_new(:, igll) = mesh_new%xyz_glob(:, iglob)
            idoubling_new(igll) = mesh_new%idoubling(ispec)
          enddo
        enddo
      enddo
    enddo

    !-- initialize variables
    allocate(location_1slice(ngll_new))

    allocate(stat(ngll_new), misloc(ngll_new))
    stat = -1
    misloc = HUGE(1.0_dp)

    allocate(model_interp(nmodel, ngll_new))
    model_interp = FILLVALUE_sp
 
    !-- loop each slices of the old mesh

    do iproc_old = 0, (nproc_old - 1)

      ! read old mesh slice
      call sem_mesh_read(mesh_old, old_mesh_dir, iproc_old, iregion)

      ! read old model
      if (allocated(model_gll_old)) then
        deallocate(model_gll_old)
      endif
      allocate(model_gll_old(nmodel, NGLLX, NGLLY, NGLLZ, mesh_old%nspec))

      call sem_io_read_gll_n(old_model_dir, iproc, iregion, &
                             model_names, nmodel, model_gll_old)

      ! locate points in this mesh slice
      call sem_mesh_locate_kdtree2(mesh_old, ngll_new, xyz_new, idoubling_new, &
        nnearest, max_search_dist, max_misloc, location_1slice)

      ! interpolate model only on points located inside an element
      do igll = 1, ngll_new

        ! safety check
        if (stat_final(igll) == 1 .and. location_1slice(igll)%stat == 1 ) then
          print *, "[WARN] igll=", igll
          print *, "------ this point is located inside more than one element!"
          print *, "------ some problem may occur."
          print *, "------ only use the first located element."
          cycle
        endif

        ! for point located inside one element in the first time
        ! or closer to one element than located before
        if ( location_1slice(igll)%stat == 1 .or. &
             (location_1slice(igll)%stat == 0 .and. &
              location_1slice(igll)%misloc < misloc_final(igll)) ) &
        then

          ! interpolate model
          do imodel = 1, nmodel
            model_interp(imodel,igll) = &
              sum(location_1slice(ipoint)%lagrange * &
                model_gll_old(imodel, :, :, :, location_1slice(igll)%eid))
          enddo

          stat_final(igll)   = location_1slice(igll)%stat
          misloc_final(igll) = location_1slice(igll)%misloc

        endif

      enddo ! igll = 1, ngll_new

    enddo ! iproc_old

    !-- output location information

    ! convert misloc relative to typical element size
    where (stat_final /= -1)
      misloc_final = misloc_final / typical_size
    endwhere

    !-- write out gll files for new mesh slice

    do ispec = 1, nspec_new
      do igllz = 1, NGLLZ
        do iglly = 1, NGLLY
          do igllx = 1, NGLLX
            igll = igllx + &
                   NGLLX * ( (iglly-1) + & 
                   NGLLY * ( (igllz-1) + & 
                   NGLLZ * ( (ispec-1))))
            if (locstat_final /= -1) then
              model_gll_new(:, igllx, iglly, igllz, ispec) = &
                model_interp(:, igll)
            endif
          enddo
        enddo
      enddo
    enddo

    call sem_io_write_gll_file_n(new_model_dir, iproc_new, iregion, &
      model_names, nmodel, model_gll_new)

  enddo ! iproc_new

  !===== exit MPI
  call synchronize_all()
  call finalize_mpi()

end program
