/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: 
 * @Author: Bernd Westermann
 * @Descr: CCXP270 config
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
 *	2005/09/12 : bootdelay added (Bernd Westermann)
 *	2005/09/24 : USB, FAT, cleanup (Bernd Westermann)
 *	2005/10/06 : Added specific variables for WCE (Pedro Perez).
 ***********************************************************************/

#ifndef __CONFIG_H
#define __CONFIG_H

/*
 * If we are developing, we might want to start armboot from ram
 * so we MUST NOT initialize critical regs like mem-timing ...
 */
//#define CONFIG_INIT_CRITICAL		/* undef for developing */
//#define DEBUG

#define RTC

/*
 * High Level Configuration Options
 * (easy to change)
 */
#define CONFIG_PXA27X		1	/* This is an PXA27x CPU    */
#define CONFIG_CCXP		1	/* On a CCXP270 Board     */
#define BOARD_LATE_INIT		1

#undef CONFIG_USE_IRQ			/* we don't need IRQ/FIQ stuff */

/*
 * Size of malloc() pool
 */
#define CFG_MALLOC_LEN		0x40000 /* Reserve 4 MB for malloc()	*/
#define CFG_GBL_DATA_SIZE	128	/* size in bytes reserved for initial data */

/*
 * Hardware drivers
 */

/* USB related stuff */
//#define SL811_DEBUG		1
#define LITTLEENDIAN		1	/* necessary for USB */
#define CONFIG_USB_CCXP 	1	/* CONFIG_USB_OHCI 1 */
#define CONFIG_DOS_PARTITION 	1
#define CONFIG_USB_STORAGE 	1

/* Video settings */
#define CONFIG_LCD			1
#ifdef CONFIG_LCD
# define CONFIG_SHARP_LQ057Q3EC02	1
# define CONFIG_SPLASH_SCREEN		1
# define CONFIG_SPLASH_WITH_CONSOLE	1
# undef CONFIG_USE_VIDEO_CONSOLE
#endif


/*
 * select serial console configuration
 */
#define CONFIG_FFUART	       	1       /* we use FFUART on CCXP270 */
#define CONFIG_ENV_OVERWRITE
#define CONFIG_BAUDRATE	       	38400

/* allow to overwrite serial and ethaddr */
#define ADD_USB_CMD             CFG_CMD_USB | CFG_CMD_FAT
#define CONFIG_COMMANDS		(CONFIG_CMD_DFL | CFG_CMD_PING | CFG_CMD_FLASH |  CFG_CMD_CLOCK| ADD_USB_CMD)

/* this must be included AFTER the definition of CONFIG_COMMANDS (if any) */
#include <cmd_confdefs.h>

#undef CONFIG_SHOW_BOOT_PROGRESS

#define CONFIG_SERVERIP		192.168.42.1
#define CONFIG_ETHADDR		00:04:F3:00:38:10
#define CONFIG_NETMASK		255.255.255.0
#define CONFIG_IPADDR		192.168.42.30

#define CONFIG_SETUP_MEMORY_TAGS 1
#define CONFIG_CMDLINE_TAG	 1			/* enable passing of ATAGs	*/
#define CONFIG_INITRD_TAG	 1

#define CONFIG_BOOTDELAY 	2
#define CONFIG_BOOTARGS    	"console=ttyS0,38400"
#define CONFIG_BOOTCOMMAND	"run boot_flash"


#if (CONFIG_COMMANDS & CFG_CMD_KGDB)
#define CONFIG_KGDB_BAUDRATE	230400			/* speed to run kgdb serial port */
#define CONFIG_KGDB_SER_INDEX	2			/* which serial port to use */
#endif


#define CONFIG_EXTRA_ENV_SETTINGS							\
	"std_bootarg=console=ttyS0,38400\0"								\
	"loadaddr=a0100000\0"							\
	"ebootaddr=a3020000\0"							\
	"wcefladdr=100000\0"							\
	"ebfladdr=80000\0"							\
	"uimg=u-boot-ccxp270stk2.bin\0"							\
	"rimg=rootfs-ccxp270stk2.jffs2\0"							\
	"kimg=uImage-ccxp270stk2\0"								\
	"eimg=eboot-ccxp270\0"								\
	"wimg=wce-ccxp270\0"								\
	"npath=/exports/nfsroot-ccxp270stk2\0"						\
	"smtd=setenv bootargs $(std_bootarg) ip=$(ipaddr):$(serverip)::$(netmask):ccxp270:eth0:off root=/dev/mtdblock2 rootfstype=jffs2 rw\0"	\
	"snfs=setenv bootargs $(std_bootarg) ip=$(ipaddr):$(serverip)::$(netmask):ccxp270:eth0:off root=/dev/nfs nfsroot=$(serverip):$(npath)\0"	\
	"gtk=tftp $(loadaddr) $(kimg)\0"						\
	"gtr=tftp $(loadaddr) $(rimg)\0"						\
	"gtu=tftp $(loadaddr) $(uimg)\0"						\
	"gtw=tftp $(loadaddr) $(wimg)\0"						\
	"gte=tftp $(ebootaddr) $(eimg)\0"						\
	"gfk=cp.w 00080000 a0100000 280000\0"					\
	"gfw=cp.b $(wcefladdr) $(loadaddr) $(wcesize)\0"			\
	"gfe=cp.b $(ebfladdr) $(ebootaddr) $(ebsize)\0"				\
	"guk=usb reset;fatload usb 0 $(loadaddr) $(kimg)\0"	\
	"gur=usb reset;fatload usb 0 $(loadaddr) $(rimg)\0"	\
	"guu=usb reset;fatload usb 0 $(loadaddr) $(uimg)\0"	\
	"guw=usb reset;fatload usb 0 $(loadaddr) $(wimg)\0"	\
	"gue=usb reset;fatload usb 0 $(ebootaddr) $(eimg)\0"	\
	"wfk=cp.b $(loadaddr) 00080000 $(filesize)\0"				\
	"wfr=cp.b $(loadaddr) 00300000 $(filesize)\0"				\
	"wfu=cp.b $(loadaddr) 00000000 $(filesize)\0"              \
	"wfw=cp.b $(loadaddr) $(wcefladdr) $(wcesize)\0"              \
	"wfe=cp.b $(ebootaddr) $(ebfladdr) $(ebsize)\0"              \
	"cfk=erase 00080000 002fffff\0"							\
	"cfr=erase 00300000 01ffffff\0"							\
	"cfe=erase $(ebfladdr) +$(ebsize)\0"					\
	"cfw=erase $(wcefladdr) +$(wcesize)\0"					\
	"cfu=erase 00000000 0003ffff\0"                         \
	"pou=protect off 00000000 0003ffff\0"                         \
	"boot_flash=run smtd gfk;bootm\0"		\
	"boot_net=run snfs gtk;bootm\0"			\
	"boot_usb=run smtd guk;bootm\0"			\
	"boot_wce_flash=run gfw;go $(loadaddr)\0"		\
	"boot_wce_net=run gtw;go $(loadaddr)\0"		\
	"boot_wce_usb=run guw;go $(loadaddr)\0"		\
	"connect_to_pb=run gfe;go $(ebootaddr)\0"		\
	"set_ebsize=setenv ebsize $(filesize);saveenv\0"	\
	"set_wcesize=setenv wcesize $(filesize);saveenv\0"	\
	"update_kernel_tftp=run gtk cfk wfk\0"		\
	"update_rootfs_tftp=run gtr cfr wfr\0"		\
	"update_uboot_tftp=run gtu pou cfu wfu\0"			\
	"update_kernel_usb=run guk cfk wfk\0"			\
	"update_rootfs_usb=run gur cfr wfr\0"			\
	"update_uboot_usb=run guu pou cfu wfu\0"			\
	"update_eboot_usb=run gue set_ebsize cfe wfe\0"	\
	"update_wce_usb=run guw set_wcesize cfw wfw\0"	\
	"update_eboot_tftp=run gte set_ebsize cfe wfe\0"	\
	"update_wce_tftp=run gtw set_wcesize cfw wfw\0"	\
	"ffxaddr=24MB\0"									\
	"ffxsize=7MB\0"
/*
 *	"splashimage=1fc0000\0"
 *	Add splashimage environment variable if you want to use an initial splash image
 *	on the CCXP 270 development kit. The splashimage variable should be equal to the
 *	memory address where the bmp image is stored. The image must be a 320x240 BMP with
 *	256.
 */
	
/*
 * Miscellaneous configurable options
 */
//#define CFG_HUSH_PARSER		1
//#define CFG_PROMPT_HUSH_PS2		"> "
#define CONFIG_BOOTFILE		"uImage-ccxp270stk2"

#define MODULE_STRING	"CCXP270"
#define	VERSION_TAG		" FS.3"		/* patched u-boot version from FS */
#define CONFIG_IDENT_STRING	" "VERSION_TAG "\nfor FS Forth-Systeme " MODULE_STRING " on STK2\n"

#define CFG_PROMPT		"CCXP270> "	/* prompt string */

#define CFG_LONGHELP				/* undef to save memory */

#define CFG_CBSIZE		256		/* Console I/O Buffer Size	*/
#define CFG_PBSIZE 		(CFG_CBSIZE+sizeof(CFG_PROMPT)+16)	/* Print Buffer Size */
#define CFG_MAXARGS		16		/* max number of command args	*/
#define CFG_BARGSIZE		CFG_CBSIZE	/* Boot Argument Buffer Size	*/
#define CFG_DEVICE_NULLDEV	1

#define CFG_MEMTEST_START	0xA3390000	/* memtest works on	*/
#define CFG_MEMTEST_END		0xA3B90000	/* 8 MB in DRAM	*/

#undef	CFG_CLKS_IN_HZ				/* everything, incl board info, in Hz */

#define CFG_LOAD_ADDR		0xa0100000	/* default load address */
#define USBD_DOWN_ADDR		0xa0100000      /* default USB download address */

#define CFG_HZ			3686400		/* incrementer freq: 3.6864 MHz */
#define CFG_CPUSPEED		0x161		/* set core clock to 400/200/100 MHz */

#define CFG_BAUDRATE_TABLE	{ 9600, 19200, 38400, 57600, 115200 }	/* valid baudrates */

/*
 * Stack sizes
 *
 * The stack sizes are set up in start.S using the settings below
 */
#define CONFIG_STACKSIZE	(128*1024)	/* regular stack */
#ifdef  CONFIG_USE_IRQ
#define CONFIG_STACKSIZE_IRQ	(4*1024)	/* IRQ stack */
#define CONFIG_STACKSIZE_FIQ	(4*1024)	/* FIQ stack */
#endif

/*
 * Physical Memory Map
 */
#define CONFIG_NR_DRAM_BANKS	4	   /* we have 4 banks of DRAM */

#define PHYS_SDRAM_1		0xa0000000 /* SDRAM Bank #1 */
#define PHYS_SDRAM_1_SIZE	0x04000000 /* 64 MB */

#define PHYS_SDRAM_2		0xa4000000 /* SDRAM Bank #2 */
#define PHYS_SDRAM_2_SIZE	0x00000000 /* 0 MB */

#define PHYS_SDRAM_3		0xa8000000 /* SDRAM Bank #3 */
#define PHYS_SDRAM_3_SIZE	0x00000000 /* 0 MB */

#define PHYS_SDRAM_4		0xac000000 /* SDRAM Bank #4 */
#define PHYS_SDRAM_4_SIZE	0x00000000 /* 0 MB */

#define CFG_DRAM_BASE		0xA0000000
#define CFG_DRAM_SIZE		0x04000000

#define CFG_FLASH_BASE		PHYS_FLASH_1
#define PHYS_FLASH_1		0x00000000 /* Flash Bank #1 */
#define PHYS_FLASH_SIZE		0x02000000     /* 32 MB */

/*
 * Hardware drivers
 */
#define CONFIG_DRIVER_SMC91111
#define CONFIG_SMC91111_BASE 	0x04000300
#define CONFIG_SMC_USE_32_BIT	1

/*
 * FLASH and environment organization
 */
#define CFG_MONITOR_BASE	CFG_FLASH_BASE
#define CFG_MONITOR_LEN		0x40000

#define CFG_MAX_FLASH_BANKS	1		 /* max number of memory banks		*/
#define CFG_MAX_FLASH_SECT	128		 /* max number of sectors on one chip    */

/* timeout values are in ticks */
#define CFG_FLASH_ERASE_TOUT	(25*CFG_HZ) /* Timeout for Flash Erase */
#define CFG_FLASH_WRITE_TOUT	(25*CFG_HZ) /* Timeout for Flash Write */

/* write flash less slowly */
#define CFG_FLASH_USE_BUFFER_WRITE 1
#define CFG_FLASH_CFI    1  /* Flash is CFI conformant  */

/* Flash environment locations */
#define CFG_ENV_IS_IN_FLASH	1
#define CFG_ENV_ADDR		(PHYS_FLASH_1 + CFG_MONITOR_LEN)	/* Addr of Environment Sector	*/
#define CFG_ENV_SIZE		0x10000					/* Total Size of Environment     	*/
#define CFG_ENV_SECT_SIZE	0x40000					/* Total Size of Environment Sector	*/

#define CPSR_IRQ_DISABLE	0x80	// IRQ disabled when =1
#define CPSR_FIQ_DISABLE	0x40	// FIQ disabled when =1
#define CPSR_FIQ_MODE		0x11
#define CPSR_IRQ_MODE		0x12
#define CPSR_SUPERVISOR_MODE	0x13
#define CPSR_UNDEF_MODE		0x1B
#define CPSR_MODE_BITS          0x1F

/*
#define CFG_GPSR0_VAL		0xFFFCFE1B
#define CFG_GPSR1_VAL		0xFFFFFFFF
#define CFG_GPSR2_VAL		0xFFFFFFFF
#define CFG_GPSR3_VAL		0x007FFFFF
#define CFG_GPCR0_VAL		0xFFFFFFFF
#define CFG_GPCR1_VAL		0xFFFFFFFF
#define CFG_GPCR2_VAL		0xFFFFFFFF
#define CFG_GPCR3_VAL		0xFFFFFFFF
#define CFG_GPDR0_VAL		0xCA7BFA00
#define CFG_GPDR1_VAL		0xFCDFAB82
#define CFG_GPDR2_VAL		0xEBE3FFFF
#define CFG_GPDR3_VAL		0x00161FF5
#define CFG_GAFR0_L_VAL		0x80000140
#define CFG_GAFR0_U_VAL		0xA51A811A
#define CFG_GAFR1_L_VAL		0x999A9548
#define CFG_GAFR1_U_VAL		0xAAA5A4AA
#define CFG_GAFR2_L_VAL		0xAAAAAAAA
#define CFG_GAFR2_U_VAL		0x00000556
#define CFG_GAFR3_L_VAL		0x00010088
#define CFG_GAFR3_U_VAL		0x00001488
#define CFG_GRER0_VAL		0x00000003
#define CFG_GRER1_VAL		0x00000000
#define CFG_GRER2_VAL		0x04000000
#define CFG_GRER3_VAL		0x00000000
*/

#define CFG_GPSR0_VAL		0x00018004
#define CFG_GPSR1_VAL		0x004F0082
#define CFG_GPSR2_VAL		0x13EFC000
#define CFG_GPSR3_VAL		0x0006E032
#define CFG_GPCR0_VAL		0x084AFE1A
#define CFG_GPCR1_VAL		0x003003F0
#define CFG_GPCR2_VAL		0x0C014000
#define CFG_GPCR3_VAL		0x00000D00
#define CFG_GPDR0_VAL		0xCA7BFA00 // old
#define CFG_GPDR1_VAL		0xFCDFAB82 // old
#define CFG_GPDR2_VAL		0xEB63FFFF
#define CFG_GPDR3_VAL		0x00161FF5 // old
#define CFG_GAFR0_L_VAL		0x80000140 // old
#define CFG_GAFR0_U_VAL		0xA51A811A // old
#define CFG_GAFR1_L_VAL		0x999A9548 // old
#define CFG_GAFR1_U_VAL		0xAAA5A4AA // old
#define CFG_GAFR2_L_VAL		0xAAAAAAAA // old
#define CFG_GAFR2_U_VAL		0x00000556 // old
#define CFG_GAFR3_L_VAL		0x00010088 // old
#define CFG_GAFR3_U_VAL		0x00001488 // old
#define CFG_GRER0_VAL		0x00000003 // old
#define CFG_GRER1_VAL		0x00000000 // old
#define CFG_GRER2_VAL		0x04000000 // old
#define CFG_GRER3_VAL		0x00000000 // old

#define CFG_PSSR_VAL		0x30

/*
 * Clock settings
 */
#define CFG_CKEN			0x00400240
/*#define CFG_CCCR			0x02000190*/ /* 312 Mhz */
#define CFG_CCCR			0x02000290 /* 520 Mhz */

/*
 * Memory settings
 */
//#define CFG_MSC0_VAL		0x7FF427D0 //OK udp eth probs
#define CFG_MSC0_VAL		0x12C427D0
#define CFG_MSC1_VAL		0x7FF07FF0
#define CFG_MSC2_VAL		0x7FF07FF0
#define CFG_MDCNFG_VAL		0x8B000AC9
#define CFG_MDREFR_VAL		0x00000019
#define CFG_MDMRS_VAL		0x00320032

#define CFG_FLYCNFG_VAL		0x00010001

/*
 * PCMCIA and CF Interfaces
 */
#define CFG_MECR_VAL		0x00000003
#define CFG_MCMEM0_VAL		0x00040286
#define CFG_MCMEM1_VAL		0x00040286
#define CFG_MCATT0_VAL		0x00040286
#define CFG_MCATT1_VAL		0x00040286
#define CFG_MCIO0_VAL		0x00040286
#define CFG_MCIO1_VAL		0x00040286

#endif	/* __CONFIG_H */
