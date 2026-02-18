/*
 *  armboot - Startup Code for ARM920 CPU-core
 *
 *  Copyright (c) 2001	Marius Gröger <mag@sysgo.de>
 *  Copyright (c) 2002	Alex Züpke <azu@sysgo.de>
 *  Copyright (c) 2002	Gary Jennejohn <gj@denx.de>
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
 * 19-08-2005:	moved to u-boot-1.1.3	Joachim Jaeger
 *
 */


#include <config.h>
#include <version.h>


/*
 *************************************************************************
 *
 * Jump vector table as in table 3.1 in [1]
 *
 *************************************************************************
 */


.globl _start
_start:	b       reset
	ldr	pc, _undefined_instruction
	ldr	pc, _software_interrupt
	ldr	pc, _prefetch_abort
	ldr	pc, _data_abort
	ldr	pc, _not_used
	ldr	pc, _irq
	ldr	pc, _fiq

_undefined_instruction:	.word undefined_instruction
_software_interrupt:	.word software_interrupt
_prefetch_abort:	.word prefetch_abort
_data_abort:		.word data_abort
_not_used:		.word not_used
_irq:			.word irq
_fiq:			.word fiq

	.balignl 16,0xdeadbeef


/*
 *************************************************************************
 *
 * Startup Code (reset vector)
 *
 * do important init only if we don't start from memory!
 * relocate armboot to ram
 * setup stack
 * jump to second stage
 *
 *************************************************************************
 */

_TEXT_BASE:
	.word	TEXT_BASE

.globl _armboot_start
_armboot_start:
	.word _start

/*
 * These are defined in the board-specific linker script.
 */
.globl _bss_start
_bss_start:
	.word __bss_start

.globl _bss_end
_bss_end:
	.word _end

#ifdef CONFIG_USE_IRQ
/* IRQ stack memory (calculated at run-time) */
.globl IRQ_STACK_START
IRQ_STACK_START:
	.word	0x0badc0de

/* IRQ stack memory (calculated at run-time) */
.globl FIQ_STACK_START
FIQ_STACK_START:
	.word 0x0badc0de
#endif



#define CLKDIVN_124		0x3 /* HCLK = FCLK/2 */
#define CLKDIVN_144		0x4 /* HCLK = FCLK/4 */
#define CLKDIVN_136		0x7 /* HCLK = FCLK/3 */
#define CLKDIVN_148		0x5 /* HCLK = FCLK/4 */
#define CLKDIVN_1612		0x7 /* HCLK = FCLK/6 */
#define CLKDIVN_188		0x4 /* HCLK = FCLK/8 */
#define MPLLCON			0x4C000004
#define UPLLCON 		0x4C000008
#define INTSUBMSK		0x4A00001C
#define LOCKTIME 		0x4C000000
#define GPBCON			0x56000010
#define GPBDAT			0x56000014
#define GPBUP			0x56000018
#define GPFCON			0x56000050
#define GPFDAT			0x56000054
#define GPFUP			0x56000058
#define GPHCON			0x56000070
#define GPHDAT			0x56000074
#define GPHUP			0x56000078
#define GSTATUS2		0x560000B4 /* Reset type */
#define GSTATUS3		0x560000B8 /* Saved PC before entering POWER_OFF mode */
#define MISCCR			0x56000080

#ifdef CPU_2440
#define CAMDIVN_148		0x0
#define CAMDIVN_1612		0x100
#define CAMDIVN_188		0x200
# if (CONFIG_SYS_CLK_FREQ ==  12000000)
#  define MDIV_532		125
#  define PDIV_532		1
#  define SDIV_532		1
#  define MDIV_405		127
#  define PDIV_405		2
#  define SDIV_405		1
#  define MDIV_304		68
#  define PDIV_304		1
#  define SDIV_304		1
#  define vREFRESH_405		992
#  define MDIV_96		56
#  define PDIV_96		2
#  define SDIV_96		1
#  define MDIV_48		56
#  define PDIV_48		2
#  define SDIV_48		2
/*#  define vMPLLCON_NOW_FAST	((MDIV_532 << 12) | (PDIV_532 << 4) | (SDIV_532))*/
#  define vMPLLCON_NOW_FAST	((MDIV_405 << 12) | (PDIV_405 << 4) | (SDIV_405))
#  define vMPLLCON_NOW_SLOW	((MDIV_405 << 12) | (PDIV_405 << 4) | (SDIV_405))
#  define vUPLLCON_NOW_USER	((MDIV_48 << 12) | (PDIV_48 << 4) | (SDIV_48))
/*#  define CLKDIVN_VAL_FAST	CLKDIVN_1612
#  define CAMDIVN_VAL_FAST	CAMDIVN_1612*/
#  define CLKDIVN_VAL_FAST	CLKDIVN_148
#  define CAMDIVN_VAL_FAST	CAMDIVN_148
#  define CLKDIVN_VAL_SLOW	CLKDIVN_148
#  define CAMDIVN_VAL_SLOW	CAMDIVN_148

# else /* SYS_CLK_FREQ == 16.9344Mhz */
#  define MDIV_533		118
#  define PDIV_533		1
#  define SDIV_533		1
#  define MDIV_400		110
#  define PDIV_400		3
#  define SDIV_400		1
#  define MDIV_300		97
#  define PDIV_300		1
#  define SDIV_300		2
#  define vREFRESH_406		992
#  define MDIV_96		60
#  define PDIV_96		4
#  define SDIV_96		1
#  define MDIV_48		60
#  define PDIV_48		4
#  define SDIV_48		2
/*#  define vMPLLCON_NOW_FAST	((MDIV_533 << 12) | (PDIV_533 << 4) | (SDIV_533))*/
#  define vMPLLCON_NOW_FAST	((MDIV_400 << 12) | (PDIV_400 << 4) | (SDIV_400))
#  define vMPLLCON_NOW_SLOW	((MDIV_300 << 12) | (PDIV_300 << 4) | (SDIV_300))
#  define vUPLLCON_NOW_USER	((MDIV_48 << 12) | (PDIV_48 << 4) | (SDIV_48))
/*#  define CLKDIVN_VAL_FAST	CLKDIVN_1612
#  define CAMDIVN_VAL_FAST	CAMDIVN_1612*/
#  define CLKDIVN_VAL_FAST	CLKDIVN_148
#  define CAMDIVN_VAL_FAST	CAMDIVN_148
#  define CLKDIVN_VAL_SLOW	CLKDIVN_136
#  define CAMDIVN_VAL_SLOW	CAMDIVN_148
# endif

#define pWTCON		0x53000000
#define SRCPND		0x4A000000
#define INTMSK		0x4A000008
#define CLKCON		0x4C00000C
#define CLKSLOW		0x4C000010
#define CLKDIVN		0x4C000014
#define CAMDIVN 	0x4C000018

#else

# if defined(CONFIG_S3C2400)
#  define pWTCON		0x15300000
/* Interupt-Controller base addresses */
#  define INTMSK		0x14400008
/* clock divisor register */
#  define CLKDIVN		0x14800014
# elif defined(CONFIG_S3C2410)
#  define pWTCON		0x53000000
/* Interupt-Controller base addresses */
#  define INTMSK		0x4A000008
/* clock divisor register */
#  define CLKDIVN		0x4C000014
#  define CLKSLOW		0x4C000010
#  define MDIV_270		0x7F   		/* Fout = 270.0MHz */
#  define PDIV_270		0x1
#  define SDIV_270		0x1
#  define MDIV_266		0x7D   		/* Fout = 266.0MHz */
#  define PDIV_266		0x1
#  define SDIV_266		0x1
#  define MDIV_260		0xA1   		/* Fout = 253.5MHz */
#  define PDIV_260		0x2
#  define SDIV_260		0x1
#  define MDIV_240		0x70   		/* Fout = 240.0MHz */
#  define PDIV_240		0x1
#  define SDIV_240		0x1
#  define MDIV_220		0x68   		/* Fout = 220.0MHz */
#  define PDIV_220		0x1
#  define SDIV_220		0x1
#  define MDIV_202		0xA1   		/* Fout = 202.8MHz */
#  define PDIV_202		0x3
#  define SDIV_202		0x1
#  define MDIV_48		0x78
#  define PDIV_48		0x2
#  define SDIV_48		0x3
#  define CLKDIVN_VAL_FAST	CLKDIVN_144
#  define CLKDIVN_VAL_SLOW	CLKDIVN_124
/*#  define vMPLLCON_NOW_FAST	((MDIV_270 << 12) | (PDIV_270 << 4) | (SDIV_270))*/
/*#  define vMPLLCON_NOW_FAST	((MDIV_266 << 12) | (PDIV_266 << 4) | (SDIV_266))*/
/*#  define vMPLLCON_NOW_FAST	((MDIV_260 << 12) | (PDIV_260 << 4) | (SDIV_260))*/
#  define vMPLLCON_NOW_FAST	((MDIV_240 << 12) | (PDIV_240 << 4) | (SDIV_240))
/*#  define vMPLLCON_NOW_FAST	((MDIV_220 << 12) | (PDIV_220 << 4) | (SDIV_220))*/
/*#  define vMPLLCON_NOW_FAST	((MDIV_202 << 12) | (PDIV_202 << 4) | (SDIV_202))*/
#  define vMPLLCON_NOW_SLOW	((MDIV_202 << 12) | (PDIV_202 << 4) | (SDIV_202))
#  define vUPLLCON_NOW_USER	((MDIV_48 << 12) | (PDIV_48 << 4) | (SDIV_48))
# endif

#endif
/*
 * the actual reset code
 */

reset:
	/*
	 * set the cpu to SVC32 mode
	 */
	mrs	r0,cpsr
	bic	r0,r0,#0x1f
	orr	r0,r0,#0xd3
	msr	cpsr,r0

#if defined(CONFIG_S3C2410)
	
/* turn off the watchdog */
	ldr     r0, =pWTCON
	mov     r1, #0x0
	str     r1, [r0]

	/*
	 * mask all IRQs by setting all bits in the INTMR - default
	 */
	mov	r1, #0xffffffff
	ldr	r0, =INTMSK
	str	r1, [r0]
	ldr	r1, =0x7ff
	ldr	r0, =INTSUBMSK
	str	r1, [r0]            /*	bl	clock24x0_init*/

#endif


#if defined(CONFIG_SKIP_LOWLEVEL_INIT)	/* for Debug purposes, to halt CPU with Debugger */
	mov	r4, #0			@ wait
44:
	add	r4, r4, #0x1
	cmp	r4, #0xF00000
	blt	44b
#endif

#if !defined(A9M2410_0) && defined(CONFIG_A9M2410)
        /* prepare ports B, F to be read (also from lowlevel_init) */
	ldr	r0, =GPHDAT
	ldr	r1, [r0]
	orr	r1, r1, #0x100 	/* switch GPIO_ON# to high */
	str	r1, [r0]

	ldr	r0, =GPHCON
	ldr	r1, [r0]
	orr	r1, r1, #0x010000 /* switch GPIO_ON# to output */
	str	r1, [r0]

	ldr	r0, =GPHUP
	ldr	r1, [r0]
	orr	r1, r1, #0x100 	/* switch off GPIO_ON# pullup */
	str	r1, [r0]

	ldr	r0, =GPBCON
	mov	r1, #0x0
	str	r1, [r0]

	ldr	r0, =GPBUP
	mov	r1, #0x7
	str	r1, [r0]

	ldr	r0, =GPFDAT
	mov	r1, #0x0
	str	r1, [r0]

	ldr	r0, =GPFCON
	mov	r1, #0x00009000
	str	r1, [r0]

	ldr	r0, =GPFUP
	mov	r1, #0x000000FF
	str	r1, [r0]

	/* 
	 * Check if the boot is caused by the 
	 * wake-up from POWER_OFF mode 
	 */
	ldr	r0, =GSTATUS2
	ldr	r1, [r0]
	tst	r1, #0x2
	/*
	 * In case of the wake-up from POWER_OFF mode, 
	 * go to POWER_OFF_WAKEUP handler 
	 */
	bne 	Wakeup_Power_Off

	b	Normal_Start

Wakeup_Power_Off:

	/* Initialize the clock */
	bl	clock24x0_init

	/* Release SCLKn after wake-up from the POWER_OFF mode */
	ldr	r1, =MISCCR
	ldr	r0, [r1]
	bic	r0, r0, #(7<<17) /* SCLK0:0->SCLK, SCLK1:0->SCLK, SCKE:L->H */
	str	r0, [r1]
    
	/* Set memory control registers */
	bl	lowlevel_init

	mov	r1, #256
20:
	subs	r1, r1, #1 /*wait until the SelfRefresh is released */
	bne	20b 

	ldr	r0, =GPHDAT
	ldr	r1, [r0]
	and	r1, r1, #0xFFFFFEFF /* switch GPIO_ON# to low */
	str	r1, [r0]

	ldr	r1,= GSTATUS3 /*GSTATUS3 has the start address just after POWER_OFF wake-up */
	ldr	r0, [r1]
	mov	pc, r0
#endif

Normal_Start:

#if defined(CONFIG_SKIP_LOWLEVEL_INIT) && defined(CONFIG_A9M2410) /* for Debug purposes */

	bl	lowlevel_init
	mov	r1, #4096
21:
	subs	r1, r1, #1 /*wait until the SelfRefresh is released */
	bne	21b

#else
	/*
	 * we do sys-critical inits only at reboot,
	 * not when booting from ram!
	 */
#ifndef CONFIG_SKIP_LOWLEVEL_INIT	 
	bl	cpu_init_crit
#endif
#ifdef CONFIG_A9M2410
	mov	r4, #0			@ wait
4:
	add	r4, r4, #0x1
	cmp	r4, #0x300
	blt	4b
#endif	
#endif

#ifdef CONFIG_A9M2410
	bl	clock24x0_init
#endif

#ifndef CONFIG_SKIP_RELOCATE_UBOOT	
relocate:				/* relocate U-Boot to RAM	    */
	adr	r0, _start		/* r0 <- current position of code   */
	ldr	r1, _TEXT_BASE		/* test if we run from flash or RAM */
	cmp     r0, r1                  /* don't reloc during debug         */
	beq     stack_setup

	ldr	r2, _armboot_start
	ldr	r3, _bss_start
	sub	r2, r3, r2		/* r2 <- size of armboot            */
	add	r2, r0, r2		/* r2 <- source end address         */

# ifdef CONFIG_BOOT_NAND
	/* copy uboot from NAND to RAM */
	mov	r0, #0			@ start at first page
	bl	_nandboot

# else /* !CONFIG_BOOT_NAND */

copy_loop:
	ldmia	r0!, {r3-r10}		/* copy from source address [r0]    */
	stmia	r1!, {r3-r10}		/* copy to   target address [r1]    */
	cmp	r0, r2			/* until source end address [r2]    */
	ble	copy_loop

# endif /* CONFIG_BOOT_NAND */

#endif /* CONFIG_SKIP_RELOCATE_UBOOT */

	/* Set up the stack						    */
stack_setup:
	ldr	r0, _TEXT_BASE		/* upper 128 KiB: relocated uboot   */
	sub	r0, r0, #CFG_MALLOC_LEN	/* malloc area                      */
	sub	r0, r0, #CFG_GBL_DATA_SIZE /* bdinfo                        */
#ifdef CONFIG_USE_IRQ
	sub	r0, r0, #(CONFIG_STACKSIZE_IRQ+CONFIG_STACKSIZE_FIQ)
#endif
	sub	sp, r0, #12		/* leave 3 words for abort-stack    */

clear_bss:
	ldr	r0, _bss_start		/* find start of bss segment        */
	ldr	r1, _bss_end		/* stop here                        */
	mov 	r2, #0x00000000		/* clear                            */

clbss_l:str	r2, [r0]		/* clear loop...                    */
	add	r0, r0, #4
	cmp	r0, r1
	bne	clbss_l

	ldr	pc, _start_armboot

_start_armboot:	.word start_armboot

#ifdef CONFIG_A9M2410
.align 4
mpll_value_FAST:
        .long   vMPLLCON_NOW_FAST
mpll_value_SLOW:
        .long   vMPLLCON_NOW_SLOW
upll_value_USER:
        .long   vUPLLCON_NOW_USER
#endif        

/*
 *************************************************************************
 *
 * CPU_init_critical registers
 *
 * setup important registers
 * setup memory timing
 *
 *************************************************************************
 */

#ifndef CONFIG_SKIP_LOWLEVEL_INIT
cpu_init_crit:
	/*
	 * flush v4 I/D caches
	 */
	mov	r0, #0
	mcr	p15, 0, r0, c7, c7, 0	/* flush v3/v4 cache */
	mcr	p15, 0, r0, c8, c7, 0	/* flush v4 TLB */

	/*
	 * disable MMU stuff and caches
	 */
	mrc	p15, 0, r0, c1, c0, 0
	bic	r0, r0, #0x00002300	@ clear bits 13, 9:8 (--V- --RS)
	bic	r0, r0, #0x00000087	@ clear bits 7, 2:0 (B--- -CAM)
	orr	r0, r0, #0x00000002	@ set bit 2 (A) Align
	orr	r0, r0, #0x00001000	@ set bit 12 (I) I-Cache
	mcr	p15, 0, r0, c1, c0, 0


	/*
	 * before relocating, we have to setup RAM timing
	 * because memory timing is board-dependend, you will
	 * find a lowlevel_init.S in your board directory.
	 */
	mov	ip, lr
	bl	lowlevel_init
	mov	lr, ip

	mov	pc, lr
#endif
/*
 *************************************************************************
 *
 * Clock Initialization
 *
 *************************************************************************
 */

clock24x0_init:

#ifdef CONFIG_A9M2410
        /* read MCONF3 */
	ldr     r0, =GPFDAT
	ldr	r2, [r0]
	bic	r2, r2, #0xFFFFFFFD

	/* FCLK:HCLK:PCLK */
        @ initialize system clocks
	ldr	r0, =LOCKTIME
	ldr     r1, =0xffffff
	str     r1, [r0]

#ifndef CPU_2440
        ldr     r0, =CLKDIVN
        ldr     r1, =CLKDIVN_VAL_SLOW
# ifndef A9M2410_0
	cmp	r2, #0x2
	bne	clk2410_slow
	ldr	r1, =CLKDIVN_VAL_FAST
clk2410_slow:
# endif        
        str     r1, [r0]
#else
        /* FCLK:HCLK:PCLK */
	ldr	r0, =CAMDIVN
	ldr	r1, =CAMDIVN_VAL_FAST
	str	r1, [r0]
        ldr     r0, =CLKDIVN
        ldr     r1, =CLKDIVN_VAL_FAST
        str     r1, [r0]

	cmp	r2, #0x0
	bne	clk2440_fast

	ldr	r0, =CAMDIVN
	ldr	r1, =CAMDIVN_VAL_SLOW
	str	r1, [r0]
        ldr     r0, =CLKDIVN
        ldr     r1, =CLKDIVN_VAL_SLOW
        str     r1, [r0]

clk2440_fast:

#endif	/* CPU_2440 */

        mrc     p15, 0, r1, c1, c0, 0           @ read ctrl register
        orr     r1, r1, #0xc0000000             @ Asynchronous
        mcr     p15, 0, r1, c1, c0, 0           @ write ctrl register

	/* configure UPLL */
        ldr     r0, =UPLLCON
        ldr	r1, upll_value_USER
        str     r1, [r0]

	nop
	nop
	nop
	nop
	nop		@ wait until upll has the effect
	nop
	nop
	nop

	nop
	nop
	nop
	
        /* MPLL setup */
	ldr     r0, =MPLLCON
	ldr	r1, mpll_value_SLOW
#ifndef A9M2410_0
	cmp	r2, #0x2
	bne	mpll_slow
	
	ldr	r1, mpll_value_FAST
mpll_slow:	
#endif
	str     r1, [r0]
	nop
	nop
	nop
	nop
	nop		@ wait until upll has the effect
	nop
	nop
	nop

	nop
	nop
	nop

#endif	/* CONFIG_A9M2410 */

	mov	pc, lr

/*
 *************************************************************************
 *
 * Interrupt handling
 *
 *************************************************************************
 */

@
@ IRQ stack frame.
@
#define S_FRAME_SIZE	72

#define S_OLD_R0	68
#define S_PSR		64
#define S_PC		60
#define S_LR		56
#define S_SP		52

#define S_IP		48
#define S_FP		44
#define S_R10		40
#define S_R9		36
#define S_R8		32
#define S_R7		28
#define S_R6		24
#define S_R5		20
#define S_R4		16
#define S_R3		12
#define S_R2		8
#define S_R1		4
#define S_R0		0

#define MODE_SVC 0x13
#define I_BIT	 0x80

/*
 * use bad_save_user_regs for abort/prefetch/undef/swi ...
 * use irq_save_user_regs / irq_restore_user_regs for IRQ/FIQ handling
 */

	.macro	bad_save_user_regs
	sub	sp, sp, #S_FRAME_SIZE
	stmia	sp, {r0 - r12}			@ Calling r0-r12
	ldr	r2, _armboot_start
	sub	r2, r2, #(CONFIG_STACKSIZE+CFG_MALLOC_LEN)
	sub	r2, r2, #(CFG_GBL_DATA_SIZE+8)  @ set base 2 words into abort stack
	ldmia	r2, {r2 - r3}			@ get pc, cpsr
	add	r0, sp, #S_FRAME_SIZE		@ restore sp_SVC

	add	r5, sp, #S_SP
	mov	r1, lr
	stmia	r5, {r0 - r3}			@ save sp_SVC, lr_SVC, pc, cpsr
	mov	r0, sp
	.endm

	.macro	irq_save_user_regs
	sub	sp, sp, #S_FRAME_SIZE
	stmia	sp, {r0 - r12}			@ Calling r0-r12
	add     r8, sp, #S_PC
	stmdb   r8, {sp, lr}^                   @ Calling SP, LR
	str     lr, [r8, #0]                    @ Save calling PC
	mrs     r6, spsr
	str     r6, [r8, #4]                    @ Save CPSR
	str     r0, [r8, #8]                    @ Save OLD_R0
	mov	r0, sp
	.endm

	.macro	irq_restore_user_regs
	ldmia	sp, {r0 - lr}^			@ Calling r0 - lr
	mov	r0, r0
	ldr	lr, [sp, #S_PC]			@ Get PC
	add	sp, sp, #S_FRAME_SIZE
	subs	pc, lr, #4			@ return & move spsr_svc into cpsr
	.endm

	.macro get_bad_stack
	ldr	r13, _armboot_start		@ setup our mode stack
	sub	r13, r13, #(CONFIG_STACKSIZE+CFG_MALLOC_LEN)
	sub	r13, r13, #(CFG_GBL_DATA_SIZE+8) @ reserved a couple spots in abort stack

	str	lr, [r13]			@ save caller lr / spsr
	mrs	lr, spsr
	str     lr, [r13, #4]

	mov	r13, #MODE_SVC			@ prepare SVC-Mode
	@ msr	spsr_c, r13
	msr	spsr, r13
	mov	lr, pc
	movs	pc, lr
	.endm

	.macro get_irq_stack			@ setup IRQ stack
	ldr	sp, IRQ_STACK_START
	.endm

	.macro get_fiq_stack			@ setup FIQ stack
	ldr	sp, FIQ_STACK_START
	.endm

/*
 * exception handlers
 */
	.align  5
undefined_instruction:
	get_bad_stack
	bad_save_user_regs
	bl 	do_undefined_instruction

	.align	5
software_interrupt:
	get_bad_stack
	bad_save_user_regs
	bl 	do_software_interrupt

	.align	5
prefetch_abort:
	get_bad_stack
	bad_save_user_regs
	bl 	do_prefetch_abort

	.align	5
data_abort:
	get_bad_stack
	bad_save_user_regs
	bl 	do_data_abort

	.align	5
not_used:
	get_bad_stack
	bad_save_user_regs
	bl 	do_not_used

#ifdef CONFIG_USE_IRQ

	.align	5
irq:
	get_irq_stack
	irq_save_user_regs
	bl 	do_irq
	irq_restore_user_regs

	.align	5
fiq:
	get_fiq_stack
	/* someone ought to write a more effiction fiq_save_user_regs */
	irq_save_user_regs
	bl 	do_fiq
	irq_restore_user_regs

#else

	.align	5
irq:
	get_bad_stack
	bad_save_user_regs
	bl 	do_irq

	.align	5
fiq:
	get_bad_stack
	bad_save_user_regs
	bl 	do_fiq

#endif

#if 0
	.align	5
.globl reset_cpu
reset_cpu:
#ifdef CONFIG_S3C2400
	bl	disable_interrupts
# ifdef CONFIG_TRAB
	bl	disable_vfd
# endif
	ldr	r1, _rWTCON
	ldr	r2, _rWTCNT
	/* Disable watchdog */
	mov	r3, #0x0000
	str	r3, [r1]
	/* Initialize watchdog timer count register */
	mov	r3, #0x0001
	str	r3, [r2]
	/* Enable watchdog timer; assert reset at timer timeout */
	mov	r3, #0x0021
	str	r3, [r1]
_loop_forever:
	b	_loop_forever
_rWTCON:
	.word	0x15300000
_rWTCNT:
	.word	0x15300008
#else /* ! CONFIG_S3C2400 */
	mov     ip, #0
	mcr     p15, 0, ip, c7, c7, 0           @ invalidate cache
	mcr     p15, 0, ip, c8, c7, 0           @ flush TLB (v4)
	mrc     p15, 0, ip, c1, c0, 0           @ get ctrl register
	bic     ip, ip, #0x000f                 @ ............wcam
	bic     ip, ip, #0x2100                 @ ..v....s........
	mcr     p15, 0, ip, c1, c0, 0           @ ctrl register
	mov     pc, r0
#endif /* CONFIG_S3C2400 */
#endif
