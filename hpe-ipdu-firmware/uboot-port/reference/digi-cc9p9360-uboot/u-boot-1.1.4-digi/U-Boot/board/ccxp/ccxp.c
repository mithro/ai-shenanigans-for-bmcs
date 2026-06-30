/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id:
 * @Author: Bernd Westermann
 * @Descr: CCXP270
 * @References:
 * @TODO:
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
/***********************************************************************
 *  @History:
 *	2005/09/08 : RC_1 (Bernd Westermann)
 *	2005/09/24 : USB, FAT, cleanup (Bernd Westermann)
 *	2005/10/24 : Added clean WCE bootargs signature (Pedro Perez)
 *	2005/10/24 : Added uboot_env_addr to bdi structure (Pedro Perez)
 ***********************************************************************/

#include <common.h>
#include <net.h>
#include <environment.h>


// SMC91x stuff
#define	BANK_SELECT		14
#define	CHIP_ID			0x09
#define	REV_REG			0x000A /* ( hi: chip id   low: rev # ) */

#define	SMC_inw(r) 		(*((volatile word *)(CONFIG_SMC91111_BASE+(r))))
#define	SMC_outw(d,r)		(*((volatile word *)(CONFIG_SMC91111_BASE+(r))) = d)
#define SMC_SELECT_BANK(x)  	{ SMC_outw( x, BANK_SELECT ); }

typedef unsigned short		word;
extern env_t *env_ptr;

int get_esa_1w(unsigned char *buffer);

/* ------------------------------------------------------------------------- */

/*
 * Miscelaneous platform dependent initialisations
 */

int board_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;

	/* memory and cpu-speed are setup before relocation */
	/* so we do _nothing_ here */

	/* arch number of CCXP270-Board */
	gd->bd->bi_arch_number = 825;

	/* adress of boot parameters */
	gd->bd->bi_boot_params = 0xa0000100;

	return 0;
}

int dram_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;

	vu_long *mem_addr1;
	long maxsize = 2 * PHYS_SDRAM_1_SIZE;
	mem_addr1 = (ulong *)CFG_MEMSIZE_START;
	gd->bd->bi_dram[0].start = PHYS_SDRAM_1;
	gd->bd->bi_dram[0].size = get_ram_size(mem_addr1, maxsize);
	return 0;
}

int board_late_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;

	char flashsize[32];
	char flashpartsize[32];
	volatile unsigned int *wce_bootargs = (volatile unsigned int *)0xa00ff000;
	unsigned char mac_data[8] = {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};
//	unsigned char hard_mac_data[8] = {0x00,0x04,0xF3,0x00,0x38,0x20,0x00,0x00};
	unsigned char mac_str[12];

	unsigned short old_bank;
	unsigned short revision_register;

	/* Clean Windows CE bootargs signature at address 0xa00ff000 */
	*wce_bootargs = 0;

	printf ("\n");

	// Detect presence of SMSC LAN91C111 Chip
	printf ("Detecting SMSC LAN91C111 Ethernet Controller...\n");

	// We want to read the version register, so we have to switch to BANK 3
	old_bank = SMC_inw(BANK_SELECT)&0xF; 	// save old bank register
	SMC_SELECT_BANK(3);			// go to bank 3 for reading revision register

	revision_register = SMC_inw(REV_REG)&0xFF;	// read revision register

	printf ("Revision ID: 0x%02X\n", (revision_register&0x0F));
	printf ("Chip ID: 0x%02X\n", (revision_register>>4)&0x0F);

	if (((revision_register>>4)&0x0F) == CHIP_ID)
	{
		printf ("SMSC LAN91C111 detected...\n");
	}

	SMC_SELECT_BANK(old_bank);

/*	if (set_esa_1w(hard_mac_data))
		{
		}
	else
		{
			printf ("Set MAC Address to 1-wire EEPROM aborted !!!\n");
			return 0;
		}

*/

	if (get_esa_1w(mac_data))
	{
		printf ("Get MAC Address from 1-wire EEPROM\n");
	}
	else
	{
		printf ("Get MAC Address from 1-wire EEPROM aborted !!!\n");
		return 0;
	}

	printf ("MAC Address from EEPROM : %02X:%02X:%02X:%02X:%02X:%02X \n",mac_data[0], mac_data[1], mac_data[2], mac_data[3], mac_data[4], mac_data[5]);

	gd->bd->bi_gw_addr = getenv_IPaddr ("gatewayip");
	gd->bd->bi_ip_mask = getenv_IPaddr ("netmask");
	gd->bd->bi_dhcp_addr = getenv_IPaddr ("serverip");
	gd->bd->bi_dns_addr = getenv_IPaddr ("dnsip");
	gd->bd->uboot_env_addr = (unsigned long)env_ptr;

	/* added for use in u-boot macros */
	sprintf(flashsize, "%x", PHYS_FLASH_SIZE);
	sprintf(flashpartsize, "%x", PHYS_FLASH_SIZE - 0x300000);
	setenv("flashsize", flashsize);
	setenv("flashpartsize", flashpartsize);

	/* copy bdinfo to start of boot-parameter block */
	memcpy((ulong *)gd->bd->bi_boot_params, gd->bd, sizeof(bd_t));

	printf ("Initializing ethernet...\n");
	if( eth_init( gd->bd ) <0 )
		printf("\nCould not initialize ethernet\n");

	sprintf (mac_str, "%02X:%02X:%02X:%02X:%02X:%02X",mac_data[0], mac_data[1], mac_data[2], mac_data[3], mac_data[4], mac_data[5]);
	setenv("ethaddr", mac_str);

	return 0;
}
