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

/*
 * Changemac 1-wire EEPROM
 *
 */
/***********************************************************************
 *  @History:
 *	2005/09/24 : cleanup (Bernd Westermann)
 ***********************************************************************/

#include <common.h>
#include <command.h>

#ifdef CONFIG_CCXP
int set_esa_1w(unsigned char *hard_mac_data);

unsigned char string_to_hex_conversion_table[55] = {
		0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,	0x08,
		0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,	0x0A,
		0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x00, 0x00, 0x00,	0x00,
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,	0x00,
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,	0x00,
		0x00, 0x00, 0x00, 0x00, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F};

int do_changemac ( cmd_tbl_t *cmdtp, int flag, int argc, char *argv[])
{
	uchar *mac_addr;
	int i, j, k, index_high, index_low=0;
	int size;
	int set_mac_ok;

	// hard_mac_data will contain the MAC address which will be programmed in the 1-wire EEPROM
	unsigned char hard_mac_data[8] = {0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};

	// The table below gives a correspondance, between the value received from the console and
	// the real hexadecimal value which need to be programmed in the EEPROM.
	//
	//	String      ASCII value of String     	Index in string_to_hex_conversion_table   	Hex value in the table
	//	'0'         0x30                      	0x30 - 0x30 = 0            				 	0x00
	//	'1'			0x31						0x31 - 0x30 = 1								0x01
	//	...
	//  'A'         0x41                      	0x41 - 0x30 = 17           					0x0A
   	//	'B'			0x42						0x42 - 0x30 = 18							0x0B
   	//	...
   	//	'a'			0x61						0x61 - 0x30 = 49							0x0A
   	//  ...
   	// The ASCII value different from '0' to '1' and 'A' to 'F' and 'a' to 'f' have a fixed value of 0.
   	// We made a translation (- 0x30) so that the first value in the table is for the ASCII code of '0'.

	if (!(argc == 2))
	{
		printf("ERROR using changemac function\n");
		return (-1);
	}

	mac_addr = argv[1];

	printf("Set following MAC ADDRESS : %s\n", mac_addr);

	// Determine the size of the string
	size = strlen(mac_addr);

	// Determine if the MAC Address is written either 0x010203040506 or 010203040506.
	// If the second character is an 'x' or 'X', the MAC address will began at the next character
	// otherwise, the first byte of the MAC address is the first character

	if (mac_addr[1] == 'x' || mac_addr[1] == 'X') {
		i=2;
		k=0;
	}
	else {
		i=0;
		k=0;
	}

	for (j=i; j<(size-1); j=j+2) {
		index_high = (int)(mac_addr[j] - '0');
		index_low = (int)(mac_addr[j+1] - '0');

		// The decoded value of the upper string is shifted from 1 byte, so that
		// one entry of hard_mac_data table is equivalent to two characters
		// For instance :
		// 'A' 'C' become 0xAC

		hard_mac_data[k] = (string_to_hex_conversion_table[index_high] << 4) | string_to_hex_conversion_table[index_low];

		k++;
	}

	set_mac_ok = set_esa_1w(hard_mac_data);

	if (set_mac_ok) {
		printf(" MAC Address programmed successfully\n");
	}
	else {
		printf(" Error programming MAC Address\n");
	}

	return (0);
}

/**************************************************/
// U_BOOT_CMD(
// 	changemac, 2, 1,      do_changemac,
// 	"changemac   - change MAC address\n",
// 	"value\n" "  - MAC Address value\n"
// );

#endif /* CFG_CMD_CHGMAC */
