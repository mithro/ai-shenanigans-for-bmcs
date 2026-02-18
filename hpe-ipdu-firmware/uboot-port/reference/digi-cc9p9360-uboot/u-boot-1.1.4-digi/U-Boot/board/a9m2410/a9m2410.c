/*
 * (C) Copyright 2002
 * Sysgo Real-Time Solutions, GmbH <www.elinos.com>
 * Marius Groeger <mgroeger@sysgo.de>
 *
 * (C) Copyright 2002
 * David Mueller, ELSOFT AG, <d.mueller@elsoft.ch>
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
#include <s3c2410.h>
#include <net.h>
#include <environment.h>


#include <a9m2410_nand.h>
#ifdef CONFIG_STATUS_LED
# include <status_led.h>
#endif /* CONFIG_STATUS_LED */

#ifdef CONFIG_DRIVER_CS8900
extern int eth_init (bd_t * bd);
#endif

/* ------------------------------------------------------------------------- */

#define FCLK_SPEED 1

#ifndef CPU_2440
#define M_MDIV	0xA1		/* Fout = 202.8MHz */
#define M_PDIV	0x3
#define M_SDIV	0x1
#endif /* CPU_2440 */

#define USB_CLOCK 1

#ifndef CPU_2440
#define U_M_MDIV	0x78
#define U_M_PDIV	0x2
#define U_M_SDIV	0x3
#endif


static ulong size;
ulong nsize;
extern env_t *env_ptr;

static inline void delay (unsigned long loops)
{
	__asm__ volatile ("1:\n"
	  "subs %0, %1, #1\n"
	  "bne 1b":"=r" (loops):"0" (loops));
}

/*
 * Miscellaneous platform dependent initialisations
 */

int board_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;
	S3C24X0_GPIO * const gpio = S3C24X0_GetBase_GPIO();

	/* set up the I/O ports */
	gpio->GPACON = 0x007FFFFF;
	gpio->GPCCON = 0x0;
	gpio->GPCUP = 0x0;
	gpio->GPDCON = 0x0;
	gpio->GPDUP = 0x0;
	gpio->GPECON = 0xAAAAAAAA;
	gpio->GPEUP = 0x0000E03F;
#ifdef CPU_2440
	gpio->GPBCON = 0x0;		/* all inputs */
	gpio->GPBUP = 0x7;		/* pullup disabled for GPB0..3 */
	gpio->GPFCON = 0x00009000;	/* GPF7 CLK_INT#, GPF6 Debug-LED */
	gpio->GPFUP = 0x000000FF;
# ifdef LCD_PWREN
	gpio->GPGDAT |= 0x1010;		/* switch off IDLE_SW#, switch off LCD backlight */
#  ifdef INV_PWREN
	gpio->GPGCON = 0x0100A93A;	/* switch off USB device */
	gpio->GPGUP = 0x0000F000;
#  else
	gpio->GPGCON = 0x0100AB3A;	/* switch off USB device, LCD_PWREN */
	gpio->GPGUP = 0x0000F010;	/* disable pullup for LCD_PWREN */
#  endif /* INV_PWREN */
# else
	gpio->GPGDAT |= 0x1000;		/* switch off IDLE_SW# */
# endif /* LCD_PWREN */
	gpio->GPJDAT = (1 << 12) | (0 << 11);
	gpio->GPJCON = 0x016aaaa;
	gpio->GPJUP = ~ ( (0<<12)|(1<<11));

	gpio->GPJDAT = ( 0 << 12 ) | ( 0 << 11);
	gpio->GPJCON = 0x016aaaa;
	gpio->GPJUP = 0x1fff;

	gpio->DSC0 = 0;
	gpio->DSC1 = 0;
#elif A9M2410_0
	gpio->GPBCON = 0x0;		/* all inputs */
	gpio->GPBUP = 0x0;		/* pullup enabled */
	gpio->GPFDAT &= 0x0FD;		/* switch FCPUSEL# to low */
	gpio->GPFCON = 0x00009004;	/* GPF7 CLK_INT#, GPF6 Debug-LED, GPF1 FCPUSEL# */
	gpio->GPFUP = 0x000000C2;
	gpio->GPGCON = 0xFF29A838;
	gpio->GPGUP = 0x0000F30A;
#else	/* A9M2410_1 */
	gpio->GPBCON = 0x0;		/* all inputs */
	gpio->GPBUP = 0x7;		/* pullup disabled for GPB0..3 */
	gpio->GPFCON = 0x00009000;	/* GPF7 CLK_INT#, GPF6 Debug-LED */
	gpio->GPFUP = 0x000000FF;
# ifdef LCD_PWREN
	gpio->GPGDAT |= 0x0010;		/* switch off LCD backlight */
#  ifdef INV_PWREN
	gpio->GPGCON = 0xFF00A938;	/* switch off USB device */
	gpio->GPGUP = 0x0000F000;
#  else
	gpio->GPGCON = 0xFF00AB38;	/* switch off USB device, LCD_PWREN */
	gpio->GPGUP = 0x0000F010;	/* disable pullup for LCD_PWREN */
#  endif /* INV_PWREN */
# endif /* LCD_PWREN */
#endif	/* CPU_2440 */

	gpio->GPHDAT |= 0x100;		/* switch BOOTINT/GPIO_ON# to high */
	gpio->GPHUP = 0x000007FF;

#ifdef USE_COM3
	gpio->GPHCON = 0x0029AAAA;
#else
	gpio->GPHCON = 0x0029FAAA;
#endif	/* USE_COM3 */

	gpio->MISCCR = 0x10140;		/* USB port1 normal,USB port0 normal, USB1 pads for device */
					/* PCLK output on CLKOUT0,UPLL CLK output on CLKOUT1 */

	/* arch number of A9M24x0 */
	if (machine_is_a9m2410())
		gd->bd->bi_arch_number = MACH_TYPE_A9M2410;
	else if (machine_is_a9m2440())
		gd->bd->bi_arch_number = MACH_TYPE_A9M2440;
	else
		gd->bd->bi_arch_number = MACH_TYPE_SMDK2410;

	/* adress of boot parameters */
	gd->bd->bi_boot_params = 0x30000100;

#if defined(CONFIG_STATUS_LED)
	status_led_set(STATUS_LED_BOOT,STATUS_LED_ON);
#endif /* CONFIG_STATUS_LED */


	switch (gpio->GPBDAT & 0x03) {
		case 0: size =  16 * (1024*1024);
                        break;
		case 1: size =  64 * (1024*1024);
                        break;
		case 2: size =  32 * (1024*1024);
                        break;
		case 3: size =  128 * (1024*1024);
                        break;
		default: size = 64 * (1024*1024);
                        break;
	}

        icache_enable();
	dcache_enable();

	return 0;
}
#ifndef A9M2410_0
static u8 Get_SDRAM_BankSize(void)
{
	S3C24X0_GPIO * const gpio = S3C24X0_GetBase_GPIO();

	vu_long *mem_addr1, *mem_addr2;
	ulong value1, value2, value3, value4, value5;

        value3 = 0xaaaa5555;
        value4 = 0xa5a5a5a5;

	switch (gpio->GPBDAT & 0x03) {
		case 0: size =  16 * (1024*1024);
                        break;
		case 1: size =  64 * (1024*1024);
                        break;
		case 2: size =  32 * (1024*1024);
                        break;
		case 3: size =  128 * (1024*1024);
                        break;
		default: size = 64 * (1024*1024);
                        break;
	}
	mem_addr1 = (ulong *)CFG_MEMTEST_START;
	mem_addr2 = (ulong *)(CFG_MEMTEST_START + size);

	value1 =  *mem_addr1;	/* save old value */
	*mem_addr1 = value4;	/* write pattern to 1st bank */
	*mem_addr2 = value3;	/* write pattern to 2nd bank */

	value5 = *mem_addr1;
	value2 = *mem_addr2;

	*mem_addr1 = value1;	/* write back old value */

	printf("");		/* necessary to work with correct values */

#if 0
        printf("value1: 0x%x\nvalue2: 0x%x\nvalue3: 0x%x\nvalue4: 0x%x\nvalue5: 0x%x\nA1: 0x%x\nA2: 0x%x\n",
        	value1,value2,value3,value4,value5,mem_addr1,mem_addr2);
#endif
	if (value2 == value3) {
		if (value4 != value5)
			return 1;	/* only one bank */
		else
			return 0;	/* both banks */
	} else
		return 1;		/* only one bank */

}

#endif	/* A9M2410_0 */

int dram_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;

#ifndef A9M2410_0
	gd->bd->bi_dram[0].start = PHYS_SDRAM_1;
	gd->bd->bi_dram[0].size = size;
	if (Get_SDRAM_BankSize() == 0)
		gd->bd->bi_dram[0].size += size;

#else
	gd->bd->bi_dram[0].start = PHYS_SDRAM_1;
	gd->bd->bi_dram[0].size = PHYS_SDRAM_1_SIZE;
	gd->bd->bi_dram[1].start = PHYS_SDRAM_2;
	gd->bd->bi_dram[1].size = PHYS_SDRAM_2_SIZE;
# ifndef SDRAM_64MB
	gd->bd->bi_dram[2].start = PHYS_SDRAM_3;
	gd->bd->bi_dram[2].size = PHYS_SDRAM_3_SIZE;
	gd->bd->bi_dram[3].start = PHYS_SDRAM_4;
	gd->bd->bi_dram[3].size = PHYS_SDRAM_4_SIZE;
	gd->bd->bi_dram[4].start = PHYS_SDRAM_5;
	gd->bd->bi_dram[4].size = PHYS_SDRAM_5_SIZE;
	gd->bd->bi_dram[5].start = PHYS_SDRAM_6;
	gd->bd->bi_dram[5].size = PHYS_SDRAM_6_SIZE;
	gd->bd->bi_dram[6].start = PHYS_SDRAM_7;
	gd->bd->bi_dram[6].size = PHYS_SDRAM_7_SIZE;
	gd->bd->bi_dram[7].start = PHYS_SDRAM_8;
	gd->bd->bi_dram[7].size = PHYS_SDRAM_8_SIZE;
# endif /* SDRAM_64MB */
#endif /* A9M2410_0 */

	return 0;
}


#if defined(CONFIG_STATUS_LED)
static int status_led_fail = 0;
#endif /* CONFIG_STATUS_LED */

#if defined(BOARD_LATE_INIT)
int board_late_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;

	char cmd[60];
	char flashsize[32];
	char flashpartsize[32];

	S3C24X0_GPIO * const gpio = S3C24X0_GetBase_GPIO();

	if ((gpio->GSTATUS1 & 0xFFFFF000) == 0x32440000) {
		printf("CPU:   S3C2440A@");
	  	if ((gpio->GPFDAT & 0x2) == 0x2)
			printf("400MHz\n");
		else
			printf("300MHz\n");

	} else {
		if ((gpio->GSTATUS1 & 0xFFFFF00F) == 0x32410000)
			printf("CPU:   S3C2410X@");
		else
			printf("CPU:   S3C2410A@");

	  	if ((gpio->GPFDAT & 0x2) == 0x2)
			printf("266MHz\n");
		else
			printf("200MHz\n");
	}

#ifndef A9M2410_0
	ulong hclk,i_hclk,f_hclk;

	hclk = get_HCLK();
	i_hclk = hclk/1000000;
	f_hclk = hclk/10000 - (100*i_hclk);

	printf("SDRAM: clock=%d.%dMHz\n",i_hclk,f_hclk);

	switch (gpio->GPBDAT & 0x04) {
		case 0: printf("SDRAM: CL=2\n");
			break;
		case 4: printf("SDRAM: CL=3\n");
			break;
		default:
			break;
	}

        if (Get_SDRAM_BankSize() != 0) {
		gpio->MISCCR |= (1 << 18);	/* switch off SCLK for 2nd bank */
		printf("Clock for second SDRAM chip switched off\n");
	}

	gpio->GPHDAT &= ~0x100;	/* switch GPIO_ON# to low */

# if (CONFIG_COMMANDS & CFG_CMD_NAND)
# include <nand.h>
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
	gd->bd->bi_nand[2].size = nand_info[0].size - NAND_START_2;

	vu_long *mem_addr;
	ulong value;

	mem_addr = (ulong *)NAND_ECC_INFO;
	value =  *mem_addr;	/* get ECC Info */
	if (value != 0x00) {
		printf("%ld ECC errors occured and corrected\n", value);
		status_led_fail = 1;
	}

# endif
#endif

	gd->bd->bi_gw_addr = getenv_IPaddr ("gatewayip");
	gd->bd->bi_ip_mask = getenv_IPaddr ("netmask");
	gd->bd->bi_dhcp_addr = getenv_IPaddr ("serverip");
	gd->bd->bi_dns_addr = getenv_IPaddr ("dnsip");
	gd->bd->uboot_env_addr = (unsigned long)env_ptr;

	/* added for use in u-boot macros */
	sprintf(flashsize, "%x", nand_info[0].size);
	sprintf(flashpartsize, "%x", gd->bd->bi_nand[2].size);
	setenv("flashsize", flashsize);
	setenv("flashpartsize", flashpartsize);

	/* copy bdinfo to start of boot-parameter block */
	memcpy((ulong *)gd->bd->bi_boot_params, gd->bd, sizeof(bd_t));

#ifdef A9M2410_USER_KEY
	if ((gpio->GPFDAT & 0x1) == 0x1) {
		printf("\nUser Key 1 pressed\n");
		if (getenv("key1") != NULL) {
			sprintf(cmd, "run key1");
			run_command(cmd, 0);
		}
        }
	if ((gpio->GPGDAT & 0x8) == 0x8) {
		printf("\nUser Key 2 pressed\n");
		if (getenv("key2") != NULL) {
			sprintf(cmd, "run key2");
			run_command(cmd, 0);
		}
        }
#endif

	if( eth_init( gd->bd ) <0 )
		printf("\nCould not initialize ethernet\n");

#if defined(CONFIG_STATUS_LED)
	if (!status_led_fail) {
		status_led_set(STATUS_LED_BOOT,STATUS_LED_OFF);
		status_led_fail = 0;
  	}
#endif /* CONFIG_STATUS_LED */
	return 0;
}
#endif /* BOARD_LATE_INIT */


#ifdef CONFIG_SHOW_BOOT_PROGRESS
void show_boot_progress (int status)
{
#if defined(CONFIG_STATUS_LED)
	if (status < 0) {
        	/* ready to transfer to kernel, make sure LED is proper state */
        	status_led_set(STATUS_LED_BOOT,STATUS_LED_ON);
        	status_led_fail = 1;
	}
#endif /* CONFIG_STATUS_LED */
}
#endif /* CONFIG_SHOW_BOOT_PROGRESS */


