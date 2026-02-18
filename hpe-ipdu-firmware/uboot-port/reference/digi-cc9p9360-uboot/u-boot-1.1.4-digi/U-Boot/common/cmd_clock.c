/*
 * (C) Copyright 2000
 * Wolfgang Denk, DENX Software Engineering, wd@denx.de.
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
/***********************************************************************
 *  @History:
 *	2005/09/24 : cleanup (Bernd Westermann)
 ***********************************************************************/

#include <common.h>
#include <command.h>

#if (CONFIG_COMMANDS & CFG_CMD_BSP)

typedef struct clock_param_s {
	unsigned short	t_clock;
	unsigned short	sys_clock;
	unsigned short	mem_clock;
	unsigned short	SDRAM_clock;
	unsigned short	LCD_clock;
	unsigned char 	CCCR_A;
	unsigned char	CCCR_L;
	unsigned char	CCCR_2N;
	unsigned char	CLKCFG_T;
	unsigned char	CLKCFG_HT;
	unsigned char	CLKCFG_B;
} clock_param_t;

clock_param_t clocks[] = {
	{208, 208, 208, 104, 104, 1, 16, 2, 1, 0, 1},
	{312, 208, 208, 104, 104, 1, 16, 3, 1, 0, 1},
	{416, 208, 208, 104, 104, 1, 16, 4, 1, 0, 1},
	{520, 208, 208, 104, 104, 1, 16, 5, 1, 0, 1},
	{624, 208, 208, 104, 104, 1, 16, 6, 1, 0, 1}};

clock_param_t *get_clock_rate(void);

int do_cmd_clock ( cmd_tbl_t *cmdtp, int flag, int argc, char *argv[])
{
	int new_clock, ind;
	int new_clock_set=1;
	int clock_ok;

	clock_param_t	*cpara;
	unsigned long CCCR_reg, CLKCFG_reg;

	if (argc == 1)
	{
		cpara = get_clock_rate();
		printf("Current working clock is : %d MHz\n", cpara->t_clock);
		return (0);
	}

	if (!(argc == 2))
	{
		printf("ERROR using changemac function\n");
		return (-1);
	}

	new_clock = (int)simple_strtoul(argv[1], NULL, 10);

	if (new_clock_set) {
		clock_ok = 1;
 		ind = new_clock / 100;

		switch (ind) {
			case 2:	ind = 0;
				break;
			case 3:	ind = 1;
				break;
			case 4:	ind = 2;
				break;
			case 5:	ind = 3;
				break;
			case 6:	ind = 4;
				break;
			default:
				clock_ok = 0;
				cpara = get_clock_rate();
				printf("\ndon't know how to install %d MHz, keeping clock speed at %d MHz\n\n", new_clock, cpara->t_clock);
		   		return (-1);
		}

		printf("Clock speed will be changed to %d MHz\n", clocks[ind].t_clock);

		clock_ok = 1;

		CCCR_reg = clocks[ind].CCCR_L | (clocks[ind].CCCR_2N) <<7 | (clocks[ind].CCCR_A) <<25;
		CLKCFG_reg = clocks[ind].CLKCFG_T | (clocks[ind].CLKCFG_HT)<<2 | (clocks[ind].CLKCFG_B)<<3;

		asm volatile (
			"ldr 	r3, =0x48000004;"	// MDREFR Register
			"ldr 	r2, [r3];" 		// read MDREFR value
			"ldr	r1, =0x00020000;"	// mask bit to set K1DB2
			"orr	r2, r2, r1;"		// write K1DB2
			"str  	r2, [r3] ;"		// Set K1DB2
			"mov	r1,	%0;"
			"ldr    r2, =0x41300000;"	// Core Clock Config Reg
			"ldr    r3, [r2];"		// read the register
			"ldr    r4, =0xcc000000;"	// mask bits to preserve
			"and	r3, r3, r4;"
			"orr	r3, r3, r1;"		// write speed values
			"str    r3, [r2];"    		// set speed
    			"mov	r1, %1;"		// set turbo mode, set fast bus
    			"orr 	r1, r1, #0x2;"		// set change frequency
			"mov	r3, r1;"		// save value
			"mcr	p14, 0, r1, c6, c0, 0;"	// frequency change  sequence
			"ldr	r1, [r2];"		// dummy read from CCCR

			"100:;"
			"mrc	p14, 0, r1, c6, c0, 0;"	// read CLKCFG
			"cmp r3, r1;"			// compare it with value written
			"bne 100b;"
			:
			: "r"(CCCR_reg),  "r"(CLKCFG_reg)
			: "r1", "r2", "r3", "r4");

		cpara=get_clock_rate();
		if (clock_ok) {
			printf("Actual Processor Clock: %d MHz   System Bus Clock %d MHz    MEM Clock %d MHz   SDRAM Clock %d MHz   LCD Clock %d MHz\n",
			cpara->t_clock, cpara->sys_clock, cpara->mem_clock, cpara->SDRAM_clock, cpara->LCD_clock);
		}
	} else {
		cpara = get_clock_rate();
		if (cpara == 0) {
			printf("error decoding clock settings, clock unknown\n");
		} else {
			printf("Actual Processor Clock: %d MHz   System Bus Clock %d MHz    MEM Clock %d MHz   SDRAM Clock %d MHz   LCD Clock %d MHz\n",
			cpara->t_clock, cpara->sys_clock, cpara->mem_clock, cpara->SDRAM_clock, cpara->LCD_clock);
		}
	}
	return (0);
}

clock_param_t *get_clock_rate(void) {
	unsigned long CCCR_reg, CLKCFG_reg;

	unsigned char	clkcfg_t, clkcfg_ht, clkcfg_b;
	unsigned char	cccr_l, cccr_2n, cccr_a;

	int i, match=0;

	asm volatile (
		"ldr r1, =0x41300000;"		// Core Clock Config Reg
		"ldr %0, [r1];"
		"mrc p14, 0, %1, c6, c0, 0;"	// read CCLKCFG register
		: "=r"(CCCR_reg), "=r"(CLKCFG_reg)
		:
		: "r1"
	);

	clkcfg_t	=	CLKCFG_reg & 0x01;
	clkcfg_ht	=	(CLKCFG_reg & 0x04) >> 2;
	clkcfg_b	=	(CLKCFG_reg & 0x08) >> 3;

	cccr_l		=	(CCCR_reg & 0x0000001f) >> 0;
	cccr_2n		=	(CCCR_reg & 0x00000780) >> 7;
	cccr_a		=	(CCCR_reg & 0x02000000) >> 25;

	for(i=0; i< sizeof(clocks) / sizeof(clock_param_t); i++) {
		if (clkcfg_t 	== clocks[i].CLKCFG_T	&& \
			clkcfg_ht	== clocks[i].CLKCFG_HT && \
			clkcfg_b	== clocks[i].CLKCFG_B && \
			cccr_l		== clocks[i].CCCR_L && \
			cccr_2n		== clocks[i].CCCR_2N && \
			cccr_a		== clocks[i].CCCR_A) {
			match=1;
			break;
		}
	}

	if (!match) {
		printf("error, unknown clock configuration\n");
		return 0;
	} else {
		return 	&(clocks[i]);
	}
}

/**************************************************/
U_BOOT_CMD(
	clock, 2, 1,      do_cmd_clock,
	"clock   - Set Processor Clock\n",
	"value\n" " - Clock value (208/312/416/520/624)\n"
);

#endif /* CONFIG_COMMANDS & CFG_CMD_BSP */
