/***********************************************************************
 *
 * Copyright (C) 2006 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id$
 * @Author: Bernd Westermann
 * @Descr: Defines helper functions for loading fpga firmware
 * @Usage: 
 * @References: [1]
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
#include <common.h>
#include <command.h>

#ifdef CONFIG_CCW9C
#ifdef CONFIG_FPGA_LOAD

#if (CONFIG_COMMANDS & CFG_CMD_NAND)
#include <nand.h>
#endif

#include <ns9750_bbus.h>
#include <ns9750_mem.h>

#define MAC_BASE		0x60000000		/* Register base address */
#define MAC_PROG		0x70000000		/* FPGA program address */
#define MAC_MASK		0xffffc001		/* Size mask and enable bit */
#define	HW_STAID0		0x60000040		/* Station ID (4 bytes) */
#define	HW_STAID1		0x60000044		/* Station ID (2 bytes) */

#define PIN_INIT	58				/* FPGA program init */
#define PIN_DONE	65				/* FPGA program done */

#define	REG32(offset)	(* (volatile uint32 *) (MAC_BASE + (offset)))

#define HW_BOOTMUX      REG32(0x1c)     /* Bootmux?  */

#define	BOOTMUX_LOW		0x00000001		/* Bootmux,bit 0, must go low after load */

#define PIO_INPUT(pin)	set_gpio_cfg_reg_val( pin, NS9750_GPIO_CFG_FUNC_GPIO|NS9750_GPIO_CFG_INPUT);
#define PIO_GET(pin)	get_gpio_stat(pin)


#if 0
#define	FPGA_DEBUG
#endif

typedef  unsigned int uint32;
volatile ulong *fpga_ver_addr;
static ulong fpgaversion;

static inline void delay( unsigned long loops ) {
	__asm__ volatile ("1:\n"
		"subs %0, %1, #1\n"
		"bne 1b":"=r" (loops):"0" (loops));
}

unsigned char WaitForPIO (int pin) {
	int i;

	for (i=0; i<1000; i++) {
		if (PIO_GET (pin) != 0)
			return 1;
		delay(10);
	}
	return 0;
}

int fpga_load( u_char *buf, ulong bsize ) {
/*int fpga_load(void) {*/
	/* Baseband firmware image */
	volatile u_char *bbfw_bin_data = buf;
	ulong bbfw_bin_data_len = bsize;
	int i;
	char *s;
	char* pcEnd;
	/* This default MAC Addr is reserved by FS Forth-Systeme for the case of
	   EEPROM failures */
	unsigned char aucMACAddr[ 6 ] =  { 0x00,0x04,0xf3,0x00,0x06,0x36 };

#ifdef FPGA_DEBUG
	printf("Loading FPGA firmware ... ");
#endif
	
	/* Set up PIO pins for programming */
	PIO_INPUT (PIN_INIT);
	PIO_INPUT (PIN_DONE);
	
	/* CS3 is used to put the FPGA into program mode. */
	/* Map to MAC_PROG address, 32 bit width, 24 wait states. */
	*get_mem_reg_addr( NS9750_MEM_STAT_CFG( 3 ) ) = NS9750_MEM_STAT_CFG_MW_32 | NS9750_MEM_STAT_CFG_PB;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_WEN( 3 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_OEN( 3 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_RD( 3 ) ) = 24;
	*get_mem_reg_addr( NS9750_MEM_STAT_PAGE( 3 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_WR( 3 ) ) = 24;
	*get_mem_reg_addr( NS9750_MEM_STAT_TURN( 3 ) ) = 0;

	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_BASE( 3 ) ) = MAC_PROG;
	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_MASK( 3 ) ) = MAC_MASK;

	/* Put FPGA into program mode */
	*(volatile uint32 *)MAC_PROG = 0;

	/* Disable CS3 */
	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_MASK( 3 ) ) = 0;
	
#ifdef FPGA_DEBUG
	printf("\n...waiting for PIN_INIT...\n");
#endif
	/* Wait for FPGA to enter program mode */
	if (!WaitForPIO (PIN_INIT)) {
		printf("ERROR\nPIN_INIT not set\n");
		return LOAD_FPGA_FAIL;
	}

	/* CS2 is used for FPGA code download. */
	/* Map to MAC_BASE address, 32 bit width, 0 wait states. */
	*get_mem_reg_addr( NS9750_MEM_STAT_CFG( 2 ) ) = NS9750_MEM_STAT_CFG_MW_32 | NS9750_MEM_STAT_CFG_PB;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_WEN( 2 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_OEN( 2 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_RD( 2 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_PAGE( 2 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_WR( 2 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_TURN( 2 ) ) = 0;

	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_BASE( 2 ) ) = MAC_BASE;
	*get_sys_reg_addr( NS9750_SYS_CS_STATIC_MASK( 2 ) ) = MAC_MASK;


#ifdef FPGA_DEBUG
	printf("\n...sending firmware...\n");
#endif
	if (bbfw_bin_data_len == 0) {
		printf("ERROR\nlength of firmware = 0\n");
		return LOAD_FPGA_FAIL;
	}
	/* Write each byte to LSB */
	for (i = 0; i < bbfw_bin_data_len; i++)
		*(volatile uint32 *)MAC_BASE = bbfw_bin_data[i];
	
#ifdef FPGA_DEBUG
	printf("\n...waiting for PIN_DONE...\n");
#endif
	/* Wait for FPGA program complete */
	if (!WaitForPIO (PIN_DONE)) {
		printf("ERROR\nPIN_DONE not set\n");
		return LOAD_FPGA_FAIL;
	}

	/* CS2 configured for read access. */
	/* Map to MAC_BASE address, 32 bit width, 8 wait states. */
	*get_mem_reg_addr( NS9750_MEM_STAT_CFG( 2 ) ) = NS9750_MEM_STAT_CFG_MW_32 | NS9750_MEM_STAT_CFG_PB;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_WEN( 2 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_WAIT_OEN( 2 ) ) = 2;
	*get_mem_reg_addr( NS9750_MEM_STAT_RD( 2 ) ) = 8;
	*get_mem_reg_addr( NS9750_MEM_STAT_PAGE( 2 ) ) = 0;
	*get_mem_reg_addr( NS9750_MEM_STAT_WR( 2 ) ) = 4;
	*get_mem_reg_addr( NS9750_MEM_STAT_TURN( 2 ) ) = 2;

	/* Enable Input drivers on wi9c dev board. */
	HW_BOOTMUX &= ~BOOTMUX_LOW;
	
	udelay( 10000 );
	
	/* read version of FPGA firmware */
	fpga_ver_addr = (ulong *)MAC_BASE;
	fpgaversion =  *fpga_ver_addr;
	if (((fpgaversion & 0x000000FF) == 0xFF) || ((fpgaversion & 0x000000FF) == 0x00)) {
		printf("ERROR\nWrong version: 0x%x\n", (fpgaversion & 0x000000FF));
		return LOAD_FPGA_FAIL;
	}

	/* set MAC address */
	if ((s = getenv("wlanaddr")) != NULL) {
		for( i=0; i<6; i++ ) {
			aucMACAddr[i] = s?simple_strtoul(s,&pcEnd,16):0;
			s = (*s) ? pcEnd+1 : pcEnd;
		}
	}
        /* configure ethernet address */
	*(ulong *)HW_STAID0 = aucMACAddr[ 3 ] | aucMACAddr[ 2 ] << 8 | aucMACAddr[ 1 ] << 16 | aucMACAddr[ 0 ] << 24 ;
	*(ulong *)HW_STAID1 = aucMACAddr[ 5 ] << 16 | aucMACAddr[ 4 ] << 24;

	return LOAD_FPGA_OK;
}

/* Convert bitstream data and check CRC */
int fpga_checkbitstream(unsigned int show, uchar* fpgadata, ulong size) {
	extern volatile ulong checksum_calc, checksum_read, fpgadatasize;
	char *s;
	ulong fpgaloadsize;
	unsigned int length;
	unsigned int swapsize;
	char buffer[80];
	unsigned char *dataptr;
	unsigned int i;

	dataptr = (unsigned char *)fpgadata;

	/* skip the first bytes of the bitsteam, their meaning is unknown */
	length = (*dataptr << 8) + *(dataptr+1);
	dataptr+=2;
	dataptr+=length;

	/* get design name (identifier, length, string) */
	length = (*dataptr << 8) + *(dataptr+1);
	dataptr+=2;
	if (*dataptr++ != 0x61) {
		printf("%s: Design name identifier not recognized in bitstream\n",
			__FUNCTION__ );
		return LOAD_FPGA_FAIL;
	}

	length = (*dataptr << 8) + *(dataptr+1);
	dataptr+=2;
	for(i=0;i<length;i++)
		buffer[i]=*dataptr++;

	if (show)
		printf("  design: %s, V%X.%X", buffer, (fpgaversion >> 4) & 0xF, fpgaversion & 0xF);

	/* get part number (identifier, length, string) */
	if (*dataptr++ != 0x62) {
		printf("%s: Part number identifier not recognized in bitstream\n",
			__FUNCTION__ );
		return LOAD_FPGA_FAIL;
	}

	length = (*dataptr << 8) + *(dataptr+1);
	dataptr+=2;
	for(i=0;i<length;i++)
		buffer[i]=*dataptr++;
	if (0)
		printf("  part number = \"%s\"\n", buffer);

	/* get date (identifier, length, string) */
	if (*dataptr++ != 0x63) {
		printf("%s: Date identifier not recognized in bitstream\n",
		       __FUNCTION__);
		return LOAD_FPGA_FAIL;
	}

	length = (*dataptr << 8) + *(dataptr+1);
	dataptr+=2;
	for(i=0;i<length;i++)
		buffer[i]=*dataptr++;
	if (show)
		printf(", %s", buffer);

	/* get time (identifier, length, string) */
	if (*dataptr++ != 0x64) {
		printf("%s: Time identifier not recognized in bitstream\n",__FUNCTION__);
		return LOAD_FPGA_FAIL;
	}

	length = (*dataptr << 8) + *(dataptr+1);
	dataptr+=2;
	for(i=0;i<length;i++)
		buffer[i]=*dataptr++;
	if (show)
		printf(", %s\n", buffer);

	/* get fpga data length (identifier, length) */
	if (*dataptr++ != 0x65) {
		printf("%s: Data length identifier not recognized in bitstream\n",
			__FUNCTION__);
		return LOAD_FPGA_FAIL;
	}
	swapsize = ((unsigned int) *dataptr     <<24) +
	           ((unsigned int) *(dataptr+1) <<16) +
	           ((unsigned int) *(dataptr+2) <<8 ) +
	           ((unsigned int) *(dataptr+3)     ) ;
	dataptr+=4;
	if (show)
		printf("  bytes in bitstream  = 0x%x\n", swapsize);

	/* check consistency of length obtained */
	int headersize = dataptr - (unsigned char *)fpgadata;

	s = getenv ("fpgasize");
	fpgaloadsize = simple_strtoul (s, NULL, 16);
	if ((swapsize >= size) || ((unsigned int)fpgaloadsize != (swapsize + headersize))) {
		printf("%s: Could not find right length of data in bitstream\n",
			__FUNCTION__);
		return LOAD_FPGA_FAIL;
	}
	checksum_calc = crc32 (0, (uchar *)dataptr, swapsize);
	fpgadatasize = swapsize;
	dataptr = dataptr + swapsize;
	checksum_read = ((unsigned int) *dataptr    ) +
	           ((unsigned int) *(dataptr+1) <<8 ) +
	           ((unsigned int) *(dataptr+2) <<16) +
	           ((unsigned int) *(dataptr+3) <<24) ;
	
#if 0
	if (checksum_read != checksum_calc) {
		printf("%s: Checksum does not match\ncalculated checksum = 0x%x\nread checksum = 0x%x\n",
			__FUNCTION__, checksum_calc, checksum_read);
		return LOAD_FPGA_FAIL;
	}
#endif
	
	printf("  calculated checksum = 0x%x\n", checksum_calc);
	
	return LOAD_FPGA_OK;
}

#endif /* CONFIG_FPGA_LOAD */
#endif /* CONFIG_CCW9C */
