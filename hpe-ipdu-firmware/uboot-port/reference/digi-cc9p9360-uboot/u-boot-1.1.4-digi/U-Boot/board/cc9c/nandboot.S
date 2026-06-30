/***********************************************************************
 *
 *  Copyright (C) 2006 by FS Forth-Systeme GmbH,
 *                     a DIGI International Company
 *  All rights reserved.
 *
 *  @Author: Joachim Jaeger
 *  @Descr: Supports small and large page size with bad-block management and ECC
 *  @References: [1] nandboot.S for A9M24x0
 *	         [2] Toshiba's NAND Flash Applications Design Guide Rev. 1.0
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
 * @Return: always, check for bad blocks and verify ECC bytes
 * @Descr: copies blocks from NAND to RAM (punDest) until unLength data has been
 *	   read. unStartBlock
 *	   autodetects small and large NAND Flashes
 *	   blinks in an endless loop, if NAND not detected
 ***********************************************************************/

#define rNF_BASE	CFG_NAND_BASE

#define	oNF_CMD		(rNF_BASE + NAND_FLASH_CMD)
#define oNF_ADDR	(rNF_BASE + NAND_FLASH_ADR)
#define oNF_DATA	(rNF_BASE + NAND_FLASH_DAT)

#define oNF_REG_CMD	oNF_CMD
#define oNF_GPIO_RB	(0x90600040)	@ address of Ready/Busy GPIO

#define vNF_GPIO_RB	(0x08)		@ Ready/Busy GPIO
#define vNF_BS_LARGE	(0x20000)	@ large block size
#define vNF_BS_SMALL	(0x4000)	@ small block size
#define vNF_PS_LARGE	(0x800)		@ large page size
#define vNF_PS_SMALL	(0x200)		@ small page size
#define vNF_OOB_LARGE	(0x40)		@ large oob size
#define vNF_OOB_SMALL	(0x10)		@ small oob size
#define vNF_BB_POS_L	(0x00)		@ bad block position for large NAND
#define vNF_BB_POS_S	(0x05)		@ bad block position for small NAND
#define vNF_CMD_READ0	(0x00)		@ command READ0
#define vNF_CMD_READS	(0x30)		@ command READ start for large NAND
#define vNF_CMD_READO	(0x50)		@ command READ OOB for small NAND
#define vNF_CMD_READID	(0x90)		@ command READ ID
#define vNF_CMD_RESET	(0xff)		@ command RESET
#define vNF_CMD_STAT	(0x70)		@ command STATUS
#define vNF_WAIT	(0xf0)		@ counter for wait loop
#define vNF_WAIT_RB	(0x0f)		@ counter for ready/busy loop
#define vNF_CHECK_BAD	(0xff)		@ value to check if block is bad

#define oNF_SP_ADDR	(0x1000)	@ address for SP at end of 4k
#define vNF_SP_SIZE	(0x40)		@ size for SP (64 Bytes)
#define vNF_ECC_SIZE	(0x18)		@ size for ECC data (24 Bytes)
#define vNF_ECC_STEP_S	(0x06)		@ 6 ECC bytes for small NAND
#define vNF_ECC_STEP_L	(0x18)		@ 24 ECC bytes for large NAND
#define vNF_ECC_POS	(0x28)		@ start position of ECC data (24 Bytes)
#define oNF_ECC_DAT_C	(0xe60)		@ calculated ECC data (oNF_SP_ADDR-vNF_SP_SIZE-vNF_ECC_SIZE)
#define oNF_ECC_DAT_R	(0xe20)		@ read ECC data (oNF_ECC_DAT_C-64bytes)
#define vNF_ECC_ERROR	(0xffffffff)	@ return value for uncorrectable ECC error
#define vNF_ECC_DATA	(0x100)		@ ECC is calculated for 256 data bytes
#define vNF_ECC_BYTES	(0x03)		@ 3 ECC bytes are calculated for 256 data bytes
#define oNF_ECC_INFO	NAND_ECC_INFO	@ Counter for correctable errors


_nandboot:
	mov	r4, lr
	ldr	sp, =oNF_SP_ADDR	@ set up SP

	stmdb   sp!, {r4}

	ldr	r3, =oNF_ECC_INFO	@ reset ECC error counter
	mov	r4, #0x00
	str	r4, [r3]

	mov	r4, #vNF_CMD_RESET	@ send reset to NAND
	ldr	r3, =oNF_REG_CMD
	strb	r4, [r3]

	mov	r3, #0
2:	mov	r4, #0			@ wait at least 5us before next command
1:	add	r4, r4, #0x1
	cmp	r4, #vNF_WAIT
	blt	1b

	add	r3, r3, #0x1
	cmp	r3, #vNF_WAIT_RB
	blt	2b

	mov	r4, #vNF_CMD_READID	@ Read ID command
	ldr	r3, =oNF_REG_CMD
	strb	r4, [r3]
        
	mov	r4, #0x00	        @ ADDR 0
	ldr	r3, =oNF_ADDR
	strb	r4, [r3]		@ write address byte

	ldr	r3, =oNF_DATA
	ldrb	r4, [r3]		@ get manufacturer ID
        
	cmp	r4, #0x20		@ STM
        cmpne	r4, #0x2C		@ Micron
        cmpne	r4, #0x98		@ Toshiba
        cmpne	r4, #0xEC		@ Samsung
        mov	r8, r4			@ save value for debuging
        mov	r9, #0x55000000		@ initialize the chip ID register
        bne	ErrorNand		@ unknown ID

	ldrb	r4, [r3]		@ get chip ID
        /* check for chips with 512 byte sectors */
        cmp	r4, #0x33		@ 16 MByte, 1.8V
        cmpne	r4, #0x73		@ 16 MByte
        cmpne	r4, #0x35		@ 32 MByte, 1.8V
        cmpne	r4, #0x75		@ 32 MByte
        cmpne	r4, #0x36		@ 64 MByte, 1.8V
        cmpne	r4, #0x76		@ 64 MByte
        cmpne	r4, #0x39		@ 128 MByte, 1.8V
        cmpne	r4, #0x78		@ 128 MByte, 1.8V, Samsung only
        cmpne	r4, #0x79		@ 128 MByte
        cmpne	r4, #0x71		@ 256 MByte
        moveq	r6, #vNF_PS_SMALL	@ small page size
        beq	_nandboot_read_page

        /* check for chips with 2 kbyte sectors */
        cmp	r4, #0xA2		@ 64 MByte, 1.8V
        cmpne	r4, #0xF2		@ 64 MByte
        cmpne	r4, #0xA1		@ 128 MByte, 1.8V
        cmpne	r4, #0xF1		@ 128 MByte
        cmpne	r4, #0xAA		@ 256 MByte, 1.8V
        cmpne	r4, #0xDA		@ 256 MByte
        cmpne	r4, #0xAC		@ 512 MByte, 1.8V
        cmpne	r4, #0xDC		@ 512 MByte
        cmpne	r4, #0xA3		@ 1 GByte, 1.8V
        cmpne	r4, #0xD3		@ 1 GByte
        moveq	r6, #vNF_PS_LARGE	@ large page size
        mov	r9, r4			@ save value for debuging
        beq	_nandboot_read_page
ErrorNand:
/* Debug Blink-LED */
	ldr	r0, =0x90600104
        ldr	r1, [r0]		@ load control register
        ldr	r2, =0x0000F000		@ AND mask, 4 bits per GPIO
        bic	r1, r1,r2
        ldr	r2, =0x0000B000		@ OR mask, GPIO with output
        orr	r1, r1,r2
        str	r1, [r0]		@ GPIO67 as GPIO output
300:
	ldr	r0, =0x90600120
        ldr	r1, [r0]		@ load control register
        ldr	r2, =0x00000008
        bic	r1, r1,r2
        str	r1, [r0]		@ GPIO67 with high level output

	ldr	r0, =0x200000
100:
	mov	r1, r1
	subs	r0, r0, #1
	bne	100b

        ldr	r0, =0x90600120
        ldr	r1, [r0]		@ load control register
        ldr	r2, =0x00000008		@ OR mask, GPIO high
        orr	r1, r1,r2
        str	r1, [r0]		@ GPIO67 with high level output

	ldr	r0, =0x200000
200:
	mov	r1, r1
	subs	r0, r0, #1
	bne	200b

	b	300b
/* end blink LED */

_nandboot_read_page:
	@ read one page
	mov	ip, lr
	bl	_nandboot_bb_check	@ first check, if block is bad
	mov	lr, ip

	mov	r4, #0			@ wait
3:	add	r4, r4, #0x1
	cmp	r4, #vNF_WAIT
	blt	3b

	mov	r4, #vNF_CMD_READ0	@ READ0
	ldr	r3, =oNF_REG_CMD
	strb	r4, [r3]

	cmp	r6, #vNF_PS_SMALL
	beq	4f
/*NAND_LARGE*/
	mov	r4, r0		        @ ADDR
        bic	r4, r4, #0x000000FF 	@ clear A0..7, start of sector
	ldr	r3, =oNF_ADDR
	strb	r4, [r3]		@ write address byte
  	mov	r4, r4, lsr #8		@ A8..11
        bic	r4, r4, #0x000000FF 	@ clear upper nibble and start of sector
	strb	r4, [r3]		@ write A8..11
	mov	r4, r0		        @ again whole ADDR
  	mov	r4, r4, lsr #11
	strb	r4, [r3]		@ write A11..18
  	mov	r4, r4, lsr #8
	strb	r4, [r3]		@ write A19..26
  	mov	r4, r4, lsr #8
	strb	r4, [r3]		@ write A27..31

	mov	r4, #vNF_CMD_READS	@ READ start
	ldr	r3, =oNF_REG_CMD
	strb	r4, [r3]

	b	5f
4:
	mov	r4, r0		        @ ADDR
        bic	r4, r4, #0x000000FF 	@ clear A0..7, start of sector
	ldr	r3, =oNF_ADDR
	strb	r4, [r3]		@ write address byte
  	mov	r4, r4, lsr #9		@ A8 not relevant here
	strb	r4, [r3]		@ write A9..16
  	mov	r4, r4, lsr #8
	strb	r4, [r3]		@ write A17..24
  	mov	r4, r4, lsr #8
        bic	r4, r4, #0x000000FC 	@ clear A2..7
	strb	r4, [r3]		@ write A25..26
5:
	mov	r3, #0
7:	mov	r4, #0			@ wait
6:	add	r4, r4, #0x1
	cmp	r4, #vNF_WAIT
	blt	6b

	add	r3, r3, #0x1
	cmp	r3, #vNF_WAIT_RB
	blt	7b

	@ copy always one page size
	@ r2 is number of bytes overall left after this copy
	@ r5 is number in page left
	cmp	r2, r6
	subge	r2, r2, r6
	movlt	r2, #0
	mov	r5, r6
	ldr	r3, =oNF_DATA

_nandboot_page_copy_to_mem:
	@ copy page to memory
	cmp	r5, #0
	beq	8f
	sub	r5, r5, #1

	ldrb	r4, [r3]
	strb	r4, [r1], #1
	b	_nandboot_page_copy_to_mem
8:
	mov	ip, lr
	bl	_nandboot_calculate_ecc
	mov	lr, ip

	@ now we check ECC
	stmdb   sp!, {r0 - r6}
	mov	r4, r1			@ keep pointer
	sub	r1, r1, r6		@ set pointer to start of page
	ldr	r2, =oNF_ECC_DAT_R	@ pointer to ECC data read
	cmp	r6, #vNF_PS_SMALL
	beq	_ecc_pos_ok
	add	r2, r2, #vNF_ECC_POS	@ correct pointer for large NAND Flash
_ecc_pos_ok:
	ldr	r3, =oNF_ECC_DAT_C	@ pointer to ECC data calculated

_correct_loop:
	mov	ip, lr
	bl	_nandboot_correct_data
	mov	lr, ip

_ecc_error:
	cmp	r0, #vNF_ECC_ERROR	@ uncorrectable ECC error
	beq	_ecc_error

	ldr	r5, =oNF_ECC_INFO
	ldr	r6, [r5]
	add	r6, r6, r0		@ count correctable ECC errors
	str	r6, [r5]

	add	r1, r1, #vNF_ECC_DATA
	add	r2, r2, #vNF_ECC_BYTES
	add	r3, r3, #vNF_ECC_BYTES
	cmp	r1, r4
	bne	_correct_loop

	ldmia   sp!, {r0 - r6}

	cmp	r2, #0
	addne	r0, r0, r6          @ select next page
	bne	_nandboot_read_page

	@ finished, all bytes read
	ldmia   sp!, {lr}
	mov	pc, lr


/***********************************************************************
 * @Function: _nandboot_bb_check
 *
 * @Descr: checks 1st page of block, if block is bad
 *	   stores ECC bytes to RAM
 ***********************************************************************/
_nandboot_bb_check:
	stmdb   sp!, {r1, r2, r7 - r9}
_bb_check_loop:
	mov	r8, #0x00
	cmp	r6, #vNF_PS_SMALL
	beq	19f
/*NAND_LARGE*/
	mov	r5, #vNF_BS_LARGE	@ block size
	mov	r7, #vNF_OOB_LARGE	@ oob size
	mov	r9, #vNF_BB_POS_L	@ bad block position
	mov	r4, r0		        @ ADDR
	cmp	r4, #0x00
	beq	20f
	mov	r8, r4, lsl #15		@ we only check 1st page
	b	20f
19:
	mov	r5, #vNF_BS_SMALL	@ block size
	mov	r7, #vNF_OOB_SMALL	@ oob size
	mov	r9, #vNF_BB_POS_S	@ bad block position
	mov	r4, r0		        @ ADDR
	cmp	r4, #0x00
	beq	20f
	mov	r8, r4, lsl #18		@ we only check 1st page
20:
	mov	r4, #0			@ wait
13:	add	r4, r4, #0x1
	cmp	r4, #vNF_WAIT
	blt	13b

	mov	r4, #vNF_CMD_READO	@ READ OOB for small NAND
	cmp	r6, #vNF_PS_SMALL
	beq	23f
	mov	r4, #vNF_CMD_READ0	@ READ0
23:
	ldr	r3, =oNF_REG_CMD
	strb	r4, [r3]

	cmp	r6, #vNF_PS_SMALL
	beq	9f
/*NAND_LARGE*/
	mov	r4, r0		        @ ADDR
	orr	r4, r4, r6
        bic	r4, r4, #0x000000FF 	@ clear A0..7, start of sector
	ldr	r3, =oNF_ADDR
	strb	r4, [r3]		@ write address byte
  	mov	r4, r4, lsr #8		@ A8..11
        bic	r4, r4, #0x000000F7 	@ clear upper nibble and start of sector
	strb	r4, [r3]		@ write A8..11
	mov	r4, r0		        @ again whole ADDR
  	mov	r4, r4, lsr #11
	strb	r4, [r3]		@ write A11..18
  	mov	r4, r4, lsr #8
	strb	r4, [r3]		@ write A19..26
  	mov	r4, r4, lsr #8
	strb	r4, [r3]		@ write A27..31

	mov	r4, #vNF_CMD_READS	@ READ start
	ldr	r3, =oNF_REG_CMD
	strb	r4, [r3]

	b	10f
9:
	mov	r4, r0		        @ ADDR
        bic	r4, r4, #0x000000FF 	@ clear A0..7, start of sector
	ldr	r3, =oNF_ADDR
	strb	r4, [r3]		@ write address byte
  	mov	r4, r4, lsr #9		@ A8 not relevant here
	strb	r4, [r3]		@ write A9..16
  	mov	r4, r4, lsr #8
	strb	r4, [r3]		@ write A17..24
  	mov	r4, r4, lsr #8
        bic	r4, r4, #0x000000FC 	@ clear A2..7
	strb	r4, [r3]		@ write A25..26
10:
	mov	r3, #0
12:	mov	r4, #0			@ wait
11:	add	r4, r4, #0x1
	cmp	r4, #vNF_WAIT
	blt	11b

	add	r3, r3, #0x1
	cmp	r3, #vNF_WAIT_RB
	blt	12b

	ldr	r1, =oNF_ECC_DAT_R
	mov	r2, #0x00
21:
	ldr	r3, =oNF_DATA
	ldrb	r4, [r3]
	strb	r4, [r1, r2]		@ store ECC bytes
	add	r2, r2, #1
	cmp	r2, r7			@ read all oob data
	bne	21b

	cmp	r8, #0x00		@ 1st page of block?
	bne	22f
	ldrb	r4, [r1, r9]		@ read bad block info
	cmp	r4, #vNF_CHECK_BAD	@ bad block?
	beq	22f
	add	r0, r0, r5		@ next block
	b	_bb_check_loop		@ check new block
22:

	cmp	r9, #vNF_BB_POS_L
	beq	_bb_check_out
	ldrb	r4, [r1, #6]		@ move ECC4 to the correct place
	strb	r4, [r1, #4]
	ldrb	r4, [r1, #7]		@ move ECC5 to the correct place
	strb	r4, [r1, #5]

_bb_check_out:
	ldmia   sp!, {r1, r2, r7 - r9}

	mov	pc, lr

/***********************************************************************
 * @Function: _nandboot_calculate_ecc
 *
 * @Descr: calculates ECC values of read page
 *	   stores ECC bytes to RAM
 *	   R1 = raw data read from NAND
 ***********************************************************************/
_nandboot_calculate_ecc:
	stmdb   sp!, {r0 - r7, lr}

	mov	r7, #0
	sub	r6, r1, r6		@ set pointer to start of page
	ldr	r4, =oNF_ECC_DAT_C	@ pointer to ECC data

_calc_loop:
	mov     lr, #0			@ initialize all 0x0
	strb    lr, [r4, r7]
	add	r7, r7, #1
	strb    lr, [r4, r7]
	add	r7, r7, #1
	strb    lr, [r4, r7]
	mov     r5, lr
	mov     r0, lr
	mov     ip, lr
30:	ldrb    r2, [r6, ip]
	adr     r3, _nandboot_ecc_tbl	@ pointer to ECC table
	ldrb    r2, [r3, r2]
	mvn     r3, ip
	tst     r2, #64
	eor     r1, r0, r3
	eor     r3, lr, ip
	add     ip, ip, #1
	and     r2, r2, #63
	andne   lr, r3, #255
	andne   r0, r1, #255
	cmp     ip, #255
	eor     r5, r5, r2
	ble     30b
	mov     r1, lr
	mov     r2, r4
	sub	r7, r7, #2
	add	r2, r2, r7
	bl      _nandboot_trans_result
	ldrb    r2, [r4, r7]
	mvn     r2, r2
	strb    r2, [r4, r7]

	add	r7, r7, #1
	ldrb    r1, [r4, r7]
	mvn     r1, r1
	strb    r1, [r4, r7]

	add	r7, r7, #1
	mvn     r3, r5
	mov     r3, r3, lsl #2
	orr     r3, r3, #3
	mov     r0, #0
	strb    r3, [r4, r7]

	mov	r2, #vNF_ECC_STEP_S
	cmp	r6, #vNF_PS_SMALL
	beq	31f
/*NAND_LARGE*/
	mov	r2, #vNF_ECC_STEP_L
31:
	add	r6, r6, #vNF_ECC_DATA
	add	r7, r7, #1
	cmp	r7, r2
	bne	_calc_loop

	ldmia   sp!, {r0 - r7, lr}

	mov	pc, lr

/***********************************************************************
 * @Function: _nandboot_trans_result
 *
 * @Descr: helper function to calculate ECC values
 *	   stores ECC bytes to RAM
 ***********************************************************************/
_nandboot_trans_result:
	stmdb   sp!, {r0 - r6, lr}

	mov     r5, #0
	mov     r4, #128
	mov     r6, r2
	and     r0, r0, #255
	and     r1, r1, #255
	mov     ip, r4
	mov     r2, r5
	mov     r3, r5
40:	tst     r1, r4
	orrne   r2, r2, ip
	add     r3, r3, #1
	mov     ip, ip, lsr #1
	tst     r0, r4
	orr     lr, r2, ip
	and     r3, r3, #255
	andne   r2, lr, #255
	cmp     r3, #3
	mov     r4, r4, lsr #1
	mov     ip, ip, lsr #1
	bls     40b
	mov     ip, #128
	mov     r3, #0
41:	tst     r1, r4
	orrne   r5, r5, ip
	add     r3, r3, #1
	mov     ip, ip, lsr #1
	tst     r0, r4
	orr     lr, r5, ip
	and     r3, r3, #255
	andne   r5, lr, #255
	cmp     r3, #3
	mov     r4, r4, lsr #1
	mov     ip, ip, lsr #1
	strhib  r5, [r6, #1]
	strhib  r2, [r6]
	ldmhiia sp!, {r0 - r6, pc}
	b       41b

/***********************************************************************
 * @Table: _nandboot_ecc_tbl
 *
 * @Descr: precalculated 256-way 1 byte column parity
 *
 ***********************************************************************/
_nandboot_ecc_tbl:
        .byte 0x00, 0x55, 0x56, 0x03, 0x59, 0x0C, 0x0F, 0x5A @/* index 0x00 */
        .byte 0x5A, 0x0F, 0x0C, 0x59, 0x03, 0x56, 0x55, 0x00
        .byte 0x65, 0x30, 0x33, 0x66, 0x3C, 0x69, 0x6A, 0x3F
        .byte 0x3F, 0x6A, 0x69, 0x3C, 0x66, 0x33, 0x30, 0x65

        .byte 0x66, 0x33, 0x30, 0x65, 0x3F, 0x6A, 0x69, 0x3C @/* index 0x20 */
        .byte 0x3C, 0x69, 0x6A, 0x3F, 0x65, 0x30, 0x33, 0x66
        .byte 0x03, 0x56, 0x55, 0x00, 0x5A, 0x0F, 0x0C, 0x59
        .byte 0x59, 0x0C, 0x0F, 0x5A, 0x00, 0x55, 0x56, 0x03

        .byte 0x69, 0x3C, 0x3F, 0x6A, 0x30, 0x65, 0x66, 0x33 @/* index 0x40 */
        .byte 0x33, 0x66, 0x65, 0x30, 0x6A, 0x3F, 0x3C, 0x69
        .byte 0x0C, 0x59, 0x5A, 0x0F, 0x55, 0x00, 0x03, 0x56
        .byte 0x56, 0x03, 0x00, 0x55, 0x0F, 0x5A, 0x59, 0x0C

        .byte 0x0F, 0x5A, 0x59, 0x0C, 0x56, 0x03, 0x00, 0x55 @/* index 0x60 */
        .byte 0x55, 0x00, 0x03, 0x56, 0x0C, 0x59, 0x5A, 0x0F
        .byte 0x6A, 0x3F, 0x3C, 0x69, 0x33, 0x66, 0x65, 0x30
        .byte 0x30, 0x65, 0x66, 0x33, 0x69, 0x3C, 0x3F, 0x6A

        .byte 0x6A, 0x3F, 0x3C, 0x69, 0x33, 0x66, 0x65, 0x30 @/* index 0x80 */
        .byte 0x30, 0x65, 0x66, 0x33, 0x69, 0x3C, 0x3F, 0x6A
        .byte 0x0F, 0x5A, 0x59, 0x0C, 0x56, 0x03, 0x00, 0x55
        .byte 0x55, 0x00, 0x03, 0x56, 0x0C, 0x59, 0x5A, 0x0F

        .byte 0x0C, 0x59, 0x5A, 0x0F, 0x55, 0x00, 0x03, 0x56 @/* index 0xA0 */
        .byte 0x56, 0x03, 0x00, 0x55, 0x0F, 0x5A, 0x59, 0x0C
        .byte 0x69, 0x3C, 0x3F, 0x6A, 0x30, 0x65, 0x66, 0x33
        .byte 0x33, 0x66, 0x65, 0x30, 0x6A, 0x3F, 0x3C, 0x69

        .byte 0x03, 0x56, 0x55, 0x00, 0x5A, 0x0F, 0x0C, 0x59 @/* index 0xC0 */
        .byte 0x59, 0x0C, 0x0F, 0x5A, 0x00, 0x55, 0x56, 0x03
        .byte 0x66, 0x33, 0x30, 0x65, 0x3F, 0x6A, 0x69, 0x3C
        .byte 0x3C, 0x69, 0x6A, 0x3F, 0x65, 0x30, 0x33, 0x66

        .byte 0x65, 0x30, 0x33, 0x66, 0x3C, 0x69, 0x6A, 0x3F @/* index 0xE0 */
        .byte 0x3F, 0x6A, 0x69, 0x3C, 0x66, 0x33, 0x30, 0x65
        .byte 0x00, 0x55, 0x56, 0x03, 0x59, 0x0C, 0x0F, 0x5A
        .byte 0x5A, 0x0F, 0x0C, 0x59, 0x03, 0x56, 0x55, 0x00

/***********************************************************************
 * @Function: _nandboot_correct_data
 *
 * @Descr: compares calculated and read ECC values
 *	   correct error if possible
 *	   R0 = return value
 *	   R1 = raw data read from NAND
 *	   R2 = ECC read from NAND
 *	   R3 = calculated ECC
 ***********************************************************************/
_nandboot_correct_data:
	stmdb   sp!, {r1 - r7, r9, sl, lr}

	mov     r7, r3
	ldrb    r0, [r3, #1]
	ldrb    sl, [r3]
	ldrb    lr, [r2]
	ldrb    r3, [r2, #1]
	mov     r6, r2
	ldrb    ip, [r7, #2]
	ldrb    r2, [r2, #2]
	eor     r5, r0, r3
	eor     r4, sl, lr
	eor     ip, ip, r2
	orr     r3, r4, r5
	orrs    r0, ip, r3
	mov     r9, r1
	ldmeqia sp!, {r1 - r7, r9, sl, pc}
	eor     r3, r4, r4, lsr #1
	eor     r2, r5, r5, lsr #1
	and     lr, r3, #85		@; 0x55
	and     r0, r2, #85		@; 0x55
	eor     r3, ip, ip, lsr #1
	cmp     lr, #85			@; 0x55
	cmpeq   r0, #85			@; 0x55
	and     r2, r3, #84		@; 0x54
	bne     53f
	cmp     r2, #84			@; 0x54
	bne     53f
	mov     r2, #128		@; 0x80
	mov     r1, #0
	mov     lr, r2
	mov     r3, r1
50:	add     r3, r3, #1
	tst     r4, r2
	and     r3, r3, #255		@; 0xff
	orrne   r1, r1, lr
	cmp     r3, #3			@; 0x3
	mov     r2, r2, lsr #2
	mov     lr, lr, lsr #1
	bls     50b
	mov     r2, #128		@; 0x80
	mov     r3, #0
51:	add     r3, r3, #1
	tst     r5, r2
	and     r3, r3, #255		@; 0xff
	orrne   r1, r1, lr
	cmp     r3, #3			@; 0x3
	mov     r2, r2, lsr #2
	mov     lr, lr, lsr #1
	bls     51b
	mov     r4, #0
	mov     r0, #4
	mov     r2, #128		@; 0x80
	mov     r3, r4
52:	add     r3, r3, #1
	and     r3, r3, #255		@; 0xff
	tst     ip, r2
	orrne   r4, r4, r0
	cmp     r3, #2
	ldrhib  lr, [r9, r1]
	mov     r0, r0, lsr #1
	movhi   r0, #1
	eorhi   r3, lr, r0, lsl r4
	mov     r2, r2, lsr #2
	strhib  r3, [r9, r1]
	ldmhiia sp!, {r1 - r7, r9, sl, pc}
	b       52b
53:	cmp     r4, #0
	mov     r3, #0
	beq     55f
54:	tst     r4, #1
	add     r2, r3, #1
	andne   r3, r2, #255		@; 0xff
	movs    r4, r4, lsr #1
	bne     54b
55:	cmp     r5, #0
	beq     57f
56:	tst     r5, #1
	add     r2, r3, #1
	andne   r3, r2, #255		@; 0xff
	movs    r5, r5, lsr #1
	bne     56b
57:	cmp     ip, #0
	beq     59f
58:	tst     ip, #1
	add     r2, r3, #1
	andne   r3, r2, #255		@; 0xff
	movs    ip, ip, lsr #1
	bne     58b
59:	cmp     r3, #1
	streqb  sl, [r6]
	ldreqb  r3, [r7, #1]
	streqb  r3, [r6, #1]
	ldreqb  r3, [r7, #2]
	moveq   r0, #2
	mvnne   r0, #0
	streqb  r3, [r6, #2]

	ldmia   sp!, {r1 - r7, r9, sl, pc}

#endif /* CONFIG_BOOT_NAND */
