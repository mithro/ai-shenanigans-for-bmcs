/***********************************************************************
 *
 *  Copyright 2005 by Sistemas Embebidos S.A.
 *  All rights reserved.
 *
 *  $Id: unc90_boot.h,v 1.2 2005-10-26 06:33:05 uzeisberger Exp $
 *  Author: Pedro Perez de Heredia
 *  Descr:  UNC90 options and constants for the boot.bin primary 
 *          bootstrap image. Note that quite options are taken from
 *          unc90.h u-boot config header file, due to the selected
 *          options in boot.bin and in u-boot must be the same.
 *  
 ***********************************************************************
 *  @History:
 *     2005/03/10 : Initial version.
 ***********************************************************************/

#define	COMPILING_UNC90_BOOT_BIN
// Take some configurations from u-boot
#include "../include/configs/unc90.h"

#define				UNC90_MODULE
#define	FALSE			0
#define	TRUE			1
#define	DELAY_PLL		100
#define DELAY_MAIN_FREQ		100
#define INPUT_FREQ_MIN		900000
#define INPUT_FREQ_MAX		32000000
#define MASTER_CLOCK		AT91C_MASTER_CLOCK
#define	PLLBR			0x10483E0E	/* 48,054857 MHz (divider by 2 for USB) */
#define	UNC90_CONSOLE_BAUDRATE	CONFIG_BAUDRATE
#define	MCKR		 	(0x02 | ((UNC90_MASTER_CLOCK_DIV-1)<<8))
#define BASE_EBI_CS0_ADDRESS	0x10000000	/* base address to access memory on CS0 */
#define BASE_EBI_CS1_ADDRESS	0x20000000	/* base address to access memory on CS1 */
#define OUTPUT_FREQ_MIN		80000000
#define OUTPUT_FREQ_MAX		240000000
#define C1_IDC			(1<<2)	/* icache and/or dcache off/on */

// define UNCOMPRESS_UBOOT if using a gzip compressed u-boot image
#undef				UNCOMPRESS_UBOOT
