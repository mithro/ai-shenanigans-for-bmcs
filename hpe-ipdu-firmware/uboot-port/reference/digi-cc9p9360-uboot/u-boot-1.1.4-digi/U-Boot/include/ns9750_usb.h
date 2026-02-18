/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: ns9750_usb.h,v 1.1 2005/01/12 13:05:26 jjaeger Exp $
 * @Author: Markus Pietrek
 * @Descr: Definitions for USB usage 
 * @References: [1] NS9750 Hardware Reference Manual/March 2004 Chap. 17
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
 *  
 ***********************************************************************/
/***********************************************************************
 *  @History:
 *     2004/11/26 : added NS_USB_MODULE_BASE_PA
 *                           USB Host Stuff
 *     2004/08/17 : removed addr_usb
 ***********************************************************************/

#ifndef FS_NS9750_USB_H
#define FS_NS9750_USB_H

#define NS_USB_MODULE_BASE	(0x90100000) /* physikal address */

/* the register addresses */

#define NS_USB_IEN			(NS_USB_MODULE_BASE + 0x0C)
#define NS_USB_ISTAT			(NS_USB_MODULE_BASE + 0x10)
#define NS_USB_HCR			(NS_USB_MODULE_BASE + 0x1000)
#define NS_USB_HCR_PORT_SAT	(NS_USB_MODULE_BASE + 0x1054)

/* register bit fields */

#define NS_USB_INT_GBL_EN 		(0x80000000)
#define NS_USB_INT_GBL_DMA 		(0x08000000)
#define NS_USB_INT_DMA_13 		(0x04000000)
#define NS_USB_INT_DMA_12		(0x02000000)
#define NS_USB_INT_DMA_11		(0x01000000)
#define NS_USB_INT_DMA_10		(0x00800000)
#define NS_USB_INT_DMA_9 		(0x00400000)
#define NS_USB_INT_DMA_8 		(0x00200000)
#define NS_USB_INT_DMA_7 		(0x00100000)
#define NS_USB_INT_DMA_6 		(0x00080000)
#define NS_USB_INT_DMA_5 		(0x00040000)
#define NS_USB_INT_DMA_4 		(0x00020000)
#define NS_USB_INT_DMA_3 		(0x00010000)
#define NS_USB_INT_DMA_2 		(0x00008000)
#define NS_USB_INT_DMA_1 		(0x00004000)
#define NS_USB_INT_FIFO	 		(0x00001000)
#define NS_USB_INT_URST	 		(0x00000800)
#define NS_USB_INT_SOF	 		(0x00000400)
#define NS_USB_INT_SUSPEND		(0x00000200)
#define NS_USB_INT_SETINF		(0x00000100)
#define NS_USB_INT_SETCFG		(0x00000080)
#define NS_USB_INT_WAKEUP		(0x00000040)
#define NS_USB_INT_OHCI_IRQ		(0x00000002)

/* the linux interrupt handler can only enable all DMA and all FIFO
 * interrupts. It is not yet possible to disable part of DMA's interrupts. */

#define NS_USB_INT_DMA_ALL		(NS_USB_INT_GBL_DMA | \
					 NS_USB_INT_DMA_13  | \
					 NS_USB_INT_DMA_12  | \
					 NS_USB_INT_DMA_11  | \
					 NS_USB_INT_DMA_10  | \
					 NS_USB_INT_DMA_9   | \
					 NS_USB_INT_DMA_8   | \
					 NS_USB_INT_DMA_7   | \
					 NS_USB_INT_DMA_6   | \
					 NS_USB_INT_DMA_5   | \
					 NS_USB_INT_DMA_4   | \
					 NS_USB_INT_DMA_3   | \
					 NS_USB_INT_DMA_2   | \
					 NS_USB_INT_DMA_1 )

#define NS_USB_INT_FIFO_ALL		(NS_USB_INT_FIFO    | \
					 NS_USB_INT_URST    | \
					 NS_USB_INT_SOF     | \
					 NS_USB_INT_SUSPEND | \
					 NS_USB_INT_SETINF  | \
					 NS_USB_INT_SETCFG  | \
					 NS_USB_INT_WAKEUP  | \
					 NS_USB_INT_OHCI_IRQ)
					 
#define NS_USB_INT_HOST		( NS_USB_INT_OHCI_IRQ )
#endif /* FS_NS9750_USB_H */
