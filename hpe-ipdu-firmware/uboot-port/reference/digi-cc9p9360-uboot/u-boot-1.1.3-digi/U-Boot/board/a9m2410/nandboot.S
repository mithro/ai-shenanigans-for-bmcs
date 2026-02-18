/***********************************************************************
 *
 *  Copyright (C) 2003 by FS Forth-Systeme GmbH.
 *  All rights reserved.
 *	
 *  @Author: Markus Pietrek
 *  @Descr: Supports only 512 bytes media with no bad-block management
 *  @References: [1] S3C2410X User's Manual Rev. 1
 *	         [2] Toshiba's NAND Flash Applications Design Guide Rev. 1.0
 * 	         [3] vivi/arch/s3c2420/head.S, Rev. 1.18 (initialization)
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

#include <config.h>

#ifdef CONFIG_BOOT_NAND	
.globl _nandboot

/***********************************************************************
 * @Function: _nandboot (unsigned int unStartBlock,
 *			  unsigned int* punDest, unsigned int unLength)
 * @Return: always, no error handling
 * @Descr: copies blocks from NAND to RAM (punDest) until unLength data has been
 *	   read. unStartBlock
 ***********************************************************************/

#define rNF_BASE	(0x4e000000)
#ifndef CPU_2440
#define	oNF_CONF	(0x00)
#define	oNF_CMD		(0x04)
#define oNF_ADDR	(0x08)
#define oNF_DATA	(0x0c)
#define oNF_STAT	(0x10)
#define oNF_ECC		(0x14)

#define vNF_CONF_RESET  (0xf830) /* NAND Controller enable, enable chip,
	                            TWRPH0 = 3 */ 			
#else
#define	oNF_CONF	(0x00)
#define	oNF_CONT	(0x04)
#define	oNF_CMMD	(0x08)
#define oNF_ADDR	(0x0c)
#define oNF_DATA	(0x10)
#define oNF_STAT	(0x20)

#define vNF_CONF_RESET  (0x0300) /* TWRPH0 = 3 */ 			
#define vNF_CONT_RESET  (0x0013) /* NAND Controller enable, enable chip */
#endif

_nandboot:
	ldr	r6, =0x200              @ page size
	
	mov	r3, #rNF_BASE           @ reset NAND Controller
	ldr	r4, =vNF_CONF_RESET
	str	r4, [r3, #oNF_CONF]
	
#ifndef CPU_2440
	ldr	r4, [r3, #oNF_CONF]
	bic	r4, r4, #0x800	        @ enable chip	
	str	r4, [r3, #oNF_CONF]
	
	mov	r4, #0xff		@ send reset to NAND
	strb	r4, [r3, #oNF_CMD]

#else
	ldr	r4, =vNF_CONT_RESET
	str	r4, [r3, #oNF_CONT]
	ldr	r4, [r3, #oNF_CONT]
	bic	r4, r4, #0x2	        @ enable chip	
	str	r4, [r3, #oNF_CONT]

	mov	r4, #0xff		@ send reset to NAND
	strb	r4, [r3, #oNF_CMMD]

#endif

	mov	r4, #0			@ wait
1:	add	r4, r4, #0x1
	cmp	r4, #0x30
	blt	1b
	
2:	ldr	r4, [r3, #oNF_STAT]	@ wait ready
	tst	r4, #0x1
	beq	2b
	
#ifndef CPU_2440
	ldr	r4, [r3, #oNF_CONF]
	orr	r4, r4, #0x800		@ disable chip
	str	r4, [r3, #oNF_CONF]
#else
	ldr	r4, [r3, #oNF_CONT]
	orr	r4, r4, #0x2		@ disable chip
	str	r4, [r3, #oNF_CONT]
#endif

_nandboot_read_page:	
	@ read one page
#ifndef CPU_2440
	ldr	r4, [r3, #oNF_CONF]
	bic	r4, r4, #0x800		@ enable chip
	str	r4, [r3, #oNF_CONF]
#else
	ldr	r4, [r3, #oNF_CONT]
	bic	r4, r4, #0x2		@ enable chip
	str	r4, [r3, #oNF_CONT]
#endif

	mov	r4, #0			@ wait 
4:
	add	r4, r4, #0x1
	cmp	r4, #0x30
	blt	4b

	mov	r4, #0x0		@ READ0
#ifndef CPU_2440   
	strb	r4, [r3, #oNF_CMD]
#else
	strb	r4, [r3, #oNF_CMMD]
#endif

	mov	r4, r0		        @ ADDR
        bic	r4, r4, #0x000000FF 	@ clear A0..7, start of sector
	strb	r4, [r3, #oNF_ADDR]	@ write address byte
  	mov	r4, r4, lsr #9		@ A8 not relevant here
	strb	r4, [r3, #oNF_ADDR]	@ write A9..16
  	mov	r4, r4, lsr #8
	strb	r4, [r3, #oNF_ADDR]	@ write A17..24
  	mov	r4, r4, lsr #8
        bic	r4, r4, #0x000000FC 	@ clear A2..7
	strb	r4, [r3, #oNF_ADDR]	@ write A25..26
5:
	ldr	r4, [r3, #oNF_STAT]     @ wait idle
	tst	r4, #0x1
	beq	5b

	@ copy at max 512 bytes
	@ r2 is number of bytes overall left after this copy
	@ r5 is number in page left
	cmp	r2, r6
	subge	r2, r2, r6
	movge	r5, r6
	movlt	r5, r2
	movlt	r2, #0

_nandboot_page_copy_to_mem:
	@ copy page to memory
	cmp	r5, #0
	beq	7f
	sub	r5, r5, #1

	ldrb	r4, [r3, #oNF_DATA]
	strb	r4, [r1], #1
	b	_nandboot_page_copy_to_mem
				
7:	
#ifndef CPU_2440
	ldr	r4, [r3, #oNF_CONF]
	orr	r4, r4, #0x800		@ disable chip
	str	r4, [r3, #oNF_CONF]
#else
	ldr	r4, [r3, #oNF_CONT]
	orr	r4, r4, #0x2		@ disable chip
	str	r4, [r3, #oNF_CONT]
#endif

	cmp	r2, #0
	addne	r0, r0, r6          @ select next page
	bne	_nandboot_read_page

	@ finished, all bytes read
#ifndef CPU_2440
	mov	r4, #0x0800
	str	r4, [r3, #oNF_CONF]     @ disable NAND Controller
#else
	mov	r4, #0x2
	str	r4, [r3, #oNF_CONT]     @ disable NAND Controller
#endif

	mov	pc, lr	
#endif /* CONFIG_BOOT_NAND */
