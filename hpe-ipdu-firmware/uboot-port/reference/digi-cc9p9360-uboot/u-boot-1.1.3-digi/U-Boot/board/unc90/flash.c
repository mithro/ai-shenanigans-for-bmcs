/*
 * (C) Copyright 2005
 * Sistemas Embebidos S.A. <www.embebidos.com>
 *  -Neil Bryan <nbryan@embebidos.com>
 *  -Pedro Perez de Heredia <pperez@embebidos.com>
 *
 * Based on existing flash support on u-boot project.
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



/* Flash Organisation Structure */
typedef struct {
	unsigned int sector_number;
	unsigned int sector_size;
} fl_org_def_t;


/* Flash Organisations */
fl_org_def_t OrgAM29LV128[] = {
	{   256,  64*1024 }	/*   256 *  64 kBytes sectors */
};

flash_info_t	flash_info[CFG_MAX_FLASH_BANKS];
ulong		flash_base_addr[CFG_MAX_FLASH_BANKS] = { CFG_FLASH_BASE };

/* AT49BV1614A Codes */
#define FLASH_CODE1		0xAA
#define FLASH_CODE2		0x55
#define ID_IN_CODE		0x90
#define ID_OUT_CODE		0xF0


#define CMD_READ_ARRAY		0x00F0
#define CMD_UNLOCK1		0x00AA
#define CMD_UNLOCK2		0x0055
#define CMD_ERASE_SETUP		0x0080
#define CMD_ERASE_CONFIRM	0x0030
#define CMD_PROGRAM		0x00A0
#define CMD_UNLOCK_BYPASS	0x0020
#define CMD_SECTOR_UNLOCK	0x0070
#define CMD_WRITE_TO_BUF	0x0025
#define CMD_WRITE_BUF_TO_FLASH	0x0029


#define BIT_ERASE_DONE		0x0080
#define BIT_RDY_MASK		0x0080
#define BIT_PROGRAM_ERROR	0x0020
#define BIT_WR_TO_BUF_ABORT	0x0002
#define BIT_TIMEOUT		0x80000000 /* our flag */

#define READY 1
#define ERR   2
#define TMO   4

#define	WRITE_BUFFER_PAGE_LEN	32

/*
 * Function prototypes
 */
void inline spin_wheel( void );


/***********************************************************************
 * @Function: flash_identification
 * @Return: The flash size in bytes.
 * @Descr: Identifies the flash device and fills the info flash struct.
 ***********************************************************************/
static void flash_identification( flash_info_t * info, int dev )
{
	u16 manuf_code, device_code, add_device_code, third_word;
	vu_short *base = (vu_short *)flash_base_addr[dev];
	
	base[0x555] = FLASH_CODE1;
	base[0x2aa] = FLASH_CODE2;
	base[0x555] = ID_IN_CODE;

	manuf_code = base[0x000];
	device_code = base[0x001];
	add_device_code = base[0x00e];
	third_word = base[0x00f];

	base[0x555] = FLASH_CODE1;
	base[0x2aa] = FLASH_CODE2;
	base[0x555] = ID_OUT_CODE;

	if( (u16)AMD_MANUFACT == manuf_code )
	{
		/* Vendor type */
		info->flash_id = AMD_MANUFACT & FLASH_VENDMASK;
		
		if( (device_code & FLASH_TYPEMASK) == (AMD_ID_MIRROR & FLASH_TYPEMASK) )
		{
			switch( add_device_code )
			{
				case (u16)AMD_ID_LV128U_2:
					if( third_word == (u16)AMD_ID_LV128U_3 )
					{
						info->flash_id |= AMD_ID_LV128U_2 & FLASH_TYPEMASK;
						printf( "AM29LV128M (16MB)\n" );
					}
					break;
				default:
					printf( "Unknown FLASH device\n" );
					break;
			}
		}
	}
}

/***********************************************************************
 * @Function: flash_number_sector
 * @Return: 
 * @Descr: 
 ***********************************************************************/
static ushort flash_number_sector( fl_org_def_t *flash_def, unsigned int nb_blocks)
{
	int i, nb_sectors = 0;

	for( i=0; i < nb_blocks; i++) {
		nb_sectors += flash_def[i].sector_number;
	}

	return nb_sectors;
}

/***********************************************************************
 * @Function: flash_unlock_sector
 * @Return: Nothing.
 * @Descr: Unlocks the selected flash sector.
 ***********************************************************************/
static void flash_unlock_sector( flash_info_t * info, unsigned int sector )
{
	vu_short *addr = (vu_short *)(info->start[sector]);
	vu_short *base = (vu_short *)(info->start[0]);

	base[0x555] = CMD_UNLOCK1;
	*addr = CMD_SECTOR_UNLOCK;
}

/***********************************************************************
 * @Function: flash_init
 * @Return: The flash size in bytes.
 * @Descr: Fills the flash_info struct and return the flash size.
 ***********************************************************************/
ulong flash_init( void )
{
	int i, j, k;
	unsigned int flash_nb_blocks, sector;
	unsigned int start_address;
	fl_org_def_t *flash;

	ulong size = 0;

	for( i = 0; i < CFG_MAX_FLASH_BANKS; i++ ) 
	{
		ulong flashbase = 0;
		
		memset( &flash_info[i], 0, sizeof(flash_info_t) );

		flash_identification( &flash_info[i], i );

		if( (flash_info[i].flash_id & FLASH_TYPEMASK) ==
			(AMD_ID_LV128U_2 & FLASH_TYPEMASK) ) {
			flash = OrgAM29LV128;
			flash_nb_blocks = sizeof( OrgAM29LV128 ) / sizeof( fl_org_def_t );
		} else {
			flash_nb_blocks = 0;
			flash = OrgAM29LV128;
		}

		flash_info[i].sector_count = flash_number_sector( flash, flash_nb_blocks );
		
		flashbase = flash_base_addr[i];
		
		sector = 0;
		start_address = flashbase;
		flash_info[i].size = 0;

		for( j = 0; j < flash_nb_blocks; j++ ) {
			for( k = 0; k < flash[j].sector_number; k++ ) {
				flash_info[i].start[sector++] = start_address;
				start_address += flash[j].sector_size;
				flash_info[i].size += flash[j].sector_size;
			}
		}

		size += flash_info[i].size;

		if( (flash_info[i].flash_id & FLASH_TYPEMASK) ==
		    (AMD_ID_LV128U_2 & FLASH_TYPEMASK) ) {
		    	/* Unlock all sectors at reset */
			for( j = 0; j < flash_info[i].sector_count; j++ ) {
				flash_unlock_sector( &flash_info[i], j );
			}
		}
	}

	/* Protect binary boot image */
	flash_protect (FLAG_PROTECT_SET,
		       CFG_FLASH_BASE,
		       CFG_FLASH_BASE + CFG_BOOT_SIZE - 1, &flash_info[0]);

#ifdef CFG_ENV_IS_IN_FLASH
	/* Protect environment variables */
	flash_protect (FLAG_PROTECT_SET,
		       CFG_ENV_ADDR,
		       CFG_ENV_ADDR + CFG_ENV_SIZE - 1, &flash_info[0]);
#endif
	/* Protect U-Boot image */
	flash_protect (FLAG_PROTECT_SET,
		       CFG_U_BOOT_BASE,
		       CFG_U_BOOT_BASE + CFG_U_BOOT_SIZE - 1, &flash_info[0]);
		       
#ifdef CFG_UNC90_FLASH_PROT_BOOTBIN
	/* Protect boot.bin image */
	flash_protect (FLAG_PROTECT_SET,
		       PHYS_FLASH_1,
		       PHYS_FLASH_1 + CFG_BOOT_SIZE - 1, &flash_info[0]);
#endif		       

	return size;
}

/***********************************************************************
 * @Function: flash_print_info
 * @Return: Nothing.
 * @Descr: Displays information of the flash device.
 ***********************************************************************/
void flash_print_info( flash_info_t * info )
{
	int i;

	switch( info->flash_id & FLASH_VENDMASK ){
		case (AMD_MANUFACT & FLASH_VENDMASK):
			printf( "AMD: " );
			break;
		default:
			printf( "info->flash_id 0x%lx\n", (ulong)info->flash_id );
			printf( "Unknown Vendor\n" );
			break;
	}

	switch( info->flash_id & FLASH_TYPEMASK ){
		case (AMD_ID_LV128U_2 & FLASH_TYPEMASK):
			printf( "AM29LV128M (16MB)\n" );
			break;
		default:
			printf( "Unknown Chip Type\n" );
			return;
			break;
	}

	printf( "  Size: %ld MB in %d Sectors\n",
		info->size >> 20, info->sector_count );

	printf ("  Sector Start Addresses:");
	
	for( i = 0; i < info->sector_count; i++ ) {
		if( (i % 5) == 0 ){
			printf ("\n   ");
		}
		printf (" 0x%08lX%s", info->start[i],
			info->protect[i] ? " (RO)" : "     ");
	}
	printf ("\n");
}

/***********************************************************************
 * @Function: flash_erase
 * @Return: Error code.
 * @Descr: Erased the selected number of sectors.
 ***********************************************************************/
int flash_erase( flash_info_t * info, int s_first, int s_last )
{
	vu_short *base = (vu_short *)(info->start[0]);
	ulong result;
	int iflag, prot, sect;
	int rc = ERR_OK;
	int chip1;

	/* first look for protection bits */
	if( info->flash_id == FLASH_UNKNOWN ) {
		printf( "%s: Error, unkown flash type: 0x%lx\n", __FUNCTION__, 
		        info->flash_id );
		return ERR_UNKNOWN_FLASH_TYPE;
	}

	if( (s_first < 0) || (s_first > s_last) ) {
		printf( "%s: Error in arguments\n", __FUNCTION__ );
		return ERR_INVAL;
	}

	if( (info->flash_id & FLASH_VENDMASK) !=
	    (AMD_MANUFACT & FLASH_VENDMASK) ) {
		printf( "%s: Unknown vendor flash: 0x%lx\n", __FUNCTION__, 
	                info->flash_id );
		return ERR_UNKNOWN_FLASH_VENDOR;
	}

	prot = 0;
	for (sect = s_first; sect <= s_last; ++sect) {
		if (info->protect[sect]) {
			prot++;
		}
	}
	if( prot )
		return ERR_PROTECTED;

	/*
	 * Disable interrupts which might cause a timeout here.
	 */
	iflag = disable_interrupts ();

	/* Start erase on unprotected sectors */
	for( sect = s_first; sect <= s_last && !ctrlc(); sect++ ) {
		debug( "Erasing sector %2d  ", sect );

		/* arm simple, non interrupt dependent timer */
		reset_timer_masked ();

		if( info->protect[sect] == 0 ) {	/* not protected */
			vu_short *addr = (vu_short *)(info->start[sect]);

			base[0x555] = CMD_UNLOCK1;
			base[0x2aa] = CMD_UNLOCK2;
			base[0x555] = CMD_ERASE_SETUP;

			base[0x555] = CMD_UNLOCK1;
			base[0x2aa] = CMD_UNLOCK2;
			*addr = CMD_ERASE_CONFIRM;

			/* wait until flash is ready */
			chip1 = 0;

			do{
				result = *addr;

				/* check timeout */
				if( get_timer_masked () > CFG_FLASH_ERASE_TOUT ) {
					base[0x555] = CMD_READ_ARRAY;
					chip1 = TMO;
					break;
				}

				if( !chip1 && (result & 0xFFFF) & BIT_ERASE_DONE )
					chip1 = READY;
			}while( !chip1 );

			base[0x555] = CMD_READ_ARRAY;

			if( chip1 == ERR ) {
				rc = ERR_PROG_ERROR;
				goto outahere;
			}
			if( chip1 == TMO ) {
				rc = ERR_TIMOUT;
				goto outahere;
			}
			
			debug( "OK\n" );
		}else {			/* it was protected */
			debug( "Sector %d protected\n", sect );
		}
		
		spin_wheel();
	}

	if( ctrlc() )
		printf( "User Interrupt!\n" );

outahere:
	/* allow flash to settle - wait 10 ms */
	udelay_masked( 10000 );

	if( iflag )
		enable_interrupts ();

	return rc;
}


/***********************************************************************
 * @Function: write_to_buffer
 * @Return: Error code.
 * @Descr: Writes from buffer to flash device using write buffer prog
 *         algorithm.
 ***********************************************************************/
static int write_word( flash_info_t * info, ulong dest, ulong data )
{
	vu_short *addr = (vu_short *)dest;
	vu_short *base = (vu_short *)(info->start[0]);
	ulong result;
	int rc = ERR_OK, iflag;
	int chip1 = 0;

	/*
	 * Check if Flash is (sufficiently) erased
	 */
	if( (*addr & data) != data )
		return ERR_NOT_ERASED;

	/*
	 * Disable interrupts which might cause a timeout
	 * here. 
	 */
	iflag = disable_interrupts ();

	base[0x555] = CMD_UNLOCK1;
	base[0x2aa] = CMD_UNLOCK2;
	base[0x555] = CMD_PROGRAM;
	*addr = data;

	/* arm simple, non interrupt dependent timer */
	reset_timer_masked ();

	do {
		result = *addr;

		/* check timeout */
		if( get_timer_masked () > CFG_FLASH_ERASE_TOUT ) {
			chip1 = ERR | TMO;
			*addr = CMD_READ_ARRAY; // Reset bank
			break;
		}
		if( (result & BIT_RDY_MASK) == (data & BIT_RDY_MASK) )
			chip1 = READY;
	}while( !chip1 );

	if( chip1 == ERR || *addr != data )
		rc = ERR_PROG_ERROR;

	if (iflag)
		enable_interrupts ();

	return rc;
}

/***********************************************************************
 * @Function: write_to_buffer
 * @Return: Error code.
 * @Descr: Writes from buffer to flash device using write buffer prog
 *         algorithm.
 ***********************************************************************/
static int write_to_buffer( flash_info_t *info, 
                            ulong dest, ushort *data, ulong len )
{
	vu_short *addr = (vu_short *)dest;
	vu_short *base = (vu_short *)(info->start[0]);
	ulong result;
	ushort *data_ptr = data;
	int rc = ERR_OK, iflag;
	int chip1 = 0;
	uchar wr_words;

	/*
	 * Check if Flash is (sufficiently) erased
	 */
	if( *addr != 0xffff ){
		printf( "Not erased! %08lx\n", dest );
		return ERR_NOT_ERASED;
	}
	/*
	 * Disable interrupts which might cause a timeout
	 * here. 
	 */
	iflag = disable_interrupts ();

	base[0x555] = CMD_UNLOCK1;
	base[0x2aa] = CMD_UNLOCK2;
	*addr = CMD_WRITE_TO_BUF;
	
	wr_words = (len > WRITE_BUFFER_PAGE_LEN) ? WRITE_BUFFER_PAGE_LEN : len;
	wr_words = wr_words / 2;
	*addr = wr_words - 1;
	
	while( wr_words > 0 ) {
		// @TODO 
		// Check for abort and generate escape sequence
		*addr++ = *data_ptr++;
		wr_words--;
	}
	
	addr--;
	data_ptr--;
	
	// Write to previous address to not exced page/sector limits
	*addr = CMD_WRITE_BUF_TO_FLASH;
		
	/* arm simple, non interrupt dependent timer */
	reset_timer_masked ();

	do {
		result = *addr;

		/* check timeout */
		if( get_timer_masked () > CFG_FLASH_ERASE_TOUT ) {
			chip1 = ERR | TMO;
			printf( "Timeout!\n" );
			break;
		}
		if( (result & BIT_RDY_MASK) == (*data_ptr & BIT_RDY_MASK) ) {
			chip1 = READY;
			break;
		}
		if( result & BIT_PROGRAM_ERROR ) {
			result = *addr;
			if( (result & BIT_RDY_MASK) == (*data_ptr & BIT_RDY_MASK) ) {
				chip1 = READY;
				break;
			}else {
				chip1 = ERR;
				break;
			}
		}else{
			if( result & BIT_WR_TO_BUF_ABORT ) {
				result = *addr;
				if( (result & BIT_RDY_MASK) == (*data_ptr & BIT_RDY_MASK) ) {
					chip1 = READY;
					break;
				}else {
					chip1 = ERR;
					break;
				}
			}
		}	
	}while( !chip1 );

	// @TODO issue write to buffer abort reset
	if( chip1 == ERR )
		rc = ERR_PROG_ERROR;

	if( iflag )
		enable_interrupts ();

	return rc;
}


/***********************************************************************
 * @Function: write_buff
 * @Return: Error code.
 * @Descr: Writes from buffer to flash device.
 ***********************************************************************/
int write_buff( flash_info_t * info, uchar * src, ulong addr, ulong cnt )
{
	ulong wp, data;
	int rc, word_cnt, wheel_cnt = 0;

	if( addr & 1 ) {
		printf( "Unaligned destination not supported\n" );
		return ERR_ALIGN;
	};

	if( (int)src & 1 ) {
		printf( "Unaligned source not supported\n" );
		return ERR_ALIGN;
	};

	wp = addr;

	while( cnt >= 2 ) {
		if( cnt > 2 ) {
			word_cnt = (cnt > WRITE_BUFFER_PAGE_LEN) ? WRITE_BUFFER_PAGE_LEN :cnt;
			
			if( (rc = write_to_buffer( info, wp, 
			     (ushort *)src, word_cnt ) ) != 0 )
				return (rc);
			src += word_cnt;
			wp += word_cnt;
			cnt -= word_cnt;
		} else {
			data = *((vu_short *)src);
			if( (rc = write_word( info, wp, data ) ) != 0 )
				return (rc);
			src += 2;
			wp += 2;
			cnt -= 2;
		}
		
		if( wheel_cnt++ > 0x400 ) {
			spin_wheel();
			wheel_cnt = 0;
		}
	}

	if( cnt == 1 ) {
		data = (*((vu_char *)src)) | (*((vu_char *)( wp + 1 )) << 8 );
		if( ( rc = write_word( info, wp, data ) ) != 0 )
			return (rc);
	}
	
	return ERR_OK;
}


/***********************************************************************
 * @Function: spin_wheel
 * @Return: Nothing.
 * @Descr: Just to show that we are still alive.
 ***********************************************************************/
void inline spin_wheel( void )
{
	static int p = 0;
	static char w[] = "\\|/-";

	printf( "\010%c", w[p] );
	(++p == 4) ? (p = 0) : 0;
}
