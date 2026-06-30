/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: ns9750_i2c.h,v 1.3 2005/01/12 13:05:26 jjaeger Exp $
 * @Author: Markus Pietrek
 * @References: [1] NS9750 Hardware Reference, March 2004, Chap. 11
 * 		[2] Derives from linux/include/arch/arm/ns9750_i2c.h
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

#ifndef FS_NS9750_I2C_H
#define FS_NS9750_I2C_H

#define	NS_I2C_MODULE_BASE	 	(0x90500000) /* physical address */

#define get_i2c_reg_addr(c) \
     ((volatile unsigned int*) ( NS_I2C_MODULE_BASE+(unsigned int) (c)))

#define NS_I2C_DATA_TX			(0x00)
#define NS_I2C_DATA_RX			(0x00)
#define NS_I2C_MASTER			(0x04)
#define NS_I2C_SLAVE			(0x08)
#define NS_I2C_CFG			(0x0C)

/* register bit fields */

#define NS_I2C_DATA_TX_PIPE		(0x8000)
#define NS_I2C_DATA_TX_DLEN		(0x4000)
#define NS_I2C_DATA_TX_VAL		(0x2000)
#define NS_I2C_DATA_TX_CMD_MA		(0x1F00)
#define NS_I2C_DATA_TX_CMD_M_NOP	(0x0000)
#define NS_I2C_DATA_TX_CMD_M_READ	(0x0400)
#define NS_I2C_DATA_TX_CMD_M_WRITE	(0x0500)
#define NS_I2C_DATA_TX_CMD_M_STOP	(0x0600)
#define NS_I2C_DATA_TX_CMD_S_NOP	(0x1000)
#define NS_I2C_DATA_TX_CMD_S_STOP	(0x1600)
#define NS_I2C_DATA_TX_DATA_MA		(0x00FF)
#define NS_I2C_DATA_TX_CMD_SH		(0x08) /* shift value for CMD_MA */

#define NS_I2C_DATA_RX_BSTS		(0x8000)
#define NS_I2C_DATA_RX_RDE		(0x4000)
#define NS_I2C_DATA_RX_SCMDL		(0x2000)
#define NS_I2C_DATA_RX_MCMDL		(0x1000)
#define NS_I2C_DATA_RX_IRQCD_MA		(0x0F00)
#define NS_I2C_DATA_RX_IRQCD_NO_IRQ   	(0x0000) /* no single bit fields */
#define NS_I2C_DATA_RX_IRQCD_M_ARBIT	(0x0100)
#define NS_I2C_DATA_RX_IRQCD_M_NO_ACK	(0x0200)
#define NS_I2C_DATA_RX_IRQCD_M_TX_DATA	(0x0300)
#define NS_I2C_DATA_RX_IRQCD_M_RX_DATA	(0x0400)
#define NS_I2C_DATA_RX_IRQCD_M_CMD_ACK	(0x0500)
#define NS_I2C_DATA_RX_IRQCD_S_RX_ABORT	(0x0800)
#define NS_I2C_DATA_RX_IRQCD_S_CMD_REQ	(0x0900)
#define NS_I2C_DATA_RX_IRQCD_S_NO_ACK	(0x0A00)
#define NS_I2C_DATA_RX_IRQCD_S_TX_DATA1	(0x0B00)
#define NS_I2C_DATA_RX_IRQCD_S_RX_DATA1	(0x0C00)
#define NS_I2C_DATA_RX_IRQCD_S_TX_DATA	(0x0D00)
#define NS_I2C_DATA_RX_IRQCD_S_RX_DATA	(0x0E00)
#define NS_I2C_DATA_RX_IRQCD_S_CGA  	(0x0F00)
#define NS_I2C_DATA_RX_DATA_MA		(0x00FF)

#define NS_I2C_MASTER_MDA_MA		(0x07FE)
#define NS_I2C_MASTER_MAM		(0x0001)
#define NS_I2C_MASTER_MDA_SH		(0x01)

#define NS_I2C_SLAVE_GCA		(0x0800)
#define NS_I2C_SLAVE_SDA_MA		(0x07FE)
#define NS_I2C_SLAVE_SAM		(0x0001)
#define NS_I2C_SLAVE_SDA_SH		(0x01)

#define NS_I2C_CFG_IRQD			(0x8000)
#define NS_I2C_CFG_TMDE			(0x4000)
#define NS_I2C_CFG_VSCD			(0x2000)
#define NS_I2C_CFG_SFW_MA		(0x1E00)
#define NS_I2C_CFG_CLREF_MA		(0x01FF)
#define NS_I2C_CFG_SFW_SH		(0x09)

#endif /* FS_NS950_I2C_H */
