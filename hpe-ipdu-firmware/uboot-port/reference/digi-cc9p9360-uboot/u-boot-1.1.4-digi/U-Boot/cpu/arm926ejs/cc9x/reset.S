/*
 *  armboot - Startup Code for ARM926EJS CPU-core
 *
 *  Copyright (c) 2003  Texas Instruments
 *
 *  ----- Adapted for OMAP1610 OMAP730 from ARM925t code ------
 *
 *  Copyright (c) 2001	Marius Gröger <mag@sysgo.de>
 *  Copyright (c) 2002	Alex Züpke <azu@sysgo.de>
 *  Copyright (c) 2002	Gary Jennejohn <gj@denx.de>
 *  Copyright (c) 2003	Richard Woodruff <r-woodruff2@ti.com>
 *  Copyright (c) 2003	Kshitij <kshitij@ti.com>
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
#include <./ns9750_sys.h>

	.align	5
.globl reset_cpu
reset_cpu:
#if defined(CONFIG_CC9C)
	/* On CC9C, IO65 is used as BOOTMUX.  As SRESET doesn't reset the GPIO
	 * configurations, set IO65's to it's reset value (i.e. 0x3 = GPIO
	 * input) explicitly first. */
	ldr	r1, gpio65cfgreg
	ldr	r2, [r1]
	bic	r2, r2, #0xf0
	orr	r2, r2, #0x30
	str	r2, [r1]
#endif /* defined(CONFIG_CC9C) */

	/* performs a reset by writing current configuration in PLL */
	ldr	r1, pll_ctrl
	ldr	r2, [r1]
	mov	r2, r2, lsr #16
	orr	r2, r2, #0x8000
	str	r2, [r1]
_loop_forever:
	b	_loop_forever

gpio65cfgreg:
	.word	0x90600104 /* GPIO Configuration Register #9 */
pll_ctrl:
	.word	(NS9750_SYS_MODULE_BASE+NS9750_SYS_PLL)
