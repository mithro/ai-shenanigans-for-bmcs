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

/*
 * Changemac 1-wire EEPROM
 *
 */

#include <common.h>
#include <command.h>

#if (CONFIG_COMMANDS & CFG_CMD_VCCCORE)

int do_vcc_core ( cmd_tbl_t *cmdtp, int flag, int argc, char *argv[])
{
	int core_voltage;
	int i, index = 0;

	int core_voltage_value[16] = {
		850, 900, 950, 1000, 1050, 1100, 1150, 1200,
		1250, 1300, 1350, 1400, 1450, 1500, 1550, 1600};

	if (!(argc == 2))
	{
		printf("ERROR using vcc_core function\n");
		return (-1);
	}

	core_voltage = (int)simple_strtoul(argv[1], NULL, 10);

	for (i=0; i<16; i++) {
		if (core_voltage == core_voltage_value[i]) {
			index = i;
			break;
		}
		else {
			index = 55;
		}
	}

	if (index == 55) {
		printf("No valid Core Voltage specified\n");
		return -1;
	}

	asm volatile (	
		//////////////////////////////////////////////////////////
		// Prerequisites for Voltage-Change Sequence		//
		//////////////////////////////////////////////////////////

		// Enable PWR I²C Interface -
		// PCFR Register (Power Manager General Configuration Register)

		"ldr 	r3, =0x40F0001C;"			// Load PCFR @
		"ldr 	r2, [r3];" 					// Read PCFR value
		"ldr	r1, =0x00000040;"			// Mask bit to set PI²C_EN
		"orr	r2, r2, r1;"				// Write PI²C_EN
		"str  	r2, [r3] ;"               	// PI²C_EN

		// Program the required delay between commands -
		// PVCR (Power Manager Voltage Change Control Register)
		"ldr 	r3, =0x40F00040;"			// Load PVCR @
		"ldr 	r2, [r3];" 					// Read PVCR value
		"bic 	r2, r2, #0x00000F80;"		// Clear all Command Delay bits
		"ldr	r1, =0x00000900;"			// Set Command Delay
		"orr	r2, r2, r1;"				// Write Command Delay
		"str  	r2, [r3] ;"               	// Command Delay

		// Program the address for the external voltage regulator into PVCR
 		"ldr 	r3, =0x40F00040;"			// Load PVCR @
		"ldr 	r2, [r3];" 					// Read PVCR value
		"bic 	r2, r2, #0x0000007F;"		// Clear all Slave Address bits
		"ldr	r1, =0x0000000C;"			// Set Slave Address
		"orr	r2, r2, r1;"				// Write Slave Address
		"str  	r2, [r3] ;"               	// Slave Address

		// Load PCMDx with commands to be sent -
		// PCMDx (Power Manager I²C Command Register File n°x)
		"ldr 	r3, =0x40F000FC;"			// Load PCMD31 @
		"ldr 	r2, [r3];" 					// Read PCMD31 value
		"bic 	r2, r2, #0x00000400;"		// Clear Last Command field
		"ldr	r1, =0x00000400;"			// Set Last Command field
		"orr	r2, r2, r1;"				// Write Last Command
		"mov	r1,	%0;"					// Set Command Data
		"bic 	r2, r2, #0x000000FF;"		// Clear Command Data field
		"orr	r2, r2, r1;"				// Write Command Data
		"bic 	r2, r2, #0x00001000;"		// Clear Multi-Byte Command field
		"str  	r2, [r3] ;"               	// PCMD31

		// Write the starting command location to PVCR
		"ldr 	r3, =0x40F00040;"			// Load PVCR @
		"ldr 	r2, [r3];" 					// Read PVCR value
		"bic 	r2, r2, #0x01F00000;"		// Clear all Read Pointer bits
		"ldr	r1, =0x01F00000;"			// Set Read Pointer
		"orr	r2, r2, r1;"				// Write Read Pointer
		"str  	r2, [r3] ;"               	// Read Pointer

		//////////////////////////////////////////////////////////
		// Sequence Initiation					//
		//////////////////////////////////////////////////////////
		"ldr    r1, =0x00000008;"			// Voltage Change field, coprocessor 14
		"mov	r3, r1;"					// save value
		"mcr	p14, 0, r1, c7, c0, 0;"		// Start Voltage Change sequence
		:
		: "r"(index)
		: "r1", "r2", "r3");

	printf("Core Voltage has been set to %d mV\n", core_voltage_value[index]);
	return (0);
}

/**************************************************/
U_BOOT_CMD(
	vcc_core, 2, 1,      do_vcc_core,
	"vcc_core   - change Core Voltage\n",
	"value\n" " - Voltage value (850/.../1600)\n"
);

#endif /* CONFIG_COMMANDS & CFG_CMD_VCCCORE */
