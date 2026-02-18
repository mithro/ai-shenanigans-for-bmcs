/*
 *  Startup Code for ARM926EJS CPU-core for CC9C/CCW9C
 *
 *  Copyright (c) 2006 DIGI International
 *
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
 */


#define LCD_PALETTE	0xA0800200	/* use LCD palette memory for code execution */
#define LCD_PALETTE_SZ	0x00000200	/* palette has limited size */
#define DEBUG_LED_CFG	0x90600104	/* GPIO configuration register for GPIO67 as DEBUG-LED */
#define DEBUG_LED_OUT	0x90600120	/* GPIO control register for GPIO67 as DEBUG-LED */

#ifdef SWITCH_BE_TO_LE
.global _start
	b _switch
#endif /* SWITCH_LE_TO_BE */

.org 0x54

.globl _switch
_switch:
#ifndef SWITCH_BE_TO_LE
	b	_end_switch
#else	
        /********************************************************************
        * set GPIO67 to output (DEBUG LED)
        ********************************************************************/
/*        ldr     r0,=DEBUG_LED_CFG	*/
	mov	r0,#0x900
	orr	r0,r0,#0x006
	mov	r0,r0,lsl #20
	orr	r0,r0,#0x00000104
	
        ldr     r1,[r0]
        mov     r2,#0x0000F000      /*AND mask, 4 bits per GPIO*/
	bic	r1,r1,r2
        mov     r2,#0x0000B000      /*OR mask, GPIO with output*/
	orr	r1,r1,r2
        str     r1,[r0]

        /* Copy code into LCD Palette RAM */
        adr     r0,SwitchEndian
/*        ldr     r1,=LCD_PALETTE	*/
	mov	r1,#0xa00
	orr	r1,r1,#0x008
	mov	r1,r1,lsl #20
	orr	r1,r1,#0x00000200
	
        mov     r2,#LCD_PALETTE_SZ
        mov     r4,r1               /* save address for jump */

1:      ldr     r3,[r0],#4
        str     r3,[r1],#4
        subs    r2,r2,#4
        bgt     1b

        adr     r14,PaletteRet      /* set return address */
        mov     r15,r4              /* jump to routine */
PaletteRet:
        nop

        /********************************************************************
        * U-BOOT continues here
        ********************************************************************/
	b	EndianSwitchReady

	/********************************************************************
	 * Switch to little endian mode
	 * This code must be limited to 0x200 bytes
	 ********************************************************************/
SwitchEndian:

	/* Clear bit 0 of Config Reg in Memory Controller */
/*	LDR	R0, =0xA0700008	*/	/* Address */
	mov	r0,#0xa00
	orr	r0,r0,#0x007
	mov	r0,r0,lsl #20
	orr	r0,r0,#0x00000008
	
	ldr	r1,[r0]			/* Load current value into R1 */
	bic	r1,r1,#0x00000001	/* Clear Bit 0 to indicate strapped to Little Endian */
	str	r1,[r0]			/* Write back*/

	/* Clear bit 3 of Misc Config Reg in System Control Module */
/*	LDR	R0, =0xA0900184	*/	/* Address */
	mov	r0,#0xa00
	orr	r0,r0,#0x009
	mov	r0,r0,lsl #20
	orr	r0,r0,#0x00000184
	
	ldr	r1,[r0]			/* Load current value into R1 */
	bic	r1,r1,#0x00000008	/* Clear Bit 3 to indicate strapped to Little Endian */
	str	r1,[r0]			/* Write back */

	/* Clear the strapped endian bits in BBusUtility Endian Config Register */
/*	LDR	R0, =0x90600080	*/	/* Address */
	mov	r0,#0x900
	orr	r0,r0,#0x006
	mov	r0,r0,lsl #20
	orr	r0,r0,#0x00000080
	
	ldr	r1,[r0]			/* Load current value into R1 */
/*	LDR	R2, =0x00001201	*/	/* switch endianess for AHB bus master, USB host controller, BBus DMA */
	mov	r2,#0x1000
	orr	r2,r2,#0x200
	orr	r2,r2,#0x00000001
	
	bic	r1,r1,r2
	str	r1,[r0]			/* Write back */

	/* Clear Endian bit in CP15 R1.*/
/*	LDR	R1, =0x00001005	*/
	mov	r1,#0x1000
	orr	r1,r1,#0x00000005
	
	mrc	p15, 0, r0, c1, c0, 0	/* read value from control register (CP15 r1 into r0) */
	bic	r0, r0, #0x00000080	/* Clear bit 7 */
	mcr	p15, 0, r0, c1, c0, 0	/* write back */

        /********************************************************************
        * switch DEBUG LED on
        ********************************************************************/
	mov	r3,#0x3
200:
/*        mov	r0,#DEBUG_LED_OUT */
	mov	r0,#0x900
	orr	r0,r0,#0x006
	mov	r0,r0,lsl #20
	orr	r0,r0,#0x0120
	
        ldr	r1,[r0]
        mov	r2,#0x00000008
	bic	r1,r1,r2
        str	r1,[r0]

	mov	r0,#0x10000
100:
	subs	r0, r0, #1
	bne	100b
        
/*        mov	r0,#DEBUG_LED_OUT */
	mov	r0,#0x900
	orr	r0,r0,#0x006
	mov	r0,r0,lsl #20
	orr	r0,r0,#0x0120
	
        ldr	r1,[r0]
        mov     r2,#0x00000008
	orr	r1,r1,r2
        str	r1,[r0]

	mov	r0,#0x10000
300:
	subs	r0, r0, #1
	bne	300b
	
	subs	r3,r3,#1
	bne	200b
        
	mov     PC,LR               /* =RET*/

#endif /* SWITCH_LE_TO_BE */

.org 0x1A0

.globl _end_switch
_end_switch:


EndianSwitchReady:

