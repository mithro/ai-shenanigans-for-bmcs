/*
 * Memory Setup stuff - taken from blob memsetup.S
 *
 * Copyright (C) 1999 2000 2001 Erik Mouw (J.A.K.Mouw@its.tudelft.nl) and
 *                     Jan-Derk Bakker (J.D.Bakker@its.tudelft.nl)
 *
 * Modified for the Samsung SMDK2410 by
 * (C) Copyright 2002
 * David Mueller, ELSOFT AG, <d.mueller@elsoft.ch>
 *
 * See file CREDITS for list of people who contributed to this
 * project.
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
 * @History:
 * 19-08-2005:	moved from memsetup to lowlevel_init	Joachim Jaeger
 *
 */


#include <config.h>
#include <version.h>


/* some parameters for the board */

/*
 *
 * Taken from linux/arch/arm/boot/compressed/head-s3c2410.S
 *
 * Copyright (C) 2002 Samsung Electronics SW.LEE  <hitchcar@sec.samsung.com>
 *
 */
#define GPBDAT			0x56000014

#define BWSCON			0x48000000

/* BWSCON */
#define DW8		 	(0x0)
#define DW16		 	(0x1)
#define DW32		 	(0x2)
#define WAIT		 	(0x1<<2)
#define UBLB		 	(0x1<<3)

#define B1_BWSCON	  	(DW32)
#define B2_BWSCON	  	(DW8)			/* could be external QUART */

#define B3_BWSCON	  	(DW16)			/* could be CAN Controller */
#define B4_BWSCON	  	(DW16 + WAIT + UBLB)	/* CF */
#define B5_BWSCON	  	(DW16 + WAIT + UBLB)	/* external Ethernet Controller */

#define B6_BWSCON	  	(DW32)
#define B7_BWSCON	  	(DW32)

/* BANK0CON */
#define B0_Tacs		 	0x0	/*  0clk */
#define B0_Tcos		 	0x0	/*  0clk */
#define B0_Tacc		 	0x7	/* 14clk */
#define B0_Tcoh		 	0x0	/*  0clk */
#define B0_Tah		 	0x0	/*  0clk */
#define B0_Tacp		 	0x0
#define B0_PMC		 	0x0	/* normal */

/* BANK1CON */
#define B1_Tacs		 	0x0	/*  0clk */
#define B1_Tcos		 	0x0	/*  0clk */
#define B1_Tacc		 	0x7	/* 14clk */
#define B1_Tcoh		 	0x0	/*  0clk */
#define B1_Tah		 	0x0	/*  0clk */
#define B1_Tacp		 	0x0
#define B1_PMC		 	0x0

#define B2_Tacs		 	0x0	/*  0clk */
#define B2_Tcos		 	0x3	/*  4clk */
#define B2_Tacc		 	0x7	/* 14clk */
#define B2_Tcoh		 	0x1	/*  1clk */
#define B2_Tah		 	0x0	/*  0clk */
#define B2_Tacp		 	0x3     /*  6clk */
#define B2_PMC		 	0x0	/* normal */

#define B3_Tacs		 	0x0	/*  0clk */
#define B3_Tcos		 	0x0	/*  0clk */
#define B3_Tacc		 	0x7	/* 14clk */
#define B3_Tcoh		 	0x0	/*  0clk */
#define B3_Tah		 	0x0	/*  0clk */
#define B3_Tacp		 	0x0
#define B3_PMC		 	0x0	/* normal */

#define B4_Tacs		 	0x0	/*  0clk */
#define B4_Tcos		 	0x3	/*  4clk */
#define B4_Tacc		 	0x7	/* 14clk */
#define B4_Tcoh		 	0x1	/*  1clk */
#define B4_Tah		 	0x0	/*  0clk */
#define B4_Tacp		 	0x3     /*  6clk */
#define B4_PMC		 	0x0	/* normal */

#define B5_Tacs		 	0x0	/*  0clk */
#define B5_Tcos		 	0x3	/*  4clk */
#define B5_Tacc		 	0x7	/* 14clk */
#define B5_Tcoh		 	0x1	/*  1clk */
#define B5_Tah		 	0x0	/*  0clk */
#define B5_Tacp		 	0x3     /*  6clk */
#define B5_PMC		 	0x0	/* normal */



#ifdef SDRAM_16MB		/* 16MB device mounted */
#  define B6_MT		 	0x3	/* SDRAM */
#  define B6_Trcd	 	0x1	/* 3clk */
#  define B6_SCAN		0x0	/* 8bit */
#  define MRSR6			0x20	/* CL2 */

#  define B7_MT		 	0x3	/* SDRAM */
#  define B7_Trcd		0x1	/* 3clk */
#  define B7_SCAN		0x0	/* 8bit */
#  define MRSR7			0x20	/* CL2 */

/* REFRESH parameter */
#  define REFEN		 	0x1	/* Refresh enable */
#  define TREFMD		0x0	/* CBR(CAS before RAS)/Auto refresh */
#  define Trp		 	0x0	/* 2clk */
#  define Trc		 	0x3	/* 7clk */
#  define Tchr		 	0x0	/* not used */
#  define REFCNT		468 	/* period=15.6us, HCLK=101.4Mhz, (2048+1-15.6*101.4) */
#  define BANKSIZE		0x32	/* Burst disable, power down mode enable, SCLK active during access, BANKSIZE 128M/128M */

#elif defined SDRAM_32MB		/* 32MB device mounted */
#  define B6_MT		 	0x3	/* SDRAM */
#  define B6_Trcd	 	0x1	/* 3clk */
#  define B6_SCAN		0x1	/* 9bit */
#  define MRSR6			0x20	/* CL2 */

#  define B7_MT		 	0x3	/* SDRAM */
#  define B7_Trcd		0x1	/* 3clk */
#  define B7_SCAN		0x1	/* 9bit */
#  define MRSR7			0x20	/* CL2 */

/* REFRESH parameter */
#  define REFEN		 	0x1	/* Refresh enable */
#  define TREFMD		0x0	/* CBR(CAS before RAS)/Auto refresh */
#  define Trp		 	0x0	/* 2clk */
#  define Trc		 	0x3	/* 7clk */
#  define Tchr		 	0x0	/* not used */
#  define REFCNT		468 	/* period=15.6us, HCLK=101.4Mhz, (2048+1-15.6*101.4) */
#  define BANKSIZE		0x30	/* Burst disable, power down mode enable, SCLK active during access, BANKSIZE 32M/32M */

#elif defined SDRAM_64MB		/* 64MB device mounted */
#  define B6_MT		 	0x3	/* SDRAM */
#  define B6_Trcd	 	0x1	/* 3clk */
#  define B6_SCAN		0x1	/* 9bit */
#  define MRSR6			0x30	/* CL3 */

#  define B7_MT		 	0x3	/* SDRAM */
#  define B7_Trcd		0x1	/* 3clk */
#  define B7_SCAN		0x1	/* 9bit */
#  define MRSR7			0x30	/* CL3 */

/* REFRESH parameter */
#  define REFEN		 	0x1	/* Refresh enable */
#  define TREFMD		0x0	/* CBR(CAS before RAS)/Auto refresh */
#  define Trp		 	0x1	/* 3clk */
#  define Trc		 	0x3	/* 7clk */
#  define Tchr		 	0x0	/* not used */
#  define REFCNT		1259 	/* period=7.8us, HCLK=101.4Mhz, (2048+1-7.8*101.4) */
#  if defined SDRAM_64MB_X2
#   define BANKSIZE		0x32	/* Burst disable, power down mode enable, SCLK active during access, BANKSIZE 128M/128M */
#  else
#   define BANKSIZE		0x31	/* Burst disable, power down mode enable, SCLK active during access, BANKSIZE 64M/64M */
#  endif
#endif /* SDRAM_xxMB */
/**************************************/

_TEXT_BASE:
	.word	TEXT_BASE

.globl lowlevel_init
lowlevel_init:
	/* memory control configuration */
	/* make r0 relative the current location so that it */
	/* reads SMRDATA out of FLASH rather than memory ! */
#ifndef A9M2410_0
	/* Now we initialize the SDRAMs according to the config resistors */
	/* r0 == SDRAMDATA */
	/* r1 == SDRAM controller regs */
	ldr	r2, =GPBDAT
	ldr	r4,[r2]
	and	r4, r4, #0x00000007
#endif
	
	adr     r0, CSDATA
	ldr	r1, =BWSCON	/* Bus Width Status Controller */
#ifndef A9M2410_0
	mov     r2, #7		/* for A9M2410_1 only the 1st part of the table */
#else
	mov     r2, #13
#endif	
0:
	ldr     r3, [r0], #4
	str     r3, [r1], #4
	subs    r2, r2, #1
	bne     0b

#ifndef A9M2410_0
	adr     r0, SDRAMDATA
	mov     r2, #6*4	/* # of entries */
	mul     r3, r4, r2	/* calculate offset in table in words */
	add     r0, r0, r3
	/* calculate start and end point */
1:
	ldr     r3, [r0], #4
	str     r3, [r1], #4
	subs    r2, r2, #4
	bne     1b
#endif

	/* everything is fine now */
	mov	pc, lr

	.ltorg
/* the literal pools origin */

CSDATA:
    .word (0+(B1_BWSCON<<4)+(B2_BWSCON<<8)+(B3_BWSCON<<12)+(B4_BWSCON<<16)+(B5_BWSCON<<20)+(B6_BWSCON<<24)+(B7_BWSCON<<28))
    .word ((B0_Tacs<<13)+(B0_Tcos<<11)+(B0_Tacc<<8)+(B0_Tcoh<<6)+(B0_Tah<<4)+(B0_Tacp<<2)+(B0_PMC))
    .word ((B1_Tacs<<13)+(B1_Tcos<<11)+(B1_Tacc<<8)+(B1_Tcoh<<6)+(B1_Tah<<4)+(B1_Tacp<<2)+(B1_PMC))
    .word ((B2_Tacs<<13)+(B2_Tcos<<11)+(B2_Tacc<<8)+(B2_Tcoh<<6)+(B2_Tah<<4)+(B2_Tacp<<2)+(B2_PMC))
    .word ((B3_Tacs<<13)+(B3_Tcos<<11)+(B3_Tacc<<8)+(B3_Tcoh<<6)+(B3_Tah<<4)+(B3_Tacp<<2)+(B3_PMC))
    .word ((B4_Tacs<<13)+(B4_Tcos<<11)+(B4_Tacc<<8)+(B4_Tcoh<<6)+(B4_Tah<<4)+(B4_Tacp<<2)+(B4_PMC))
    .word ((B5_Tacs<<13)+(B5_Tcos<<11)+(B5_Tacc<<8)+(B5_Tcoh<<6)+(B5_Tah<<4)+(B5_Tacp<<2)+(B5_PMC))

    .word ((B6_MT<<15)+(B6_Trcd<<2)+(B6_SCAN))
    .word ((B7_MT<<15)+(B7_Trcd<<2)+(B7_SCAN))
    .word ((REFEN<<23)+(TREFMD<<22)+(Trp<<20)+(Trc<<18)+REFCNT)
    .word (BANKSIZE)
    .word (MRSR6)
    .word (MRSR7)
    
SDRAMDATA:
SDRAM_16MB_CL2:		/* 16MB device (15.6us) MCONF0[00] MCONF2[0] */
    .word ((0x3<<15)+(0x1<<2)+(0x0))
    .word ((0x3<<15)+(0x1<<2)+(0x0))
    .word ((0x1<<23)+(0x0<<22)+(0x0<<20)+(0x3<<18)+468)
    .word (0x32)
    .word (0x20)
    .word (0x20)
SDRAM_64MB_CL2:		/* 64MB device (7.8us) MCONF0[01] MCONF2[0] */
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x1<<23)+(0x0<<22)+(0x1<<20)+(0x3<<18)+1259)
    .word (0x31)
    .word (0x20)
    .word (0x20)
SDRAM_32MB_CL2:		/* 32MB device (15.6us) MCONF0[10] MCONF2[0] */
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x1<<23)+(0x0<<22)+(0x0<<20)+(0x3<<18)+468)
    .word (0x30)
    .word (0x20)
    .word (0x20)
SDRAM_128MB_CL2:	/* 128MB device (7.8us) does not exist at the moment MCONF0[11] MCONF2[0] */
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x1<<23)+(0x0<<22)+(0x1<<20)+(0x3<<18)+1259)
    .word (0x32)
    .word (0x20)
    .word (0x20)
SDRAM_16MB_CL3:		/* 16MB device (15.6us) MCONF0[00] MCONF2[1] */
    .word ((0x3<<15)+(0x1<<2)+(0x0))
    .word ((0x3<<15)+(0x1<<2)+(0x0))
    .word ((0x1<<23)+(0x0<<22)+(0x0<<20)+(0x3<<18)+468)
    .word (0x32)
    .word (0x30)
    .word (0x30)
SDRAM_64MB_CL3:		/* 64MB device (7.8us) MCONF0[01] MCONF2[1] */
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x1<<23)+(0x0<<22)+(0x1<<20)+(0x3<<18)+1259)
    .word (0x31)
    .word (0x30)
    .word (0x30)
SDRAM_32MB_CL3:		/* 32MB device (15.6us) MCONF0[10] MCONF2[1] */
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x1<<23)+(0x0<<22)+(0x0<<20)+(0x3<<18)+468)
    .word (0x30)
    .word (0x30)
    .word (0x30)
SDRAM_128MB_CL3:	/* 128MB device (7.8us) does not exist at the moment MCONF0[11] MCONF2[1] */
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x3<<15)+(0x1<<2)+(0x1))
    .word ((0x1<<23)+(0x0<<22)+(0x1<<20)+(0x3<<18)+1259)
    .word (0x32)
    .word (0x30)
    .word (0x30)


