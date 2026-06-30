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

/*
 * If we are developing, we might want to start armboot from ram
 * so we MUST NOT initialize critical regs like mem-timing ...
 */

/* define for developing */
#undef	CONFIG_SKIP_LOWLEVEL_INIT
/* define for developing */

/*
 * High Level Configuration Options
 * (easy to change)
 */
#define CONFIG_ARM926EJS		1	/* This is an ARM926EJS Core	*/
#define CONFIG_NS9360		1	/* in an NetSilicon NS9360 SoC     */
#define CONFIG_A9M9360		1       /* on an FS Forth-Systeme Module */
#define CPU     "NS9360"
#define BOARD_LATE_INIT		1	/* Enables initializations before jumping to main loop */
#define CRYSTAL			294912
#define PLLFS			((*get_sys_reg_addr( NS9750_SYS_PLL ) >>0x17 ) & 0x3)
#define PLLND			((*get_sys_reg_addr( NS9750_SYS_PLL ) >>0x10 ) & 0x1f)


#define CONFIG_BOOT_NAND	1
#define NS9750_ETH_PHY_ADDRESS	(0x0001)
#define CONFIG_SYS_CLK_FREQ	(100*CRYSTAL * (PLLND +1) / (1<<PLLFS))
#define CPU_CLK_FREQ		(CONFIG_SYS_CLK_FREQ/2)
#define AHB_CLK_FREQ		(CONFIG_SYS_CLK_FREQ/4)

#define BBUS_CLK_FREQ	(CONFIG_SYS_CLK_FREQ/8)

#undef CONFIG_USE_IRQ			/* we don't need IRQ/FIQ stuff */


/* Size of malloc() pool */
#define CFG_MALLOC_LEN		(256*1024)
#define CFG_GBL_DATA_SIZE		128     /* size in bytes reserved for \
								      initial data */

/*
 * Hardware drivers
 */
 /* USB related stuff */
#define LITTLEENDIAN	1						/* necessary for USB */
#define CONFIG_USB_OHCI 1
#define CONFIG_DOS_PARTITION 1
#define CONFIG_USB_STORAGE 1
/* ethernet stuff */
#define CONFIG_DRIVER_NS9750_ETHERNET	1	/* use on-chip ethernet */

#ifdef CONFIG_A9MVALI		/* this option is passed in the Makefile */
/*
 * select serial console configuration
 */
#define CFG_NS9750_UART			1*/	/* use on-chip UART */
#define PLATFORM "val"
#define SER "ttyS1"
#define CONFIG_BOOTFILE	"uImage-cc9p9360val"
#elif CONFIG_A9M9750DEV
#define CFG_NS16550
#define CFG_NS16550_SERIAL
#define CFG_NS16550_REG_SIZE	 1
#define CFG_NS16550_CLK		 18432000
#define CFG_NS16550_COM1	 0x40000000
#define PLATFORM "dev"
#define SER "ttyS0"
#define CONFIG_BOOTFILE	"uImage-cc9p9360dev"
#endif /*CONFIG_A9MVALI*/

#define CONFIG_CONS_INDEX	1 
/* allow to overwrite serial and ethaddr */
#define CONFIG_ENV_OVERWRITE

#define CONFIG_BAUDRATE		38400

/***********************************************************
 * Command definition
 ***********************************************************/
#define CONFIG_COMMANDS \
	((CONFIG_CMD_DFL &	\
	  ~CFG_CMD_CACHE &	\
	  ~CFG_CMD_FLASH) |	\
	 CFG_CMD_DATE	 |	\
	 CFG_CMD_EEPROM  |	\
	 CFG_CMD_I2C	 |	\
	 CFG_CMD_IMI     |	\
	 CFG_CMD_JFFS2   |	\
	 CFG_CMD_NAND	 |	\
	 CFG_CMD_NET	 |	\
	 CFG_CMD_PING    |	\
	 CFG_CMD_REGINFO  | \
	 CFG_CMD_FAT  | \
	 CFG_CMD_USB)

/************************************************************
 * A9M9360 default environment settings 
 ************************************************************/
	
#define CONFIG_EXTRA_ENV_SETTINGS			\
	"std_bootarg=console="SER",38400\0"		\
	"uimg=u-boot-cc9p9360"PLATFORM".bin\0"		\
	"rimg=rootfs-cc9p9360"PLATFORM".jffs2\0"	\
	"kimg=uImage-cc9p9360"PLATFORM"\0"		\
	"nimg=netos-cc9p9360\0"				\
	"loadaddr=100000\0"				\
	"nsldr=400000\0"				\
	"nsexe=400024\0"				\
	"npath=/exports/nfsroot-cc9p9360"PLATFORM"\0"							\
	"smtd=setenv bootargs $(std_bootarg) ip=$(ipaddr):$(serverip)::$(netmask):9360:eth0:off root=/dev/mtdblock2 rootfstype=jffs2\0"	\
	"snfs=setenv bootargs $(std_bootarg) ip=$(ipaddr):$(serverip)::$(netmask):9360:eth0:off root=nfs nfsroot=$(serverip):$(npath)\0"	\
	"gtk=tftp $(loadaddr) $(kimg)\0"		\
	"gtr=tftp $(loadaddr) $(rimg)\0"		\
	"gtu=tftp $(loadaddr) $(uimg)\0"		\
	"gtn=tftp $(nsldr) $(nimg)\0"		\
	"gfk=nand read.jffs2 $(loadaddr) 40000 2C0000\0"		\
	"gfn=nand read.jffs2 $(nsldr) 40000 2C0000\0"		\
	"guk=usb reset;fatload usb 0 $(loadaddr) $(kimg)\0"		\
	"gur=usb reset;fatload usb 0 $(loadaddr) $(rimg)\0"		\
	"guu=usb reset;fatload usb 0 $(loadaddr) $(uimg)\0"		\
	"gun=usb reset;fatload usb 0 $(nsldr) $(nimg)\0"	\
	"wfr=nand write.jffs2 $(loadaddr) 300000 $(filesize)\0"		\
	"wfk=nand write.jffs2 $(loadaddr) 40000  $(filesize)\0"		\
	"wfu=nand write.jffs2 $(loadaddr) 0 $(filesize)\0"		\
	"wfn=nand write.jffs2 $(nsldr) 40000 $(filesize)\0"	\
	"cfr=nand erase 300000 $(flashpartsize)\0"			\
	"cfk=nand erase 40000 2C0000\0"					\
	"cfu=nand erase 0 40000\0"                              \
	"boot_flash=run smtd gfk;bootm\0"			\
	"boot_ns_flash=run gfn;go $(nsexe)\0"	\
	"boot_net=run snfs gtk;bootm\0"			\
	"boot_ns_net=run gtn;go $(nsexe)\0"		\
	"boot_usb=run smtd guk;bootm\0"			\
	"boot_ns_usb=run gun;go $(nsexe)\0"		\
	"update_kernel_tftp=run gtk cfk wfk\0"		\
	"update_rootfs_tftp=run gtr cfr wfr\0"		\
	"update_uboot_tftp=run gtu cfu wfu\0"		\
	"update_kernel_usb=run guk cfk wfk\0"		\
	"update_rootfs_usb=run gur cfr wfr\0"		\
	"update_uboot_usb=run guu cfu wfu\0"		\
	"update_ns_usb=run gun cfk wfn\0"		\
	"update_ns_tftp=run gtn cfk wfn\0"		


#include <cmd_confdefs.h>

#define CONFIG_BOOTDELAY	4

#define CONFIG_ETHADDR		00:04:f3:ff:ff:fb /*@TODO unset */
#define CONFIG_NETMASK		255.255.255.0
#define CONFIG_IPADDR		192.168.42.30
#define CONFIG_SERVERIP		192.168.42.1

#define CONFIG_CMDLINE_TAG	1 /* passing of ATAGs */
#define CONFIG_INITRD_TAG		1
#define CONFIG_SETUP_MEMORY_TAGS 1

#define CONFIG_BOOTCOMMAND	"run boot_flash"

/*
 * Miscellaneous configurable options
 */
#define	VERSION_TAG		" FS.3"		/* patched u-boot version from FS */
#define	CFG_LONGHELP			/* undef to save memory		*/
#define	CFG_PROMPT		"CC9P9360 # "	/* Monitor Command Prompt	*/
#define	MODULE_STRING	"CC9P9360"
#define 	CONFIG_IDENT_STRING VERSION_TAG

#define	CFG_CBSIZE		256		/* Console I/O Buffer Size	*/
#define	CFG_PBSIZE (CFG_CBSIZE+sizeof(CFG_PROMPT)+16) /* Print Buffer Size */
#define	CFG_MAXARGS		16		/* max number of command args	*/
#define	CFG_BARGSIZE		CFG_CBSIZE	/* Boot Argument Buffer Size	*/

#define CFG_MEMTEST_START	0x00000000	/* memtest works on	*/
#define CFG_MEMTEST_END		0x00f80000	/* 15,5 MB in DRAM	*/

#undef  CFG_CLKS_IN_HZ		/* everything, incl board info, in Hz */

#define	CFG_LOAD_ADDR		0x00100000	/* default load address	*/

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
/* TODO */
#define CONFIG_NR_DRAM_BANKS	1	   /* we have 1 bank of DRAM */
#define PHYS_SDRAM_1		0x00000000	 /* SDRAM Bank #1 */
/* size will be defined in include/configs when you make the config */
/*#define PHYS_SDRAM_1_SIZE */

#define PHYS_FLASH_1		0x50000000 /* Flash Bank #1 */
#define CFG_FLASH_BASE		PHYS_FLASH_1

#define PHYS_NAND_FLASH		0x50000000 /* NAND Flash Bank #1 */
#define CFG_NAND_BASE		PHYS_NAND_FLASH

#define NAND_BUSY_GPIO		49

/*-----------------------------------------------------------------------
 * FLASH and environment organization
 */
/* @TODO*/
#define CONFIG_AMD_LV400	1	/* uncomment this if you have a LV400 flash */
#if 0
#define CONFIG_AMD_LV800	1	/* uncomment this if you have a LV800 flash */
#endif

#define CFG_MAX_FLASH_BANKS	1	/* max number of memory banks */
#ifdef CONFIG_AMD_LV800
#define PHYS_FLASH_SIZE		0x00100000 /* 1MB */
#define CFG_MAX_FLASH_SECT	(19)	/* max number of sectors on one chip */
#define CFG_ENV_ADDR		(CFG_FLASH_BASE + 0x0F0000) /* addr of environment */
#endif
#ifdef CONFIG_AMD_LV400
#define PHYS_FLASH_SIZE		0x00080000 /* 512KB */
#define CFG_MAX_FLASH_SECT	(11)	/* max number of sectors on one chip */
#define CFG_ENV_ADDR		(CFG_FLASH_BASE + 0x070000) /* addr of environment */
#endif

/* timeout values are in ticks */
#define CFG_FLASH_ERASE_TOUT	(5*CFG_HZ) /* Timeout for Flash Erase */
#define CFG_FLASH_WRITE_TOUT	(5*CFG_HZ) /* Timeout for Flash Write */

/* taken from a9m2410 */

#define	CONFIG_RTC_DS1337	1
#define CFG_I2C_RTC_ADDR	0x68	/* Dallas DS1337 RTC address */

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

/* @TODO */
/*#define	CFG_ENV_IS_IN_NAND	1 */
#define CFG_ENV_IS_IN_EEPROM 1
#define CFG_ENV_OFFSET		0x500	/* environment starts at 0x500 of EEPROM */
#define CFG_ENV_SIZE			0x800	/* 2048 bytes may be used for env vars */
				   					/* total size of a M24LC64 is 8192 bytes */


#if (CONFIG_COMMANDS & CFG_CMD_NAND)
# include <ns9750_nand.h>
#endif /* CONFIG_CMD_NAND */


#if 0
#define CFG_JFFS_CUSTOM_PART
#define CFG_JFFS2_RAMBASE	0x00400000 /* where JFFS2 image is copied to.\
					    * leave space for decompression of\
					    * kernel */
/* max. size of of mtd partition in RAM. Beware that U-Boot is at end of RAM */
#define CFG_JFFS2_RAMSIZE	(0x00800000)
#endif


#define CONFIG_NR_NAND_PART	3	/* 3 partitions in NAND Flash */
#define NAND_NAME_0	"u-boot"
#define NAND_START_0	0x00000000
#define NAND_SIZE_0	0x00040000
#define NAND_NAME_1	"kernel"
#define NAND_START_1	0x00040000
#define NAND_SIZE_1	0x002C0000
#define NAND_NAME_2	"rootfs"
#define NAND_START_2	0x00300000
#define NAND_SIZE_2	0x01D00000	/* size of last partition will be calculated */

#define CONFIG_JFFS2_NAND
#define CONFIG_JFFS2_NAND_OFF   0x00300000
#define CONFIG_JFFS2_NAND_SIZE  0x01D00000 

#define CONFIG_JFFS2_DEV	"nand0"
#define CONFIG_JFFS2_PART_SIZE		0x01D00000  
#define CONFIG_JFFS2_PART_OFFSET 	0x00300000

#endif	/* __CONFIG_H */
