/*
 * Copyright (C) 2005 by FS Forth-Systeme GmbH.
 * All rights reserved.
 * Jonas Dietsche <jdietsche@fsforth.de>
 *
 * Configuation settings for the FS Forth-Systeme GmbH's A9M9750 Module
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

#ifndef __CONFIG_H
#define __CONFIG_H

#include <asm-arm/sizes.h>
#include <ns9750_sys.h>
#include <configs/digi_common.h>
#include <configs/userconfig.h>

#define CONFIG_GCC41	1

#define CONFIG_MISC_INIT_R	1	/* call misc_init_r()           */

#if 0
#define CONFIG_MTD_DEBUG 1
#define CONFIG_MTD_DEBUG_VERBOSE 3
#endif

/*
 * If we are developing, we might want to start armboot from ram
 * so we MUST NOT initialize critical regs like mem-timing ...
 */
/* define for developing */
#undef	CONFIG_SKIP_LOWLEVEL_INIT

/* FPGA Firmware load... */
#define CONFIG_FPGA_COUNT	1
#define CONFIG_FPGA_LOAD	1
#define LOAD_FPGA_OK		0
#define LOAD_FPGA_FAIL		1

/*
 * High Level Configuration Options
 * (easy to change)
 */
#define CONFIG_ARM926EJS	1	/* This is an ARM926EJS Core	*/
#define CONFIG_NS9360		1	/* in an NetSilicon NS9360 SoC     */
#define CONFIG_CCW9C		1
#define CPU	"NS9360"
#define CONFIG_MACH_CCW9CJS		/* Select board mach-type */
#define BOARD_LATE_INIT		1	/* Enables initializations before jumping to main loop */
#define CRYSTAL 294912
#define PLLFS		((*get_sys_reg_addr( NS9750_SYS_PLL ) >>0x17 ) & 0x3)
#define PLLND		((*get_sys_reg_addr( NS9750_SYS_PLL ) >>0x10 ) & 0x1f)

/* will be defined in include/configs when you make the config */
/*#define CONFIG_CC9C_NAND*/

#ifdef CONFIG_CC9C_NAND
#define CONFIG_BOOT_NAND	1
#define CFG_NO_FLASH		1	/* No NOR-Flash available */
#define PLATFORM	"nand"
#define EBOOTFLADDR	"280000"
#define WCEFLADDR	"380000"
#define FPGAFLADDR	"180000"
#define CONFIG_BOOTFILE	"uImage-ccw9cjsnand"
#define NAND_WAIT_READY( nand ) udelay(25)		/* 2KiB flash have 25 us */
#else
#define CFG_FLASH_CFI		/* The flash is CFI compatible	*/
#define CFG_FLASH_CFI_DRIVER	/* Use common CFI driver	*/
#define PLATFORM	"nor"
#define EBOOTFLADDR	"501C0000"
#define WCEFLADDR	"502C0000"
#define FPGAFLADDR	"500C0000"
#define CONFIG_BOOTFILE	"uImage-ccw9cjsnor"
#endif /*CONFIG_CC9C_NAND*/

#define NS9750_ETH_PHY_ADDRESS	(0x0001)
/*#define CONFIG_SYS_CLK_FREQ	309657600 */	/*154.8288MHz*/
/*#define CONFIG_SYS_CLK_FREQ	353894400 */ /*176.9472MHz*/

#define CONFIG_SYS_CLK_FREQ (100*CRYSTAL * (PLLND +1) / (1<<PLLFS))

#define CPU_CLK_FREQ		(CONFIG_SYS_CLK_FREQ/2)
#define AHB_CLK_FREQ		(CONFIG_SYS_CLK_FREQ/4)
#define BBUS_CLK_FREQ		(CONFIG_SYS_CLK_FREQ/8)

#undef CONFIG_USE_IRQ			/* we don't need IRQ/FIQ stuff */


/*
 * Size of malloc() pool
 */
#define CFG_MALLOC_LEN		(256*1024)
#define CFG_GBL_DATA_SIZE       256     /* size in bytes reserved for initial data */


/************************************************************
 * Activate LEDs while booting
 ************************************************************/
#define CONFIG_STATUS_LED	1
#define CONFIG_CC9C_LED		1
#define	CONFIG_SHOW_BOOT_PROGRESS	1	/* Show boot progress on LEDs	*/

#define CFG_NS9750_UART			1	/* use on-chip UART */
#define CONFIG_DRIVER_NS9750_ETHERNET	1	/* use on-chip ethernet */

/* USB related stuff */
#define LITTLEENDIAN	1						/* necessary for USB */
#define CONFIG_USB_OHCI 1
#define CONFIG_DOS_PARTITION 1
#define CONFIG_USB_STORAGE 1

/*
 * select serial console configuration
 */
#if !defined(CONFIG_CONS_INDEX)
# define CONFIG_CONS_INDEX	1	/*0= Port B; 1= Port A; 2= Port C; 3=Port D */
#endif

#define CONFIG_BAUDRATE		38400

#define CONFIG_SILENT_RESCUE	1
#ifdef CONFIG_SILENT_CONSOLE
# define CFG_SET_SILENT		"yes"
#else
# define CFG_SET_SILENT		"no"
#endif

/* allow to overwrite serial and ethaddr */
#define CONFIG_ENV_OVERWRITE

#define	CFG_DIGI_ENVIRONMENT

#define	CONFIG_DIGI_CMD	1		/* enables DIGI board specific commands */

/***********************************************************
 * Command definition
 ***********************************************************/
#ifdef CONFIG_CC9C_NAND
#define CONFIG_COMMANDS ( \
         CONFIG_COMMANDS_DIGI | \
/*	 CFG_CMD_MII	 |*/	\
	 CFG_CMD_NAND    | \
         0 )
#else
#define CONFIG_COMMANDS ( \
         CONFIG_COMMANDS_DIGI | \
	 CFG_CMD_FLASH	 |	\
/*	 CFG_CMD_MII	 |*/	\
         0 )
#endif	/* CONFIG_CC9C_NAND */

/************************************************************
 * CCW9C default environment settings
 ************************************************************/
#define CONFIG_EXTRA_ENV_SETTINGS			\
	"std_bootarg=console=ttyS1,38400\0"		\
	"silent="CFG_SET_SILENT"\0"			\
	"uimg=u-boot-ccw9cjs"PLATFORM".bin\0"		\
	"rimg=rootfs-ccw9cjs"PLATFORM".jffs2\0"		\
	"kimg=uImage-ccw9cjs"PLATFORM"\0"		\
	"eimg=eboot-cc9x\0"				\
	"fimg=wifi.bit\0"				\
	"fpgasize=6263f\0"				\
	"wimg=wce-cc9x\0"				\
	"loadaddr=200000\0"				\
	"wceloadaddr=2C0000\0"				\
	"ebootaddr=200000\0"				\
	"ebootfladdr="EBOOTFLADDR"\0"			\
	"wcefladdr="WCEFLADDR"\0"			\
	"npath=/exports/nfsroot-ccw9cjs"PLATFORM"\0"	\
	"smtd=setenv bootargs ${std_bootarg} ip=${ipaddr}:${serverip}::${netmask}:9360:eth0:off root=/dev/mtdblock4 rootfstype=jffs2\0"	\
	"snfs=setenv bootargs ${std_bootarg} ip=${ipaddr}:${serverip}::${netmask}:9360:eth0:off root=nfs nfsroot=${serverip}:${npath}\0"


/* this must be included AFTER the definition of CONFIG_COMMANDS (if any) */
#include <cmd_confdefs.h>

#define CONFIG_BOOTDELAY		4
#define CONFIG_ZERO_BOOTDELAY_CHECK	/* check for keypress on bootdelay==0 */

/* ====================== NOTE ========================= */
/* The following default ethernet MAC address was selected
 * so as to not collide with any known production device.
 */
#define CONFIG_ETHADDR		00:04:f3:ff:ff:fb /*@TODO unset */
#define CONFIG_NETMASK		255.255.255.0
#define CONFIG_IPADDR		192.168.42.30
#define CONFIG_SERVERIP		192.168.42.1
#define CONFIG_GATEWAYIP	192.168.42.1

#define CONFIG_CMDLINE_TAG	1 /* passing of ATAGs */
#define CONFIG_INITRD_TAG	1
#define CONFIG_SETUP_MEMORY_TAGS 1

#define CONFIG_BOOTCOMMAND	"dboot linux flash"

/*
 * Miscellaneous configurable options
 */
#define	CFG_LONGHELP				/* undef to save memory		*/
#define	CFG_PROMPT		"CCW9C # "	/* Monitor Command Prompt	*/
#if !defined(VERSION_TAG)
# define VERSION_TAG		" FS.2-rc2"	/* patched u-boot version from FS */
#endif
#define MODULE_STRING		"ConnectCoreWi9C"
#define CONFIG_IDENT_STRING	" " VERSION_TAG "\nfor DIGI " MODULE_STRING " on Jump Start Board"

#define	CFG_CBSIZE		256		/* Console I/O Buffer Size	*/
#define	CFG_PBSIZE (CFG_CBSIZE+sizeof(CFG_PROMPT)+16) /* Print Buffer Size */
#define	CFG_MAXARGS		16		/* max number of command args	*/
#define	CFG_BARGSIZE		CFG_CBSIZE	/* Boot Argument Buffer Size	*/

#define CFG_MEMTEST_START	0x00000000	/* memtest works on	*/
#define CFG_MEMTEST_END		0x00f80000	/* 15,5 MB in DRAM	*/

#undef  CFG_CLKS_IN_HZ		/* everything, incl board info, in Hz */

#define	CFG_LOAD_ADDR		0x00200000	/* default load address	*/

#define	CFG_HZ			(CPU_CLK_FREQ/64)

/* valid baudrates */
#define CFG_BAUDRATE_TABLE	{ 9600, 19200, 38400, 57600, 115200 }

/*-----------------------------------------------------------------------
 * Stack sizes
 *
 * The stack sizes are set up in start.S using the settings below
 */
#define CONFIG_STACKSIZE	(128*1024)	/* regular stack */
#ifdef CONFIG_USE_IRQ
#define CONFIG_STACKSIZE_IRQ	(4*1024)	/* IRQ stack */
#define CONFIG_STACKSIZE_FIQ	(4*1024)	/* FIQ stack */
#endif

/*-----------------------------------------------------------------------
 * Physical Memory Map
 */
#define CONFIG_NR_DRAM_BANKS	1	   		/* we have 1 bank of DRAM */
#define PHYS_SDRAM_1				0x00000000	 /* SDRAM Bank #1 */
/* size will be defined in include/configs when you make the config */
/*#define PHYS_SDRAM_1_SIZE */

#ifdef CONFIG_CC9C_NAND
#define PHYS_NAND_FLASH		0x50000000 /* NAND Flash Bank #1 */
#define CFG_NAND_BASE		PHYS_NAND_FLASH

#define CFG_NAND_BASE_LIST	{ CFG_NAND_BASE }

#define CFG_NAND_UNALIGNED	1
#define NAND_ECC_INFO		CFG_LOAD_ADDR	/* address in SDRAM is used */

#define NAND_NO_RB
#define NAND_BUSY_GPIO			3
#endif /*CONFIG_CC9C_NAND*/


/*-----------------------------------------------------------------------
 * FLASH and environment organization
 */

#define CFG_MAX_FLASH_BANKS	1	/* max number of memory banks */
#define PHYS_FLASH_1		0x50000000 /* Flash Bank #1 */
#define CFG_FLASH_BASE		PHYS_FLASH_1
#define CFG_MAX_FLASH_SECT	(71)	/* max number of sectors on one chip */
#define CFG_ENV_ADDR		(CFG_FLASH_BASE + 0x80000) /* addr of environment */


/* timeout values are in ticks */
#define CFG_FLASH_ERASE_TOUT	(5*CFG_HZ) /* Timeout for Flash Erase */
#define CFG_FLASH_WRITE_TOUT	(5*CFG_HZ) /* Timeout for Flash Write */

/* use internal RTC */
#define	CONFIG_RTC_NS9360	1

#define CONFIG_HARD_I2C		1	/* I2C with hardware support */
#define CONFIG_DRIVER_NS9750_I2C 1	/* I2C driver */
#define CFG_I2C_SPEED 		100000	/* Hz */
#define CFG_I2C_SLAVE 		0x7F	/* I2C slave addr */

#define CFG_I2C_EEPROM_ADDR	0x50	/* EEPROM address */
#define CFG_I2C_EEPROM_ADDR_LEN	2	/* 2 address bytes */

#undef CFG_I2C_EEPROM_ADDR_OVERFLOW
#define CFG_EEPROM_PAGE_WRITE_BITS 5	/* 32 bytes page write mode on M24LC64 */
#define CFG_EEPROM_PAGE_WRITE_DELAY_MS 10
#define CFG_EEPROM_PAGE_WRITE_ENABLE 1


/* I2C settings */
#define CONFIG_HARD_I2C			1	/* I2C with hardware support */
#define CONFIG_DRIVER_NS9750_I2C	1	/* I2C driver */
#define CFG_I2C_SPEED 			100000	/* Hz */
#define CFG_I2C_SLAVE 			0x7F	/* I2C slave addr */

#if (CONFIG_COMMANDS & CFG_CMD_NAND)
#include <ns9750_nand.h>

#define	CFG_ENV_IS_IN_NAND	1
#define CFG_ENV_OFFSET		0x00100000	/* environment starts at end of u-boot partition */
#define CFG_ENV_SIZE		0x00020000	/* one sector in NAND */

#define CONFIG_NR_NAND_PART	5	/* 5 partitions in NAND Flash */
#define NAND_NAME_0	"u-boot"
#define NAND_START_0	0x00000000
#define NAND_SIZE_0	0x00100000
#define NAND_NAME_1	"env"
#define NAND_START_1	0x00100000
#define NAND_SIZE_1	0x00080000	/* place for duplicate sector and bad blocks */
#define NAND_NAME_2	"fpga"
#define NAND_START_2	0x00180000
#define NAND_SIZE_2	0x00100000
#define NAND_NAME_3	"kernel"
#define NAND_START_3	0x00280000
#define NAND_SIZE_3	0x00300000
#define NAND_NAME_4	"rootfs"
#define NAND_START_4	0x00580000
#define NAND_SIZE_4	0x01A80000	/* size of last partition will be calculated */

#define CONFIG_JFFS2_NAND
#define CONFIG_JFFS2_NAND_OFF   0x00580000
#define CONFIG_JFFS2_NAND_SIZE  0x01A80000

#define CONFIG_JFFS2_DEV	"nand0"
#define CONFIG_JFFS2_PART_SIZE		0x01A80000
#define CONFIG_JFFS2_PART_OFFSET 	0x00580000

/* TODO test JFFS2 CMDLINE */
/* add this variable to the default settings:
	"mtdparts="MTDPARTS_DEFAULT"\0"			\

#define CONFIG_JFFS2_CMDLINE
#define MTDIDS_DEFAULT		"nand0=CCW9C-0"
#define MTDPARTS_DEFAULT	"mtdparts=CCW9C-0:1m@0(u-boot)ro,"	\
						"512k@1m(environment),"	\
						"1m@1536k(fpga)ro,"	\
						"3m@2560k(kernel),"	\
						"-@5632k(rootfs)ro"
*/

#else /* if (CONFIG_COMMANDS & CFG_CMD_NAND) */

#define CFG_ENV_IS_IN_FLASH     1
#define CFG_ENV_SIZE            0x10000		/* one sector */
#define CFG_ENV_SECT_SIZE	0x10000		/* Total Size of Environment Sector	*/

#endif

#endif	/* __CONFIG_H */
