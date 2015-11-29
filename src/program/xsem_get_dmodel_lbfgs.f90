subroutine selfdoc()
  print '(a)', "NAME"
  print '(a)', ""
  print '(a)', "  xsem_get_dmodel_lbfgs"
  print '(a)', "    - calculate model udpate direction by l-bfgs"
  print '(a)', ""
  print '(a)', "SYNOPSIS"
  print '(a)', ""
  print '(a)', "  xsem_get_dmodel_lbfgs \"
  print '(a)', "    <nproc> <mesh_dir> <kernel_dir> <dm_dg_dir_list> <model_tags> "
  print '(a)', "    <use_mask> <out_dir>"
  print '(a)', "DESCRIPTION"
  print '(a)', ""
  print '(a)', ""
  print '(a)', "PARAMETERS"
  print '(a)', ""
  print '(a)', "  (int) nproc: number of mesh slices"
  print '(a)', "  (string) mesh_dir: directory containing proc000***_reg1_solver_data.bin"
  print '(a)', "  (string) kernel_dir: directory holds proc***_reg1_***_kernel.bin"
  print '(a)', "  (string) dm_dg_dir_list: list of dmodel_dir,dkernel_dir,step_length"
  print '(a)', "  (string) model_tags: comma delimited string, e.g. mu,lamda,rho"
  print '(a)', "  (string) kernel_suffix: suffix to append on model names, e.g. _kernel_precond"
  print '(a)', "  (logical) use_mask:  flag if masking is used (mask files should locate in kernel_dir)"
  print '(a)', "  (string) out_dir: output directory"
  print '(a)', ""
  print '(a)', "NOTE"
  print '(a)', ""
  print '(a)', "  1. _dmodel will be appended to model_tags for output files"
  print '(a)', "  2. _dkernel will be appended to model_tags for output files"
  print '(a)', "  3. the mask is applied on initial Hessian(H0)."
  print '(a)', "  4. must run in parallel with <nproc> processes"
end subroutine


program get_dmodel_lbfgs

  use sem_constants
  use sem_io
  use sem_mesh
  use sem_utils
  use sem_parallel

  implicit none

  !===== declare variables

  ! command line args
  integer, parameter :: nargs = 8
  character(len=MAX_STRING_LEN) :: args(nargs)
  integer :: nproc
  character(len=MAX_STRING_LEN) :: mesh_dir
  character(len=MAX_STRING_LEN) :: kernel_dir
  character(len=MAX_STRING_LEN) :: dm_dg_dir_list
  character(len=MAX_STRING_LEN) :: model_tags
  character(len=MAX_STRING_LEN) :: kernel_suffix
  logical :: use_mask
  character(len=MAX_STRING_LEN) :: out_dir

  ! local variables
  integer, parameter :: iregion = IREGION_CRUST_MANTLE ! crust_mantle
  integer :: i, ier
  ! mpi
  integer :: nrank, myrank
  ! model names
  integer :: nmodel
  character(len=MAX_STRING_LEN), allocatable :: model_names(:)
  ! mesh
  type(sem_mesh_data) :: mesh_data
  integer :: nspec
  ! mask
  real(dp), dimension(:,:,:,:), allocatable :: mask
  ! kernel
  real(dp), dimension(:,:,:,:,:), allocatable :: kernel
  character(len=MAX_STRING_LEN), allocatable :: kernel_names(:)
  ! lbfgs: dm, dg
  real(dp), dimension(:,:,:,:,:), allocatable :: q
  character(len=MAX_STRING_LEN), allocatable :: lines(:)
  integer :: nstep_lbfgs
  character(len=MAX_STRING_LEN), allocatable :: dm_dir(:), dg_dir(:)
  real(dp), dimension(:), allocatable :: step_length
  character(len=MAX_STRING_LEN), allocatable :: dm_names(:), dg_names(:)
  real(dp), dimension(:,:,:,:,:,:), allocatable :: dm, dg
  ! lbfgs: rho,alpha,beta
  real(dp), dimension(:), allocatable :: rho, alpha
  real(dp) :: beta, rho_sum, alpha_sum, beta_sum, gamma, gamma_sum
  real(dp) :: q_norm, q_norm_sum
  real(dp), dimension(:,:,:,:), allocatable :: gll_volume 

  !===== start MPI
  call init_mpi()
  call world_size(nrank)
  call world_rank(myrank)

  !===== read command line arguments
  if (command_argument_count() /= nargs) then
    if (myrank == 0) then
      call selfdoc()
      print *, "[ERROR] xsem_get_dmodel_lbfgs: check your input arguments."
      call abort_mpi()
    endif
  endif
  call synchronize_all()

  do i = 1, nargs
    call get_command_argument(i, args(i))
  enddo
  read(args(1),*) nproc
  read(args(2),'(a)') mesh_dir 
  read(args(3),'(a)') kernel_dir 
  read(args(4),'(a)') dm_dg_dir_list
  read(args(5),'(a)') model_tags
  read(args(6),'(a)') kernel_suffix
  select case (args(7))
    case ('0')
      use_mask = .false.
    case ('1')
      use_mask = .true.
    case default
      if (myrank == 0) then
        print *, '[ERROR]: use_mask must be 0 or 1'
        call abort_mpi() 
      endif
  end select
  read(args(8),'(a)') out_dir

  call synchronize_all()

  !====== validate inputs 
  if (nrank /= nproc) then
    if (myrank == 0) then
      print *, "[ERROR] must run in processes of number ", nproc
      call abort_mpi()
    endif
  endif
  call synchronize_all()

  !===== parse model tags
  call sem_utils_delimit_string(model_tags, ',', model_names, nmodel)

  if (myrank == 0) then
    print *, '# nmodel=', nmodel
    print *, '# model_names=', (trim(model_names(i))//"  ", i=1,nmodel)
  endif

  allocate(dm_names(nmodel), dg_names(nmodel), kernel_names(nmodel))
  do i = 1, nmodel
    kernel_names(i) = trim(model_names(i))//trim(kernel_suffix)
    dm_names(i) = trim(model_names(i))//"_dmodel"
    dg_names(i) = trim(model_names(i))//"_dkernel"
  enddo

  !===== read dm_dg_dir_list
  call sem_utils_read_line(dm_dg_dir_list, lines, nstep_lbfgs)

  allocate(dm_dir(nstep_lbfgs), dg_dir(nstep_lbfgs))
  allocate(step_length(nstep_lbfgs))
  allocate(rho(nstep_lbfgs), alpha(nstep_lbfgs))

  do i = 1, nstep_lbfgs
    read(lines(i),*,iostat=ier) dm_dir(i), dg_dir(i), step_length(i)
    if (ier /= 0) then
      if (myrank == 0) then
        print *, "[ERROR] failed to read dm_dg_dir_list at line ", i
        call abort_mpi()
      endif
    endif
    if (myrank == 0) then
      print *, i, trim(dm_dir(i)), trim(dg_dir(i)), step_length(i)
    endif
  enddo
  call synchronize_all()

  !====== calculate model update diretion

  ! get mesh geometry
  if (myrank == 0) print *, '#====== get mesh geometry' 
  call sem_mesh_read(mesh_dir, myrank, iregion, mesh_data)
  nspec = mesh_data%nspec

  ! initialize data 
  allocate(dm(nmodel,NGLLX,NGLLY,NGLLZ,nspec,nstep_lbfgs), &
           dg(nmodel,NGLLX,NGLLY,NGLLZ,nspec,nstep_lbfgs))
  allocate(kernel(nmodel,NGLLX,NGLLY,NGLLZ,nspec))
  allocate(q(nmodel,NGLLX,NGLLY,NGLLZ,nspec))
  allocate(gll_volume(NGLLX,NGLLY,NGLLZ,nspec))
  if (use_mask) then
    allocate(mask(NGLLX,NGLLY,NGLLZ,nspec))
  endif

  ! get gll volume
  call sem_mesh_gll_volume(mesh_data, gll_volume)

  ! read current kernel
  call sem_io_read_gll_file_n(kernel_dir, myrank, iregion, &
    kernel_names, nmodel, kernel)

  !-- l-bfgs: first loop
  if (myrank == 0) print *, '#====== L-BFGS: start' 

  if (myrank == 0) print *, ' q = -g (g: kernel)'
  q = -1.0 * kernel

  if (myrank == 0) print *, '#====== L-BFGS: first loop' 
  do i = 1, nstep_lbfgs

    if (myrank == 0) print *, '#-- step ', i

    ! read dm(i)
    call sem_io_read_gll_file_n(dm_dir(i), myrank, iregion, &
      dm_names, nmodel, dm(:,:,:,:,:,i))

    ! read dg(i)
    call sem_io_read_gll_file_n(dg_dir(i), myrank, iregion, &
      dg_names, nmodel, dg(:,:,:,:,:,i))

    ! dm(i) = step_length * dm(i)
    dm(:,:,:,:,:,i) = step_length(i) * dm(:,:,:,:,:,i)

    ! rho(i) = 1 / (dm(i), dg(i))
    rho(i) = sum(dm(:,:,:,:,:,i) * dg(:,:,:,:,:,i) * spread(gll_volume,1,nmodel))
    call synchronize_all()
    call sum_all_dp(rho(i), rho_sum)
    call synchronize_all()
    call bcast_all_singledp(rho_sum)
    rho(i) = 1.0_dp / rho_sum

    if (myrank == 0) print *, ' rho(i)=1/(dm(i),dg(i))=', rho(i)

    ! alpha(i) = rho(i) * (dm(i), q)
    alpha(i) = sum(dm(:,:,:,:,:,i) * q(:,:,:,:,:) * spread(gll_volume,1,nmodel))
    call synchronize_all()
    call sum_all_dp(alpha(i), alpha_sum)
    call synchronize_all()
    call bcast_all_singledp(alpha_sum)
    alpha(i) = rho(i) * alpha_sum

    if (myrank == 0) print *, ' alpha(i)=rho(i)*(dm(i),q)=', alpha(i)

    ! q = q - alpha(i)*dg(i)
    q = q - alpha(i)*dg(:,:,:,:,:,i)

  enddo

  !-- L-BFGS: apply initial Hessian q <- H0 * q
  ! H0 ~ (dm(1), dg(1)) / (dg(1), dg(1)) * IdentityMatrix
  ! 1: most recent iteration
  gamma = sum(dg(:,:,:,:,:,1)**2 * spread(gll_volume,1,nmodel))
  call synchronize_all()
  call sum_all_dp(gamma, gamma_sum)
  call bcast_all_singledp(gamma_sum)
  gamma = 1.0_dp / rho(1) / gamma_sum
  q = gamma * q

  if (myrank == 0) then
    print *, '#====== L-BFGS: apply initial Hessian'
    print *, 'H0 ~ gamma * I ~ (dm(1), dg(1)) / (dg(1), dg(1)) * I'
    print *, 'gamma=', gamma
  endif

  if (use_mask) then
    if (myrank==0) print *, 'mask is applied.'
    call sem_io_read_gll_file_1(kernel_dir, myrank, iregion, 'mask', mask)
    q = q * spread(mask,1,nmodel)
  endif

  !-- L-BFGS: second loop
  if (myrank==0) print *, '#====== L-BFGS: second loop'
  do i = nstep_lbfgs, 1, -1

    if (myrank==0) print *, '#-- step ', i

    ! beta = rho(i) * (dg(i), q)
    beta = sum(dg(:,:,:,:,:,i) * q(:,:,:,:,:) * spread(gll_volume,1,nmodel))
    call synchronize_all()
    call sum_all_dp(beta, beta_sum)
    call bcast_all_singledp(beta_sum)
    beta = rho(i) * beta_sum

    if (myrank == 0) print *, 'beta=rho(i)*(dg(i),q)=', beta

    ! q = q + (alpha(i) - beta)*dm(i)
    q = q + (alpha(i)-beta)*dm(:,:,:,:,:,i)

  enddo

  !-- compute normalized correlation coef. between model update direction and kernel 
  call synchronize_all()
  q_norm = sum(q**2 * spread(gll_volume,1,nmodel))
  call synchronize_all()
  call sum_all_dp(q_norm, q_norm_sum)

  call synchronize_all()
  beta = sum(kernel**2 * spread(gll_volume,1,nmodel))
  call synchronize_all()
  call sum_all_dp(beta, beta_sum)

  call synchronize_all()
  gamma = sum(q * kernel * spread(gll_volume,1,nmodel))
  call synchronize_all()
  call sum_all_dp(gamma, gamma_sum)

  call synchronize_all()
  if (myrank == 0) then
    print *, '#====== L-BFGS: end'
    print *, ' q <- H * (-g)'
    print *, ' ||q||=', sqrt(q_norm_sum)
    print *, ' ||g||=', sqrt(beta_sum)
    print *, ' (q, g)/(|q|*|g|)=', gamma_sum/sqrt(q_norm_sum)/sqrt(beta_sum)
  endif

  !---- write out new dmodel
  call synchronize_all()
  call sem_io_write_gll_file_n(out_dir, myrank, iregion, dm_names, nmodel, q)

  call synchronize_all()
  call finalize_mpi()

end program