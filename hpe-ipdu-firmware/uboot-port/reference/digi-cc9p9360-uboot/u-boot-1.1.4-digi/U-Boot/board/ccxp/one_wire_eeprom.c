/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: 
 * @Author: Sebastien Meyer
 * @Descr: CCXP270 one wire eeprom
 * @References: 
 * @TODO:
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
/***********************************************************************
 *  @History:
 *	2005/09/08 : RC_1 (Bernd Westermann)
  *	2005/09/24 : cleanup (Bernd Westermann)
***********************************************************************/
#include <common.h>

#define	SNO_WRITE_SCRATCHPAD	0x0f
#define SNO_READ_SCRATCHPAD	0xaa
#define SNO_COPY_SCRATCHPAD	0x55
#define SNO_READ_MEMORY		0xf0
#define SNO_SKIP_ROM		0xcc


/*-----------------------------------------------------------------------
 * Functions
 */
int reset_1w(void);
int sno_read(void);
void sno_write_1(void);
void sno_write_0(void);
void sno_write_byte (unsigned char sbyte);
unsigned char sno_read_byte (void);
unsigned char sno_crc8(unsigned char * data, unsigned long count);
unsigned short sno_crc16_write_scratchpad(unsigned char * address, unsigned char * data, unsigned long count);
unsigned short sno_crc16_read_scratchpad(unsigned char * address, unsigned char * data, unsigned long count);
int sno_reset(void);
int get_esa_1w(unsigned char *buffer);
int set_esa_1w(unsigned char *hard_mac_data);

/*-----------------------------------------------------------------------
 */

int reset_1w(void) {
	int fu_result;

	asm volatile (
		"ldr r4, =0x00800000;"		// mask for GPIO 5
		"ldr r5, =0x40e00014;"			// pin dir register
		"ldr r6, [r5];"
		"orr r6, r6, r4;"
		"str r6, [r5];"			// set GPIO to output
		"ldr r5, =0x40e0002c;"		// output clear register
		"str r4, [r5];"			// reset pin
		"ldr r5, =0x40a00010;"		// timer 500 usec
		"ldr r6, [r5];"
		"ldr r7, =1800;"
		"adc r6, r6, r7;"

		"112:;"
		"ldr r7, [r5];"
		"cmp r7, r6;"
		"bls 112b;"
		"ldr r5, =0x40e00020;"		// output set register
		"str r4, [r5];"			// reset pin
		"ldr r5, =0x40e00014;"		// pin dir register
		"ldr r6, [r5];"
		"bic r6, r6, r4;"
		"str r6, [r5];"			// set GPIO to input
		"ldr r5, =0x40a00010;"		// timer 80 usec
		"ldr r6, [r5];"
		"ldr r7, =288;"
		"adc r6, r6, r7;"

		"113:;"
		"ldr r7, [r5];"
		"cmp r7, r6;"
		"bls 113b;"
		"ldr r5, =0x40e00008;"		// pin level register
		"ldr r6, [r5];"
		"and r6, r6, r4;"
		"mov %0, r6, lsr#23;"		// shift right by 23
		"ldr r5, =0x40a00010;"		// timer 500 usec
		"ldr r6, [r5];"
		"ldr r7, =1800;"
		"adc r6, r6, r7;"

		"114:;"
		"ldr r7, [r5];"
		"cmp r7, r6;"
		"bls 114b;"

		: "=r"(fu_result)
		:
		: "r4","r5","r6","r7");

	return fu_result;
}

int sno_read(void) {
	int fu_result;

	asm volatile (
		"ldr r4, =0x00800000;"		// mask for GPIO 5
		"ldr r5, =0x40e00014;"		// pin dir register
		"ldr r6, [r5];"
		"orr r6, r6, r4;"
		"str r6, [r5];"			// set GPIO to output
		"ldr r5, =0x40e0002c;"		// output clear register
		"str r4, [r5];"			// reset pin
		"ldr r5, =0x40a00010;"		// timer 5 usec
		"ldr r6, [r5];"
		"adc r6, r6, #18;"

		"112:;"
		"ldr r7, [r5];"
		"cmp r7, r6;"
		"bls 112b;"
		"ldr r5, =0x40e00014;"		// pin dir register
		"ldr r6, [r5];"
		"bic r6, r6, r4;"
		"str r6, [r5];"			// set GPIO to input
		"ldr r5, =0x40a00010;"		// timer 5 usec
		"ldr r6, [r5];"
		"adc r6, r6, #18;"

		"113:;"
		"ldr r7, [r5];"
		"cmp r7, r6;"
		"bls 113b;"
		"ldr r5, =0x40e00008;"		// pin level register
		"ldr r6, [r5];"
		"and r6, r6, r4;"
		"mov %0, r6, lsr#23;"		// shift right by 23

		: "=r"(fu_result)
		:
		: "r4","r5","r6","r7");
	return fu_result;
}

void sno_write_1(void) {
	asm volatile (
		"ldr r4, =0x00800000;"		// mask for GPIO 5
		"ldr r5, =0x40e00014;"		// pin dir register
		"ldr r6, [r5];"
		"orr r6, r6, r4;"
		"str r6, [r5];"			// set GPIO to output
		"ldr r5, =0x40e0002c;"		// output clear register
		"str r4, [r5];"			// reset pin
		"ldr r5, =0x40a00010;"		// timer 5 usec
		"ldr r6, [r5];"
		"adc r6, r6, #18;"

		"112:;"
		"ldr r7, [r5];"
		"cmp r7, r6;"
		"bls 112b;"
		"ldr r5, =0x40e00020;"		// output set register
		"str r4, [r5];"			// reset pin
		"ldr r5, =0x40e00014;"		// pin dir register
		"ldr r6, [r5];"
		"bic r6, r6, r4;"
		"str r6, [r5];"			// set GPIO to input
		"ldr r5, =0x40a00010;"		// timer 60 usec
		"ldr r6, [r5];"
		"adc r6, r6, #214;"

		"113:;"
		"ldr r7, [r5];"
		"cmp r7, r6;"
		"bls 113b;"
		:
		:
		: "r4","r5","r6","r7");
}

void sno_write_0(void) {
	asm volatile (
		"ldr r4, =0x00800000;"		// mask for GPIO 5
		"ldr r5, =0x40e00014;"		// pin dir register
		"ldr r6, [r5];"
		"orr r6, r6, r4;"
		"str r6, [r5];"			// set GPIO to output
		"ldr r5, =0x40e0002c;"		// output clear register
		"str r4, [r5];"			// reset pin
		"ldr r5, =0x40a00010;"		// timer 67 usec
		"ldr r6, [r5];"
		"adc r6, r6, #240;"

		"112:;"
		"ldr r7, [r5];"
		"cmp r7, r6;"
		"bls 112b;"
		"ldr r5, =0x40e00020;"		// output set register
		"str r4, [r5];"			// reset pin
		"ldr r5, =0x40e00014;"		// pin dir register
		"ldr r6, [r5];"
		"bic r6, r6, r4;"
		"str r6, [r5];"			// set GPIO to input

		:
		:
		: "r4","r5","r6","r7");
}

void sno_write_byte (unsigned char sbyte) {
	unsigned char mask;
	int i;

	mask = 0x01;
	for (i=0; i<8; i++) {
		if (sbyte & mask) {
			sno_write_1();
		}
		else {
			sno_write_0();
		}
		mask <<= 1;
		udelay(1);
	}
}


unsigned char sno_read_byte (void) {
	unsigned char mask = 0x01;
	unsigned char abyte = 0x00;
	unsigned char return_value;
	int i;

	for (i=0; i<8; i++) {
		return_value = sno_read();
		if (return_value) {
			abyte |= mask;
		}
		udelay(80);
		mask <<= 1;
	}
	return abyte;
}

//////////////////////////////////////////////////////////////////////////
/*	The function sno_crc8 can be adapted to be used with the DS2431 ROM */
//////////////////////////////////////////////////////////////////////////
unsigned char sno_crc8(unsigned char * data, unsigned long count) {
unsigned char look_up_table[256] = {
0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53};

int i;
unsigned char crc = 0;

	for (i=0; i<count; i++) {
		crc = look_up_table[crc ^data[i]];
	}
	return crc;
}

unsigned short sno_crc16_write_scratchpad(unsigned char * address, unsigned char * data, unsigned long count) {
unsigned char look_up_table_lo[256] = {
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40};

unsigned char look_up_table_hi[256] = {
0x00, 0xC0, 0xC1, 0x01, 0xC3, 0x03, 0x02, 0xC2,
0xC6, 0x06, 0x07, 0xC7, 0x05, 0xC5, 0xC4, 0x04,
0xCC, 0x0C, 0x0D, 0xCD, 0x0F, 0xCF, 0xCE, 0x0E,
0x0A, 0xCA, 0xCB, 0x0B, 0xC9, 0x09, 0x08, 0xC8,
0xD8, 0x18, 0x19, 0xD9, 0x1B, 0xDB, 0xDA, 0x1A,
0x1E, 0xDE, 0xDF, 0x1F, 0xDD, 0x1D, 0x1C, 0xDC,
0x14, 0xD4, 0xD5, 0x15, 0xD7, 0x17, 0x16, 0xD6,
0xD2, 0x12, 0x13, 0xD3, 0x11, 0xD1, 0xD0, 0x10,
0xF0, 0x30, 0x31, 0xF1, 0x33, 0xF3, 0xF2, 0x32,
0x36, 0xF6, 0xF7, 0x37, 0xF5, 0x35, 0x34, 0xF4,
0x3C, 0xFC, 0xFD, 0x3D, 0xFF, 0x3F, 0x3E, 0xFE,
0xFA, 0x3A, 0x3B, 0xFB, 0x39, 0xF9, 0xF8, 0x38,
0x28, 0xE8, 0xE9, 0x29, 0xEB, 0x2B, 0x2A, 0xEA,
0xEE, 0x2E, 0x2F, 0xEF, 0x2D, 0xED, 0xEC, 0x2C,
0xE4, 0x24, 0x25, 0xE5, 0x27, 0xE7, 0xE6, 0x26,
0x22, 0xE2, 0xE3, 0x23, 0xE1, 0x21, 0x20, 0xE0,
0xA0, 0x60, 0x61, 0xA1, 0x63, 0xA3, 0xA2, 0x62,
0x66, 0xA6, 0xA7, 0x67, 0xA5, 0x65, 0x64, 0xA4,
0x6C, 0xAC, 0xAD, 0x6D, 0xAF, 0x6F, 0x6E, 0xAE,
0xAA, 0x6A, 0x6B, 0xAB, 0x69, 0xA9, 0xA8, 0x68,
0x78, 0xB8, 0xB9, 0x79, 0xBB, 0x7B, 0x7A, 0xBA,
0xBE, 0x7E, 0x7F, 0xBF, 0x7D, 0xBD, 0xBC, 0x7C,
0xB4, 0x74, 0x75, 0xB5, 0x77, 0xB7, 0xB6, 0x76,
0x72, 0xB2, 0xB3, 0x73, 0xB1, 0x71, 0x70, 0xB0,
0x50, 0x90, 0x91, 0x51, 0x93, 0x53, 0x52, 0x92,
0x96, 0x56, 0x57, 0x97, 0x55, 0x95, 0x94, 0x54,
0x9C, 0x5C, 0x5D, 0x9D, 0x5F, 0x9F, 0x9E, 0x5E,
0x5A, 0x9A, 0x9B, 0x5B, 0x99, 0x59, 0x58, 0x98,
0x88, 0x48, 0x49, 0x89, 0x4B, 0x8B, 0x8A, 0x4A,
0x4E, 0x8E, 0x8F, 0x4F, 0x8D, 0x4D, 0x4C, 0x8C,
0x44, 0x84, 0x85, 0x45, 0x87, 0x47, 0x46, 0x86,
0x82, 0x42, 0x43, 0x83, 0x41, 0x81, 0x80, 0x40,
};

	// CRC16 Calculation using the Table Look-up Method
	//	(see Maxim DS2431 chip - Application Note n°27)
	int i;

	unsigned char Current_CRC16_Lo = 0;
	unsigned char Current_CRC16_Hi = 0;
	unsigned char New_CRC16_Lo = 0;
	unsigned char New_CRC16_Hi = 0;
	unsigned char Input_Byte = 0;

	unsigned short Table_Hi_Index = 0;
	unsigned short Table_Lo_Index = 0;
	unsigned short CRC_Value = 0;

	//////////////////////////////////////////////////////////////////////////////////
	// CRC16 calculation for a Write ScracthPad command				//
	// 	1-) First clearing the CRC generator					//
	//	2-) Shifting in the command code					//
	//	3-)	Shifting in the Target Addresses TA1 and TA2			//
	//	4-)	Shifting in all the data bytes as they were sent by the DS2431	//
	//										//
	//	Finally the CRC value must be inverted					//
	//										//
	//////////////////////////////////////////////////////////////////////////////////

	//	2-) Shifting in the command code

	Input_Byte = SNO_WRITE_SCRATCHPAD;

	Table_Hi_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Hi = look_up_table_hi[Table_Hi_Index];

	Table_Lo_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Lo = look_up_table_lo[Table_Lo_Index] ^ Current_CRC16_Hi;

	Current_CRC16_Lo = New_CRC16_Lo;
	Current_CRC16_Hi = New_CRC16_Hi;

	//	3-)	Shifting in the Target Addresses TA1 and TA2

	// First Address Byte

	Input_Byte = address[0];

	Table_Hi_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Hi = look_up_table_hi[Table_Hi_Index];

	Table_Lo_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Lo = look_up_table_lo[Table_Lo_Index] ^ Current_CRC16_Hi;

	Current_CRC16_Lo = New_CRC16_Lo;
	Current_CRC16_Hi = New_CRC16_Hi;

	// Second Address Byte

	Input_Byte = address[1];

	Table_Hi_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Hi = look_up_table_hi[Table_Hi_Index];

	Table_Lo_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Lo = look_up_table_lo[Table_Lo_Index] ^ Current_CRC16_Hi;

	Current_CRC16_Lo = New_CRC16_Lo;
	Current_CRC16_Hi = New_CRC16_Hi;


	//	4-)	Shifting in all the data bytes as they were sent by the DS2431


	for (i=0; i<count; i++) {
		Input_Byte = data[i];

		Table_Hi_Index = Current_CRC16_Lo ^ Input_Byte;
		New_CRC16_Hi = look_up_table_hi[Table_Hi_Index];

		Table_Lo_Index = Current_CRC16_Lo ^ Input_Byte;
		New_CRC16_Lo = look_up_table_lo[Table_Lo_Index] ^ Current_CRC16_Hi;

		Current_CRC16_Lo = New_CRC16_Lo;
		Current_CRC16_Hi = New_CRC16_Hi;
	}

	//	Finally the CRC value must be inverted
	CRC_Value = ((New_CRC16_Hi << 8) | New_CRC16_Lo) ^ 0xFFFF;

	return CRC_Value;
}

unsigned short sno_crc16_read_scratchpad(unsigned char * address, unsigned char * data, unsigned long count) {
unsigned char look_up_table_lo[256] = {
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40};

unsigned char look_up_table_hi[256] = {
0x00, 0xC0, 0xC1, 0x01, 0xC3, 0x03, 0x02, 0xC2,
0xC6, 0x06, 0x07, 0xC7, 0x05, 0xC5, 0xC4, 0x04,
0xCC, 0x0C, 0x0D, 0xCD, 0x0F, 0xCF, 0xCE, 0x0E,
0x0A, 0xCA, 0xCB, 0x0B, 0xC9, 0x09, 0x08, 0xC8,
0xD8, 0x18, 0x19, 0xD9, 0x1B, 0xDB, 0xDA, 0x1A,
0x1E, 0xDE, 0xDF, 0x1F, 0xDD, 0x1D, 0x1C, 0xDC,
0x14, 0xD4, 0xD5, 0x15, 0xD7, 0x17, 0x16, 0xD6,
0xD2, 0x12, 0x13, 0xD3, 0x11, 0xD1, 0xD0, 0x10,
0xF0, 0x30, 0x31, 0xF1, 0x33, 0xF3, 0xF2, 0x32,
0x36, 0xF6, 0xF7, 0x37, 0xF5, 0x35, 0x34, 0xF4,
0x3C, 0xFC, 0xFD, 0x3D, 0xFF, 0x3F, 0x3E, 0xFE,
0xFA, 0x3A, 0x3B, 0xFB, 0x39, 0xF9, 0xF8, 0x38,
0x28, 0xE8, 0xE9, 0x29, 0xEB, 0x2B, 0x2A, 0xEA,
0xEE, 0x2E, 0x2F, 0xEF, 0x2D, 0xED, 0xEC, 0x2C,
0xE4, 0x24, 0x25, 0xE5, 0x27, 0xE7, 0xE6, 0x26,
0x22, 0xE2, 0xE3, 0x23, 0xE1, 0x21, 0x20, 0xE0,
0xA0, 0x60, 0x61, 0xA1, 0x63, 0xA3, 0xA2, 0x62,
0x66, 0xA6, 0xA7, 0x67, 0xA5, 0x65, 0x64, 0xA4,
0x6C, 0xAC, 0xAD, 0x6D, 0xAF, 0x6F, 0x6E, 0xAE,
0xAA, 0x6A, 0x6B, 0xAB, 0x69, 0xA9, 0xA8, 0x68,
0x78, 0xB8, 0xB9, 0x79, 0xBB, 0x7B, 0x7A, 0xBA,
0xBE, 0x7E, 0x7F, 0xBF, 0x7D, 0xBD, 0xBC, 0x7C,
0xB4, 0x74, 0x75, 0xB5, 0x77, 0xB7, 0xB6, 0x76,
0x72, 0xB2, 0xB3, 0x73, 0xB1, 0x71, 0x70, 0xB0,
0x50, 0x90, 0x91, 0x51, 0x93, 0x53, 0x52, 0x92,
0x96, 0x56, 0x57, 0x97, 0x55, 0x95, 0x94, 0x54,
0x9C, 0x5C, 0x5D, 0x9D, 0x5F, 0x9F, 0x9E, 0x5E,
0x5A, 0x9A, 0x9B, 0x5B, 0x99, 0x59, 0x58, 0x98,
0x88, 0x48, 0x49, 0x89, 0x4B, 0x8B, 0x8A, 0x4A,
0x4E, 0x8E, 0x8F, 0x4F, 0x8D, 0x4D, 0x4C, 0x8C,
0x44, 0x84, 0x85, 0x45, 0x87, 0x47, 0x46, 0x86,
0x82, 0x42, 0x43, 0x83, 0x41, 0x81, 0x80, 0x40,
};

	// CRC16 Calculation using the Table Look-up Method
	//	(see Maxim DS2431 chip - Application Note n°27)

	int i;

	unsigned char Current_CRC16_Lo = 0;
	unsigned char Current_CRC16_Hi = 0;
	unsigned char New_CRC16_Lo = 0;
	unsigned char New_CRC16_Hi = 0;
	unsigned char Input_Byte = 0;

	unsigned short Table_Hi_Index = 0;
	unsigned short Table_Lo_Index = 0;
	unsigned short CRC_Value = 0;

	//////////////////////////////////////////////////////////////////////////////////
	// CRC16 calculation for a Read ScracthPad command				//
	// 	1-) First clearing the CRC generator					//
	//	2-) Shifting in the command code					//
	//	3-)	Shifting in the Target Addresses TA1, TA2 and E/S byte		//
	//	4-)	Shifting in all the data bytes as they were sent by the DS2431	//
	//										//
	//		Finally the CRC value must be inverted				//
	//										//
	//////////////////////////////////////////////////////////////////////////////////

	//	2-) Shifting in the command code

	Input_Byte = SNO_WRITE_SCRATCHPAD;

	Table_Hi_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Hi = look_up_table_hi[Table_Hi_Index];

	Table_Lo_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Lo = look_up_table_lo[Table_Lo_Index] ^ Current_CRC16_Hi;

	Current_CRC16_Lo = New_CRC16_Lo;
	Current_CRC16_Hi = New_CRC16_Hi;

	//	3-)	Shifting in the Target Addresses TA1, TA2 and E/S byte

	// First Address Byte

	Input_Byte = address[0];

	Table_Hi_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Hi = look_up_table_hi[Table_Hi_Index];

	Table_Lo_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Lo = look_up_table_lo[Table_Lo_Index] ^ Current_CRC16_Hi;

	Current_CRC16_Lo = New_CRC16_Lo;
	Current_CRC16_Hi = New_CRC16_Hi;

	// Second Address Byte

	Input_Byte = address[1];

	Table_Hi_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Hi = look_up_table_hi[Table_Hi_Index];

	Table_Lo_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Lo = look_up_table_lo[Table_Lo_Index] ^ Current_CRC16_Hi;

	Current_CRC16_Lo = New_CRC16_Lo;
	Current_CRC16_Hi = New_CRC16_Hi;

	// E/S byte

	Input_Byte = address[2];

	Table_Hi_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Hi = look_up_table_hi[Table_Hi_Index];

	Table_Lo_Index = Current_CRC16_Lo ^ Input_Byte;
	New_CRC16_Lo = look_up_table_lo[Table_Lo_Index] ^ Current_CRC16_Hi;

	Current_CRC16_Lo = New_CRC16_Lo;
	Current_CRC16_Hi = New_CRC16_Hi;


	//	4-)	Shifting in all the data bytes as they were sent by the DS2431


	for (i=0; i<count; i++) {
		Input_Byte = data[i];

		Table_Hi_Index = Current_CRC16_Lo ^ Input_Byte;
		New_CRC16_Hi = look_up_table_hi[Table_Hi_Index];

		Table_Lo_Index = Current_CRC16_Lo ^ Input_Byte;
		New_CRC16_Lo = look_up_table_lo[Table_Lo_Index] ^ Current_CRC16_Hi;

		Current_CRC16_Lo = New_CRC16_Lo;
		Current_CRC16_Hi = New_CRC16_Hi;
	}

	//	Finally the CRC value must be inverted

	CRC_Value = ((New_CRC16_Hi << 8) | New_CRC16_Lo) ^ 0xFFFF;

	return CRC_Value;
}

int sno_reset(void) {

	int result;

	result = reset_1w();
	if (!result) {
		//printf("presence pulse detected\n");
		return 0;
	}
	else {
		printf("NO presence pulse detected TRITON270\n");
		return 1;
	}
}


int get_esa_1w(unsigned char *buffer)
{
	int		i;
	unsigned char	mac_data[8] = {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};

	udelay(2000);
	//HAL_DELAY_US(2000);			// 2 msec recovery time

	// check status of application register
	if(sno_reset()) {
		printf("no eeprom device for MAC address found \n");
		return 0;
	}

	//////////////////////////////////////////////////////////////////////////////////////////
	//	READ COMMAND									//
	//	 -------------------------------------------------------------------------	//
	//	|	RST	 |	PD	 | 	Select | RM   |	TA		 | Data	 	| FF Loop         |		//
	//	|	M->S |	S->M |	M->S   | M->S |	M->S 	 | S->M	    | S->M 	    	  |		//
	//	 -------------------------------------------------------------------------		//
	//																					//
	//	M->S	= Master to slave														//
	//	S->M	= Slave to master														//
	//																					//
	//	RST 	= 1-Wire Reset Pulse generated by Master								//
	//	PD 		= 1-Wire Presence Pulse generated by slave								//
	//	Select 	= Command and data to satisfy the ROM function protocol					//
	//	RM		= Command "Read Memory"													//
	//	TA		= Target Address TA1, TA2												//
	//	Data	= Transfer as many data bytes as needed to reach the end of the memory	//
	//	FF loop = Indefinite loop where the master reads FF bytes						//
	//																					//
	//////////////////////////////////////////////////////////////////////////////////////

	sno_reset();
	sno_write_byte(SNO_SKIP_ROM);
	sno_write_byte(SNO_READ_MEMORY);
	sno_write_byte(0x00);		// register address
	sno_write_byte(0x00);

	for(i=0;i<8;i++) {
		mac_data[i] = sno_read_byte();
	}

	if(sno_reset()) {
		printf("no eeprom device for MAC address found \n");
		return 0;
	}

	for(i=0; i<6; i++)
		buffer[i] = mac_data[i];

	return 1;
}

int set_esa_1w(unsigned char *hard_mac_data)
{
	int i;

	//unsigned char	hard_mac_data[8] = {0x04,0x04,0xF3,0xF3,0x38,0x10,0xFF,0xFF};
	unsigned char	hard_address[3] = {0x00, 0x00, 0x00};

	unsigned char	read_scratch_data[8] = {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};
	unsigned char	read_scratch_address[3] = {0x00, 0x00, 0x00};

	unsigned char	mac_data[8] = {0x00,0x00,0x0c,0xc6,0x00,0x00,0x00,0x00};

	unsigned char	crc_write_scratch[2] = {0x00, 0x00};

	unsigned short	crc_write_calculated, crc_write_from_one_wire;

	udelay(2000);
	//HAL_DELAY_US(2000);			// 2 msec recovery time


	// Write the MAC address in the 1-wire EEPROM - for this we will use the
	// WRITE SCRATCHPAD command

	//////////////////////////////////////////////////////////////////////////////////////
	//	WRITE SCRATCHPAD COMMAND														//
	//	 ---------------------------------------------------------------------			//
	//	|	RST	 |	PD	 | 	Select | WS	  |	TA	 | 8-T2:T0 | CRC16\ | FF Loop |			//
	//	|	M->S |	S->M |	M->S   | M->S |	M->S | M->S	   | S->M 	| S->M	  |			//
	//	 ---------------------------------------------------------------------			//
	//																					//
	//	M->S	= Master to slave														//
	//	S->M	= Slave to master														//
	//																					//
	//	RST 	= 1-Wire Reset Pulse generated by Master								//
	//	PD 		= 1-Wire Presence Pulse generated by slave								//
	//	Select 	= Command and data to satisfy the ROM function protocol					//
	//	WS		= Command "Write Scratchpad"											//
	//	TA		= Target Address TA1, TA2												//
	//	8-T2:T0 = Transfer as many bytes as needed to reach the end of the scratchpad	//
	//			  for a given target address											//
	//	CRC16\ 	= Transfer of an inverted CRC16											//
	//	FF loop = Indefinite loop where the master reads FF bytes						//
	//																					//
	//////////////////////////////////////////////////////////////////////////////////////

	sno_reset();

	// Command and data to satisfy the ROM function protocol
	sno_write_byte(SNO_SKIP_ROM);

	// Write in the Scratchpad
	sno_write_byte(SNO_WRITE_SCRATCHPAD);

	// Write the address of the data memory
	for (i=0; i<2; i++)
	{
		sno_write_byte(hard_address[i]);
	};

	// Write 8 bytes in the Scratchpad
	for (i=0; i<8; i++)
	{
		sno_write_byte(hard_mac_data[i]);
	};

	// Read the CRC of the Write ScratchPad command
	for (i=0; i<2; i++)
	{
		crc_write_scratch[i] = sno_read_byte();
	};

	crc_write_from_one_wire = ((crc_write_scratch[1] << 8) | crc_write_scratch[0]);

	// Calculate the CRC16 value for the Write Scratchpad command

	crc_write_calculated = sno_crc16_write_scratchpad(hard_address,hard_mac_data,8);

	if (crc_write_calculated!=crc_write_from_one_wire) {
		printf("Write ScratchPad command CRC Checksum Error !!!\n\n");
		return 0;
	}

	//////////////////////////////////////////////////////////////////////////////////////
	//	READ SCRATCHPAD COMMAND															//
	//	 -----------------------------------------------------------------------		//
	//	|	RST	 |	PD	 | 	Select | RS	  |	TA-E/S | 8-T2:T0 | CRC16\ | FF Loop |		//
	//	|	M->S |	S->M |	M->S   | M->S |	M->S   | M->S	 | S->M   | S->M    |		//
	//	 -----------------------------------------------------------------------		//
	//																					//
	//	M->S	= Master to slave														//
	//	S->M	= Slave to master														//
	//																					//
	//	RST 	= 1-Wire Reset Pulse generated by Master								//
	//	PD 		= 1-Wire Presence Pulse generated by slave								//
	//	Select 	= Command and data to satisfy the ROM function protocol					//
	//	RS		= Command "Read Scratchpad"												//
	//	TA-E/S	= Target Address TA1, TA2 with E/S byte									//
	//	8-T2:T0 = Transfer as many bytes as needed to reach the end of the scratchpad	//
	//			  for a given target address											//
	//	CRC16\ 	= Transfer of an inverted CRC16											//
	//	FF loop = Indefinite loop where the master reads FF bytes						//
	//																					//
	//////////////////////////////////////////////////////////////////////////////////////


	// Reset the 1-wire Line to avoid the FF infinite loop after Write ScratchPad command
	sno_reset();

	// Command and data to satisfy the ROM function protocol
	sno_write_byte(SNO_SKIP_ROM);

	// Write Read Scratchpad command
	sno_write_byte(SNO_READ_SCRATCHPAD);

	// Read the Scratchpad addresses

	// Read TA - E/S in the Scratchpad
	for (i=0; i<3; i++)
	{
		read_scratch_address[i] = sno_read_byte();
	}


	// Read Data in the Scratchpad
	for (i=0; i<8; i++)
	{
		read_scratch_data[i] = sno_read_byte();
	}

	//////////////////////////////////////////////////////////////////////////////////////
	//	COPY SCRATCHPAD COMMAND															//
	//	 ---------------------------------------------------------------------			//
	//	|	RST	 |	PD	 | 	Select | CPS  |	TA-E/S	 | Programming | AA Loop |			//
	//	|	M->S |	S->M |	M->S   | M->S |	M->S 	 | M->S	   	   | S->M 	 |			//
	//	 ---------------------------------------------------------------------			//
	//																					//
	//	M->S	= Master to slave														//
	//	S->M	= Slave to master														//
	//																					//
	//	RST 	= 1-Wire Reset Pulse generated by Master								//
	//	PD 		= 1-Wire Presence Pulse generated by slave								//
	//	Select 	= Command and data to satisfy the ROM function protocol					//
	//	CPS		= Command "Copy Scratchpad"												//
	//	TA-E/S	= Target Address TA1, TA2 with E/S byte									//
	//	Programming	= Data transfer to EEPROM; no activity on the 1-wire bus permitted	//
	//				  during this time													//
	//	AA loop = Indefinite loop where the master reads AA bytes						//
	//																					//
	//////////////////////////////////////////////////////////////////////////////////////

	// Reset the 1-wire Line to avoid the FF infinite loop after Write ScratchPad command
	sno_reset();

	// Command and data to satisfy the ROM function protocol
	sno_write_byte(SNO_SKIP_ROM);

	// Copy the Scratchpad
	sno_write_byte(SNO_COPY_SCRATCHPAD);

	// Write the address of the data memory + E/S Byte
	for (i=0; i<3; i++)
	{
		sno_write_byte(read_scratch_address[i]);
	}

	udelay(15000);
	//HAL_DELAY_US(15000);			// 15 msec waiting for programming

	// Reset the 1-wire Line to avoid the FF infinite loop after Write ScratchPad command
	sno_reset();

	// check status of application register
	if(sno_reset()) {
		printf("no eeprom device for MAC address found \n");
		return 0;
	}

	//////////////////////////////////////////////////////////////////////////////////////
	//	READ COMMAND																	//
	//	 -------------------------------------------------------------------------		//
	//	|	RST	 |	PD	 | 	Select | RM   |	TA		 | Data	 	| FF Loop         |		//
	//	|	M->S |	S->M |	M->S   | M->S |	M->S 	 | S->M	    | S->M 	    	  |		//
	//	 -------------------------------------------------------------------------		//
	//																					//
	//	M->S	= Master to slave														//
	//	S->M	= Slave to master														//
	//																					//
	//	RST 	= 1-Wire Reset Pulse generated by Master								//
	//	PD 		= 1-Wire Presence Pulse generated by slave								//
	//	Select 	= Command and data to satisfy the ROM function protocol					//
	//	RM		= Command "Read Memory"													//
	//	TA		= Target Address TA1, TA2												//
	//	Data	= Transfer as many data bytes as needed to reach the end of the memory	//
	//	FF loop = Indefinite loop where the master reads FF bytes						//
	//																					//
	//////////////////////////////////////////////////////////////////////////////////////

	sno_reset();
	sno_write_byte(SNO_SKIP_ROM);
	sno_write_byte(SNO_READ_MEMORY);
	sno_write_byte(0x00);						// register address
	sno_write_byte(0x00);

	for(i=0;i<8;i++) {
		mac_data[i] = sno_read_byte();
	}


	if(sno_reset()) {
		printf("no eeprom device for MAC address found \n");
		return 0;
	}

	return 1;
}
