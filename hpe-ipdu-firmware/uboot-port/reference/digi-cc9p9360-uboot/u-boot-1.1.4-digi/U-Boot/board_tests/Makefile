#
#  board_tests/Makefile
#
#  Copyright (C) 2006 by Digi International Inc.
#  All rights reserved.
#
#  This program is free software; you can redistribute it and/or modify it
#  under the terms of the GNU General Public License version2  as published by
#  the Free Software Foundation.
#
#
#  !Revision:   $Revision$: 
#  !Author:     Markus Pietrek
#  !Descr: 
#  !References: 
#  !Usage: from U-Boot, make ARCH=arm BOARD=unc90 TOPDIR=`pwd` -C board_tests clean
#

,PHONY: clean all

ifeq ($(BOARD),unc90)
LOAD_ADDR = 0x20100000
else ifeq ($(BOARD),cc9c)
LOAD_ADDR = 0x00200000
else
$(error "Please define a LOAD_ADDR for this board $(BOARD)" )
endif

EX_LDFLAGS += -Ttext $(LOAD_ADDR) -T arm.lds

include $(TOPDIR)/config.mk

MKIMAGE=../tools/mkimage

APPS      += perf.elf
BIN	  += perf.bin
OBJS_perf  = perf.o
OBJS      += $(OBJS_perf)

ifeq (0,1)
# don't compile it
APPS          += test_mem.elf
BIN	      += test_mem.bin
OBJS_test_mem  = test_mem.o
OBJS          += $(OBJS_test_mem)
endif

ifeq ($(BIG_ENDIAN),y)
EX_LDFLAGS += -EB
endif

LIB      = libstart.a

LIBAOBJS = start.o
LIBOBJS = $(LIBAOBJS)

USE_LIBS = $(LIB) ../examples/libstubs.a ../lib_generic/libgeneric.a ../lib_arm/div0.o

gcclibdir := $(shell dirname `$(CC) -print-libgcc-file-name`)
clibdir := $(shell dirname `$(CC) $(CFLAGS) -print-file-name=libc.a`)

CPPFLAGS += -I..
CFLAGS   += -mapcs-frame

# $(APPS) so they are not deleted afterwards

all:	.depend $(APPS) $(USE_LIBS) $(BIN)

$(LIB): $(LIBOBJS)
	$(AR) crsv $@ $(LIBOBJS)

#########################################################################
%.elf:	%.o $(LIB)
	$(LD) -g $(EX_LDFLAGS) \
		-o $@ $< $(USE_LIBS) \
		-L$(gcclibdir) -lgcc

%.bin:	%.elf
	$(OBJCOPY) -O binary $< $@ 2>/dev/null

%.uboot: %.bin
	$(MKIMAGE) -O u-boot -T standalone -C none \
		  -A $(ARCH) -a $(LOAD_ADDR) \
		  -n $< \
		  -e `printf 0x%x \`expr \\\`printf %i $(LOAD_ADDR)\\\` + 68\`` \
	          -d $< \
	     	  $@

#########################################################################

.depend:	Makefile $(OBJS:.o=.c) $(LIBCOBJS:.o=.c) $(LIBAOBJS:.o=.S)
		$(CC) -M $(CFLAGS) $(OBJS:.o=.c) $(LIBCOBJS:.o=.c) $(LIBAOBJS:.o=.S) > $@

sinclude .depend

#########################################################################

clean:
	rm -f $(OBJS) $(BIN)
