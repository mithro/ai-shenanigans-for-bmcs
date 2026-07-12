# SPDX-License-Identifier: Apache-2.0
# Build the AST2050 ARM test stub (ARM926EJ-S, little-endian, linked at 0x0).
# The P2A word list is produced on demand by arm-stub-boot-p2a.py (reads the .bin).
CROSS  ?= arm-linux-gnueabi-
AS      = $(CROSS)as
LD      = $(CROSS)ld
OBJCOPY = $(CROSS)objcopy
OBJDUMP = $(CROSS)objdump

ASFLAGS = -march=armv5te -EL
LDFLAGS = -EL -Ttext=0x0 -e _vectors --no-warn-rwx-segments

all: uart-hello.bin uart-hello.lst

uart-hello.o: uart-hello.S
	$(AS) $(ASFLAGS) -o $@ $<

uart-hello.elf: uart-hello.o
	$(LD) $(LDFLAGS) -o $@ $<

uart-hello.bin: uart-hello.elf
	$(OBJCOPY) -O binary $< $@

uart-hello.lst: uart-hello.elf
	$(OBJDUMP) -d $< > $@

clean:
	rm -f uart-hello.o uart-hello.elf uart-hello.bin uart-hello.lst

.PHONY: all clean
