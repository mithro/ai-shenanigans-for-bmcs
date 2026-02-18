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

#undef DEBUG


/*
 * If we are developing, we might want to start armboot from ram
 * so we MUST NOT initialize critical regs like mem-timing ...
 */
//#define CONFIG_INIT_CRITICAL		/* undef for developing */

/* General UNC90 module configuration */
//#define				UNC90_MAIN_CLOCK_184320000
//#define				UNC90_MAIN_CLOCK_179712000
//#define				UNC90_MAIN_CLOCK_165888000
#define				UNC90_MAIN_CLOCK_158515200
//#define				UNC90_MAIN_CLOCK_152064000
//#define				UNC90_MAIN_CLOCK_138240000
//#define				UNC90_MAIN_CLOCK_110592000

#define	UNC90_MASTER_CLOCK_DIV		3
#define	UNC90_MSTR_CLK_DIV_LINUX	2


#undef					CONFIG_AT91RM9200DK		/* not on an AT91RM9200DK Board	 */
#undef					CONFIG_USE_IRQ			/* we don't need IRQ/FIQ stuff */
#define CONFIG_UNC90			1
#define CONFIG_CMDLINE_TAG		1	/* enable passing of ATAGs */
#define	VERSION_TAG			" FS.3"	/* patched u-boot version from FS */
#define CONFIG_IDENT_STRING		VERSION_TAG
#define CONFIG_SETUP_MEMORY_TAGS 	1
#define CONFIG_INITRD_TAG		1
#undef CONFIG_BOOTBINFUNC
#define CONFIG_BAUDRATE			38400	/* 115200 */ 
#define CFG_MALLOC_LEN			(CFG_ENV_SIZE + 128*1024)
#define CFG_GBL_DATA_SIZE		128	/* size in bytes reserved for initial data */
#define CONFIG_BOOTDELAY		3
#undef CONFIG_HARD_I2C
#define CONFIG_SOFT_I2C
#define CFG_I2C_SPEED			100000		/* not used */
#define CFG_I2C_SLAVE			0x7f		/* not used */
#define CFG_COPY_ENV_TO_SRAM		1		/* Copy environment from eeprom to internal AT91RM9200 SRAM */
#define	CONFIG_SHOW_BOOT_PROGRESS 	/* Show boot progress on LEDs	*/
#define CFG_UNC90_ENV_IN_EEPROM		1
#undef CFG_UNC90_ENV_IN_FLASH
#define CFG_UNC90_FLASH_PROT_BOOTBIN	1
#define BOARD_LATE_INIT			1	/* Enables initializations before jumping to main loop */
#define	CONFIG_SKIP_LOWLEVEL_INIT	1	/* Still using boot.bin */
#define CONFIG_BOOTARGS    		"console=ttyS0"
#define CONFIG_BOOTCOMMAND		"run boot_flash"
#define	CFG_LONGHELP				/* undef to save memory		*/

/*
 * Software (bit-bang) I2C driver configuration
 */
#define PA_SDA		0x02000000	/* PA 25 */
#define PA_SCL		0x04000000	/* PA 26 */

#define I2C_INIT	{*AT91C_PIOA_PER |=  (PA_SDA | PA_SCL); \
			*AT91C_PIOA_OER |=  PA_SCL; \
			*AT91C_PMC_PCER = 1 << AT91C_ID_PIOA; \
			*AT91C_PIOA_IFDR |=  (PA_SDA | PA_SCL); \
			*AT91C_PIOA_IDR |=  (PA_SDA | PA_SCL); \
			*AT91C_PIOA_MDER |=  (PA_SDA | PA_SCL);}
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

/*
 * Hardware drivers
 */

/* define one of these to choose the DBGU, USART0  or USART1 as console */
#undef CONFIG_DBGU
#undef CONFIG_USART1
#define CONFIG_USART2

/* USB related stuff */
#define CONFIG_USB_OHCI			1
#define CONFIG_USB_STORAGE		1
#define CONFIG_DOS_PARTITION		1
#define CFG_DEVICE_DEREGISTER		/* needs device_deregister */
#define LITTLEENDIAN			1  /* used by usb_ohci.c */
#define CONFIG_AT91C_PQFP_UHPBUG	1  /* We are not a pqfp chip... but this solves the UNC90 hardware
                                       bug (missing pull-down resistors on the un-connected USB interface) */


#undef	CONFIG_HWFLOW			/* don't include RTS/CTS flow control support	*/
#undef	CONFIG_MODEM_SUPPORT		/* disable modem initialization stuff */

#define CONFIG_COMMANDS		\
		       ((CONFIG_CMD_DFL | \
			CFG_CMD_DHCP		|	\
			CFG_CMD_I2C)		&	\
		      ~(CFG_CMD_BDI		|	\
			CFG_CMD_IMI		|	\
			CFG_CMD_FPGA		|	\
			CFG_CMD_MISC		|	\
			CFG_CMD_LOADS )		|	\
			CFG_CMD_PING	        |	\
			CFG_CMD_DATE 	        |	\
			CFG_CMD_FAT 	        |	\
			CFG_CMD_USB		|	\
			CFG_CMD_FAT )


/************************************************************
 * UNC90 default environment settings 
 ************************************************************/
#define CONFIG_EXTRA_ENV_SETTINGS							\
	"std_bootarg=\0"								\
	"ipaddr=192.168.42.30\0"								\
	"serverip=192.168.42.1\0"								\
	"netmask=255.255.255.0\0"								\
	"dhcp=no\0"									\
	"link=auto\0"								\
	"loadaddr=20100000\0"								\
	"rimg=rootfs-unc90dev.jffs2\0"							\
	"kimg=uImage-unc90dev\0"								\
	"uimg=u-boot-unc90dev.bin\0"							\
	"npath=/exports/nfsroot-unc90dev\0"						\
	"smtd=setenv bootargs ip=$(ipaddr):$(serverip)::$(netmask)::eth0:off root=/dev/mtdblock3 rootfstype=jffs2\0"	\
	"snfs=setenv bootargs ip=$(ipaddr):$(serverip)::$(netmask)::eth0:off root=nfs nfsroot=$(serverip):$(npath)\0"	\
	"gtk=tftp $(loadaddr) $(kimg)\0"						\
	"gtr=tftp $(loadaddr) $(rimg)\0"						\
	"gtu=tftp $(loadaddr) $(uimg)\0"						\
	"gfk=cp.w 10040000 $(loadaddr) 180000\0"				\
	"guk=usb reset;fatload usb 0 $(loadaddr) $(kimg)\0" \
	"gur=usb reset;fatload usb 0 $(loadaddr) $(rimg)\0" \
	"guu=usb reset;fatload usb 0 $(loadaddr) $(uimg)\0" \
	"wfk=cp.b $(loadaddr) 10040000 $(filesize)\0"			\
	"wfr=cp.b $(loadaddr) 10340000 $(filesize)\0"			\
	"wfu=cp.b $(loadaddr) 10000000 $(filesize)\0"			\
	"cfk=erase 10040000 1033ffff\0"							\
	"cfr=erase 10340000 1063ffff\0"							\
	"cfu=protect off 1:0-3;erase 10000000 1003ffff\0"      \
	"boot_flash=run smtd gfk;bootm\0"		\
	"boot_net=run snfs gtk;bootm\0"			\
	"boot_usb=run smtd guk;bootm\0"			\
	"update_kernel_tftp=run gtk cfk wfk\0"		\
	"update_rootfs_tftp=run gtr cfr wfr\0"		\
	"update_uboot_tftp=run gtu cfu wfu\0"			\
	"update_kernel_usb=run guk cfk wfk\0"			\
	"update_rootfs_usb=run gur cfr wfr\0"			\
	"update_uboot_usb=run guu cfu wfu\0"			\
	""

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

			
			
#ifndef COMPILING_UNC90_BOOT_BIN
/* This section is not important for boot.bin */

/* this must be included AFTER the definition of CONFIG_COMMANDS (if any) */
#include <cmd_confdefs.h>

#define CONFIG_NR_DRAM_BANKS		1
#define PHYS_SDRAM			0x20000000
#define PHYS_SDRAM_SIZE			0x1000000  /* 16 megs */

#define CFG_MEMTEST_START		PHYS_SDRAM
#define CFG_MEMTEST_END			CFG_MEMTEST_START + PHYS_SDRAM_SIZE - 262144

#define CONFIG_DRIVER_ETHER
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

#define CFG_CMD_NETCONFIG_DRIVER_ETHER
#define CONFIG_NET_RETRY_COUNT		20

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
#ifdef CONFIG_BOOTBINFUNC
#define CFG_ENV_ADDR			(PHYS_FLASH_1 + 0x60000)  /* after u-boot.bin */
#define CFG_ENV_SIZE			0x10000 /* sectors are 64K here */
#else
#define CFG_ENV_ADDR			(PHYS_FLASH_1 + 0x20000)  /* between boot.bin and u-boot.bin.gz */
#define CFG_ENV_SIZE			0x10000  /* 0x8000 */
#endif 

#endif  //CFG_UNC90_ENV_IN_EEPROM
#endif



#define CFG_LOAD_ADDR			0x20100000  /* default load address */

#ifdef CONFIG_BOOTBINFUNC
#define CFG_BOOT_SIZE			0x00 /* 0 KBytes */
#define CFG_U_BOOT_BASE			PHYS_FLASH_1
#define CFG_U_BOOT_SIZE			0x40000 /* 256 KBytes */
#else
#define CFG_BOOT_SIZE			0x10000 /* 64 KBytes */
#define CFG_U_BOOT_BASE			(PHYS_FLASH_1 + CFG_BOOT_SIZE)
#define CFG_U_BOOT_SIZE			0x30000 /* 192 KBytes */
#endif

#define CFG_BAUDRATE_TABLE		{115200 , 19200, 38400, 57600, 9600 }

#define CFG_PROMPT			"UNC90> "	/* Monitor Command Prompt */
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

#define CONFIG_STACKSIZE	(32*1024)	/* regular stack */

#ifdef CONFIG_USE_IRQ
#error CONFIG_USE_IRQ not supported
#endif

#endif // (COMPILING_UNC90_BOOT_BIN)

#if defined(UNC90_MAIN_CLOCK_110592000)

  #define AT91C_MAIN_CLOCK	110592000	
  #define PLLAR			0x20173F04	/* 110,59 MHz for PLLA */

#elif defined(UNC90_MAIN_CLOCK_138240000)
   
  #define AT91C_MAIN_CLOCK	138240000	
  #define PLLAR			0x201D3F04	/* 138,24 MHz for PLLA */

#elif defined(UNC90_MAIN_CLOCK_152064000)
   
  #define AT91C_MAIN_CLOCK	152064000	
  #define PLLAR			0x20203F04	/* 119,8 MHz for PLLA */

#elif defined(UNC90_MAIN_CLOCK_158515200)
   
  #define AT91C_MAIN_CLOCK	158515200	
  #define PLLAR			0x202A3F05	/* 158,5 MHz for PLLA */
  
#elif defined(UNC90_MAIN_CLOCK_165888000)

  #define AT91C_MAIN_CLOCK	165888000	
  #define PLLAR			0x20233F04	/* 165,88 MHz for PLLA */

#elif defined(UNC90_MAIN_CLOCK_179712000)

  #define AT91C_MAIN_CLOCK	179712000	
  #define PLLAR			0x20263F04	/* 179,712 MHz for PLLA */
   
#elif defined(UNC90_MAIN_CLOCK_184320000)

  #define AT91C_MAIN_CLOCK	184320000	
  #define PLLAR			0x2027BF04	/* 184,320 MHz for PLLA */
  
#endif      

#define AT91C_MASTER_CLOCK	(AT91C_MAIN_CLOCK/UNC90_MASTER_CLOCK_DIV)
#define AT91C_MASTER_CLOCK_2	(AT91C_MAIN_CLOCK/UNC90_MSTR_CLK_DIV_LINUX)

#define AT91_SLOW_CLOCK		32768		/* slow clock */
#define CFG_AT91C_BRGR_DIVISOR	((AT91C_MASTER_CLOCK >> 4)/CONFIG_BAUDRATE)	/* hardcode so no __divsi3 : */
										/* AT91C_MASTER_CLOCK / baudrate / 16 */
#define CFG_AT91C_BRGR_DIV_2	((AT91C_MASTER_CLOCK_2 >> 4)/CONFIG_BAUDRATE)	/* idem */

#define CFG_HZ 1000
#define CFG_HZ_CLOCK AT91C_MASTER_CLOCK/2	/* AT91C_TC0_CMR is implicitly set to */
					/* AT91C_TC_TIMER_DIV1_CLOCK */

#endif
