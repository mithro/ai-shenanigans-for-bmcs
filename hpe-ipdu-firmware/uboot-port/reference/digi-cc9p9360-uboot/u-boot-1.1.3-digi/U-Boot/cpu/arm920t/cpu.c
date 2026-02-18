/*
 * (C) Copyright 2002
 * Sysgo Real-Time Solutions, GmbH <www.elinos.com>
 * Marius Groeger <mgroeger@sysgo.de>
 *
 * (C) Copyright 2002
 * Gary Jennejohn, DENX Software Engineering, <gj@denx.de>
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

/*
 * CPU specific code
 */

#include <common.h>
#include <command.h>
#include <arm920t.h>
#ifdef CONFIG_UNC90	
#include <asm/arch/hardware.h>
#endif

/* read co-processor 15, register #1 (control register) */
static unsigned long read_p15_c1 (void)
{
	unsigned long value;

	__asm__ __volatile__(
		"mrc     p15, 0, %0, c1, c0, 0   @ read control reg\n"
		: "=r" (value)
		:
		: "memory");

#ifdef MMU_DEBUG
	printf ("p15/c1 is = %08lx\n", value);
#endif
	return value;
}

/* write to co-processor 15, register #1 (control register) */
static void write_p15_c1 (unsigned long value)
{
#ifdef MMU_DEBUG
	printf ("write %08lx to p15/c1\n", value);
#endif
	__asm__ __volatile__(
		"mcr     p15, 0, %0, c1, c0, 0   @ write it back\n"
		:
		: "r" (value)
		: "memory");

	read_p15_c1 ();
}

static void cp_delay (void)
{
	volatile int i;

	/* copro seems to need some delay between reading and writing */
	for (i = 0; i < 100; i++);
}

/* See also ARM Ref. Man. */
#define C1_MMU		(1<<0)		/* mmu off/on */
#define C1_ALIGN	(1<<1)		/* alignment faults off/on */
#define C1_DC		(1<<2)		/* dcache off/on */
#define C1_BIG_ENDIAN	(1<<7)	/* big endian off/on */
#define C1_SYS_PROT	(1<<8)		/* system protection */
#define C1_ROM_PROT	(1<<9)		/* ROM protection */
#define C1_IC		(1<<12)		/* icache off/on */
#define C1_HIGH_VECTORS	(1<<13)	/* location of vectors: low/high addresses */
#define RESERVED_1	(0xf << 3)	/* must be 111b for R/W */

int cpu_init (void)
{
	/*
	 * setup up stacks if necessary
	 */
#ifdef CONFIG_USE_IRQ
	DECLARE_GLOBAL_DATA_PTR;

	IRQ_STACK_START = _armboot_start - CFG_MALLOC_LEN - CFG_GBL_DATA_SIZE - 4;
	FIQ_STACK_START = IRQ_STACK_START - CONFIG_STACKSIZE_IRQ;
#endif
	return 0;
}

#ifdef CONFIG_UNC90	
#define	MAX_LOOPS_FOR_MCKRDY	100000000

int update_master_clock_freq( int css, int div, int pres )
{
	DECLARE_GLOBAL_DATA_PTR;
	int baudrate;
	AT91PS_PMC pmc;
#ifdef CONFIG_DBGU
	AT91PS_USART us = (AT91PS_USART) AT91C_BASE_DBGU;
#endif
#ifdef CONFIG_USART0
	AT91PS_USART us = (AT91PS_USART) AT91C_BASE_US0;
#endif
#ifdef CONFIG_USART1
	AT91PS_USART us = (AT91PS_USART) AT91C_BASE_US1;
#endif
#ifdef CONFIG_USART2
	AT91PS_USART us = (AT91PS_USART) AT91C_BASE_US2;
#endif
	 
	if( ( pres < 0 || pres > 7 ) ||
	    ( css < 0 || pres > 3 ) ||
	    ( div < 0 || div > 3 ) )
		return 1;
	
	pmc = AT91C_BASE_PMC;

	// Write MCKR in two accesses. See AT91RM9200 errata sheet
	pmc->PMC_MCKR = (div << 8);
	pmc->PMC_MCKR = css | (pres << 2) | (div << 8);

	while( !(pmc->PMC_SR & AT91C_PMC_MCKRDY) );

	if( (baudrate = gd->baudrate) <= 0 )
		baudrate = CONFIG_BAUDRATE;
	if( baudrate == 0 || baudrate == CONFIG_BAUDRATE )
		us->US_BRGR = CFG_AT91C_BRGR_DIV_2;	/* hardcode so no __divsi3 */
	else
		us->US_BRGR = (AT91C_MASTER_CLOCK_2 >> 4)/baudrate;
	
	return 0;
}
#endif


int cleanup_before_linux (void)
{
	/*
	 * this function is called just before we call linux
	 * it prepares the processor for linux
	 *
	 * we turn off caches etc ...
	 */

	unsigned long i;
#ifdef CONFIG_UNC90	
	int ret;

	/*
	 * Configure the Master Clock as PLLA clock / 2 to optimize 
	 * peripheral performance.
	 */
	//printf( "Configuring MCKR to jump to linux\n" );
	
	if( ( ret = update_master_clock_freq( AT91C_PMC_CSS_PLLA_CLK,
	                                      UNC90_MSTR_CLK_DIV_LINUX - 1,
	                                      AT91C_PMC_PRES_CLK ) ) != 0 )
		printf( "update_master_clock_freq error: %d\n", ret );
#endif

	disable_interrupts ();

	/* turn off I/D-cache */
	asm ("mrc p15, 0, %0, c1, c0, 0":"=r" (i));
	i &= ~(C1_DC | C1_IC);
	asm ("mcr p15, 0, %0, c1, c0, 0": :"r" (i));

	/* flush I/D-cache */
	i = 0;
	asm ("mcr p15, 0, %0, c7, c7, 0": :"r" (i));
	return (0);
}

int do_reset (cmd_tbl_t *cmdtp, int flag, int argc, char *argv[])
{
	disable_interrupts ();
	reset_cpu (0);
	/*NOTREACHED*/
	return (0);
}

void icache_enable (void)
{
	ulong reg;

	reg = read_p15_c1 ();
	cp_delay ();
	write_p15_c1 (reg | C1_IC);
}

void icache_disable (void)
{
	ulong reg;

	reg = read_p15_c1 ();
	cp_delay ();
	write_p15_c1 (reg & ~C1_IC);
}

int icache_status (void)
{
	return (read_p15_c1 () & C1_IC) != 0;
}

#ifdef USE_920T_MMU
/* It makes no sense to use the dcache if the MMU is not enabled */
void dcache_enable (void)
{
	ulong reg;

	reg = read_p15_c1 ();
	cp_delay ();
	write_p15_c1 (reg | C1_DC);
}

void dcache_disable (void)
{
	ulong reg;

	reg = read_p15_c1 ();
	cp_delay ();
	reg &= ~C1_DC;
	write_p15_c1 (reg);
}

int dcache_status (void)
{
	return (read_p15_c1 () & C1_DC) != 0;
}
#endif
