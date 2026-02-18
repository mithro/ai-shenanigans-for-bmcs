/*
 * (C) Copyright 2000-2002
 * Wolfgang Denk, DENX Software Engineering, wd@denx.de.
 *
 * (C) Copyright 2001 Sysgo Real-Time Solutions, GmbH <www.elinos.com>
 * Andreas Heppel <aheppel@sysgo.de>

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
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston,
 * MA 02111-1307 USA
 */

#include <common.h>

#if defined(CFG_ENV_IS_IN_EEPROM) /* Environment is in EEPROM */

#include <command.h>
#include <environment.h>
#include <linux/stddef.h>

DECLARE_GLOBAL_DATA_PTR;

env_t *env_ptr = NULL;

char * env_name_spec = "EEPROM";

extern uchar (*env_get_char)(int);
extern uchar env_get_char_memory (int index);


uchar env_get_char_spec (int index)
{
	uchar c;

	eeprom_read (CFG_DEF_EEPROM_ADDR,
		     CFG_ENV_OFFSET+index+offsetof(env_t,data),
		     &c, 1);
	return (c);
}

void env_relocate_spec (void)
{
#if defined( CONFIG_UNC90 ) && defined( CFG_COPY_ENV_TO_SRAM )
	volatile unsigned char *sram_ptr;
	
	sram_ptr = (volatile unsigned char *)0x00000100;
#endif	
	eeprom_read (CFG_DEF_EEPROM_ADDR,
		     CFG_ENV_OFFSET,
		     (uchar*)env_ptr,
		     CFG_ENV_SIZE);
		     
#if defined( CONFIG_UNC90 ) && defined( CFG_COPY_ENV_TO_SRAM )
	// Copy environment to SRAM
	memcpy( (uchar *)sram_ptr, (uchar *)env_ptr, CFG_ENV_SIZE );
#endif	
}

int saveenv(void)
{
#if defined( CONFIG_UNC90 ) && defined( CFG_COPY_ENV_TO_SRAM )
	volatile unsigned char *sram_ptr;
	
	// Internal SRAM is remmaped so access through address 0x0
	sram_ptr = (volatile unsigned char *)0x00000100;
	
	// Copy environment to SRAM
	memcpy( (uchar *)sram_ptr, (uchar *)env_ptr, CFG_ENV_SIZE );
#endif	
	return eeprom_write (CFG_DEF_EEPROM_ADDR,
			     CFG_ENV_OFFSET,
			     (uchar *)env_ptr,
			     CFG_ENV_SIZE);
}

/************************************************************************
 * Initialize Environment use
 *
 * We are still running from ROM, so data use is limited
 * Use a (moderately small) buffer on the stack
 */
int env_init(void)
{
	ulong crc, len, new;
	unsigned off;
	uchar buf[64];

#if defined( CONFIG_UNC90 ) && defined( CFG_COPY_ENV_TO_SRAM )
	
	volatile unsigned int *reg;
	volatile unsigned char *sram_ptr;
	
	// Now that we are running from SRAM remap the internal 
	// Memory Area 0
	reg = (volatile unsigned int *)0xffffff00;
	*reg = 0x00000001;
#endif	
	
	eeprom_init ();	/* prepare for EEPROM read/write */

	/* read old CRC */
	eeprom_read (CFG_DEF_EEPROM_ADDR,
		     CFG_ENV_OFFSET+offsetof(env_t,crc),
		     (uchar *)&crc, sizeof(ulong));

	new = 0;
	len = ENV_SIZE;
	off = offsetof(env_t,data);
	while (len > 0) {
		int n = (len > sizeof(buf)) ? sizeof(buf) : len;

		eeprom_read (CFG_DEF_EEPROM_ADDR, CFG_ENV_OFFSET+off, buf, n);
		new = crc32 (new, buf, n);
		len -= n;
		off += n;
	}

	if (crc == new) {
		gd->env_addr  = offsetof(env_t,data);
		gd->env_valid = 1;
		
#if defined( CONFIG_UNC90 ) && defined( CFG_COPY_ENV_TO_SRAM )
		// Internal SRAM is remmaped so access through address 0x0
		sram_ptr = (volatile unsigned char *)0x00000100;
		// Copy environment to SRAM
		memcpy( (uchar *)sram_ptr, (uchar *)env_ptr, CFG_ENV_SIZE );
#endif	
		
	} else {
		gd->env_addr  = 0;
		gd->env_valid = 0;
	}

	return (0);
}

#endif /* CFG_ENV_IS_IN_EEPROM */
