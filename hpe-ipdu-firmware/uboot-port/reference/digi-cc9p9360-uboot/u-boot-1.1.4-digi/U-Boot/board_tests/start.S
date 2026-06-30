/*
 *  board_tests/start.S
 *
 *  Copyright (C) 2006 by Digi International Inc.
 *  All rights reserved.
 *
 *  This program is free software; you can redistribute it and/or modify it
 *  under the terms of the GNU General Public License version2  as published by
 *  the Free Software Foundation.
*/
/*
 *  !Revision:   $Revision$: 
 *  !Author:     Markus Pietrek
 *  !Descr:      Calls main
*/

.globl main
.globl app_startup
.global hang
                
_start:
        /* U-boot calls us with exactly 4 parameters already on stack */

        /* app_startup( argv ) */
        mov     r5, r0
        mov     r0, r1
        mov     r6, r1
        bl      app_startup

        /* main( argc, argv ) */
        mov     r0, r5
        mov     r1, r6
        bl      main

return_to_uboot:                
        /* return to U-Boot */
        ldmia   sp!, {r4, r5, r6, pc}

        /* div0 needs it */
hang:
        b hang          
