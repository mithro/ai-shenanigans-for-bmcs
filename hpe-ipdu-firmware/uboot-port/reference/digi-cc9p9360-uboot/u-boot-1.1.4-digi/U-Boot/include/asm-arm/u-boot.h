/*
 * (C) Copyright 2002
 * Sysgo Real-Time Solutions, GmbH <www.elinos.com>
 * Marius Groeger <mgroeger@sysgo.de>
 *
 * (C) Copyright 2002
 * Sysgo Real-Time Solutions, GmbH <www.elinos.com>
 * Alex Zuepke <azu@sysgo.de>
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
 ********************************************************************
 * NOTE: This header file defines an interface to U-Boot. Including
 * this (unmodified) header file in another file is considered normal
 * use of U-Boot, and does *not* fall under the heading of "derived
 * work".
 ********************************************************************
 */

#ifndef _U_BOOT_H_
#define _U_BOOT_H_	1

typedef struct bd_info {
    int			bi_baudrate;	/* serial console baudrate */
    unsigned long	bi_ip_addr;	/* IP Address */
    unsigned char	bi_enetaddr[6]; /* Ethernet adress */
    struct environment_s	       *bi_env;
    ulong	        bi_arch_number;	/* unique id for this board */
    ulong	        bi_boot_params;	/* where this board expects params */
    struct				/* RAM configuration */
    {
	ulong start;
	ulong size;
    }bi_dram[CONFIG_NR_DRAM_BANKS];
#if defined (CONFIG_A9M2410) || defined (CONFIG_A9M9750) || \
    defined (CONFIG_A9M9750) || defined (CONFIG_A9M9360) || \
    defined (CONFIG_CC9C_NAND)
    struct				/* NAND Flash configuration */
    {
	ulong start;
	ulong size;
	char * name;
    }bi_nand[CONFIG_NR_NAND_PART];
#endif
#if defined (CONFIG_A9M2410) || defined (CONFIG_A9M9750) || \
    defined (CONFIG_A9M9360) || defined (CONFIG_CC9C) || defined (CONFIG_CCXP) || \
    defined (CONFIG_CCW9C)
    unsigned long	bi_gw_addr;	/* IP Address of gateway */
    unsigned long	bi_ip_mask;	/* IP mask */
    unsigned long	bi_dhcp_addr;	/* DHCP Address */
    unsigned long	bi_dns_addr;	/* DNS Address */
    int	bi_version; /* same CPLD, FPGA Version */ 
    unsigned long	uboot_env_addr;	/* Address of U-Boot environment */
#endif
} bd_t;

#define bi_env_data bi_env->data
#define bi_env_crc  bi_env->crc

#endif	/* _U_BOOT_H_ */
