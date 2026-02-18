/*
 * (C) Copyright 2003
 * David Müller ELSOFT AG Switzerland. d.mueller@elsoft.ch
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

/************************************************
 * NAME	    : s3c2440.h
 * Version  : 2004.
 *
 ************************************************/

#ifndef __S3C2440_H__
#define __S3C2440_H__

#define S3C24X0_SPI_CHANNELS	2

/* include common stuff */
#include <s3c24x0.h>

#define NFDATA8			(*(volatile unsigned char *)0x4E000010)
#define NFDATA16		(*(volatile unsigned short *)0x4E000010)
#define NFDATA32		(*(volatile unsigned *)0x4E000010)

/* S3C2440 only supports 512 Byte HW ECC */
#define S3C2440_ECCSIZE		512
#define S3C2440_ECCBYTES	3

#define NAND_OOB_SIZE           (16)
#define NAND_PAGES_IN_BLOCK     (32)
#define NAND_PAGE_SIZE          (512)

#define NAND_BLOCK_SIZE         (NAND_PAGE_SIZE*NAND_PAGES_IN_BLOCK)
#define NAND_BLOCK_MASK         (NAND_BLOCK_SIZE - 1)
#define NAND_PAGE_MASK          (NAND_PAGE_SIZE - 1)

#undef HW_ECC_2440


#endif /*__S3C2440_H__*/
