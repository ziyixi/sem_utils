#FC = ifort
#FC = gfortran 
FC = mpif90

obj_dir = obj
bin_dir = bin
inc_dir = include
src_dir = src

netcdf_mod = /opt/local/include

module_dir = ${src_dir}/module
shared_dir = ${src_dir}/shared
program_dir = ${src_dir}/program

# gfortran
#FCFLAGS = -g -Wall -pedantic
FCFLAGS = -O2
FCFLAGS += -I$(inc_dir) -J$(obj_dir) -I$(netcdf_mod)
LDFLAGS = -L$(netcdf_mod) -lnetcdff

# ifort
#FCFLAGS = -g
##FCFLAGS = -O2
#FCFLAGS += -I $(inc_dir) -module $(obj_dir) -assume byterecl
#LDFLAGS =

module = sem_constants_mod sem_io_mod sem_mesh_mod \
		  sem_parallel_mod sem_utils_mod
shared = gll_library geographic_mod
program = xsem_interp_xyz \
		  xsem_slab_model \
		  xsem_slice_gcircle

#------------------------------------------
module_obj = $(patsubst  %,$(obj_dir)/%.o, $(module))
shared_obj = $(patsubst  %,$(obj_dir)/%.o, $(shared))
program_obj = $(patsubst %,$(obj_dir)/%.o, $(program))

all : $(program)

$(shared_obj) :
	$(FC) -c $(shared_dir)/$(patsubst %.o,%.f90,$(@F)) -o $@ $(FCFLAGS)

$(module_obj) : $(shared_obj)
	$(FC) -c $(module_dir)/$(patsubst %.o,%.f90,$(@F)) -o $@ $(FCFLAGS)

$(program_obj) : $(shared_obj) $(module_obj)
	$(FC) -c $(program_dir)/$(patsubst %.o,%.f90,$(@F)) -o $@ $(FCFLAGS)

#xsem_slice_gcircle : $(program_obj) $(shared_obj) $(module_obj)
#	$(FC) -o $(bin_dir)/$@ $@ $(shared_obj) $(module_obj) $(FCFLAGS) $(LDFLAGS)

$(program) : $(program_obj) $(shared_obj) $(module_obj)
	$(FC) -o $(bin_dir)/$(@F) $(patsubst %,$(obj_dir)/%.o, $(@F)) \
		$(shared_obj) $(module_obj) $(FCFLAGS) $(LDFLAGS)

# explicit specified dependencies
#$(module): $(shared)
#$(OBJ): $(SHARED) $(MOD)
#$(SHARED) : $(ODIR)/constants_module.o

.PHONY: clean

clean :
	\rm $(bin_dir)/* $(obj_dir)/*
