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

/*
 * If we are developing, we might want to start armboot from ram
 * so we MUST NOT initialize critical regs like mem-timing ...
 */
/* define for developing */
#undef	CONFIG_SKIP_LOWLEVEL_INIT


/*
 * High Level Configuration Options
 * (easy to change)
 */
#define CONFIG_ARM926EJS		1	/* This is an ARM926EJS Core	*/
#define CONFIG_NS9360		1	/* in an NetSilicon NS9360 SoC     */
#define CONFIG_CC9C			1
#define CPU     "NS9360"
#define BOARD_LATE_INIT		1	/* Enables initializations before jumping to main loop */

/* will be defined in include/configs when you make the config */
/*#define CONFIG_CC9C_NAND*/

#ifdef CONFIG_CC9C_NAND
#define CONFIG_BOOT_NAND	1
#endif /*CONFIG_CC9C_NAND*/

#define NS9750_ETH_PHY_ADDRESS	(0x0001)
#define CONFIG_SYS_CLK_FREQ	309657600	/*154.8288MHz*/
/*#define CONFIG_SYS_CLK_FREQ	353894400 */ /*176.9472MHz*/

#define CPU_CLK_FREQ		(CONFIG_SYS_CLK_FREQ/2)
#define AHB_CLK_FREQ		(CONFIG_SYS_CLK_FREQ/4)
#define BBUS_CLK_FREQ		(CONFIG_SYS_CLK_FREQ/8)

#undef CONFIG_USE_IRQ			/* we don't need IRQ/FIQ stuff */


/*
 * Size of malloc() pool
 */
#define CFG_MALLOC_LEN		(256*1024)
#define CFG_GBL_DATA_SIZE       128     /* size in bytes reserved for initial data */


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
#define CONFIG_CONS_INDEX	1	/*0= Port B; 1= Port A; 2= Port C; 3=Port D */    
#define CONFIG_BAUDRATE		38400

/* allow to overwrite serial and ethaddr */
#define CONFIG_ENV_OVERWRITE

/***********************************************************
 * Command definition
 ***********************************************************/
#ifdef CONFIG_CC9C_NAND
#define CONFIG_COMMANDS \
	((CONFIG_CMD_DFL &	\
	  ~CFG_CMD_CACHE &	\
	  ~CFG_CMD_FLASH)|	\
	 CFG_CMD_IMI     |	\
	 CFG_CMD_MII	 |	\
	 CFG_CMD_NAND	 |	\
	 CFG_CMD_NET	 |	\
	 CFG_CMD_PING    |	\
	 CFG_CMD_REGINFO)
#else
#define CONFIG_COMMANDS \
	((CONFIG_CMD_DFL &	\
	  ~CFG_CMD_CACHE)    |	\
	 CFG_CMD_FLASH |	\
	 CFG_CMD_IMI     |	\
	 CFG_CMD_I2C	 |	\
	 CFG_CMD_MII	 |	\
	 CFG_CMD_NET	 |	\
	 CFG_CMD_PING    |	\
	 CFG_CMD_REGINFO |	\
	 CFG_CMD_FAT |	\
	 CFG_CMD_USB)
#endif

/************************************************************
 * CC9C default environment settings
 ************************************************************/

#define CONFIG_EXTRA_ENV_SETTINGS							\
	"std_bootarg=console=ttyS1,38400\0"								\
	"uimg=u-boot-cc9cdev.bin\0"							\
	"rimg=rootfs-cc9cdev.jffs2\0"						\
	"kimg=uImage-cc9cdev\0"							    \
	"loadaddr=100000\0"									    \
	"npath=/exports/nfsroot-cc9cdev\0"					\
	"smtd=setenv bootargs $(std_bootarg) ip=$(ipaddr):$(serverip)::$(netmask):cc9c:eth0:off root=/dev/mtdblock2 rootfstype=jffs2\0"	\
	"snfs=setenv bootargs $(std_bootarg) ip=$(ipaddr):$(serverip)::$(netmask):cc9c:eth0:off root=nfs nfsroot=$(serverip):$(npath)\0"	\
	"gfk=cp.w 50050000 $(loadaddr) 1B0000\0"				\
	"gtk=tftp $(loadaddr) $(kimg)\0"						\
	"gtr=tftp $(loadaddr) $(rimg)\0"						\
	"gtu=tftp $(loadaddr) $(uimg)\0"						\
	"guk=usb reset;fatload usb 0 $(loadaddr) $(kimg)\0" \
	"gur=usb reset;fatload usb 0 $(loadaddr) $(rimg)\0" \
	"guu=usb reset;fatload usb 0 $(loadaddr) $(uimg)\0" \
	"wfr=cp.b $(loadaddr) 50200000 $(filesize)\0"		\
	"wfk=cp.b $(loadaddr) 50050000 $(filesize)\0"		\
	"wfu=cp.b $(loadaddr) 50000000 $(filesize)\0"            \
	"cfr=erase 50200000 503fffff\0"					      	\
	"cfk=erase 50050000 501fffff\0"					      	\
	"cfu=erase 50000000 5003ffff\0"                              \
	"boot_flash=run smtd gfk;bootm\0"		\
	"boot_net=run snfs gtk;bootm\0"			\
	"boot_usb=run smtd guk;bootm\0"			\
	"update_kernel_tftp=run gtk cfk wfk\0"		\
	"update_rootfs_tftp=run gtr cfr wfr\0"		\
	"update_uboot_tftp=run gtu cfu wfu\0"			\
	"update_kernel_usb=run guk cfk wfk\0"			\
	"update_rootfs_usb=run gur cfr wfr\0"			\
	"update_uboot_usb=run guu cfu wfu\0"			\


/* this must be included AFTER the definition of CONFIG_COMMANDS (if any) */
#include <cmd_confdefs.h>

#define CONFIG_BOOTDELAY		4

/* ====================== NOTE ========================= */
/* The following default ethernet MAC address was selected
 * so as to not collide with any known production device.
 */
#define CONFIG_ETHADDR		00:04:f3:ff:ff:fb /*@TODO unset */
#define CONFIG_NETMASK		255.255.255.0
#define CONFIG_IPADDR		192.168.42.30
#define CONFIG_SERVERIP		192.168.42.1

#define CONFIG_CMDLINE_TAG	1 /* passing of ATAGs */
#define CONFIG_INITRD_TAG	1
#define CONFIG_SETUP_MEMORY_TAGS 1

#define CONFIG_BOOTFILE	"uImage-cc9cdev"
#define CONFIG_BOOTCOMMAND	"run boot_flash"

#if (CONFIG_COMMANDS & CFG_CMD_KGDB)
#define CONFIG_KGDB_BAUDRATE	115200		/* speed to run kgdb serial port */
/* what's this ? it's not used anywhere */
#define CONFIG_KGDB_SER_INDEX	1		/* which serial port to use */
#endif

/*
 * Miscellaneous configurable options
 */
#define	CFG_LONGHELP				/* undef to save memory		*/
#define	CFG_PROMPT		"CC9C # "	/* Monitor Command Prompt	*/
#define	VERSION_TAG		" FS.3"		/* patched u-boot version from FS */
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
#define CONFIG_NR_DRAM_BANKS	1	   		/* we have 1 bank of DRAM */
#define PHYS_SDRAM_1				0x00000000	 /* SDRAM Bank #1 */
/* size will be defined in include/configs when you make the config */
/*#define PHYS_SDRAM_1_SIZE */

#ifdef CONFIG_CC9C_NAND
#define PHYS_NAND_FLASH		0x50000000 /* NAND Flash Bank #1 */
#define CFG_NAND_BASE		PHYS_NAND_FLASH

#define NAND_BUSY_GPIO			3
#endif /*CONFIG_CC9C_NAND*/

/*-----------------------------------------------------------------------
 * FLASH and environment organization
 */

#define CFG_MAX_FLASH_BANKS	1	/* max number of memory banks */
#define PHYS_FLASH_1		0x50000000 /* Flash Bank #1 */
#define CFG_FLASH_BASE		PHYS_FLASH_1
#define PHYS_FLASH_SIZE		SZ_4M /* 4MB */
#define CFG_MAX_FLASH_SECT	(71)	/* max number of sectors on one chip */
#define CFG_ENV_ADDR		(CFG_FLASH_BASE + 0x040000) /* addr of environment */
 

/* timeout values are in ticks */
#define CFG_FLASH_ERASE_TOUT	(5*CFG_HZ) /* Timeout for Flash Erase */
#define CFG_FLASH_WRITE_TOUT	(5*CFG_HZ) /* Timeout for Flash Write */

#define CFG_ENV_IS_IN_FLASH	1
#define CFG_ENV_SIZE			0x10000	/* one sector */


#if (CONFIG_COMMANDS & CFG_CMD_NAND)
# include <ns9750_nand.h>
#endif /* CONFIG_CMD_NAND */

/* I2C settings */ 
#define CONFIG_HARD_I2C			1	/* I2C with hardware support */
#define CONFIG_DRIVER_NS9750_I2C	1	/* I2C driver */
#define CFG_I2C_SPEED 			100000	/* Hz */
#define CFG_I2C_SLAVE 			0x7F	/* I2C slave addr */


#endif	/* __CONFIG_H */
