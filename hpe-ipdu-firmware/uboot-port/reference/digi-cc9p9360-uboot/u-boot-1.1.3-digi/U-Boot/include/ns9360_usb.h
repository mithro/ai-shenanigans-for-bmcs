/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: ns9360_usb.h,v 1.1 2005-08-31 09:50:07 jdietsch Exp $
 * @Author: Jonas Dietsche
 * @Descr: Definitions for USB usage with u-boot
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
#ifndef FS_NS9360_USB_H
#define FS_NS9360_USB_H

#define NS_USB_MODULE_BASE	(0x90801000) /* physikal address */

#define NS_USB_HCR			(NS_USB_MODULE_BASE )
#define NS_USB_HCR_PORT_SAT	(NS_USB_MODULE_BASE + 0x54)


#endif /* FS_NS9360_USB_H */
