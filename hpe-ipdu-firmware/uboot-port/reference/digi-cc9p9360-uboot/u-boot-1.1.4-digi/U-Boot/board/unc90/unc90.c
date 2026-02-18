/*
 * (C) Copyright 2002
 * Sysgo Real-Time Solutions, GmbH <www.elinos.com>
 * Marius Groeger <mgroeger@sysgo.de>
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
#include <asm/arch/AT91RM9200.h>


static void unc90_enable_ethernet_phy (void);

/* ------------------------------------------------------------------------- */
/*
 * Miscelaneous platform dependent initialisations
 */

int board_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;

	/* Enable Ethernet PHY */
	unc90_enable_ethernet_phy();

	/* Enable Ctrlc */
	console_init_f ();

	//icache_enable ();

#ifdef USE_920T_MMU
	//dcache_enable ();
#endif /* USE_920T_MMU */

	/* memory and cpu-speed are setup before relocation */
	/* so we do _nothing_ here */

	/* arch number of UNC90-Module */
	if (machine_is_unc90())
		gd->bd->bi_arch_number = MACH_TYPE_UNC90;

	/* adress of boot parameters */
	gd->bd->bi_boot_params = PHYS_SDRAM + 0x100;

	return 0;
}

/*****************************************************************************
 * initialization ethernet phy
 ****************************************************************************/
static void unc90_enable_ethernet_phy (void)
{
	AT91PS_PIO p_pio = AT91C_BASE_PIOA;

	/* Setup the PWRDWN pin on UNC90, PA4 configured as output active low */
	p_pio->PIO_PER = AT91C_PIO_PA4;
	p_pio->PIO_OER = AT91C_PIO_PA4;
	p_pio->PIO_CODR = AT91C_PIO_PA4;
}

void flash_preinit(void)
{
	/* Nothing to do... */
}

static u8 compute_sdram_nr_banks( void )
{
	vu_long *bank_addr1, *bank_addr2;
	ulong bank1_old, pattern_bank1, pattern_bank2, read_bank1, read_bank2;

        pattern_bank2 = 0xaaaa5555;
        pattern_bank1 = 0xa5a5a5a5;

	bank_addr1 = (ulong *)PHYS_SDRAM;
	bank_addr2 = (ulong *)(PHYS_SDRAM + PHYS_SDRAM_SIZE);

	bank1_old =  *bank_addr1;	/* save old value */
	*bank_addr1 = pattern_bank1;	/* write pattern to 1st bank */
	*bank_addr2 = pattern_bank2;	/* write pattern to 2nd bank */

	read_bank1 = *bank_addr1;	/* read from 1st bank */
	read_bank2 = *bank_addr2;	/* read from 2nd bank */

	*bank_addr1 = bank1_old;	/* write back old value */

	if( read_bank2 == pattern_bank2 ) {
		if( pattern_bank1 != read_bank1 )
			return 1;	/* only one bank */
		else
			return 2;	/* both banks */
	}

	return 1;	/* only one bank */

}

int dram_init (void)
{
	DECLARE_GLOBAL_DATA_PTR;

	gd->bd->bi_dram[0].start = PHYS_SDRAM;
	gd->bd->bi_dram[0].size = PHYS_SDRAM_SIZE;

	// Depending on the number of banks... adjust the SDRAM size
	gd->bd->bi_dram[0].size *= compute_sdram_nr_banks();

	return 0;
}


#if defined(BOARD_LATE_INIT)
#include <net.h>
int board_late_init( )
{
	char flashsize[32];
	char flashpartsize[32];

	/* added for use in u-boot macros */
	sprintf(flashsize, "%x", PHYS_FLASH_SIZE);
	sprintf(flashpartsize, "%x", PHYS_FLASH_SIZE - 0x340000);
	setenv("flashsize", flashsize);
	setenv("flashpartsize", flashpartsize);

#ifdef CONFIG_DRIVER_ETHER
	DECLARE_GLOBAL_DATA_PTR;

	if( eth_init( gd->bd ) < 0 )
		printf( "Error initializing ethernet intefaze\n" );
#endif
	return 0;
}

#endif /*BOARD_LATE_INIT*/

#ifdef CONFIG_STATUS_LED
#include <status_led.h>
#endif /* CONFIG_STATUS_LED */

#ifdef CONFIG_SHOW_BOOT_PROGRESS
void show_boot_progress (int status)
{
	if( status < 0 ) {
		/* ready to transfer to kernel, make sure LED is proper state */
		status_led_set( STATUS_LED_BOOT, STATUS_LED_ON );
	}
}
#endif /* CONFIG_SHOW_BOOT_PROGRESS */





