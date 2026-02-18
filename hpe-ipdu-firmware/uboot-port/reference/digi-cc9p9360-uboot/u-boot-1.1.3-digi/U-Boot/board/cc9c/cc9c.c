/*
 * (C) Copyright 2002
 * Sysgo Real-Time Solutions, GmbH <www.elinos.com>
 * Marius Groeger <mgroeger@sysgo.de>
 *
 * (C) Copyright 2002
 * David Mueller, ELSOFT AG, <d.mueller@elsoft.ch>
 *
 * (C) Copyright 2003
 * Texas Instruments, <www.ti.com>
 * Kshitij Gupta <Kshitij@ti.com>
 *
 * Copyright (C) 2005 by FS Forth-Systeme GmbH.
 * All rights reserved.
 * Jonas Dietsche <jdietsche@fsforth.de>
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

#include <common.h>

#include <./configs/cc9c.h>
#include <./ns9750_bbus.h>

#include <ns9750_sys.h>
#include <ns9750_mem.h>

#include <net.h>

void flash__init( void );

static inline void delay( unsigned long loops )
{
	__asm__ volatile ("1:\n"
		"subs %0, %1, #1\n"
		"bne 1b":"=r" (loops):"0" (loops));
}


/***********************************************************************
 * @Function: board_init
 * @Return: 0
 * @Descr: Enables BBUS modules and other devices
 ***********************************************************************/

int board_init( void )
{
	DECLARE_GLOBAL_DATA_PTR;

	/* set BOOTMUX to low */
	set_gpio_cfg_reg_val( 65, NS9750_GPIO_CFG_FUNC_GPIO|NS9750_GPIO_CFG_OUTPUT );
	/* Active BBUS modules */
	*get_bbus_reg_addr( NS9750_BBUS_MASTER_RESET ) = 0;
		
	/* arch number of NS9360 */
	gd->bd->bi_arch_number = 836;

	/* adress of boot parameters */
	gd->bd->bi_boot_params = 0x00000100;


/* this speeds up your boot a quite a bit.  However to make it
 *  work, you need make sure your kernel startup flush bug is fixed.
 *  ... rkw ...
 */
	icache_enable();

	flash__init();
	return 0;
}


int misc_init_r (void)
{
	/* currently empty */
	return (0);
}

/******************************
 Routine:
 Description:
******************************/
void flash__init (void)
{
	/* setup CS1 */
	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_BASE( 1 ) ) = 0x50000000;
  	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_MASK( 1 ) ) = 0xff000001;	
	*get_mem_reg_addr( NS9750_MEM_STAT_CFG( 1 ) ) = NS9750_MEM_STAT_CFG_MW_16 | NS9750_MEM_STAT_CFG_PB;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_WEN( 1 ) ) = 0x2;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_OEN( 1 ) ) = 0x2;
	*get_mem_reg_addr( NS9750_MEM_STAT_RD( 1 ) ) = 0x6;
	*get_mem_reg_addr( NS9750_MEM_STAT_WR( 1 ) ) = 0x6;
}

/******************************
 Routine:
 Description:
******************************/
int dram_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;

	gd->bd->bi_dram[0].start = PHYS_SDRAM_1;
	gd->bd->bi_dram[0].size = PHYS_SDRAM_1_SIZE;

#if CONFIG_NR_DRAM_BANKS > 1
	gd->bd->bi_dram[1].start = PHYS_SDRAM_2;
	gd->bd->bi_dram[1].size = PHYS_SDRAM_2_SIZE;
#endif
	return 0;
}

#if (CONFIG_COMMANDS & CFG_CMD_NAND)

#include <linux/mtd/nand.h>
extern struct nand_chip nand_dev_desc[ CFG_MAX_NAND_DEVICE ];

void nand_init( void )
{
	set_gpio_cfg_reg_val( NAND_BUSY_GPIO,
			      NS9750_GPIO_CFG_FUNC_GPIO | NS9750_GPIO_CFG_INPUT);

	nand_probe( CFG_NAND_BASE );
        if( nand_dev_desc[ 0 ].ChipID != NAND_ChipID_UNKNOWN )
                print_size( nand_dev_desc[0].totlen, "\n" );
}

#endif /* CONFIG_CMD_NAND */

#ifdef BOARD_LATE_INIT
int board_late_init (void)
{
	char flashsize[32];
	char flashpartsize[32];
	
	DECLARE_GLOBAL_DATA_PTR;

	gd->bd->bi_gw_addr = getenv_IPaddr ("gatewayip");
	gd->bd->bi_ip_mask = getenv_IPaddr ("netmask");
	gd->bd->bi_dhcp_addr = getenv_IPaddr ("serverip");
	gd->bd->bi_dns_addr = getenv_IPaddr ("dnsip");
	
	/* added for use in u-boot macros */ 
	sprintf(flashsize, "%x", PHYS_FLASH_SIZE);
	sprintf(flashpartsize, "%x", PHYS_FLASH_SIZE - 0x200000);
	setenv("flashsize", flashsize);
	setenv("flashpartsize", flashpartsize); 
	
	 /* copy bdinfo to start of boot-parameter block */
 	memcpy((int*)gd->bd->bi_boot_params, gd->bd, sizeof(bd_t));
	
	/* init ethernet */
	if( eth_init( gd->bd ) <0 )
		puts("\ncould not initialize ethernet\n");
		
	return 0;
}
#endif /*BOARD_LATE_INIT*/
