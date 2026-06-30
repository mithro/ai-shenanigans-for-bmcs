/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: 
 * @Author: Bernd Westermann
 * @Descr: CCXP270 Board lowlevel init
 * @References: Lubbock
 * @TODO:
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston,
 * MA 02111-1307 USA
 *
 ***********************************************************************/
/***********************************************************************
 *  @History:
 *	2005/09/08 : RC_1 (Bernd Westermann)
 *	2005/09/24 : USB, FAT, cleanup (Bernd Westermann)
 ***********************************************************************/

#include <config.h>
#include <version.h>
#include <asm/arch/pxa-regs.h>

/*--------------------------------------------------------------*/
/*								*/
/* BLINK106 : Blinking GPIO106 macro debugging 			*/
/*		the current bootloader				*/
/*								*/
/*								*/
/*--------------------------------------------------------------*/
.macro BLINK106
			
	ldr		r0,=0x40E0010C
	ldr		r1, [r0]
	orr		r1,r1,#0x00000400
	str		r1,   [r0]		// Set GPIO as output		
	ldr		r0,=0x40E00100
	ldr		r1, [r0]
	orr		r1,r1,#0x00000400
	str		r1,   [r0]		// Set default value on high

   	
1415:  	ldr		r0,=0x40E00118		// GPSR3 REGISTER
   	str		r1,	[r0]		// Switch the LED off


   	ldr		r2,=0x002		// Wait some time
   	mov		r3,#1
999:
   	sub		r2, r2, r3
   	cmp		r2,#0
   	bne		999b



220961:
   	ldr		r1,=0x00000400		// We use GPIO106 for controlling the debug LED
   	ldr		r0,=0x40E00124		// GPCR3 REGISTER
   	str		r1,	[r0]		// Switch the LED on


   	ldr		r2,=0x002		// Wait some time
   	mov		r3,#1
998:
   	sub		r2, r2, r3
   	cmp		r2,#0
   	bne		998b
.endm


/*--------------------------------------------------------------*/
/*								*/
/* MEMSETUP : Memory setup subroutine				*/
/*								*/
/*								*/
/*--------------------------------------------------------------*/

.globl lowlevel_init
lowlevel_init:


/* ---------------------------------------------------------------- */
/* if we come out of sleep mode, check if there is a pointer	    */
/* from the os, and jump to it if so				    */
/* ---------------------------------------------------------------- */

//	ldr r0, =RCSR			/* check reset source */
//	ldr	r1, [r0]
//	and r1, r1, #4			/* check if RCSR[SMR] is valid : */
					/* Sleep-Exit Reset from Sleep or Deep-Sleep Mode */
//	cmp r1, #4
//	bne 1923f

//	ldr r2, =PSPR			/* check if there is a pointer from the operating system */
//	ldr r1, [r2]
//	cmp r1, #0
//	beq 1923f

//	ldr r3, =0x0000000f		/* reset RCSR, clear all reset sources */
//	str r3, [r0]



/* ---------------------------------------------------------------- */
/* Clear DRI value from MDREFR register				    */
/* ---------------------------------------------------------------- */

	ldr	r1,  =MDREFR
	ldr	r2,  [r1]		/* Read MDREFR value */
	ldr	r3,  =0xFFF
	bic 	r2, r2, r3		/* Clear out value in DRI */
	orr	r2, r2, #0x00000019	/* Put in a valid SDRAM Refresh Interval (DRI) */
	str	r2, [r1]


/* ---------------------------------------------------------------- */
/* Initialize Timing for Sync Memory (SDCLK0)              	    */
/* ---------------------------------------------------------------- */

	ldr r3, =MDCNFG         	/* sdram config -- sdram should remain disabled !!!!! */
	ldr r2, =0x8B000AC8		/* 13 rows / 9 col / 2 bank / 32 bit / CL3 / */
/* SDRAM disabled */
	str r2, [r3]
	
	ldr     r1,     =MEMC_BASE		/* get memory controller base addr. */
	ldr	r4,	[r1, #MDREFR_OFFSET]

	bic     r4,  r4, #MDREFR_K0FREE
	bic     r4,  r4, #MDREFR_K1FREE
	bic     r4,  r4, #MDREFR_K2FREE
	//bic     r4,  r4, #MDREFR_K1DB2
	//bic     r4,  r4, #MDREFR_K0DB4
	orr     r4,  r4, #MDREFR_K1DB2
	orr     r4,  r4, #MDREFR_K1RUN

	/* Change from "self-refresh and clock stop" to "self-refresh" */
	str	r4,	[r1, #MDREFR_OFFSET]
	
	/* Read MDREFR value (to make sure the previous value stuck) */
	ldr     r4,  	[r1, #MDREFR_OFFSET]


/* ---------------------------------------------------------------- */
/* Initialize SDRAM       	                                    */
/* ---------------------------------------------------------------- */

	/* Clear the self-refresh bit */
        bic     r4, r4, #MDREFR_SLFRSH
        
        /* Change from "self-refresh" to "power down" */
        str     r4, [r1, #MDREFR_OFFSET]	
        ldr     r4, [r1, #MDREFR_OFFSET]

	/* Assert MDREFR:E1PIN */
        orr     r4, r4, #MDREFR_E1PIN
        
        /* Change from "power down" to "PWRDWNX" */
        str     r4, [r1, #MDREFR_OFFSET]
        ldr     r4, [r1, #MDREFR_OFFSET]

        nop
        nop	/* No write required to change from "PWRDWNX" to "NOP" 	
        

/* ---------------------------------------------------------------- */
/* Write MDCNFG with enable bits asserted			    */
/*		(MDCNFG:DEx set to 1).				    */	
/* ---------------------------------------------------------------- */

	ldr     r3,	[r1, #MDCNFG_OFFSET]
	orr	r3,	r3,  #MDCNFG_DE0
	str     r3,	[r1, #MDCNFG_OFFSET]
	mov	r0, 	r3


/*--------------------------------------------------------------*/
/*								*/
/* GPIO_CONF : Configure GPIOs					*/
/*								*/
/*								*/
/*--------------------------------------------------------------*/


1923 :
	ldr		r0,	=GPCR0
	ldr		r1,	=CFG_GPCR0_VAL
	str		r1,   [r0]

	ldr		r0,	=GPCR1
	ldr		r1,	=CFG_GPCR1_VAL
	str		r1,   [r0]

	ldr		r0,	=GPCR2
	ldr		r1,	=CFG_GPCR2_VAL
	str		r1,   [r0]

	ldr		r0,	=GPCR3
	ldr		r1,	=CFG_GPCR3_VAL
	str		r1,   [r0]

	ldr		r0,	=GPSR0
	ldr		r1,	=CFG_GPSR0_VAL
	str		r1,   [r0]

	ldr		r0,	=GPSR1
	ldr		r1,	=CFG_GPSR1_VAL
	str		r1,   [r0]

	ldr		r0,	=GPSR2
	ldr		r1,	=CFG_GPSR2_VAL
	str		r1,   [r0]

	ldr		r0,	=GPSR3
	ldr		r1,	=CFG_GPSR3_VAL
	str		r1,   [r0]

	ldr		r0,	=GPDR0
	ldr		r1,	=CFG_GPDR0_VAL
	str		r1,   [r0]

	ldr		r0,	=GPDR1
	ldr		r1,	=CFG_GPDR1_VAL
	str		r1,   [r0]

	ldr		r0,	=GPDR2
	ldr		r1,	=CFG_GPDR2_VAL
	str		r1,   [r0]

	ldr		r0,	=GPDR3
	ldr		r1,	=CFG_GPDR3_VAL
	str		r1,   [r0]

	ldr		r0,	=GAFR0_L
	ldr		r1,	=CFG_GAFR0_L_VAL
	str		r1,   [r0]

	ldr		r0,	=GAFR0_U
	ldr		r1,	=CFG_GAFR0_U_VAL
	str		r1,   [r0]

	ldr		r0,	=GAFR1_L
	ldr		r1,	=CFG_GAFR1_L_VAL
	str		r1,   [r0]

	ldr		r0,	=GAFR1_U
	ldr		r1,	=CFG_GAFR1_U_VAL
	str		r1,   [r0]

	ldr		r0,	=GAFR2_L
	ldr		r1,	=CFG_GAFR2_L_VAL
	str		r1,   [r0]

	ldr		r0,	=GAFR2_U
	ldr		r1,	=CFG_GAFR2_U_VAL
	str		r1,   [r0]

	ldr		r0,	=GAFR3_L
	ldr		r1,	=CFG_GAFR3_L_VAL
	str		r1,   [r0]

	ldr		r0,	=GAFR3_U
	ldr		r1,	=CFG_GAFR3_U_VAL
	str		r1,   [r0]
	
	ldr		r0,	=GRER0
	ldr		r1,	=CFG_GRER0_VAL
	str		r1,   [r0]
	
	ldr		r0,	=GRER1
	ldr		r1,	=CFG_GRER1_VAL
	str		r1,   [r0]
	
	ldr		r0,	=GRER2
	ldr		r1,	=CFG_GRER2_VAL
	str		r1,   [r0]
	
	ldr		r0,	=GRER3
	ldr		r1,	=CFG_GRER3_VAL
	str		r1,   [r0]

/* ---------------------------------------------------------------- */
/* The RDH and PH bits on PXA27x must be set to enable updated	    */
/* GPIO pins. These are sticky bits.				    */
/* ---------------------------------------------------------------- */

        ldr		r0,	=PSSR		// Load Power Manager Sleep Status register
	ldr		r1,	=CFG_PSSR_VAL	// Set the PH and RDH bits to enable all GPIOs
	str		r1,   [r0]		// Enable all GPIO lines

/* ---------------------------------------------------------------- */
/* Read back from APB to ensure our writes have			    */
/* completed before continuing					    */
/* ---------------------------------------------------------------- */

	ldr     	r2, [r0]
	
/* ---------------------------------------------------------------- */
/* PCFR : Power Manager General Configuration Register		    */
/* ---------------------------------------------------------------- */

	ldr r3,	=PCFR		/* clear PCFR[FS] and PCFR[FP] */
	ldr r2, [r3]
	bic r2, r2, #0x00000006
	str r2, [r3]


/* ---------------------------------------------------------------- */
/* The MRC instruction move a value from the coprocessor p15	    */
/* to the XScale processor register r0				    */
/* ---------------------------------------------------------------- */

  	MRC p15, 0, r0, c0, c0, 0	/* read the ID reg ....  0x69052100 */
					/* and display it if possible */

	mov    r0, #0x78		/* turn everything off */
	
	/* The MCR instruction move the value contained */
	/* in r0 source to the coprocessor p15. */

	MCR p15, 0, r0, c1, c0, 0    	/* caches off -- MMU off or ID map */
	MCR p15, 0, r0, c7, c7, 0	/* Invalidate the I & D cache, mini- d cache, and BTB */
	MCR p15, 0, r0, c7, c10, 4	/* Drain write buffer -- r0 ignored */

	MRC p15, 0, r0, c2, c0, 0 	/* arbitrary read of CP15 */
	mov r0, r0 			/* wait for it */
	sub PC, PC, #4 			/* branch to next instruction */

    	nop
    	nop
    	nop
    	nop


	/* setup manager access, interrupts, etc. */
	/* grant manager access to all domains */

	/* The MVN instruction moves the 1's complement value contained in #0 to r0. */
    	mvn    r0, #0    				// all 1s
   	MCR    p15, 0, r0, c3, c0, 0


/* ---------------------------------------------------------------- */
/* All IRQs should be masked to prevent spurious IRQs		    */
/* ---------------------------------------------------------------- */

	ldr     r3,  =ICMR	/* Pending interrupts are masked */
	mov	r2,  #0
	str     r2,  [r3]
	ldr     r3,  =ICMR2
	str     r2,  [r3]

	ldr     r3,  =ICLR	/* Route all interrupts to CPU IRQ */
	mov 	r2,  #0
	str     r2,  [r3]
	ldr     r3,  =ICLR2
	str     r2,  [r3]

	ldr	r3,  =ICCR	/* Only enabled and unmasked interrupts bring core out of idle */
	mov	r2,  #1
	str	r2,  [r3]


/* ---------------------------------------------------------------- */
/* Turn on the RTC circuit (if you want)		            */
/* ---------------------------------------------------------------- */

#ifdef RTC
	/* enable the 32Khz oscillator for RTC and PowerManager */
	ldr     r1,  =OSCC
	mov     r2,  #OSCC_OON
	str     r2,  [r1]

#else
#error "RTC not defined"
#endif


/* ---------------------------------------------------------------- */
/* Enable memory interface                                          */
/*                                                                  */
/* The sequence below is based on the recommended init steps        */
/* detailed in the Intel PXA250 Operating Systems Developers Guide, */
/* Chapter 10.                                                      */
/* ---------------------------------------------------------------- */

/* ---------------------------------------------------------------- */
/* Step 1: Wait for at least 200 microsedonds to allow internal     */
/*         clocks to settle. Only necessary after hard reset...     */
/*         FIXME: can be optimized later                            */
/* ---------------------------------------------------------------- */

	ldr r3, =OSCR			/* reset the OS Timer Count to zero */
	mov r2, #0
	str r2, [r3]
	ldr r4, =0x300			/* really 0x2E1 is about 200usec,   */
					/* so 0x300 should be plenty        */
10:
	ldr r2, [r3]
	cmp r4, r2
	bgt 10b

/* ---------------------------------------------------------------- */
/* Step 2: Initialize Asynchronous static memory controller        */
/* ---------------------------------------------------------------- */

mem_init:

	ldr     r1,  =MEMC_BASE		/* get memory controller base addr. */

	/* MSC registers: timing, bus width, mem type                       */

	/* MSC0: nCS(0,1)                                                   */
	ldr     r2,   =CFG_MSC0_VAL
	str     r2,   [r1, #MSC0_OFFSET]
	ldr     r2,   [r1, #MSC0_OFFSET]	/* read back to ensure      */
						/* that data latches        */

	/* MSC1: nCS(2,3)                                                   */
	ldr     r2,  =CFG_MSC1_VAL
	str     r2,  [r1, #MSC1_OFFSET]
	ldr     r2,  [r1, #MSC1_OFFSET]

	/* MSC2: nCS(4,5)                                                   */
	ldr     r2,  =CFG_MSC2_VAL
	str     r2,  [r1, #MSC2_OFFSET]
	ldr     r2,  [r1, #MSC2_OFFSET]
	
	
/* ---------------------------------------------------------------- */
/* Step 3: Disable (mask) all interrupts at interrupt controller   */
/* ---------------------------------------------------------------- */

	mov     r1,  #0		/* clear int. level register (IRQ, not FIQ) */
	ldr     r2,  =ICLR
	str     r1,  [r2]
	ldr     r2,  =ICLR2
	str     r1,  [r2]

	ldr     r2,  =ICMR	/* mask all interrupts at the controller    */
	str     r1,  [r2]
	ldr     r2,  =ICMR2
	str     r1,  [r2]

/* ---------------------------------------------------------------- */
/* Step 3a: clear all  edge detect status bits  */
/* ---------------------------------------------------------------- */

	mov     r1,  #0xFFFFFFFF
	ldr     r2,  =GEDR0
	str     r1,  [r2]
	ldr     r2,  =GEDR1
	str     r1,  [r2]
	ldr     r2,  =GEDR2
	str     r1,  [r2]
	ldr     r2,  =GEDR3
	str     r1,  [r2]


/* ---------------------------------------------------------------- */
/* Step 4: Make sure the DCACHE is off   			    */
/* ---------------------------------------------------------------- */

	mov 	r1, #0x78		// Turn everything off
	mcr	p15, 0, r1, c1, c0, 0	// Cache off, MMU off

	
/* ---------------------------------------------------------------- */
/* Step 5: Clear DRI value from MDREFR register		    */
/* ---------------------------------------------------------------- */
/*								    */
/* Before accessing MDREFR we need a valid DRI field, so we set     */
/* this to power on defaults + DRI field.                           */
/* ---------------------------------------------------------------- */

	ldr	r1,  =MDREFR
	ldr	r2,  [r1]		// Read MDREFR value
	ldr	r3,  =0xFFF
	bic 	r2, r2, r3		// Clear out value in DRI
	orr	r2, r2, #0x00000019	// Put in a valid SDRAM Refresh Interval (DRI)
	str	r2, [r1]

	
/* ---------------------------------------------------------------- */
/* Step 6: Configure Synchronous Flash later			    */
/* ---------------------------------------------------------------- */

	ldr	r1,  =SXCNFG
	mov	r2,  #0x0
	str	r2,  [r1]
	
BLINK106


/* ---------------------------------------------------------------- */
/* Step 7: Initialize Timing for Sync Memory (SDCLK0)              */
/* ---------------------------------------------------------------- */

	ldr	r1,     =MDCNFG
	ldr	r4,	[r1, #MDREFR_OFFSET]

	bic     r4,  r4, #MDREFR_K0FREE
	bic     r4,  r4, #MDREFR_K1FREE
	bic     r4,  r4, #MDREFR_K2FREE
	//bic     r4,  r4, #MDREFR_K1DB2
	bic     r4,  r4, #MDREFR_K0DB4
	orr     r4,  r4, #MDREFR_K1DB2
	orr     r4,  r4, #MDREFR_K1RUN


	/* Change from "self-refresh and clock stop" to "self-refresh" */
	str	r4,	[r1, #MDREFR_OFFSET]
	
	/* Read MDREFR value (to make sure the previous value stuck) */
	ldr     r4,  	[r1, #MDREFR_OFFSET]

	/* Note: preserve the mdrefr value in r4 */

/* ---------------------------------------------------------------- */
/* Step 8: Initialize SDRAM                                         */
/* ---------------------------------------------------------------- */

	/* Clear the self-refresh bit */
        bic     r4, r4, #MDREFR_SLFRSH
        
        /* Change from "self-refresh" to "power down" */
        str     r4, [r1, #MDREFR_OFFSET]	
        ldr     r4, [r1, #MDREFR_OFFSET]

	/* Assert MDREFR:E1PIN */
        orr     r4, r4, #MDREFR_E1PIN
        
        /* Change from "power down" to "PWRDWNX" */
        str     r4, [r1, #MDREFR_OFFSET]
        ldr     r4, [r1, #MDREFR_OFFSET]

        nop
        nop	/* No write required to change from "PWRDWNX" to "NOP" 	
        

/* ---------------------------------------------------------------- */
/* Step 9: write MDCNFG with MDCNFG:DEx deasserted (set to 0), to  */
/*		configure but not enable each SDRAM partition pair. */	
/* ---------------------------------------------------------------- */

	ldr	r4,	=CFG_MDCNFG_VAL
	bic	r4,	r4,	#(MDCNFG_DE0|MDCNFG_DE1)
	bic	r4,	r4,	#(MDCNFG_DE2|MDCNFG_DE3)

	str     r4,     [r1, #MDCNFG_OFFSET]	/* write back MDCNFG */
	ldr     r4,     [r1, #MDCNFG_OFFSET]


/* ---------------------------------------------------------------- */
/* Step 10: Wait for the clock to the SDRAMs to stabilize,	    */
/*		100..200 µsec.					    */	
/* ---------------------------------------------------------------- */

	ldr r3, =OSCR			/* reset the OS Timer Count to zero */
	mov r2, #0
	str r2, [r3]
	ldr r4, =0x300			/* really 0x2E1 is about 200usec, */
					/* so 0x300 should be plenty */
100:
	ldr r2, [r3]
	cmp r4, r2
	bgt 100b



/* ---------------------------------------------------------------- */
/* Step 11: Trigger a number (usually 8) refresh cycles by	    */
/*	attempting non-burst read or write accesses to disabled	    */
/*	SDRAM, as commonly specified in the power up sequence	    */
/*	documented in SDRAM data sheets. The address(es) used	    */
/*	for this purpose must not be cacheable.			    */
/* ---------------------------------------------------------------- */

	ldr	r3,	=CFG_DRAM_BASE
	str	r2,	[r3]
	str	r2,	[r3]
	str	r2,	[r3]
	str	r2,	[r3]
	str	r2,	[r3]
	str	r2,	[r3]
	str	r2,	[r3]
	str	r2,	[r3]

/* ---------------------------------------------------------------- */
/* Step 12: Write MDCNFG with enable bits asserted		    */
/*		(MDCNFG:DEx set to 1).				    */	
/* ---------------------------------------------------------------- */

	ldr     r3,	[r1, #MDCNFG_OFFSET]
	orr	r3,	r3,  #MDCNFG_DE0
	str     r3,	[r1, #MDCNFG_OFFSET]
	mov	r0, 	r3

/* ---------------------------------------------------------------- */
/* Step 13: Write MDMRS						    */
/* ---------------------------------------------------------------- */	

	ldr     r2,  =CFG_MDMRS_VAL
	str     r2,  [r1, #MDMRS_OFFSET]

/* ---------------------------------------------------------------- */
/* Step 14: Wait for 600 µsec					    */	
/* ---------------------------------------------------------------- */

	ldr r3, =OSCR         		/* reset the OS Timer Count to zero */
	mov r2, #0
	str r2, [r3]
	ldr r4, =0x900			/* really 0x8A3 is about 600usec, */
					/* so 0x900 should be plenty */
101:
	ldr r2, [r3]
	cmp r4, r2
	bgt 101b
	
/* ---------------------------------------------------------------- */
/* We are finished with Intel's memory controller initialisation    */
/* Configure now PC Card Interface
/* ---------------------------------------------------------------- */
 
	ldr		r0,	=MCMEM0
	ldr		r1,	=CFG_MCMEM0_VAL
	str		r1,   [r0]
	
	ldr		r0,	=MCMEM1
	ldr		r1,	=CFG_MCMEM1_VAL
	str		r1,   [r0]
	
	ldr		r0,	=MCATT0
	ldr		r1,	=CFG_MCATT0_VAL
	str		r1,   [r0]	
	
	ldr		r0,	=MCATT1
	ldr		r1,	=CFG_MCATT1_VAL
	str		r1,   [r0]

	ldr		r0,	=MCIO0
	ldr		r1,	=CFG_MCIO0_VAL
	str		r1,   [r0]	

	ldr		r0,	=MCIO1
	ldr		r1,	=CFG_MCIO1_VAL
	str		r1,   [r0]	
	
	ldr		r0,	=MECR
	ldr		r1,	=CFG_MECR_VAL
	str		r1,   [r0]


/* ---------------------------------------------------------------- */
/* Clock initialisation                                             */
/* ---------------------------------------------------------------- */

initclks:

	/* Write the core clock config register */

	ldr     r2,  =CFG_CCCR		/*0x02000110 */
	ldr     r1,  =CCCR
	str     r2,  [r1]		/* Set speed */

	/* Turn on turbo mode */
	mov	r2,  #0xB		/* Set Turbo Mode and Frequency change */
	mov 	r3,  r2			/* Save value */
	mcr     p14, 0, r2, c6, c0, 0	/* Frequency change sequence */
	ldr	r2,  [r1]		/* Dummy Read from CCCR Register */
	
   102:
    	mrc     p14, 0, r2, c6, c0, 0
    	cmp 	r3, r2
    	bne	102b
    	
	/* ---------------------------------------------------------------- */
	/* End memsetup                                                     */
	/* ---------------------------------------------------------------- */

endmemsetup:

        mov     pc, lr
