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
 * Copyright (C) 2004-2005 by FS Forth-Systeme GmbH.
 * All rights reserved.
 * Markus Pietrek <mpietrek@fsforth.de>
 * derived from omap1610innovator.c
 * @References: [1] NS9750 Hardware Reference/December 2003
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

#include <ns9750_bbus.h>
#include <ns9750_mem.h>
#include <ns9750_sys.h>
#include <net.h>

void flash__init( void );
void ether__init( void );
int cs_init ( void );

static ulong size;

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

	/* Active BBUS modules */
	*get_bbus_reg_addr( NS9750_BBUS_MASTER_RESET ) = 0;

#ifdef CONFIG_A9M9750		
	/* arch number of NS9750 */
	gd->bd->bi_arch_number = 699;
#endif

#ifdef CONFIG_A9M9360
	/* arch number of NS9360 */
	gd->bd->bi_arch_number = 700;
#endif
	
	/* adress of boot parameters */
	gd->bd->bi_boot_params = 0x00000100;
	
	/* set to 1 to boot proper */
	gd->bd->bi_version = 1;

/* this speeds up your boot a quite a bit.  However to make it
 *  work, you need make sure your kernel startup flush bug is fixed.
 *  ... rkw ...
 */
	icache_enable();

	flash__init();
	ether__init();
#ifdef CONFIG_A9M9750DEV
	cs_init();
#endif /* CONFIG_A9M9750DEV */
	return 0;
}

 
static ulong Get_SDRAM_Size(void)
{
/* !!!This function is only working, if the correct SPI bootloader is used!!! */
        
	ulong base;
	
	base = (*get_sys_reg_addr(NS9750_SYS_CS_DYN_BASE(0)) & 0xFFFFF000);

	size = ~(*get_sys_reg_addr(NS9750_SYS_CS_DYN_MASK(0)) & 0xFFFFF000) + 1;
	
	base += size;

	if ((*get_sys_reg_addr(NS9750_SYS_CS_DYN_BASE(1)) & 0xFFFFF000) == base)
		size += size;	/* second bank equipped */

	return size;		

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
}
/*************************************************************
 Routine:ether__init
 Description: take the Ethernet controller out of reset and wait
	  		   for the EEPROM load to complete.
*************************************************************/
void ether__init (void)
{
}

/***********************************************************************
 * @Function: cs_init
 * @Return: 0
 * @Descr: initializes the chip selects (only ifdef CONFIG_A9M9750DEV)
 ***********************************************************************/
int cs_init( void )
{
	/* setup CS0 */
	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_BASE( 0 ) ) = 0x40000000;
  	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_MASK( 0 ) ) = 0xfffff001;	
	*get_mem_reg_addr( NS9750_MEM_STAT_CFG( 0 ) ) = NS9750_MEM_STAT_CFG_MW_8 | NS9750_MEM_STAT_CFG_PB;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_WEN( 0 ) ) = 0x2;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_OEN( 0 ) ) = 0x2;
	*get_mem_reg_addr( NS9750_MEM_STAT_RD( 0 ) ) = 0x6;
	*get_mem_reg_addr( NS9750_MEM_STAT_WR( 0 ) ) = 0x6;
	
	/* setup CS2 */
	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_BASE( 2 ) ) = 0x60000000;
  	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_MASK( 2 ) ) = 0xff000001;	
	*get_mem_reg_addr( NS9750_MEM_STAT_CFG( 2 ) ) = NS9750_MEM_STAT_CFG_MW_16 | NS9750_MEM_STAT_CFG_PB;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_WEN( 2 ) ) = 0x2;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_OEN( 2 ) ) = 0x2;
	*get_mem_reg_addr( NS9750_MEM_STAT_RD( 2 ) ) = 0x6;
	*get_mem_reg_addr( NS9750_MEM_STAT_WR( 2 ) ) = 0x6;

#if defined(CONFIG_A9M9360) && defined(CONFIG_A9M9750DEV)
	set_gpio_cfg_reg_val(66, NS9750_GPIO_CFG_FUNC_0 | NS9750_GPIO_CFG_OUTPUT);
	set_gpio_cfg_reg_val(67, NS9750_GPIO_CFG_FUNC_0 | NS9750_GPIO_CFG_OUTPUT);
	set_gpio_cfg_reg_val(68, NS9750_GPIO_CFG_FUNC_0 | NS9750_GPIO_CFG_OUTPUT);
	set_gpio_cfg_reg_val(69, NS9750_GPIO_CFG_FUNC_0 | NS9750_GPIO_CFG_OUTPUT);
#endif
	
	return 0;
}

/**********************************************************************
 * @Function: dev_board_info
 * @Return: nothing
 * @Descr: prints some info about the A9M9750DEV board
 ***********************************************************************/
void dev_board_info( void )
{
#ifdef CONFIG_A9M9750DEV
	DECLARE_GLOBAL_DATA_PTR;
	
	uchar cpldlvr;
	uchar fpgalvr;
	uchar bvr;
	int i;

	/* wait 500ms for FPGA */
	udelay( 500000 );
		
	cpldlvr = *((volatile uchar *)0x40000040);
	fpgalvr = *((volatile uchar *)0x60000010);
	bvr = *((volatile uchar *)0x60000000);

	printf("for FS Forth-Systeme " MODULE_STRING " module on A9M9750DEV_%i board\n", ( bvr >> 4 ) & 0xF );
	
	if( cpldlvr != fpgalvr )
	{
		puts("***************************************************************************\n");
		printf("The logic Version of the CPLD and FPGA differ\n"
			 "Please update to the same Versions\n"
			 "CPLD Version: %i.%i\n"
			 "FPGA Version: %i.%i\n", (cpldlvr >> 4) & 0xF, cpldlvr & 0xF, (fpgalvr >> 4) & 0xF, fpgalvr & 0xF );
		puts("***************************************************************************\n");
		
		gd->bd->bi_version = 0;	
	}
	else
	{
		gd->bd->bi_version = 1;
		printf("CPLD Version: %i.%i\n"
			 "FPGA Version: %i.%i\n\n", (cpldlvr >> 4) & 0xF, cpldlvr & 0xF, (fpgalvr >> 4) & 0xF, fpgalvr & 0xF );
	}
#else
	printf("for FS Forth-Systeme " MODULE_STRING " module on undefined board\n");
#endif /*CONFIG_A9M9750DEV*/
}

/******************************
 Routine:
 Description:
******************************/
int dram_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;

	gd->bd->bi_dram[0].start = PHYS_SDRAM_1;
	gd->bd->bi_dram[0].size = Get_SDRAM_Size();

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
	DECLARE_GLOBAL_DATA_PTR;
	set_gpio_cfg_reg_val( NAND_BUSY_GPIO,
			      NS9750_GPIO_CFG_FUNC_GPIO | NS9750_GPIO_CFG_INPUT);

	nand_probe( CFG_NAND_BASE );
        if( nand_dev_desc[ 0 ].ChipID != NAND_ChipID_UNKNOWN )
                printf ("%4lu MB\n", nand_dev_desc[0].totlen >> 20);
		
	 /* fill in the NAND partition info for bdinfo */
	gd->bd->bi_nand[0].name = (char *) NAND_NAME_0;
	gd->bd->bi_nand[0].start = NAND_START_0;
	gd->bd->bi_nand[0].size = NAND_SIZE_0;
	gd->bd->bi_nand[1].name = (char *) NAND_NAME_1;
	gd->bd->bi_nand[1].start = NAND_START_1;
	gd->bd->bi_nand[1].size = NAND_SIZE_1;
	gd->bd->bi_nand[2].name = (char *) NAND_NAME_2;
	gd->bd->bi_nand[2].start = NAND_START_2;
	gd->bd->bi_nand[2].size = nand_dev_desc[0].totlen - NAND_START_2;
}

#endif /* CONFIG_CMD_NAND */

#ifdef BOARD_LATE_INIT
int board_late_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;
	char cmd[60];
	char flashsize[32];
	char flashpartsize[32];
	set_gpio_cfg_reg_val( 45, NS9750_GPIO_CFG_FUNC_GPIO | NS9750_GPIO_CFG_INPUT);
	set_gpio_cfg_reg_val( 46, NS9750_GPIO_CFG_FUNC_GPIO | NS9750_GPIO_CFG_INPUT);
	
	gd->bd->bi_gw_addr = getenv_IPaddr ("gatewayip");
	gd->bd->bi_ip_mask = getenv_IPaddr ("netmask");
	gd->bd->bi_dhcp_addr = getenv_IPaddr ("serverip");
	gd->bd->bi_dns_addr = getenv_IPaddr ("dnsip");
	
	/* added for use in u-boot macros */ 
	sprintf(flashsize, "%x", nand_dev_desc[0].totlen);
	sprintf(flashpartsize, "%x", gd->bd->bi_nand[2].size);
	setenv("flashsize", flashsize);
	setenv("flashpartsize", flashpartsize);
	
	printf("CPU:   %s @%i.%iMHz\n\n", CPU, CPU_CLK_FREQ/1000000 , CPU_CLK_FREQ %1000000);
	 
	 /* copy bdinfo to start of boot-parameter block */
 	memcpy((int*)gd->bd->bi_boot_params, gd->bd, sizeof(bd_t));
	
	if( gd->bd->bi_version == 0 )
	{
		/* we don't want to boot with wrong settings.. */
		run_command("setenv bootcmd", 0);
		printf("\nautoboot disabled due to CPLD/FPGA Version mismatch\n");
	}
	else
	{	
		if (get_gpio_stat(45) == 0)
		{
			printf("\nUser Key 1 pressed\n");
			if (getenv("key1") != NULL)
			{
				sprintf(cmd, "run key1");
				run_command(cmd, 0);
			}
	
		}
		if (get_gpio_stat(46) == 0)
		{
			printf("\nUser Key 2 pressed\n");
			if (getenv("key2") != NULL)
			{
				sprintf(cmd, "run key2");
				run_command(cmd, 0);
			}
		}
	}
	
	if( eth_init( gd->bd ) <0 )
		puts("\ncould not initialize ethernet\n");
		
	return 0;
}
#endif /*BOARD_LATE_INIT*/
