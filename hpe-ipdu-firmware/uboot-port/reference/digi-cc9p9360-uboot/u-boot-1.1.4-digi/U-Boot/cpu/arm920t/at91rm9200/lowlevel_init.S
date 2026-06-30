/*
 * Memory Setup stuff - taken from blob memsetup.S
 *
 * Copyright (C) 1999 2000 2001 Erik Mouw (J.A.K.Mouw@its.tudelft.nl) and
 *		       Jan-Derk Bakker (J.D.Bakker@its.tudelft.nl)
 *
 * Modified for the at91rm9200dk board by
 * (C) Copyright 2004
 * Gary Jennejohn, DENX Software Engineering, <garyj@denx.de>
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
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston,
 * MA 02111-1307 USA
 */

#include <config.h>
#include <version.h>

#ifndef CONFIG_SKIP_LOWLEVEL_INIT
/*
 * some parameters for the board
 *
 * This is based on rm9200dk.cfg for the BDI2000 from ABATRON which in
 * turn is based on the boot.bin code from ATMEL
 *
 */

/* flash */
#define MC_PUIA		0xFFFFFF10
#define MC_PUP		0xFFFFFF50
#define MC_PUER		0xFFFFFF54
#define MC_ASR		0xFFFFFF04
#define MC_AASR		0xFFFFFF08
#define EBI_CFGR	0xFFFFFF64
#define SMC2_CSR	0xFFFFFF70

/* clocks */
#define PLLAR		0xFFFFFC28
#define PLLBR		0xFFFFFC2C
#define MCKR		0xFFFFFC30

/*#define AT91C_BASE_CKGR 0xFFFFFC20 */
/*#define CKGR_MOR 0 */

#define CKGR_MOR 	0xFFFFFC20
#define CKGR_MCFR 	0xFFFFFC24
#define PMC_SR	 	0xFFFFFC68

/* sdram */
#define PIOC_ASR	0xFFFFF870
#define PIOC_BSR	0xFFFFF874
#define PIOC_PDR	0xFFFFF804
#define EBI_CSA		0xFFFFFF60
#define SDRC_CR		0xFFFFFF98
#define SDRC_MR		0xFFFFFF90
#define SDRC_TR		0xFFFFFF94


_MTEXT_BASE:
#undef START_FROM_MEM
#ifdef START_FROM_MEM
	.word	TEXT_BASE-PHYS_FLASH_1
#else
	.word	TEXT_BASE
#endif

.globl lowlevel_init
lowlevel_init:
	/* Get the CKGR Base Address */
/*	ldr     r1, =AT91C_BASE_CKGR */
	ldr     r1, =CKGR_MOR
	/* Main oscillator Enable register */
#ifdef CFG_USE_MAIN_OSCILLATOR
	ldr     r0, =0x0000FF01		/* Enable main oscillator,  OSCOUNT = 0xFF */
#else
	ldr     r0, =0x0000FF00		/* Disable main oscillator, OSCOUNT = 0xFF */
#endif
	/* str     r0, [r1, #CKGR_MOR] */
	str     r0, [r1]
	/* Add loop to compensate Main Oscillator startup time */
	ldr     r0, =0x00000100
LoopOsc:
	subs    r0, r0, #1
	bhi     LoopOsc

	/* check main oscillator working */
	ldr	r1,=CKGR_MCFR
	ldr	r0,[r1]
	mov	r4,r0		/* save for debug purpose */
	tst	r0,#0x00010000	/* check MAINRDY */
	beq	mainclock_fail

	/* memory control configuration */
	/* this isn't very elegant, but	 what the heck */
	ldr	r0, =SMRDATA
	ldr	r1, _MTEXT_BASE
	sub	r0, r0, r1
	add	r2, r0, #80
0:
	/* the address */
	ldr	r1, [r0], #4
	/* the value */
	ldr	r3, [r0], #4
	str	r3, [r1]
	cmp	r2, r0
	bne	0b

/*	/* delay - this is all done by guess */
/*	ldr	r0, =0x00010000 */
/*1: */
/*	subs	r0, r0, #1 */
/*	bhi	1b */

	/* delay - this is all done by guess */
	ldr	r0, =0x00010000
1:	subs	r0, r0, #1
	bhi	1b

	/* check main clock stabilized, PLLs locked and master clock ready*/
	/* never seen this fail, even with delay loop above set to 1 */
	ldr	r1,=PMC_SR
	ldr	r0,[r1]
	mov	r4,r0		/* save for debug purpose */
	and	r0,r0,#0x0000000F	/* check MCKRDY|LOCKB|LOCKA|MOSCS */
	cmp	r0,#0x0000000F
	bne	pll_fail


	ldr	r0, =SMRDATA1
	ldr	r1, _MTEXT_BASE
	sub	r0, r0, r1
	add	r2, r0, #176
2:
	/* the address */
	ldr	r1, [r0], #4
	/* the value */
	ldr	r3, [r0], #4
	str	r3, [r1]
	cmp	r2, r0
	bne	2b

	/* switch from FastBus to Asynchronous clock mode */
	mrc	p15, 0, r0, c1, c0, 0
	orr	r0, r0, #0xC0000000	@ set bit 31 (iA) and 30 (nF)
	mcr	p15, 0, r0, c1, c0, 0

	/* everything is fine now */
	mov	pc, lr

mainclock_fail:
	/* switch PORT_A6 LED on */
	/* enable PIO */
	ldr	r0,=0xFFFFF600
	ldr	r1,=0x08000000
	str	r1,[r0]

	/* Activate output */
	ldr	r0,=0xFFFFF610
	ldr	r1,=0x08000000
	str	r1,[r0]

1:	b	1b


pll_fail:
	/* switch PORTA_4 LED on */
	/* enable PIO */
	ldr	r0,=0xFFFFF600
	ldr	r1,=0x00000002
	str	r1,[r0]

	/* Activate output */
	ldr	r0,=0xFFFFF610
	ldr	r1,=0x00000002
	str	r1,[r0]

1:	b	1b


	.ltorg

SMRDATA:
	.word MC_PUIA
	.word MC_PUIA_VAL	/* not documented */
	.word MC_PUP
	.word MC_PUP_VAL	/* not documented */
	.word MC_PUER
	.word MC_PUER_VAL	/* not documented */
	.word MC_ASR
	.word MC_ASR_VAL	/* is read only register!! */
	.word MC_AASR
	.word MC_AASR_VAL	/* is read only register!! */
	.word EBI_CFGR
	.word EBI_CFGR_VAL	/* enable/disable pull up on D0..15 */
	.word SMC2_CSR
	.word SMC2_CSR_VAL	/* Boot-Flash timing */
	.word PLLAR
	.word PLLAR_VAL
	.word PLLBR
	.word PLLBR_VAL
	.word MCKR
	.word MCKR_VAL
	/* SMRDATA is 80 bytes long */
	/* here there's a delay of 100 */
SMRDATA1:
	.word PIOC_ASR
	.word PIOC_ASR_VAL	/* PIOC Peripheral A select PC16..31 as D16..31 */
	.word PIOC_BSR
	.word PIOC_BSR_VAL	/* PIOC Peripheral B select: noop */
	.word PIOC_PDR
	.word PIOC_PDR_VAL	/* PIOC PIO disable PC16..31 */
	.word EBI_CSA
	.word EBI_CSA_VAL	/* CS1 = SDRAM */
	.word SDRC_CR
	.word SDRC_CR_VAL	/* SDRAM configuration register */
	.word SDRC_MR
	.word SDRC_MR_VAL	/* set All Banks Precharge Mode */
	.word SDRAM
	.word SDRAM_VAL		/* Access SDRAM */
	.word SDRC_MR
	.word SDRC_MR_VAL1	/* set Refresh Mode */
	.word SDRAM
	.word SDRAM_VAL		/* 1. */
	.word SDRAM
	.word SDRAM_VAL
	.word SDRAM
	.word SDRAM_VAL
	.word SDRAM
	.word SDRAM_VAL
	.word SDRAM
	.word SDRAM_VAL
	.word SDRAM
	.word SDRAM_VAL
	.word SDRAM
	.word SDRAM_VAL
	.word SDRAM
	.word SDRAM_VAL		/* do 8 refresh cycles */
	.word SDRC_MR
	.word SDRC_MR_VAL2	/* set Load Mode Register mode */
	.word SDRAM1		/* SDRAM mode = ?? */
	.word SDRAM_VAL
	.word SDRC_MR
	.word SDRC_MR_VAL3	/* set normal OP */
	.word SDRAM
	.word SDRAM_VAL
	.word SDRC_TR
	.word SDRC_TR_VAL	/* refresh timer */
	.word SDRAM
	.word SDRAM_VAL
	/* SMRDATA1 is 176 bytes long */
#endif /* CONFIG_SKIP_LOWLEVEL_INIT */