/* SPDX-License-Identifier: Apache-2.0
 * Minimal AST2050 ARM test stub: configure UART2 and print a signature forever.
 *
 * This is the P2A-independent WITNESS for the DRAM-boot experiments
 * (P2A-DRAM-BOOT-SEQUENCE.md): it proves the ARM fetched and ran OUR code from
 * DRAM, because the signature shows up on the BMC debug UART
 * (UART2 @ 0x1e784000 -> Pi /dev/serial-bmc-console @ 1200 8N1), which is a
 * channel completely separate from the P2A path we used to load it.
 *
 * Linked at 0x00000000 (the ARM reset vector, which the DRAM->0x0 remap points at
 * DRAM). The 8 exception vectors all branch to _start, so any reset/exception
 * fetch lands in the stub. ARM926EJ-S comes out of reset in ARM state, SVC mode,
 * MMU+caches off, so DRAM and the UART MMIO are directly accessible.
 *
 * Build:  make            (-> uart-hello.bin, and uart-hello.words for P2A)
 */
	.arm
	.section .text
	.global _start

_vectors:
	b	_start			/* 0x00 reset          */
	b	_start			/* 0x04 undefined      */
	b	_start			/* 0x08 svc            */
	b	_start			/* 0x0c prefetch abort */
	b	_start			/* 0x10 data abort     */
	b	_start			/* 0x14 (reserved)     */
	b	_start			/* 0x18 irq            */
	b	_start			/* 0x1c fiq            */

_start:
	ldr	r0, =0x1e784000		/* UART2 base                     */
	mov	r1, #0x83
	str	r1, [r0, #0x0c]		/* LCR = DLAB|8N1                 */
	mov	r1, #0xe2
	str	r1, [r0, #0x00]		/* DLL = 0xE2  (divisor 1250)     */
	mov	r1, #0x04
	str	r1, [r0, #0x04]		/* DLH = 0x04  -> 1200 baud @24MHz */
	mov	r1, #0x03
	str	r1, [r0, #0x0c]		/* LCR = 8N1, DLAB off            */
	mov	r1, #0x07
	str	r1, [r0, #0x08]		/* FCR = enable + clear FIFOs     */

again:
	adr	r2, msg
1:	ldrb	r3, [r2], #1		/* next char                      */
	cmp	r3, #0
	beq	delay
2:	ldr	r4, [r0, #0x14]		/* LSR                            */
	tst	r4, #0x20		/* wait for THR empty (bit5)      */
	beq	2b
	str	r3, [r0, #0x00]		/* THR <- char                    */
	b	1b
delay:
	ldr	r5, =0x02000000		/* ~a few hundred ms between lines */
3:	subs	r5, r5, #1
	bne	3b
	b	again

	.ltorg				/* dump literal pools here (in range) */
	.align	2
msg:
	.asciz	"\r\nAST2050-ARM-ALIVE-P2A-DRAM-BOOT\r\n"
	.align	2
