/*
 * (C) Copyright 2002
 * Sysgo Real-Time Solutions, GmbH <www.elinos.com>
 * Marius Groeger <mgroeger@sysgo.de>
 * Gary Jennejohn <gj@denx.de>
 * David Mueller <d.mueller@elsoft.ch>
 *
 * Configuation settings for the SAMSUNG SMDK2410 board.
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
 * @History:
 * 19-08-2005:	moved to u-boot-1.1.3	Joachim Jaeger
 *
 */

#ifndef __CONFIG_H
#define __CONFIG_H

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
#define	CONFIG_ARM920T			/* This is an ARM920T Core	*/
#define	CONFIG_S3C2410			/* in a SAMSUNG S3C2410 SoC     */
#define	CONFIG_A9M2410			/* FS Forth-Systeme A9M2410 Module  */
#undef	A9M2410_0			/* Version 0 of A9M2410 */

/* #define	CPU_2440 1 */		/* FS Forth-Systeme A9M2440 Module  */
/* this define will be passed by make a9m2440_config */

#define	A9M2410_USER_KEY		/* Enables environment changes via USER KEYs at startup */
#define	CONFIG_SHOW_BOOT_PROGRESS 	/* Show boot progress on LEDs	*/
#define	BOARD_LATE_INIT		 	/* Enables initializations before jumping to main loop */

/* #define	USE_COM2 */		/* Output via COM2 */
/* #define	USE_COM3 */		/* Output via COM3 */
/* these defines will be passed by following make calls:
					a9m2410_COM2_config
					a9m2410_COM3_config
					a9m2440_COM2_config
					a9m2440_COM3_config */

#define	LCD_PWREN 1			/* use GPG4 as LCD_PWREN pin */
#define	INV_PWREN 1			/* use LCD_PWREN inverted */


/* input clock of PLL */
#ifdef CPU_2440
#define	CONFIG_SYS_CLK_FREQ	16934400	/* the A9M2440 has 16.9344MHz input clock */
#define	FULL_INIT 1
#define PLATFORM "2440"
#else
#define	CONFIG_SYS_CLK_FREQ	12000000	/* the A9M2410 has 12MHz input clock */
#undef	FULL_INIT
#define PLATFORM "2410"
#endif

/* SDRAM defines */
#undef	SDRAM_16MB			/* Size of SDRAM device 16MB */
#define	SDRAM_32MB			/* Size of SDRAM device 32MB */
#undef	SDRAM_64MB			/* Size of SDRAM device 64MB */
#undef	SDRAM_64MB_X2			/* additional defines 2 banks of SDRAM device 64MB */

#define	USE_920T_MMU		1
#undef	CONFIG_USE_IRQ			/* we don't need IRQ/FIQ stuff */

/***********************************************************
 * I2C stuff:
 * the A9M2410 is equipped with a ST M24LC64 EEPROM at
 * address 0x50 with 16bit addressing
 ***********************************************************/
#define CONFIG_HARD_I2C		1	/* I2C with hardware support */
#define CONFIG_DRIVER_S3C24X0_I2C 1	/* I2C driver for SMDK2410 */
#define CFG_I2C_SPEED 		100000	/* I2C speed */
#define CFG_I2C_SLAVE 		0x7F	/* I2C slave addr */

#define CFG_I2C_EEPROM_ADDR	0x50	/* EEPROM address */
#define CFG_I2C_EEPROM_ADDR_LEN	2	/* 2 address bytes */

#undef CFG_I2C_EEPROM_ADDR_OVERFLOW
#define CFG_EEPROM_PAGE_WRITE_BITS 5	/* 32 bytes page write mode on M24LC64 */
#define CFG_EEPROM_PAGE_WRITE_DELAY_MS 10
#define CFG_EEPROM_PAGE_WRITE_ENABLE 1

/*
 * Size of malloc() pool
 */
#define CFG_MALLOC_LEN		(256*1024)
#define CFG_GBL_DATA_SIZE	128	/* size in bytes reserved for initial data */

/*
 * Hardware drivers
 */
 /* USB related stuff */
#define LITTLEENDIAN	1	/* necessary for USB */
#define CONFIG_USB_OHCI 1
#define CONFIG_DOS_PARTITION 1
#define CONFIG_USB_STORAGE 1

#define CONFIG_DRIVER_CS8900	1	/* we have a CS8900 on-board */
#define CS8900_BASE		0x29000300
#define CS8900_BUS16		1 /* the Linux driver does accesses as shorts */

/* LCD related stuff */
#if 0
#define CONFIG_LCD 	1
#define CONFIG_SHARP_LQ057Q3DC02 1
#endif

/*
 * select serial console configuration
 */
#ifdef USE_COM2
#define CONFIG_SERIAL2          	/* we use SERIAL 2 on A9M24x0 */

#elif defined USE_COM3
#define CONFIG_SERIAL3          	/* we use SERIAL 3 on A9M24x0 */

#else
#define CONFIG_SERIAL1          	/* we use SERIAL 1 on A9M24x0 */
#endif

/************************************************************
 * RTC
 ************************************************************/
#define	CONFIG_RTC_DS1337	1
#define CFG_I2C_RTC_ADDR	0x68	/* Dallas DS1337 RTC address */

/************************************************************
 * Activate LEDs while booting
 ************************************************************/
#define CONFIG_STATUS_LED
#define CONFIG_SMDK2410_LED

/* allow to overwrite serial and ethaddr */
#define CONFIG_ENV_OVERWRITE

#define CONFIG_BAUDRATE		38400

/***********************************************************
 * Command definition
 ***********************************************************/
#define ADD_USB_CMD             CFG_CMD_USB | CFG_CMD_FAT

#define CONFIG_COMMANDS \
	((CONFIG_CMD_DFL &	\
	  ~CFG_CMD_CACHE &	\
	  ~CFG_CMD_FLASH)|	\
	 CFG_CMD_DATE	 |	\
	 CFG_CMD_ELF	 |	\
	 CFG_CMD_EEPROM  |	\
	 CFG_CMD_I2C	 |	\
	 CFG_CMD_JFFS2   |	\
	 CFG_CMD_NAND	 |	\
	 CFG_CMD_NET	 |	\
	 CFG_CMD_PING    |	\
	 CFG_CMD_REGINFO |	\
	 /*CFG_CMD_USBD  | */\
	 ADD_USB_CMD)

#include <cmd_confdefs.h>

/************************************************************
 * A9M24x0 default environment settings
 ************************************************************/
#define CONFIG_EXTRA_ENV_SETTINGS							\
	"std_bootarg=console=ttySAC0,38400\0"								\
	"loadaddr=30100000\0"									\
	"wceloadaddr=30600000\0"								\
	"ebootaddr=30100000\0"			\
	"ebootfladdr=40000\0"					\
	"wcefladdr=100000\0"										\
	"uimg=u-boot-a9m"PLATFORM"dev.bin\0"				\
	"rimg=rootfs-a9m"PLATFORM"dev.jffs2\0"						\
	"kimg=uImage-a9m"PLATFORM"dev\0"							    \
	"eimg=eboot-a9m24x0\0"									\
	"wimg=wce-a9m24x0\0"										\
	"npath=/exports/nfsroot-a9m"PLATFORM"dev\0"							\
	"smtd=setenv bootargs $(std_bootarg) ip=$(ipaddr):$(serverip)::$(netmask):"PLATFORM":eth0:off root=/dev/mtdblock2 rootfstype=jffs2\0"	\
	"snfs=setenv bootargs $(std_bootarg) ip=$(ipaddr):$(serverip)::$(netmask):"PLATFORM":eth0:off root=nfs nfsroot=$(serverip):$(npath)\0"	\
	"gtk=tftp $(loadaddr) $(kimg)\0"						\
	"gtr=tftp $(loadaddr) $(rimg)\0"						\
	"gtu=tftp $(loadaddr) $(uimg)\0"						\
	"gtw=tftp $(wceloadaddr) $(wimg)\0"					\
	"gte=tftp $(ebootaddr) $(eimg)\0"					\
	"gfe=nand read.jffs2 $(ebootaddr) $(eimg)\0"					\
	"gfk=nand read.jffs2 $(loadaddr) 40000 2C0000\0"				\
	"gfw=nand read.jffs2 $(wceloadaddr) $(wcefladdr) $(wcesize)\0"	\
	"guk=usb reset;fatload usb 0 $(loadaddr) $(kimg)\0" \
	"gur=usb reset;fatload usb 0 $(loadaddr) $(rimg)\0" \
	"guu=usb reset;fatload usb 0 $(loadaddr) $(uimg)\0" \
	"guw=usb reset;fatload usb 0 $(wceloadaddr) $(wimg)\0"	\
	"gue=usb reset;fatload usb 0 $(ebootaddr) $(eimg)\0"		\
	"wfr=nand write.jffs2 $(loadaddr) 300000 $(filesize)\0"		\
	"wfk=nand write.jffs2 $(loadaddr) 40000 $(filesize)\0"		\
	"wfu=nand write.jffs2 $(loadaddr) 0 $(filesize)\0"            \
	"wfw=nand write.jffs2 $(wceloadaddr) $(wcefladdr) $(wcesize)\0"	\
	"wfe=nand write.jffs2 $(ebootaddr) $(ebootfladdr) $(esize)\0"	\
	"cfr=nand erase 300000 $(flashpartsize)\0"		       			\
	"cfk=nand erase 40000 2C0000\0"					      	\
	"cfw=nand erase $(wcefladdr) 1400000\0"				\
	"cfu=nand erase 0 40000\0"                             \
	"cfe=nand erase $(ebootfladdr) C0000\0"		\
	"boot_flash=run smtd gfk;bootm\0"		\
	"boot_net=run snfs gtk;bootm\0"			\
	"boot_usb=run smtd guk;bootm\0"			\
	"boot_wce_flash=run gfw;go $(wceloadaddr)\0"	\
	"boot_wce_net=run gtw;go $(wceloadaddr)\0"		\
	"boot_wce_usb=run guw; go $(wceloadaddr)\0"		\
	"set_wcesize=setenv wcesize $(filesize);saveenv\0"	\
	"set_esize=setenv esize $(filesize);saveenv\0"		\
	"update_kernel_tftp=run gtk cfk wfk\0"		\
	"update_rootfs_tftp=run gtr cfr wfr\0"		\
	"update_uboot_tftp=run gtu cfu wfu\0"			\
	"update_eboot_tftp=run gte set_esize cfe wfe\0"		\
	"update_wce_usb=run guw set_wcesize cfw wfw\0"	\
	"update_wce_tftp=run gtw set_wcesize cfw wfw\0"	\
	"update_kernel_usb=run guk cfk wfk\0"			\
	"update_rootfs_usb=run gur cfr wfr\0"			\
	"update_uboot_usb=run guu cfu wfu\0"			\
	"update_eboot_usb=run gue set_esize cfe wfe\0"		\
	"connect_to_pb=run gfe;go $(ebootaddr)\0"	\


#define CONFIG_CMDLINE_TAG	1 /* passing of ATAGs */
#define CONFIG_INITRD_TAG	1
#define CONFIG_SETUP_MEMORY_TAGS 1

#define CONFIG_BOOTDELAY	2
#define CONFIG_BOOTARGS		"console=ttySAC0"
#define CONFIG_ETHADDR		00:04:f3:00:06:35 /*FS Forth Default MAC */
#define CONFIG_NETMASK		255.255.255.0
#define CONFIG_IPADDR		192.168.42.30
#define CONFIG_SERVERIP		192.168.42.1
#define CONFIG_BOOTCOMMAND	"run boot_flash"

#if (CONFIG_COMMANDS & CFG_CMD_KGDB)
#define CONFIG_KGDB_BAUDRATE	115200		/* speed to run kgdb serial port */
/* what's this ? it's not used anywhere */
#define CONFIG_KGDB_SER_INDEX	1		/* which serial port to use */
#endif

/*
 * Miscellaneous configurable options
 */
#define VERSION_TAG "FS.3"
#ifdef CPU_2440
# define MODULE_STRING	"A9M2440"
# define CFG_PROMPT	"A9M2440 # "	/* Monitor Command Prompt	*/
# define CONFIG_BOOTFILE	"uImage-a9m2440dev"
#else
# define MODULE_STRING	"A9M2410"
# define CFG_PROMPT	"A9M2410 # "	/* Monitor Command Prompt	*/
# define CONFIG_BOOTFILE	"uImage-a9m2410dev"
#endif /* CPU_2440 */

#define CONFIG_IDENT_STRING	" " VERSION_TAG "\nfor FS Forth-Systeme " MODULE_STRING " on A9M2410DEV"

#define	CFG_LONGHELP				/* undef to save memory		*/

#define	CFG_CBSIZE		256		/* Console I/O Buffer Size	*/
#define	CFG_PBSIZE (CFG_CBSIZE+sizeof(CFG_PROMPT)+16) /* Print Buffer Size */
#define	CFG_MAXARGS		16		/* max number of command args	*/
#define CFG_BARGSIZE		CFG_CBSIZE	/* Boot Argument Buffer Size	*/

#define CFG_MEMTEST_START	0x30000000	/* memtest works on	*/
#define CFG_MEMTEST_END		0x31F80000	/* 31,5 MB SDRAM in 1 bank */
#define CFG_MEMTEST_MIRROR	0x34000000	/* to check if 2nd bank	is populated*/

#undef  CFG_CLKS_IN_HZ		/* everything, incl board info, in Hz */

#define	CFG_LOAD_ADDR		0x30100000	/* default load address	*/
#define USBD_DOWN_ADDR		0x31000000      /* default USB download address */

/* the PWM TImer 4 uses a counter of 15625 for 10 ms, so we need */
/* it to wrap 100 times (total 1562500) to get 1 sec. */
#define	CFG_HZ			1562500

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
#ifdef A9M2410_0
#ifdef SDRAM_16MB
#define CONFIG_NR_DRAM_BANKS	8	   /* we have 8 banks of DRAM */
#define PHYS_SDRAM_1		0x30000000 /* SDRAM Bank #1 */
#define PHYS_SDRAM_1_SIZE	0x00400000 /* 4 MB */
#define PHYS_SDRAM_2		0x31000000 /* SDRAM Bank #2 */
#define PHYS_SDRAM_2_SIZE	0x00400000 /* 4 MB */
#define PHYS_SDRAM_3		0x32000000 /* SDRAM Bank #3 */
#define PHYS_SDRAM_3_SIZE	0x00400000 /* 4 MB */
#define PHYS_SDRAM_4		0x33000000 /* SDRAM Bank #4 */
#define PHYS_SDRAM_4_SIZE	0x00400000 /* 4 MB */
#define PHYS_SDRAM_5		0x38000000 /* SDRAM Bank #5 */
#define PHYS_SDRAM_5_SIZE	0x00400000 /* 4 MB */
#define PHYS_SDRAM_6		0x39000000 /* SDRAM Bank #6 */
#define PHYS_SDRAM_6_SIZE	0x00400000 /* 4 MB */
#define PHYS_SDRAM_7		0x3A000000 /* SDRAM Bank #7 */
#define PHYS_SDRAM_7_SIZE	0x00400000 /* 4 MB */
#define PHYS_SDRAM_8		0x3B000000 /* SDRAM Bank #8 */
#define PHYS_SDRAM_8_SIZE	0x00400000 /* 4 MB */

#elif defined SDRAM_32MB
#define CONFIG_NR_DRAM_BANKS	8	   /* we have 8 banks of DRAM */
#define PHYS_SDRAM_1		0x30000000 /* SDRAM Bank #1 */
#define PHYS_SDRAM_1_SIZE	0x00800000 /* 8 MB */
#define PHYS_SDRAM_2		0x31000000 /* SDRAM Bank #2 */
#define PHYS_SDRAM_2_SIZE	0x00800000 /* 8 MB */
#define PHYS_SDRAM_3		0x32000000 /* SDRAM Bank #3 */
#define PHYS_SDRAM_3_SIZE	0x00800000 /* 8 MB */
#define PHYS_SDRAM_4		0x33000000 /* SDRAM Bank #4 */
#define PHYS_SDRAM_4_SIZE	0x00800000 /* 8 MB */
#define PHYS_SDRAM_5		0x38000000 /* SDRAM Bank #5 */
#define PHYS_SDRAM_5_SIZE	0x00800000 /* 8 MB */
#define PHYS_SDRAM_6		0x39000000 /* SDRAM Bank #6 */
#define PHYS_SDRAM_6_SIZE	0x00800000 /* 8 MB */
#define PHYS_SDRAM_7		0x3A000000 /* SDRAM Bank #7 */
#define PHYS_SDRAM_7_SIZE	0x00800000 /* 8 MB */
#define PHYS_SDRAM_8		0x3B000000 /* SDRAM Bank #8 */
#define PHYS_SDRAM_8_SIZE	0x00800000 /* 8 MB */

#elif defined SDRAM_64MB
#define CONFIG_NR_DRAM_BANKS	2	   /* we have 2 banks of DRAM */
#define PHYS_SDRAM_1		0x30000000 /* SDRAM Bank #1 */
#define PHYS_SDRAM_1_SIZE	0x04000000 /* 64 MB */
#define PHYS_SDRAM_2		0x34000000 /* SDRAM Bank #2 */
#define PHYS_SDRAM_2_SIZE	0x04000000 /* 64 MB */
#endif

#else	/* A9M2410_1 or A9M2440 */
#if defined SDRAM_16MB
#define CONFIG_NR_DRAM_BANKS	2	   /* we have 2 bank of DRAM */
#define PHYS_SDRAM_1		0x30000000 /* SDRAM Bank #1 */
#define PHYS_SDRAM_1_SIZE	0x01000000 /* 16 MB */
#define PHYS_SDRAM_2		0x31000000 /* SDRAM Bank #2 */
#define PHYS_SDRAM_2_SIZE	0x01000000 /* 16 MB */
#else
/* the physical size will be read by configuration resistors */
#define CONFIG_NR_DRAM_BANKS	1	   /* we have 1 bank of DRAM */
#define PHYS_SDRAM_1		0x30000000 /* SDRAM Bank #1 */
#endif

#endif /* A9M2410_0 */

#define PHYS_FLASH_1		0x00000000 /* Flash Bank #1 */

#define CFG_FLASH_BASE		PHYS_FLASH_1

/*-----------------------------------------------------------------------
 * FLASH and environment organization
 */

#define CONFIG_AMD_LV400	1	/* uncomment this if you have a LV400 flash */
#if 0
#define CONFIG_AMD_LV800	1	/* uncomment this if you have a LV800 flash */
#endif

#define CFG_MAX_FLASH_BANKS	0	/* max number of memory banks */
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


/* Use EEPROM for environment variables */
#define CFG_ENV_IS_IN_EEPROM    1	/* use EEPROM for environment vars */
#define CFG_ENV_OFFSET		0x500	/* environment starts at 0x500 of EEPROM */
#define CFG_ENV_SIZE		0x1B00	/* 6912 bytes may be used for env vars */
				   	/* total size of a M24LC64 is 8192 bytes */

/*-----------------------------------------------------------------------
 * NAND flash settings
 */
#define CONFIG_BOOT_NAND	1	/* undefined to boot in NOR mode */

#define CONFIG_NR_NAND_PART	3	/* 3 partitions in NAND Flash */
#define NAND_NAME_0	"uboot"
#define NAND_START_0	0x00000000
#define NAND_SIZE_0	0x00040000
#define NAND_NAME_1	"kernel"
#define NAND_START_1	0x00040000
#define NAND_SIZE_1	0x002C0000
#define NAND_NAME_2	"rootfs"
#define NAND_START_2	0x00300000
#define NAND_SIZE_2	0x01D00000	/* size of last partition will be calculated */

#define CONFIG_JFFS2_NAND

#define CONFIG_JFFS2_NAND_OFF	0x00300000
#define CONFIG_JFFS2_NAND_SIZE	0x01D00000
#define CONFIG_JFFS2_DEV		"nand0"
#define CONFIG_JFFS2_PART_SIZE		0x01D00000	/* size of partition will be calculated */
#define CONFIG_JFFS2_PART_OFFSET	0x00300000


#endif	/* __CONFIG_H */
