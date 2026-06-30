/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: ns9750_nand.h,v 1.2 2005-09-13 13:18:16 jdietsch Exp $
 * @Author: Markus Pietrek
 * @Descr: Implements commands for accessing memory mapped NAND Flash on NS9750
 *         derivates. Requires PHYS_NAND_FLASH defined.
 *         Currently only one NAND is supported.
 * @References: [1] doc/README.nand
 *              [2] common/cmd_nand.c
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

#ifndef FS_NS9750_NAND_H
#define FS_NS9750_NAND_H

#include <ns9750_bbus.h>

#define CFG_MAX_NAND_DEVICE	1 /* Max number of flash devices */

#ifndef CONFIG_CC9C_NAND
#define NAND_FLASH_DAT	(0x0000) /* Data Read/Write */
#define NAND_FLASH_ADR	(0x2000) /* Adr Write */
#define NAND_FLASH_CMD	(0x4000) /* Cmd Write */
#else
#define NAND_FLASH_DAT	0x00000000 /* Data Read/Write */
#define NAND_FLASH_ADR	0x00008000 /* Adr Write */
#define NAND_FLASH_CMD	0x00010000 /* Cmd Write */
#endif /*CONFIG_CC9C_NAND */

#define CFG_NAND_CE
#define CFG_NAND_CLE
#define CFG_NAND_ALE
#define CFG_NAND_RDY

#define NAND_WAIT_READY( nand ) do { } while( !get_gpio_stat( NAND_BUSY_GPIO ) )

#define WRITE_NAND_COMMAND( d, adr ) do { \
		*((volatile unsigned char*) (adr+NAND_FLASH_CMD)) = d; \
		 } while( 0 );

#define WRITE_NAND_ADDRESS( d, adr ) do { \
		*((volatile unsigned char*) (adr+NAND_FLASH_ADR)) = d; \
		 } while( 0 );

#define WRITE_NAND( d, adr ) do { \
		*((volatile unsigned char*) (adr+NAND_FLASH_DAT)) = d; \
		 } while( 0 );

#define READ_NAND( adr ) ((unsigned char)(*(volatile unsigned char*)	\
					  (adr + NAND_FLASH_DAT)))

#define NAND_DISABLE_CE( nand )
#define NAND_ENABLE_CE( nand )
#define NAND_CTL_CLRALE( nandptr )
#define NAND_CTL_SETALE( nandptr )
#define NAND_CTL_CLRCLE( nandptr )
#define NAND_CTL_SETCLE( nandptr )

/* taken from [1] */
#ifndef CONFIG_CC9C_NAND
#define SECTORSIZE 			512
#define ADDR_COLUMN 		1
#define ADDR_PAGE 			2
#define ADDR_COLUMN_PAGE 	3
#define NAND_ChipID_UNKNOWN 	0x00
#define NAND_MAX_FLOORS 		1
#define NAND_MAX_CHIPS		1
#else
#define SECTORSIZE 			2048
#define ADDR_COLUMN 		2
#define ADDR_PAGE 			3
#define ADDR_COLUMN_PAGE 	5
#define NAND_ChipID_UNKNOWN 	0x00
#define NAND_MAX_FLOORS 		1
#define NAND_MAX_CHIPS		1
#endif /*CONFIG_CC9C_NAND */
#endif /* FS_NS9750_NAND_H */
