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

#include <ns9750_bbus.h>

#include <ns9750_sys.h>
#include <ns9750_mem.h>

#include <net.h>

#ifdef CC9CGNU
# include <i2c.h>
#endif

#ifdef CONFIG_STATUS_LED
# include <status_led.h>
#endif /* CONFIG_STATUS_LED */

void flash__init( void );

#ifdef CONFIG_CC9C_NAND
static ulong size;
#endif

#if defined(CONFIG_STATUS_LED)
static int status_led_fail = 0;
#endif /* CONFIG_STATUS_LED */

static inline void delay( unsigned long loops ) {
	__asm__ volatile ("1:\n"
		"subs %0, %1, #1\n"
		"bne 1b":"=r" (loops):"0" (loops));
}


/***********************************************************************
 * @Function: board_init
 * @Return: 0
 * @Descr: Enables BBUS modules and other devices
 ***********************************************************************/

int board_init( void ) {
	DECLARE_GLOBAL_DATA_PTR;

	/* set BOOTMUX to low */
	set_gpio_cfg_reg_val( 65, NS9750_GPIO_CFG_FUNC_GPIO|NS9750_GPIO_CFG_OUTPUT );
	/* Active BBUS modules */
	*get_bbus_reg_addr( NS9750_BBUS_MASTER_RESET ) = 0;

	/* arch number of CC9CJS */
	if (machine_is_cc9cjs())
		gd->bd->bi_arch_number = MACH_TYPE_CC9CJS;

	/* adress of boot parameters */
	gd->bd->bi_boot_params = 0x00000100;


#ifdef BOARD_LATE_INIT
	set_gpio_cfg_reg_val( 72, NS9750_GPIO_CFG_FUNC_GPIO | NS9750_GPIO_CFG_INPUT);
	set_gpio_cfg_reg_val( 69, NS9750_GPIO_CFG_FUNC_GPIO | NS9750_GPIO_CFG_INPUT);
#endif
	
#if defined(CONFIG_STATUS_LED)
	status_led_set(STATUS_LED_BOOT,STATUS_LED_ON);
#endif /* CONFIG_STATUS_LED */

/* this speeds up your boot a quite a bit.  However to make it
 *  work, you need make sure your kernel startup flush bug is fixed.
 *  ... rkw ...
 */
	icache_enable();

#ifndef CONFIG_CC9C_NAND
	flash__init();
#endif /*CONFIG_CC9C_NAND*/
	return 0;
}


int misc_init_r (void) {
	/* currently empty */
	return (0);
}

/******************************
 Routine:
 Description:
******************************/
#ifndef CONFIG_CC9C_NAND
void flash__init (void) {
	/* setup CS1 */
	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_BASE( 1 ) ) = 0x50000000;
  	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_MASK( 1 ) ) = 0xff000001;
	*get_mem_reg_addr( NS9750_MEM_STAT_CFG( 1 ) ) = NS9750_MEM_STAT_CFG_MW_16 | NS9750_MEM_STAT_CFG_PB;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_WEN( 1 ) ) = 0x2;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_OEN( 1 ) ) = 0x2;
	*get_mem_reg_addr( NS9750_MEM_STAT_RD( 1 ) ) = 0x6;
	*get_mem_reg_addr( NS9750_MEM_STAT_WR( 1 ) ) = 0x6;
}
#endif

/******************************
 Routine:
 Description:
******************************/
#ifdef CONFIG_CC9C_NAND
static ulong Get_SDRAM_Size(void) {
/* !!!This function is only working, if the correct SPI bootloader is used!!! */

	ulong base;

	base = (*get_sys_reg_addr(NS9750_SYS_CS_DYN_BASE(0)) & 0xFFFFF000);

	size = ~(*get_sys_reg_addr(NS9750_SYS_CS_DYN_MASK(0)) & 0xFFFFF000) + 1;

	base += size;

	if ((*get_sys_reg_addr(NS9750_SYS_CS_DYN_BASE(1)) & 0xFFFFF000) == base)
		size += size;	/* second bank equipped */

	return size;

}
#endif

int dram_init (void) {
	DECLARE_GLOBAL_DATA_PTR;

	gd->bd->bi_dram[0].start = PHYS_SDRAM_1;
#ifdef CONFIG_CC9C_NAND
	gd->bd->bi_dram[0].size = Get_SDRAM_Size();
#else
	gd->bd->bi_dram[0].size = PHYS_SDRAM_1_SIZE;
#endif

#if CONFIG_NR_DRAM_BANKS > 1
	gd->bd->bi_dram[1].start = PHYS_SDRAM_2;
	gd->bd->bi_dram[1].size = PHYS_SDRAM_2_SIZE;
#endif
	return 0;
}

#ifdef BOARD_LATE_INIT
int board_late_init (void) {
#ifdef CC9CGNU
	uchar iostatus;
#endif
	char flashsize[32];
	char cmd[10];

	DECLARE_GLOBAL_DATA_PTR;

# if (CONFIG_COMMANDS & CFG_CMD_NAND)
	char flashpartsize[32];
#  include <nand.h>
extern nand_info_t nand_info[CFG_MAX_NAND_DEVICE];

	 /* fill in the NAND partition info for bdinfo */
	gd->bd->bi_nand[0].name = (char *) NAND_NAME_0;
	gd->bd->bi_nand[0].start = NAND_START_0;
	gd->bd->bi_nand[0].size = NAND_SIZE_0;
	gd->bd->bi_nand[1].name = (char *) NAND_NAME_1;
	gd->bd->bi_nand[1].start = NAND_START_1;
	gd->bd->bi_nand[1].size = NAND_SIZE_1;
	gd->bd->bi_nand[2].name = (char *) NAND_NAME_2;
	gd->bd->bi_nand[2].start = NAND_START_2;
	gd->bd->bi_nand[2].size = NAND_SIZE_2;
	gd->bd->bi_nand[3].name = (char *) NAND_NAME_3;
	gd->bd->bi_nand[3].start = NAND_START_3;
	gd->bd->bi_nand[3].size = nand_info[0].size - NAND_START_3;

	vu_long *mem_addr;
	ulong value;

	mem_addr = (ulong *)NAND_ECC_INFO;
	value =  *mem_addr;	/* get ECC Info */
	
	if (value != 0x00) {
		printf("\n0x%x ECC errors occured and corrected\n\n", value);
#if defined(CONFIG_STATUS_LED)
		status_led_fail = 1;
#endif
	}

	/* added for use in u-boot macros */
	sprintf(flashsize, "%x", nand_info[0].size);
	sprintf(flashpartsize, "%x", gd->bd->bi_nand[3].size);
	setenv("flashpartsize", flashpartsize);
# else
extern flash_info_t flash_info[];	/* info for FLASH chips */
	
	/* added for use in u-boot macros */
	sprintf(flashsize, "%x", flash_info[0].size);

# endif /* CONFIG_CMD_NAND */

	setenv("flashsize", flashsize);

	gd->bd->bi_gw_addr = getenv_IPaddr ("gatewayip");
	gd->bd->bi_ip_mask = getenv_IPaddr ("netmask");
	gd->bd->bi_dhcp_addr = getenv_IPaddr ("serverip");
	gd->bd->bi_dns_addr = getenv_IPaddr ("dnsip");

	printf("CPU: %s @ %i.%iMHz\n\n", CPU, CPU_CLK_FREQ/1000000 , CPU_CLK_FREQ %1000000);

	 /* copy bdinfo to start of boot-parameter block */
 	memcpy((int*)gd->bd->bi_boot_params, gd->bd, sizeof(bd_t));

	/* init ethernet */
	if( eth_init( gd->bd ) <0 )
		puts("\ncould not initialize ethernet\n");

#if defined(CONFIG_USER_KEY)
#ifdef CC9CGNU
	i2c_read(0x21, 0, 0, &iostatus, 1);
	iostatus |= 0x42;
	i2c_write(0x21, 0, 0, &iostatus, 1);
	i2c_read(0x21, 0, 0, &iostatus, 1);

	if (!(iostatus & 0x40)) {
		printf("\nUser Key 1 pressed\n");
		if (getenv("key1") != NULL) {
			sprintf(cmd, "run key1");
			run_command(cmd, 0);
		}
	}
	if (!(iostatus & 0x02)) {
		printf("\nUser Key 2 pressed\n");
		if (getenv("key2") != NULL) {
			sprintf(cmd, "run key2");
			run_command(cmd, 0);
		}
	}
#else
	if (get_gpio_stat(72) == 0) {
		printf("\nUser Key 1 pressed\n");
		if (getenv("key1") != NULL) {
			sprintf(cmd, "run key1");
			run_command(cmd, 0);
		}
	}
	if (get_gpio_stat(69) == 0) {
		printf("\nUser Key 2 pressed\n");
		if (getenv("key2") != NULL) {
			sprintf(cmd, "run key2");
			run_command(cmd, 0);
		}
	}
#endif /* CC9CGNU */
#endif /* CONFIG_USER_KEY */

#if defined(CONFIG_STATUS_LED)
	if (!status_led_fail) {
		status_led_set(STATUS_LED_BOOT,STATUS_LED_OFF);
		status_led_fail = 0;
  	}
#endif /* CONFIG_STATUS_LED */
	
	return 0;
}
#endif /*BOARD_LATE_INIT*/

#ifdef CONFIG_SHOW_BOOT_PROGRESS
void show_boot_progress (int status) {
#if defined(CONFIG_STATUS_LED)
	if (status < 0) {
        	/* ready to transfer to kernel, make sure LED is proper state */
        	status_led_set(STATUS_LED_BOOT,STATUS_LED_ON);
        	status_led_fail = 1;
	}
#endif /* CONFIG_STATUS_LED */
}
#endif /* CONFIG_SHOW_BOOT_PROGRESS */

