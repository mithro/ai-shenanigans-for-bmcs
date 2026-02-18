#######################################################################
#
# Copyright (C) 2004 by FS Forth-Systeme GmbH.
# Markus Pietrek <mpietrek@fsforth.de>
#
# @TODO
# Linux-Kernel is expected to be at 0000'8000, entry 0000'8000
# optionally with a ramdisk at 0080'0000
#
# we load ourself to 0010'0000


TEXT_BASE = 0x00100000

PLATFORM_RELFLAGS_BIG += -mbig-endian

PLATFORM_CPPFLAGS_BIG += -mbig-endian

