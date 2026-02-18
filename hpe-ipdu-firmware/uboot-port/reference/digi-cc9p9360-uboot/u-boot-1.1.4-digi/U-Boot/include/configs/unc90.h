/*
 * Sistemas Embebidos S.A. && FS Forth-Systeme GmbH
 *   -Pedro Perez de Heredia <pperez@embebidos.com>
 *   -Neil Bryan <nbryan@embebidos.com>
 *
 * Configuation settings for the UNC90 module.
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

#include <configs/digi_common.h>

#ifndef __ASSEMBLY__
#include <asm/arch/AT91RM9200.h>
#endif

#undef DEBUG

/****************************************************************************
 * General AT91RM9200 configuration (taken from at91rm9200dk.h)
 ****************************************************************************/

#define AT91C_MAIN_CLOCK        	158515200       /* from 18.432 MHz crystal */
#define AT91C_MASTER_CLOCK		(AT91C_MAIN_CLOCK/2)	/* peripheral clock (AT91C_MASTER_CLOCK / 3) */
//#define AT91C_MAIN_CLOCK        	180000000       /* from 18.432 MHz crystal */
//#define AT91C_MASTER_CLOCK		60000000	/* peripheral clock (AT91C_MASTER_CLOCK / 3) */

#define AT91_SLOW_CLOCK			32768	/* slow clock */

#define CONFIG_ARM920T			1
#define CONFIG_AT91RM9200		1
#undef	CONFIG_AT91RM9200DK		/* not on an AT91RM9200DK Board	 */
#define CONFIG_UNC90			1
#define CONFIG_MACH_UNC90               /* Select board mach-type */

#undef  CONFIG_USE_IRQ			/* we don't need IRQ/FIQ stuff */
#define USE_920T_MMU			1

#undef	CONFIG_SKIP_LOWLEVEL_INIT

#define CONFIG_CMDLINE_TAG		1	/* enable passing of ATAGs */
#define CONFIG_SETUP_MEMORY_TAGS 	1
#define CONFIG_INITRD_TAG		1


#define MODULE_STRING			"CC9U"
#define CONFIG_IDENT_STRING		"\nfor Digi International " MODULE_STRING " on UNCBAS_3"
#define CFG_PROMPT			"CC9U> "	/* Monitor Command Prompt */
#define CONFIG_BAUDRATE			38400	/* 115200 */
#define CONFIG_BOOTDELAY		3

#define CFG_COPY_ENV_TO_SRAM		1		/* Copy environment from eeprom to internal AT91RM9200 SRAM */
#define	CONFIG_SHOW_BOOT_PROGRESS 	1		/* Show boot progress on LEDs	*/
#define CFG_UNC90_ENV_IN_EEPROM		1
#undef CFG_UNC90_ENV_IN_FLASH
#undef CFG_UNC90_FLASH_PROT_BOOTBIN
#define BOARD_LATE_INIT			1	/* Enables initializations before jumping to main loop */
#define CONFIG_BOOTARGS    		"console=ttyS0"
#define CONFIG_BOOTCOMMAND		"run boot_flash"
#define	CFG_LONGHELP			/* undef to save memory		*/

#ifndef CONFIG_SKIP_LOWLEVEL_INIT
#define CFG_USE_MAIN_OSCILLATOR		1
/* flash */
#define MC_PUIA_VAL	0x00000000
#define MC_PUP_VAL	0x00000000
#define MC_PUER_VAL	0x00000000
#define MC_ASR_VAL	0x00000000
#define MC_AASR_VAL	0x00000000
#define EBI_CFGR_VAL	0x00000000
#define SMC2_CSR_VAL	0x01003288 /* 0 RWHOLD, 1 RWSETUP, 0 ACSS, 0 DRP=Standard Read Protocol, \
				      1 DBW=16-bit, 1 BAT=16-bit device, 2 TDF, 1 WSEN, 8 NWS */


/* clocks */
#define PLLAR_VAL	0x202A3F05 /* 158,5 MHz for PLLA */
#define PLLBR_VAL	0x1048BE0E /* 48.054857 MHz (divider by 2 for USB) */
#define MCKR_VAL	0x00000102 /* PCK/3 = MCK Master Clock = 59.904000MHz from PLLA */
//#define PLLAR_VAL	0x2270BE40 /* 180 MHz for Processor Clock */
//#define PLLBR_VAL	0x107C3E18 /* (18.432 / 24 * 125) /2 = 48.000 */
//#define MCKR_VAL	0x00000202 /* PCK/3 = MCK Master Clock = 60.000MHz from PLLA */

/* sdram */
#define PIOC_ASR_VAL	0xFFFF0000 /* Configure PIOC as peripheral (D16/D31) */
#define PIOC_BSR_VAL	0x00000000
#define PIOC_PDR_VAL	0xFFFF0000
#define EBI_CSA_VAL	0x00000002 /* CS1=SDRAM */
//#define SDRC_CR_VAL	0x2188c155 /* set up the SDRAM */
#define SDRC_CR_VAL 	0x3399C255 /* Calculated values */
//#define SDRC_CR_VAL	0x3399c155 /* Values taken over from another platform */

#define SDRAM		0x20000000 /* address of the SDRAM */
#define SDRAM1		0x20000080 /* address of the SDRAM */
#define SDRAM_VAL	0x00000000 /* value written to SDRAM */
#define SDRC_MR_VAL	0x00000002 /* Precharge All */
#define SDRC_MR_VAL1	0x00000004 /* refresh */
#define SDRC_MR_VAL2	0x00000003 /* Load Mode Register */
#define SDRC_MR_VAL3	0x00000000 /* Normal Mode */
//#define SDRC_TR_VAL	0x000002E0 /* Write refresh rate */
#define SDRC_TR_VAL	0x000004D8 /* Write refresh rate for 158MHz/2 */
//#define SDRC_TR_VAL	0x000003A9 /* Write refresh rate for 180MHz/3 */

#endif	/* CONFIG_SKIP_LOWLEVEL_INIT */

/*
 * Size of malloc() pool
 */
#define CFG_MALLOC_LEN	(CFG_ENV_SIZE + 128*1024)
#define CFG_GBL_DATA_SIZE	128	/* size in bytes reserved for initial data */

/*
 * Hardware drivers
 */

/* define one of these to choose the DBGU, USART0  or USART1 as console */
#undef CONFIG_DBGU
#undef CONFIG_USART0
#undef CONFIG_USART1
#define CONFIG_USART2

#undef	CONFIG_HWFLOW			/* don't include RTS/CTS flow control support	*/
#undef	CONFIG_MODEM_SUPPORT		/* disable modem initialization stuff */
#define CONFIG_ENV_OVERWRITE
#define	CONFIG_DIGI_CMD	1		/* enables DIGI board specific commands */

/***********************************************************
 * Command definition
 ***********************************************************/

#define CONFIG_COMMANDS	( \
         CONFIG_COMMANDS_DIGI | \
	 CFG_CMD_FLASH | \
         0 )

/* this must be included AFTER the definition of CONFIG_COMMANDS (if any) */
#include <cmd_confdefs.h>

/* will be used from board_tests/ */
#define BOARD_TEST_SDRAM_START          0x20200000
#define BOARD_TEST_SDRAM_SIZE           0x00400000
#define BOARD_TEST_NOR_START            0x10200000
#define BOARD_TEST_NOR_SIZE             0x00200000

#define CONFIG_NR_DRAM_BANKS		1
#define PHYS_SDRAM			0x20000000
#define PHYS_SDRAM_SIZE			0x1000000  /* 16 megs */

#define CFG_MEMTEST_START		PHYS_SDRAM
#define CFG_MEMTEST_END			CFG_MEMTEST_START + PHYS_SDRAM_SIZE - 262144

#define CONFIG_DRIVER_ETHER
#define CFG_CMD_NETCONFIG_DRIVER_ETHER
#define CONFIG_NET_RETRY_COUNT		20
#undef CONFIG_AT91C_USE_RMII
#undef CONFIG_HAS_DATAFLASH

#define PHYS_FLASH_1			0x10000000
#define PHYS_FLASH_SIZE			0x1000000  /* 16 megs main flash */
#define CFG_FLASH_BASE			PHYS_FLASH_1
#define CFG_MAX_FLASH_BANKS		1
#define CFG_MAX_FLASH_SECT		256
#define CFG_FLASH_ERASE_TOUT		(2*CFG_HZ) /* Timeout for Flash Erase */
#define CFG_FLASH_WRITE_TOUT		(2*CFG_HZ) /* Timeout for Flash Write */

//#define CFG_FLASH_CFI			/* The flash is CFI compatible	*/
//#define CFG_FLASH_CFI_DRIVER		/* Use common CFI driver	*/

#undef	CFG_ENV_IS_IN_DATAFLASH

#ifdef CFG_ENV_IS_IN_DATAFLASH
#define CFG_ENV_OFFSET			0x20000
#define CFG_ENV_ADDR			(CFG_DATAFLASH_LOGIC_ADDR_CS0 + CFG_ENV_OFFSET)
#define CFG_ENV_SIZE			0x2000  /* 0x8000 */
#else
// EEPROM stuff
#ifdef CFG_UNC90_ENV_IN_EEPROM
#define CFG_ENV_IS_IN_EEPROM		1
#define CFG_I2C_EEPROM_ADDR		0x50
#define CFG_I2C_EEPROM_ADDR_LEN		2
#define CFG_ENV_OFFSET			0x100
#define CFG_ENV_SIZE			0x800
#undef CFG_I2C_EEPROM_ADDR_OVERFLOW
#define CFG_EEPROM_PAGE_WRITE_BITS	5	/* 32 bytes page write mode on M24LC64 */
#define CFG_EEPROM_PAGE_WRITE_DELAY_MS	10
#define CFG_EEPROM_PAGE_WRITE_ENABLE	1
#else  //CFG_UNC90_ENV_IN_EEPROM
// ENV Flash stuff
#define CFG_ENV_IS_IN_FLASH		1
#ifdef CONFIG_SKIP_LOWLEVEL_INIT
#define CFG_ENV_ADDR			(PHYS_FLASH_1 + 0x60000)  /* after u-boot.bin */
#define CFG_ENV_SIZE			0x10000 /* sectors are 64K here */
#else
#define CFG_ENV_ADDR			(PHYS_FLASH_1 + 0x20000)  /* between boot.bin and u-boot.bin.gz */
#define CFG_ENV_SIZE			0x10000  /* 0x8000 */

#endif  //CONFIG_SKIP_LOWLEVEL_INIT
#endif  //CFG_UNC90_ENV_IN_EEPROM
#endif  //CFG_ENV_IS_IN_DATAFLASH

#define CFG_LOAD_ADDR			0x20100000  /* default load address */

#ifdef CONFIG_SKIP_LOWLEVEL_INIT
#define CFG_BOOT_SIZE			0x00 /* 0 KBytes */
#define CFG_U_BOOT_BASE			PHYS_FLASH_1
#define CFG_U_BOOT_SIZE			0x40000 /* 256 KBytes */
#else
#define CFG_BOOT_SIZE			0x10000 /* 64 KBytes */
#define CFG_U_BOOT_BASE			(PHYS_FLASH_1 + CFG_BOOT_SIZE)
#define CFG_U_BOOT_SIZE			0x30000 /* 192 KBytes */
#endif  //CONFIG_SKIP_LOWLEVEL_INIT

#define CFG_BAUDRATE_TABLE		{115200 , 19200, 38400, 57600, 9600 }

#define CFG_CBSIZE			256		/* Console I/O Buffer Size */
#define CFG_MAXARGS			16		/* max number of command args */
#define CFG_PBSIZE			(CFG_CBSIZE+sizeof(CFG_PROMPT)+16) /* Print Buffer Size */

#ifdef	CFG_COPY_ENV_TO_SRAM
#define	AT91_SRAM_PHYS		0x00200000
#endif


#ifndef __ASSEMBLY__
/*-----------------------------------------------------------------------
 * Board specific extension for bd_info
 *
 * This structure is embedded in the global bd_info (bd_t) structure
 * and can be used by the board specific code (eg board/...)
 */

struct bd_info_ext {
	/* helper variable for board environment handling
	 *
	 * env_crc_valid == 0    =>   uninitialised
	 * env_crc_valid  > 0    =>   environment crc in flash is valid
	 * env_crc_valid  < 0    =>   environment crc in flash is invalid
	 */
	int env_crc_valid;
};
#endif

#define CFG_HZ 1000
#define CFG_HZ_CLOCK AT91C_MASTER_CLOCK/2	/* AT91C_TC0_CMR is implicitly set to */
						/* AT91C_TC_TIMER_DIV1_CLOCK */

#define CONFIG_STACKSIZE	(32*1024)	/* regular stack */

#ifdef CONFIG_USE_IRQ
#error CONFIG_USE_IRQ not supported
#endif

/* USB related stuff */
#define CONFIG_USB_OHCI			1
#define CONFIG_USB_STORAGE		1
#define CONFIG_DOS_PARTITION		1
#define CFG_DEVICE_DEREGISTER		/* needs device_deregister */
#define LITTLEENDIAN			1  /* used by usb_ohci.c */
#define CONFIG_AT91C_PQFP_UHPBUG	1  /* We are not a pqfp chip... but this solves the UNC90 hardware bug (missing pull-down resistors on the un-connected USB interface) */

/* Software (bit-bang) I2C driver configuration */

#undef CONFIG_HARD_I2C
#define CONFIG_SOFT_I2C	1
#define CFG_I2C_SPEED	100000		/* not used */
#define CFG_I2C_SLAVE	0x7f		/* not used */

#define PA_SDA		0x02000000	/* PA 25 */
#define PA_SCL		0x04000000	/* PA 26 */

#define I2C_INIT	{*AT91C_PIOA_PER =  (PA_SDA | PA_SCL); \
			*AT91C_PIOA_OER =  PA_SCL; \
			*AT91C_PMC_PCER = 1 << AT91C_ID_PIOA; \
			*AT91C_PIOA_IFDR =  (PA_SDA | PA_SCL); \
			*AT91C_PIOA_IDR =  (PA_SDA | PA_SCL); \
			*AT91C_PIOA_MDER =  (PA_SDA | PA_SCL);}
#define I2C_ACTIVE	{*AT91C_PIOA_OER =  PA_SDA; \
			while (*AT91C_PIOA_OSR & PA_SDA != 0);}
#define I2C_TRISTATE	{*(AT91C_PIOA_ODR) = PA_SDA; \
			while (*AT91C_PIOA_OSR & PA_SDA == 0);}
#define I2C_READ	(*(AT91C_PIOA_PDSR) & PA_SDA)?1:0
#define I2C_SDA(bit)	{if(bit) *AT91C_PIOA_SODR =  PA_SDA; \
			else	*AT91C_PIOA_CODR =  PA_SDA;}
#define I2C_SCL(bit)	{if(bit) *(AT91C_PIOA_SODR) =  PA_SCL; \
			else	*(AT91C_PIOA_CODR) =  PA_SCL;}

#define I2C_DELAY	udelay(2)	/* 1/4 I2C clock duration */


/************************************************************
 * UNC90 i2c RTC on UNCBAS_3
 ************************************************************/
#define	CONFIG_RTC_DS1337	1
#define CFG_I2C_RTC_ADDR	0x68	/* Dallas DS1337 RTC address */


/************************************************************
 * UNC90 status led
 ************************************************************/
#define CONFIG_STATUS_LED
#ifdef	 CONFIG_STATUS_LED

# define STATUS_LED_BOOT		0		/* LED 0 used for boot status */
# define CONFIG_UNC90_USE_A4_LED
# undef  CONFIG_UNC90_USE_A6_LED
# define CONFIG_BOOT_LED_STATE		0
# define STATUS_LED_BIT			0x00000001
# define STATUS_LED_PERIOD		(CFG_HZ / 2)
# define STATUS_LED_STATE		STATUS_LED_BLINKING
# define STATUS_LED_ACTIVE		1		/* LED on for bit == 1	*/

#endif


/************************************************************
 * UNC90 default environment settings
 ************************************************************/
#define CONFIG_EXTRA_ENV_SETTINGS		\
	"std_bootarg=\0"			\
	"ipaddr=192.168.42.30\0"		\
	"serverip=192.168.42.1\0"		\
	"netmask=255.255.255.0\0"		\
	"gateway=192.168.42.1\0"		\
	"dns=192.168.42.1\0"			\
	"uimg=u-boot-unc90dev.bin\0"		\
	"rimg=rootfs-unc90dev.jffs2\0"		\
	"kimg=uImage-unc90dev\0"		\
	"npath=/exports/nfsroot-unc90dev\0"	\
	"smtd=setenv bootargs ip=${ipaddr}:${serverip}::${netmask}::eth0:off root=/dev/mtdblock3 rootfstype=jffs2\0"	\
	"snfs=setenv bootargs ip=${ipaddr}:${serverip}::${netmask}::eth0:off root=nfs nfsroot=${serverip}:${npath}\0"	\
	"gtk=tftp ${loadaddr} ${kimg}\0"			\
	"gtr=tftp ${loadaddr} ${rimg}\0"			\
	"gtu=tftp ${loadaddr} ${uimg}\0"			\
	"gfk=cp.w 10040000 ${loadaddr} 180000\0"		\
	"guk=usb reset;fatload usb 0 ${loadaddr} ${kimg}\0" 	\
	"gur=usb reset;fatload usb 0 ${loadaddr} ${rimg}\0" 	\
	"guu=usb reset;fatload usb 0 ${loadaddr} ${uimg}\0" 	\
	"wfk=cp.b ${loadaddr} 10040000 ${filesize}\0"		\
	"wfr=cp.b ${loadaddr} 10340000 ${filesize}\0"		\
	"wfu=cp.b ${loadaddr} 10000000 ${filesize}\0"		\
	"cfk=erase 10040000 1033ffff\0"				\
	"cfr=erase 10340000 1063ffff\0"				\
	"cfu=protect off 1:0-3;erase 10000000 1003ffff\0"	\
	"boot_flash=run smtd gfk;bootm\0"			\
	"boot_net=run snfs gtk;bootm\0"				\
	"boot_usb=run smtd guk;bootm\0"				\
	"update_kernel_tftp=run gtk cfk wfk\0"			\
	"update_rootfs_tftp=run gtr cfr wfr\0"			\
	"update_uboot_tftp=run gtu cfu wfu\0"			\
	"update_kernel_usb=run guk cfk wfk\0"			\
	"update_rootfs_usb=run gur cfr wfr\0"			\
	"update_uboot_usb=run guu cfu wfu\0"			\
	"loadaddr=20100000\0"					\
	"dhcp=no\0"						\
	"link=auto\0"						\
	""

#endif
