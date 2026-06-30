# Copyright (C) 2004 by FS Forth-Systeme GmbH.
# Joachim Jaeger <jjaeger@fsforth.de>
#
# @TODO
# Linux-Kernel is expected to be at 3010'0000, entry 3010'8000
# optionally with a ramdisk at 3060'0000
#
# we load ourself to 303c'0000 for A9M2410_0
# we load ourself to 3058'0000 for A9M2410_1 and A9M2440
# we load ourself to 3008'0000 for A9M2410_1 and A9M2440 @ LxNETES3.2
# we load ourself to 3010'0000 for A9M2410_1 and A9M2440 @ LxNETES4.0
#


TEXT_BASE = 0x30100000
