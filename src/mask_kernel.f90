! make mask file for event kernel, e.g. mask source / shallow mantle

subroutine selfdoc()
  print *, 'Usage: xmask_kernel <topo_dir> <source_vtk> <width(km)> <depth_stop> <depth_pass> <out_dir> <mask_name>'
  print *, 'files read: <topo_dir>/proc000***_reg1_solver_data.bin'
  print *, 'source_vtk: generated by specfem3D in forward simulation'
  print *, 'files written: <out_dir>/proc000***_reg1_<mask_name>.bin'
  stop
end subroutine

program mask_kernel 

  use constants,only: CUSTOM_REAL,MAX_STRING_LEN,IIN,IOUT, &
    NPROCTOT_VAL,NGLLCUBE,R_EARTH_KM,PI

  use sem_IO

  implicit none

  !---- declare variables
  integer, parameter :: iregion = 1

  ! command line arguments
  integer, parameter :: nargs = 7
  character(len=MAX_STRING_LEN) :: args(nargs)
  real(CUSTOM_REAL) :: source_width, depth_stop, depth_pass
  character(len=MAX_STRING_LEN) :: topo_dir, source_vtk, out_dir, mask_name
  
  ! local vars
  integer :: i, iproc, ispec, igllx, iglly, igllz, iglob, ier
  character(len=MAX_STRING_LEN) :: dummy

  type(sem_mesh) :: mesh_data
  integer :: isrc, nsrc
  real(CUSTOM_REAL), allocatable :: xyz_src(:,:), mask(:,:,:,:)
  real(CUSTOM_REAL) :: distsq, r, r_stop, r_pass, weight

  !---- get command line arguments 
  do i = 1, nargs 
    call get_command_argument(i,args(i), status=ier)
    if (trim(args(i)) == '') then
      call selfdoc()
    endif
  enddo
  read(args(1),'(a)') topo_dir
  read(args(2),'(a)') source_vtk
  read(args(3),*) source_width
  read(args(4),*) depth_stop
  read(args(5),*) depth_pass
  read(args(6),'(a)') out_dir
  read(args(7),'(a)') mask_name

  !---- read source_vtk
  open(unit=IIN, file=source_vtk, iostat=ier)
  if (ier /= 0) stop 'Error open source_vtk'

  ! skip header lines
  read(IIN,*)
  read(IIN,*)
  read(IIN,*)
  read(IIN,*)
  ! nsrc
  read(IIN,*,iostat=ier) dummy, nsrc, dummy 
  if (ier /= 0) stop 'Error read nsrc'
  ! xyz_src
  allocate(xyz_src(3,nsrc))
  do isrc = 1, nsrc
    read(IIN,*,iostat=ier) xyz_src(1,isrc), xyz_src(2,isrc), xyz_src(3,isrc)
    print *, 'isrc=', isrc
    print *, 'xyz_src(:,isrc)=', xyz_src(:,isrc)
    if (ier /= 0) stop 'Error read source location' 
  enddo
  close(IIN)

  !---- create kernel mask 

  call sem_set_dimension(iregion)

  allocate(mask(NGLLX,NGLLY,NGLLZ,NSPEC))

  ! non-dimensionalize
  source_width = source_width / SNGL(R_EARTH_KM)
  r_stop = 1 - depth_stop/SNGL(R_EARTH_KM)
  r_pass = 1 - depth_pass/SNGL(R_EARTH_KM)

  print *, 'after non-dimensinalize'
  print *, 'source_width=', source_width
  print *, 'r_stop=', r_stop
  print *, 'r_pass=', r_pass

  do iproc = 0, NPROCTOT_VAL-1

    ! read mesh data
    call sem_read_mesh(mesh_data,topo_dir,iproc,iregion)

    do ispec = 1, NSPEC
      do igllz = 1, NGLLZ
        do iglly = 1, NGLLY
          do igllx = 1, NGLLX

            weight = 1.0_CUSTOM_REAL

            iglob = mesh_data%ibool(igllx,iglly,igllz,ispec)
            ! mask source
            do isrc = 1, nsrc
              distsq = sum((mesh_data%xyz(:,iglob) - xyz_src(:,isrc))**2)
              weight = weight * (1.0_CUSTOM_REAL - exp(-(distsq/source_width**2)**2 ))
            enddo

            ! mask shallow mantle
            r = sqrt(sum(mesh_data%xyz(:,iglob)**2))
            if (r >= r_stop) weight = 0.0_CUSTOM_REAL
            if (r < r_stop .and. r > r_pass ) then
              weight = weight * 0.5_CUSTOM_REAL * &
                (1.0_CUSTOM_REAL + cos(SNGL(PI)*(r-r_pass)/(r_stop-r_pass)))
            endif

            mask(igllx,iglly,igllz,ispec) = weight

          enddo
        enddo
      enddo
    enddo

    ! save mask file
    call sem_open_datafile_for_write(IOUT,out_dir,iproc,iregion,mask_name)
    write(IOUT) mask
    close(IOUT)

  enddo ! iproc

end program mask_kernel
